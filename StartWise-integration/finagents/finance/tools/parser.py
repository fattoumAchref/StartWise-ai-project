import base64
import json
import os
import re
from pathlib import Path
from typing import Any, Optional

import httpx
import pandas as pd

from finagents.models.data_models import DataQuality, FinancialContext, Phase


ESPRIT_BASE_URL = "https://tokenfactory.esprit.tn/api"
ESPRIT_MODEL = "hosted_vllm/Llama-3.1-70B-Instruct"

# ── Live exchange rates ────────────────────────────────────────────────────────

_RATE_CACHE: dict[str, float] = {}
_RATE_CACHE_TS: float = 0.0
_RATE_CACHE_TTL = 3600  # 1 hour

SUPPORTED_CURRENCIES = {"EUR", "USD", "GBP", "MAD", "DZD", "SAR", "AED", "CHF"}
CURRENCY_ALIASES = {
    "euro": "EUR", "euros": "EUR", "€": "EUR",
    "dollar": "USD", "dollars": "USD", "$": "USD", "usd": "USD",
    "pound": "GBP", "sterling": "GBP", "£": "GBP",
    "dirham": "MAD", "dh": "MAD", "mad": "MAD",
    "dinar algérien": "DZD", "dzd": "DZD",
    "riyal": "SAR", "sar": "SAR",
    "dirham emirat": "AED", "aed": "AED",
    "franc suisse": "CHF", "chf": "CHF",
}


def _fetch_live_rates(base: str = "TND") -> dict[str, float]:
    """Fetch live rates from open.er-api.com (free, no key required). Returns {currency: rate_to_TND}."""
    import time
    global _RATE_CACHE, _RATE_CACHE_TS
    now = time.time()
    if _RATE_CACHE and now - _RATE_CACHE_TS < _RATE_CACHE_TTL:
        return _RATE_CACHE
    try:
        resp = httpx.get(f"https://open.er-api.com/v6/latest/TND", timeout=8.0)
        resp.raise_for_status()
        data = resp.json()
        # rates[X] = how many X per 1 TND → invert to get TND per 1 X
        raw: dict[str, float] = data.get("rates", {})
        result: dict[str, float] = {}
        for cur in SUPPORTED_CURRENCIES:
            if cur in raw and raw[cur] > 0:
                result[cur] = 1.0 / raw[cur]  # 1 EUR → TND
        _RATE_CACHE = result
        _RATE_CACHE_TS = now
        return result
    except Exception:
        # Fallback to last known approximate rates (clearly labelled as approximate)
        return {}


def _detect_foreign_currency(text: str) -> set[str]:
    """Detect non-TND currency mentions in the user text."""
    found: set[str] = set()
    upper = text.upper()
    for cur in SUPPORTED_CURRENCIES:
        if cur in upper:
            found.add(cur)
    lower = text.lower()
    for alias, cur in CURRENCY_ALIASES.items():
        if alias in lower:
            found.add(cur)
    return found


def _build_currency_hint(text: str) -> str:
    """Return a live-rate hint string to inject into the prompt, or empty string."""
    currencies = _detect_foreign_currency(text)
    if not currencies:
        return ""
    rates = _fetch_live_rates()
    if not rates:
        return ""
    lines = []
    for cur in sorted(currencies):
        if cur in rates:
            lines.append(f"  - 1 {cur} = {rates[cur]:.4f} TND (taux live)")
    if not lines:
        return ""
    return (
        "\n\nCURRENCY CONVERSION (use these EXACT live rates — do NOT use your own knowledge):\n"
        + "\n".join(lines)
        + "\nConvert all amounts to TND before filling the JSON fields.\n"
    )


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
        revenue_history=[],
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
        "  \"revenue_history\": [{\"date\": \"YYYY-MM-DD\", \"revenue\": number}],\n"
        "  \"data_quality\": {\n"
        "    \"burn\": \"REAL|ESTIMATED|ASSUMPTION|MISSING\",\n"
        "    \"cash\": \"REAL|ESTIMATED|ASSUMPTION|MISSING\",\n"
        "    \"revenue\": \"REAL|ESTIMATED|ASSUMPTION|MISSING\"\n"
        "  }\n"
        "}\n\n"
        "Revenue history rules:\n"
        "- If the founder mentions revenues for several months, extract each as a {date, revenue} pair.\n"
        "- Use YYYY-MM-01 format for dates. If only the month name is given, assume current year.\n"
        "- Example: 'janvier 1200, février 1450, mars 1800' → [{\"date\":\"2025-01-01\",\"revenue\":1200},{\"date\":\"2025-02-01\",\"revenue\":1450},{\"date\":\"2025-03-01\",\"revenue\":1800}]\n"
        "- If no monthly history is mentioned, return an empty array [].\n\n"
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
        "Input: '3 clients perdus sur 20' → churn_rate: 0.15 (calculate: 3/20)\n"
        "Input: 'on perd 2 clients par mois, on en a 50' → churn_rate: 0.04 (calculate: 2/50)\n"
        "Input: 'j ai perdu 3 clients ce mois' → set n_clients_lost=3; if n_clients known divide to get churn_rate\n"
        "Input: 'startup EdTech, formation en ligne pour etudiants' → secteur: 'EdTech'\n"
        "Input: 'plateforme SaaS B2B pour les PME tunisiennes' → secteur: 'SaaS B2B'\n"
        "Input: 'marketplace de livraison, on connecte restaurants et clients' → secteur: 'Marketplace / Livraison'\n"
        "Input: 'application de sante, telemedicine' → secteur: 'HealthTech'\n"
        "Input: 'solution fintech, paiement mobile en Tunisie' → secteur: 'FinTech'\n"
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


