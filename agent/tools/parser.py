import base64
import json
import os
import re
from pathlib import Path
from typing import Any, Optional

import httpx
import pandas as pd

from models.data_models import DataQuality, FinancialContext, Phase


ESPRIT_BASE_URL = "https://tokenfactory.esprit.tn/api"
ESPRIT_MODEL = "hosted_vllm/Llama-3.1-70B-Instruct"


def _empty_context() -> FinancialContext:
    return FinancialContext(
        burn_rate=None,
        cash_balance=None,
        monthly_revenue=None,
        n_clients=None,
        prix_client=None,
        churn_rate=None,
        marketing_budget=None,
        new_clients_month=None,
        cogs=None,
        months_data=None,
        secteur=None,
        pays="TN",
        phase_hint=Phase.SEED,
        intent_fundraising=False,
        burn_quality=DataQuality.MISSING,
        cash_quality=DataQuality.MISSING,
        revenue_quality=DataQuality.MISSING,
        hypotheses=[],
    )


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        if isinstance(value, str):
            v = value.strip().replace(" ", "")
            if not v:
                return None
            v = v.replace(",", ".")
            return float(v)
        return float(value)
    except Exception:
        return None


def _safe_int(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        if isinstance(value, str) and not value.strip():
            return None
        return int(float(value))
    except Exception:
        return None


def _normalize_key(value: str) -> str:
    return value.strip().lower().replace(" ", "_")


def _extract_quality_enum(raw_quality: Any, default: DataQuality = DataQuality.MISSING) -> DataQuality:
    if isinstance(raw_quality, DataQuality):
        return raw_quality
    if not isinstance(raw_quality, str):
        return default

    key = raw_quality.strip().upper()
    mapping = {
        "REAL": DataQuality.REAL,
        "ESTIMATED": DataQuality.ESTIMATED,
        "ASSUMPTION": DataQuality.ASSUMPTION,
        "MISSING": DataQuality.MISSING,
    }
    return mapping.get(key, default)


def _detect_intent_fundraising(text: str) -> bool:
    lowered = (text or "").lower()
    # Whole-word or phrase patterns to avoid false positives like "livrer", "levée de rideau"
    patterns = [
        r"\blever\s+(des\s+)?fonds\b",
        r"\blev[eé]e\s+(de\s+)?(fonds|capital|seed|s[eé]rie)\b",
        r"\binvestisseur\b",
        r"\bfunding\b",
        r"\braise\s+(funds?|capital|money)\b",
        r"\bseed\s+round\b",
        r"\bseries\s+[a-c]\b",
        r"\blev[eé]e\s+de\s+fonds\b",
    ]
    return any(re.search(p, lowered) for p in patterns)


def _detect_phase(monthly_revenue: Optional[float], intent_fundraising: bool) -> Phase:
    no_revenue = monthly_revenue is None or monthly_revenue == 0
    if no_revenue and intent_fundraising:
        return Phase.SEED_RAISING
    if no_revenue:
        return Phase.SEED
    if intent_fundraising:
        return Phase.FUNDRAISING
    return Phase.TRACTION


def _build_extraction_prompt() -> str:
    return (
        "You are a financial data extractor for Tunisian startups.\n"
        "The founder message can be in French or English.\n"
        "Return ONLY valid JSON, no markdown, no extra text, no explanation.\n"
        "Extract ONLY values explicitly mentioned by the founder.\n\n"
        "IMPORTANT RULES:\n"
        "- Numbers may use French formatting: '18 000' means 18000, '1 500' means 1500.\n"
        "- churn_rate must always be a decimal: 7% → 0.07, 3% → 0.03\n"
        "- prix_client is the monthly revenue per client in TND\n"
        "- burn_rate is total monthly expenses including salaries, rent, marketing\n"
        "- If a value is not explicitly mentioned, return null\n\n"
        "JSON schema to return:\n"
        "{\n"
        "  \"burn_rate\": number|null,\n"
        "  \"cash_balance\": number|null,\n"
        "  \"monthly_revenue\": number|null,\n"
        "  \"n_clients\": integer|null,\n"
        "  \"prix_client\": number|null,\n"
        "  \"churn_rate\": number|null,\n"
        "  \"marketing_budget\": number|null,\n"
        "  \"new_clients_month\": integer|null,\n"
        "  \"cogs\": number|null,\n"
        "  \"months_data\": integer|null,\n"
        "  \"secteur\": string|null,\n"
        "  \"pays\": string|null,\n"
        "  \"intent_fundraising\": boolean,\n"
        "  \"hypotheses\": string[],\n"
        "  \"data_quality\": {\n"
        "    \"burn\": \"REAL|ESTIMATED|ASSUMPTION|MISSING\",\n"
        "    \"cash\": \"REAL|ESTIMATED|ASSUMPTION|MISSING\",\n"
        "    \"revenue\": \"REAL|ESTIMATED|ASSUMPTION|MISSING\"\n"
        "  }\n"
        "}\n\n"
        "Data quality rules:\n"
        "- REAL: founder cites a precise source like bank statement, Stripe, invoice, or says 'exactement'\n"
        "- ESTIMATED: founder uses words like environ, autour de, approximately, about, a peu pres\n"
        "- ASSUMPTION: founder uses words like je pense, j'espere, normalement, I think, I hope\n"
        "- MISSING: value not mentioned at all\n\n"
        "Examples of correct extraction:\n"
        "Input: 'mes depenses sont environ 18 000 dinars' → burn_rate: 18000, burn quality: ESTIMATED\n"
        "Input: 'solde bancaire exactement 95 000 dinars, verifie ce matin' → cash_balance: 95000, cash quality: REAL\n"
        "Input: 'churn autour de 7%' → churn_rate: 0.07\n"
        "Input: 'je cherche a lever des fonds' → intent_fundraising: true\n"
    )


def _clean_llm_json_response(raw: str) -> str:
    cleaned = (raw or "").strip()
    # Strip markdown code fences properly
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned.strip())
    cleaned = cleaned.strip()
    if cleaned.startswith("{") and cleaned.endswith("}"):
        return cleaned
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        return cleaned[start : end + 1]
    return cleaned


def _call_esprit_llm(messages: list[dict[str, Any]]) -> dict[str, Any]:
    api_key = os.getenv("ESPRIT_API_KEY", "")
    if not api_key:
        raise ValueError("ESPRIT_API_KEY is missing")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": ESPRIT_MODEL,
        "messages": messages,
        "temperature": 0,
    }

    with httpx.Client(base_url=ESPRIT_BASE_URL, timeout=60.0, verify=False) as client:
        response = client.post("/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

    content = data.get("choices", [{}])[0].get("message", {}).get("content", "{}")
    cleaned = _clean_llm_json_response(content)
    return json.loads(cleaned)


def _extract_from_text_with_llm(text: str) -> dict[str, Any]:
    messages = [
        {"role": "system", "content": _build_extraction_prompt()},
        {"role": "user", "content": text},
    ]
    return _call_esprit_llm(messages)


def _pdf_to_base64_images(pdf_path: Path) -> list[str]:
    images: list[str] = []
    try:
        import fitz  # type: ignore

        with fitz.open(str(pdf_path)) as doc:
            for page in doc:
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                png_bytes = pix.tobytes("png")
                images.append(base64.b64encode(png_bytes).decode("ascii"))
    except Exception:
        return []
    return images


def _extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract raw text from a PDF using PyMuPDF (no vision model needed)."""
    try:
        import fitz  # type: ignore

        with fitz.open(str(pdf_path)) as doc:
            pages_text = [page.get_text() for page in doc]
        return "\n".join(pages_text).strip()
    except Exception:
        return ""


def _extract_from_pdf_with_llm(pdf_path: Path) -> dict[str, Any]:
    # Extract text first — works with any LLM, no vision required
    text = _extract_text_from_pdf(pdf_path)
    if text:
        return _extract_from_text_with_llm(text)

    # Fallback: image-based extraction (only if vision model is available)
    images_b64 = _pdf_to_base64_images(pdf_path)
    if not images_b64:
        return {}

    user_content: list[dict[str, Any]] = [
        {"type": "text", "text": "Extract FinancialContext values from this PDF content."}
    ]
    for b64 in images_b64:
        user_content.append(
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
        )
    messages = [
        {"role": "system", "content": _build_extraction_prompt()},
        {"role": "user", "content": user_content},
    ]
    return _call_esprit_llm(messages)


def _find_column(df: pd.DataFrame, aliases: list[str]) -> Optional[str]:
    normalized = {_normalize_key(c): c for c in df.columns}
    for alias in aliases:
        key = _normalize_key(alias)
        if key in normalized:
            return normalized[key]
    return None


def _extract_from_tabular_file(path: Path) -> dict[str, Any]:
    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
    else:
        df = pd.read_excel(path)

    if df.empty:
        return {}

    df_non_empty = df.dropna(how="all")
    if df_non_empty.empty:
        return {}

    row = df_non_empty.iloc[-1]
    aliases = {
        "burn_rate": ["burn_rate", "burn", "depenses", "expenses", "charges"],
        "cash_balance": ["cash_balance", "cash", "tresorerie", "solde", "balance"],
        "monthly_revenue": ["monthly_revenue", "revenue", "revenus", "ca", "chiffre_affaires", "mrr"],
        "n_clients": ["n_clients", "clients", "customers", "nb_clients"],
        "prix_client": ["prix_client", "prix", "price", "arpu", "revenue_per_client"],
        "churn_rate": ["churn_rate", "churn", "attrition"],
    }

    extracted: dict[str, Any] = {
        "marketing_budget": None,
        "new_clients_month": None,
        "cogs": None,
        "months_data": len(df_non_empty),
        "secteur": None,
        "pays": "TN",
        "intent_fundraising": False,
        "hypotheses": [],
        "data_quality": {"burn": "ESTIMATED", "cash": "ESTIMATED", "revenue": "ESTIMATED"},
    }

    for target, possible_names in aliases.items():
        col = _find_column(df_non_empty, possible_names)
        extracted[target] = row[col] if col else None

    secteur_col = _find_column(df_non_empty, ["secteur", "sector"])
    pays_col = _find_column(df_non_empty, ["pays", "country"])
    extracted["secteur"] = row[secteur_col] if secteur_col else None
    extracted["pays"] = row[pays_col] if pays_col and row[pays_col] else "TN"

    return extracted


def _normalize_churn(value: Optional[float]) -> Optional[float]:
    """Ensure churn_rate is always in decimal form (0.07, not 7)."""
    if value is None:
        return None
    return value / 100.0 if value > 1.0 else value


def _infer_missing_fields(
    monthly_revenue: Optional[float],
    n_clients: Optional[int],
    prix_client: Optional[float],
) -> tuple[Optional[float], Optional[int], Optional[float]]:
    """Infer prix_client or monthly_revenue when one can be derived from the others."""
    if prix_client is None and monthly_revenue is not None and n_clients and n_clients > 0:
        prix_client = monthly_revenue / n_clients
    elif monthly_revenue is None and prix_client is not None and n_clients and n_clients > 0:
        monthly_revenue = prix_client * n_clients
    return monthly_revenue, n_clients, prix_client


def _fix_quality(value: Optional[float], quality: DataQuality) -> DataQuality:
    """If a value is present but quality is MISSING, upgrade to ESTIMATED."""
    if value is not None and quality == DataQuality.MISSING:
        return DataQuality.ESTIMATED
    return quality


def _build_context(extracted: dict[str, Any], source_text: str = "") -> FinancialContext:
    burn_rate = _safe_float(extracted.get("burn_rate"))
    cash_balance = _safe_float(extracted.get("cash_balance"))
    monthly_revenue = _safe_float(extracted.get("monthly_revenue"))
    n_clients = _safe_int(extracted.get("n_clients"))
    prix_client = _safe_float(extracted.get("prix_client"))
    churn_rate = _normalize_churn(_safe_float(extracted.get("churn_rate")))
    marketing_budget = _safe_float(extracted.get("marketing_budget"))
    new_clients_month = _safe_int(extracted.get("new_clients_month"))
    cogs = _safe_float(extracted.get("cogs"))
    months_data = _safe_int(extracted.get("months_data"))

    # Infer missing fields from related values
    monthly_revenue, n_clients, prix_client = _infer_missing_fields(
        monthly_revenue, n_clients, prix_client
    )

    llm_intent = extracted.get("intent_fundraising")
    intent_fundraising = bool(llm_intent) if llm_intent is not None else False
    if _detect_intent_fundraising(source_text):
        intent_fundraising = True

    phase_hint = _detect_phase(monthly_revenue, intent_fundraising)

    dq = extracted.get("data_quality") or {}
    burn_quality = _fix_quality(burn_rate, _extract_quality_enum(dq.get("burn"), DataQuality.MISSING))
    cash_quality = _fix_quality(cash_balance, _extract_quality_enum(dq.get("cash"), DataQuality.MISSING))
    revenue_quality = _fix_quality(monthly_revenue, _extract_quality_enum(dq.get("revenue"), DataQuality.MISSING))

    hypotheses = extracted.get("hypotheses") or []
    if not isinstance(hypotheses, list):
        hypotheses = []
    hypotheses = [str(h).strip() for h in hypotheses if str(h).strip()]

    secteur = extracted.get("secteur")
    pays = extracted.get("pays") or "TN"

    return FinancialContext(
        burn_rate=burn_rate,
        cash_balance=cash_balance,
        monthly_revenue=monthly_revenue,
        n_clients=n_clients,
        prix_client=prix_client,
        churn_rate=churn_rate,
        marketing_budget=marketing_budget,
        new_clients_month=new_clients_month,
        cogs=cogs,
        months_data=months_data,
        secteur=str(secteur) if secteur is not None else None,
        pays=str(pays),
        phase_hint=phase_hint,
        intent_fundraising=intent_fundraising,
        burn_quality=burn_quality,
        cash_quality=cash_quality,
        revenue_quality=revenue_quality,
        hypotheses=hypotheses,
    )


def parse_founder_input(input_value: str) -> FinancialContext:
    try:
        path = Path(input_value)
        if path.exists() and path.is_file():
            suffix = path.suffix.lower()
            if suffix in {".csv", ".xls", ".xlsx"}:
                try:
                    extracted = _extract_from_tabular_file(path)
                    return _build_context(extracted, source_text="")
                except Exception:
                    return _empty_context()

            if suffix == ".pdf":
                try:
                    extracted = _extract_from_pdf_with_llm(path)
                    return _build_context(extracted, source_text="")
                except Exception:
                    return _empty_context()

            return _empty_context()

        try:
            extracted = _extract_from_text_with_llm(input_value)
            return _build_context(extracted, source_text=input_value)
        except Exception:
            return _empty_context()
    except Exception:
        return _empty_context()


if __name__ == "__main__":
    sample = (
        "Nous faisons environ 25k TND de revenus mensuels avec 50 clients payants, "
        "prix moyen 500 TND, cash en banque 120k, burn autour de 40k. "
        "On veut faire une levée seed round bientot."
    )
    parsed = parse_founder_input(sample)
    print(parsed)