def _build_known_context_hint(known_context: Optional[dict]) -> str:
    """Inject previously known field values into the prompt so the LLM can reason about relative answers."""
    if not known_context:
        return ""
    lines = []
    for k, v in known_context.items():
        if v is not None:
            lines.append(f"  - {k}: {v}")
    if not lines:
        return ""
    return (
        "\n\nKNOWN VALUES FROM PREVIOUS CONVERSATION TURNS (already confirmed by founder):\n"
        + "\n".join(lines)
        + "\n\nUse these known values to resolve relative answers in the current message.\n"
        "Examples:\n"
        "- If n_clients=20 is known and founder says 'j ai perdu 3 clients' → churn_rate = 3/20 = 0.15\n"
        "- If n_clients=50 is known and founder says 'on perd 2 par mois' → churn_rate = 2/50 = 0.04\n"
        "- If burn_rate is already known and founder does NOT mention it again → return null (don't repeat it)\n"
        "- If secteur is already known and founder does NOT contradict it → return null (don't overwrite it)\n"
        "Only extract fields explicitly provided or clearly computable from the current message + known values.\n"
    )


def _extract_from_text_with_llm(text: str, known_context: Optional[dict] = None) -> dict[str, Any]:
    system_prompt = (
        _build_extraction_prompt()
        + _build_known_context_hint(known_context)
        + _build_currency_hint(text)
    )
    messages = [
        {"role": "system", "content": system_prompt},
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
        return _extract_from_text_with_llm(text)  # currency hint applied inside

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

    # Extract revenue history if the file has date + revenue columns (each row = one month)
    date_col    = _find_column(df_non_empty, ["date", "mois", "month", "periode"])
    revenue_col = _find_column(df_non_empty, ["monthly_revenue", "revenue", "revenus", "ca", "mrr"])
    if date_col and revenue_col and len(df_non_empty) >= 2:
        history_items = []
        for _, row in df_non_empty.iterrows():
            try:
                import pandas as _pd
                raw_date = row[date_col]
                raw_rev  = float(row[revenue_col])
                if _pd.isna(raw_date) or raw_rev <= 0:
                    continue
                parsed_date = _pd.to_datetime(raw_date)
                history_items.append({
                    "date":    parsed_date.strftime("%Y-%m-01"),
                    "revenue": raw_rev,
                })
            except Exception:
                continue
        if len(history_items) >= 2:
            extracted["revenue_history"] = history_items

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

    from finagents.models.data_models import RevenueDataPoint as _RDP
    raw_history = extracted.get("revenue_history") or []
    revenue_history = []
    for _item in raw_history:
        if isinstance(_item, dict):
            try:
                _date = str(_item.get("date", "")).strip()
                _rev  = float(_item.get("revenue", 0))
                if _date and _rev > 0:
                    revenue_history.append(_RDP(date=_date, revenue=_rev))
            except Exception:
                pass

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
        revenue_history=revenue_history,
    )


def parse_founder_input(input_value: str, known_context: Optional[dict] = None) -> FinancialContext:
    """Parse a founder message (text, PDF, CSV) into a FinancialContext.

    Args:
        input_value: raw founder message or file path
        known_context: dict of already-confirmed field values from prior conversation turns.
            The LLM uses these to resolve relative answers like "j'ai perdu 3 clients"
            when n_clients is already known.
    """
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
            extracted = _extract_from_text_with_llm(input_value, known_context=known_context)
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
