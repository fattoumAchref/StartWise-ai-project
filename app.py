from dotenv import load_dotenv

load_dotenv()

import os
import tempfile
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Generator

import httpx
import streamlit as st

try:
    from agent.tools.parser import parse_founder_input
    from agent.tools.validator import validate_financial_context
    from agent.tools.fetch_benchmarks import fetch_benchmarks

    MODULES_OK = True
except Exception:
    MODULES_OK = False


st.set_page_config(
    page_title="StartWise",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
* { box-sizing: border-box; }

/* ── Main background ── */
[data-testid="stAppViewContainer"] {
    background: #f9f9f9;
}

/* ── Sidebar dark ── */
[data-testid="stSidebar"] {
    background: #171717;
    border-right: none;
}

[data-testid="stSidebar"] * {
    color: #ececec !important;
}

[data-testid="stSidebar"] .stButton > button {
    background: transparent;
    color: #ececec !important;
    border: 1px solid #3a3a3a;
    border-radius: 8px;
    font-size: 0.875rem;
    padding: 0.55rem 1rem;
    width: 100%;
    text-align: left;
    transition: background 0.15s;
}

[data-testid="stSidebar"] .stButton > button:hover {
    background: #2a2a2a !important;
    border-color: #555;
}

[data-testid="stSidebar"] hr {
    border-color: #2e2e2e !important;
}

[data-testid="stSidebar"] .stFileUploader {
    background: #1e1e1e;
    border: 1px dashed #3a3a3a;
    border-radius: 8px;
    padding: 0.5rem;
}

[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] {
    background: #1e1e1e !important;
    border: 1px dashed #3a3a3a !important;
    border-radius: 8px !important;
}

[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] * {
    color: #888 !important;
    font-size: 0.82rem;
}

/* ── Animations ── */
@keyframes msgIn {
    from { opacity: 0; transform: translateY(10px); }
    to   { opacity: 1; transform: translateY(0); }
}
@keyframes fadeUp {
    from { opacity: 0; transform: translateY(6px); }
    to   { opacity: 1; transform: translateY(0); }
}
@keyframes pulse {
    0%, 100% { opacity: 0.3; }
    50%       { opacity: 1; }
}

/* ── Hide avatars ── */
[data-testid="stChatMessageAvatarAssistant"],
[data-testid="stChatMessageAvatarUser"],
[data-testid="stChatMessageAvatar"] {
    display: none !important;
}

/* ── Messages area ── */
.block-container {
    max-width: 720px !important;
    margin: 0 auto !important;
    padding: 2rem 1rem 7rem 1rem !important;
}

/* Base message — no avatar space needed */
[data-testid="stChatMessage"] {
    background: transparent;
    border: none;
    border-radius: 0;
    padding: 1.1rem 0 1.1rem 0;
    margin: 0;
    border-bottom: 1px solid #f0f0f0;
    animation: msgIn 0.28s cubic-bezier(0.22, 1, 0.36, 1) both;
    gap: 0 !important;
}

/* User bubble */
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
    background: #ffffff;
    border-radius: 14px;
    padding: 0.9rem 1.2rem;
    border: 1px solid #e8e8e8;
    margin: 0.6rem 0;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}

/* Assistant — subtle left accent */
[data-testid="stChatMessage"]:not(:has([data-testid="stChatMessageAvatarUser"])) {
    padding-left: 1rem;
    border-left: 2px solid #e0e0e0;
    border-bottom: none;
    margin: 0.5rem 0;
    transition: border-color 0.2s;
}
[data-testid="stChatMessage"]:not(:has([data-testid="stChatMessageAvatarUser"])):hover {
    border-left-color: #aaaaaa;
}

[data-testid="stChatMessage"] p,
[data-testid="stChatMessage"] li {
    color: #1a1a1a !important;
    font-size: 0.94rem;
    line-height: 1.75;
    animation: fadeUp 0.2s ease-out both;
}

[data-testid="stChatMessage"] strong {
    color: #0a0a0a;
    font-weight: 600;
}

[data-testid="stChatMessage"] code {
    background: #f4f4f5;
    color: #111;
    border-radius: 5px;
    padding: 2px 7px;
    font-family: 'SF Mono', 'Fira Code', monospace;
    font-size: 0.87em;
    border: 1px solid #e4e4e7;
    transition: background 0.15s;
}

[data-testid="stChatMessage"] code:hover {
    background: #ececee;
}

[data-testid="stChatMessage"] hr {
    border: none;
    border-top: 1px solid #f0f0f0;
    margin: 0.8rem 0;
}

/* ── Welcome screen animation ── */
.welcome-title {
    animation: fadeUp 0.5s cubic-bezier(0.22, 1, 0.36, 1) both;
}
.welcome-sub {
    animation: fadeUp 0.5s 0.1s cubic-bezier(0.22, 1, 0.36, 1) both;
}

/* ── Input bar ── */
[data-testid="stChatInputContainer"] {
    background: #f9f9f9;
    border-top: 1px solid #ebebeb;
    padding: 1rem 0;
    max-width: 720px !important;
    margin: 0 auto !important;
    backdrop-filter: blur(8px);
    background: rgba(249,249,249,0.92) !important;
}

[data-testid="stChatInput"] textarea {
    background: #ffffff;
    color: #1a1a1a;
    border: 1px solid #d4d4d4;
    border-radius: 14px;
    font-size: 0.95rem;
    padding: 13px 18px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.07);
    transition: border-color 0.2s, box-shadow 0.2s;
}

[data-testid="stChatInput"] textarea::placeholder {
    color: #bbb;
}

[data-testid="stChatInput"] textarea:focus {
    border-color: #222;
    box-shadow: 0 0 0 3px rgba(0,0,0,0.06), 0 2px 8px rgba(0,0,0,0.07);
    outline: none;
}

/* ── Badges ── */
.badge {
    display: inline-block;
    padding: 0.18rem 0.55rem;
    border-radius: 4px;
    font-size: 0.76rem;
    font-weight: 600;
    letter-spacing: 0.3px;
}

.badge-valid {
    background: #ecf7ed;
    color: #1e7e34;
    border: 1px solid #b8debb;
}

.badge-incomplete {
    background: #fff4e5;
    color: #b45309;
    border: 1px solid #f5d08a;
}

.questions-label {
    font-size: 0.78rem;
    font-weight: 600;
    color: #999999;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    margin-bottom: 0.4rem;
}

/* ── Welcome heading ── */
.welcome-title {
    font-size: 1.9rem;
    font-weight: 700;
    color: #0a0a0a;
    letter-spacing: -0.5px;
    text-align: center;
    margin-bottom: 0.4rem;
}

.welcome-sub {
    font-size: 0.9rem;
    color: #888;
    text-align: center;
}

/* ── Sidebar metric row ── */
.sidebar-metric {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.3rem 0;
    border-bottom: 1px solid #2a2a2a;
}

.sidebar-metric-label { color: #888 !important; font-size: 0.8rem; }
.sidebar-metric-value { color: #ececec !important; font-size: 0.82rem; font-weight: 600; }
</style>
""",
    unsafe_allow_html=True,
)

# ── Session state ──────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []
if "financial_context" not in st.session_state:
    st.session_state.financial_context = None
if "validation_result" not in st.session_state:
    st.session_state.validation_result = None
if "last_uploaded_file" not in st.session_state:
    st.session_state.last_uploaded_file = None


# ── Helpers ────────────────────────────────────────────────────────────────────
def _to_dict(obj: Any) -> dict:
    if obj is None:
        return {}
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    try:
        return asdict(obj)
    except Exception:
        return {}


def _fmt(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:,.0f}".replace(",", " ")
    return str(value)


def _has_new_financial_data(ctx: Any) -> bool:
    d = _to_dict(ctx)
    financial_keys = [
        "burn_rate", "cash_balance", "monthly_revenue",
        "n_clients", "prix_client", "churn_rate",
        "marketing_budget", "new_clients_month", "cogs",
    ]
    return any(d.get(k) is not None for k in financial_keys)


def _count_financial_fields(ctx: Any) -> int:
    d = _to_dict(ctx)
    financial_keys = [
        "burn_rate", "cash_balance", "monthly_revenue",
        "n_clients", "prix_client", "churn_rate",
        "marketing_budget", "new_clients_month", "cogs",
    ]
    return sum(1 for k in financial_keys if d.get(k) is not None)


def _quality_enum_to_str(val: Any) -> str:
    try:
        from models.data_models import DataQuality
        if isinstance(val, DataQuality):
            mapping = {
                DataQuality.REAL: "REAL",
                DataQuality.ESTIMATED: "ESTIMATED",
                DataQuality.ASSUMPTION: "ASSUMPTION",
                DataQuality.MISSING: "MISSING",
            }
            return mapping.get(val, "MISSING")
    except Exception:
        pass
    if isinstance(val, float):
        return {1.0: "REAL", 0.7: "ESTIMATED", 0.4: "ASSUMPTION", 0.1: "MISSING"}.get(val, "MISSING")
    if isinstance(val, str):
        return val.upper()
    return "MISSING"


def _merge_contexts(existing: Any, new: Any) -> Any:
    if existing is None:
        return new
    if new is None:
        return existing

    if _count_financial_fields(new) >= 3:
        return new

    existing_dict = _to_dict(existing)
    new_dict = _to_dict(new)

    merged = {}
    for key in existing_dict:
        new_val = new_dict.get(key)
        old_val = existing_dict.get(key)
        if new_val is not None and new_val not in ([], ""):
            merged[key] = new_val
        else:
            merged[key] = old_val

    merged["data_quality"] = {
        "burn": _quality_enum_to_str(merged.get("burn_quality")),
        "cash": _quality_enum_to_str(merged.get("cash_quality")),
        "revenue": _quality_enum_to_str(merged.get("revenue_quality")),
    }

    try:
        from agent.tools.parser import _build_context
        return _build_context(merged, source_text="")
    except Exception:
        return new


# ── LLM text call (raw, no JSON parsing) ──────────────────────────────────────
def _call_llm_text(messages: list) -> str:
    api_key = os.getenv("ESPRIT_API_KEY", "")
    if not api_key:
        return ""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "hosted_vllm/Llama-3.1-70B-Instruct",
        "messages": messages,
        "temperature": 0.3,
    }
    try:
        with httpx.Client(
            base_url="https://tokenfactory.esprit.tn/api",
            timeout=60.0,
            verify=False,
        ) as client:
            response = client.post("/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "")
    except Exception:
        return ""


# ── LLM-generated questions ────────────────────────────────────────────────────

# Maps field names extracted from missing_critical to their display label
_FIELD_LABELS: dict[str, str] = {
    "burn_rate": "burn rate",
    "cash_balance": "cash balance",
    "monthly_revenue": "revenue mensuel",
    "n_clients": "nombre de clients",
    "prix_client": "prix par client",
    "churn_rate": "churn rate",
    "marketing_budget": "budget marketing",
    "new_clients_month": "nouveaux clients / mois",
    "cogs": "coût variable (COGS)",
    "months_data": "historique (mois)",
    "secteur": "secteur",
    "pays": "pays",
}


def _extract_field_from_missing(entry: str) -> tuple[str, str]:
    """Return (field_key, display_label) from a missing_critical entry string."""
    for key, label in _FIELD_LABELS.items():
        if key in entry.lower():
            return key, label
    raw = entry.split("—")[0].strip()
    return raw, raw


def _incoherence_label(entry: str) -> str:
    """Extract the specific fields involved in an incoherence for the parenthetical label."""
    found = [label for key, label in _FIELD_LABELS.items() if key in entry.lower()]
    if found:
        return " / ".join(found) + " — incohérence"
    return "incohérence"


def _generate_questions_with_llm(ctx: Any, validation: Any) -> list[str]:
    missing = list(getattr(validation, "missing_critical", []) or [])
    inco = list(getattr(validation, "incoherences", []) or [])

    # Build structured items: one question per missing field + one per incoherence
    items: list[tuple[str, str, str]] = []  # (field_key, field_label, context_hint)
    for entry in missing:
        key, label = _extract_field_from_missing(entry)
        hint = entry.split("—")[1].strip() if "—" in entry else ""
        items.append((key, label, hint))
    for entry in inco:
        label = _incoherence_label(entry)
        items.append(("incoherence", label, entry))

    if not items:
        return []

    ctx_dict = _to_dict(ctx)
    known_parts = []
    for key, label in _FIELD_LABELS.items():
        v = ctx_dict.get(key)
        if v is not None:
            known_parts.append(f"{key}={v}")
    known_str = ", ".join(known_parts) if known_parts else "aucune"

    # Build the structured list to send to the LLM
    items_str = "\n".join(
        f"{i+1}. champ={key} | label={label} | contexte={hint}"
        for i, (key, label, hint) in enumerate(items)
    )
    n = len(items)

    messages = [
        {
            "role": "system",
            "content": (
                "Tu es un analyste CFO pour startups tunisiennes. "
                "Pour chaque champ financier manquant ou incohérent, génère exactement une question courte, "
                "précise et professionnelle en français. "
                f"Tu dois retourner EXACTEMENT {n} lignes, une question par ligne. "
                "Chaque question DOIT se terminer par le nom du champ entre parenthèses, "
                "exemple : 'Quel est votre burn rate mensuel total ? (burn rate)'. "
                "Sans numérotation, sans tirets, sans markdown."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Données déjà connues : {known_str}\n\n"
                f"Champs à questionner ({n} au total) :\n{items_str}\n\n"
                f"Génère exactement {n} questions, une par ligne."
            ),
        },
    ]

    raw = _call_llm_text(messages)

    if raw.strip():
        questions = [line.strip() for line in raw.strip().split("\n") if line.strip()]
        # Ensure the field label is in parentheses — add it if LLM forgot
        result = []
        for i, q in enumerate(questions[:n]):
            if i < len(items):
                _, label, _ = items[i]
                if f"({label})" not in q:
                    q = f"{q.rstrip('?').rstrip('.').strip()} ? ({label})"
            result.append(q)
        # If LLM returned fewer lines than expected, append fallbacks
        for i in range(len(result), n):
            key, label, hint = items[i]
            if key == "incoherence":
                result.append(f"Pouvez-vous clarifier cette situation ? ({label})")
            else:
                result.append(f"Pouvez-vous préciser votre {label} ? ({label})")
        return result

    # Fallback: build questions locally
    fallback = []
    for key, label, hint in items:
        if key == "incoherence":
            fallback.append(f"Pouvez-vous clarifier cette situation ? ({label})")
        else:
            fallback.append(f"Pouvez-vous préciser votre {label} ? ({label})")
    return fallback


# ── Format extracted data ──────────────────────────────────────────────────────
def _format_extracted_data(ctx: Any, validation: Any) -> str:
    ctx_dict = _to_dict(ctx)
    score = getattr(validation, "data_quality_score", 0.0)
    inco = list(getattr(validation, "incoherences", []) or [])
    is_valid = bool(getattr(validation, "is_valid", False))

    metrics = [
        ("Burn Rate", "burn_rate", "DT/mois"),
        ("Cash Balance", "cash_balance", "DT"),
        ("Revenue mensuel", "monthly_revenue", "DT/mois"),
        ("Clients actifs", "n_clients", ""),
        ("Prix par client", "prix_client", "DT"),
        ("Churn rate", "churn_rate", None),
        ("Secteur", "secteur", None),
        ("Pays", "pays", None),
    ]

    lines = []
    status_label = "Complet" if is_valid else "Incomplet"
    status_class = "badge-valid" if is_valid else "badge-incomplete"
    lines.append(
        f"<span class='badge {status_class}'>{status_label}</span> "
        f"<span style='color:#888;font-size:0.83rem;margin-left:0.5rem'>Qualité des données : {score:.0%}</span>"
    )
    lines.append("\n")

    has_any = False
    for label, key, unit in metrics:
        val = ctx_dict.get(key)
        if val is None:
            continue
        has_any = True
        if key == "churn_rate":
            formatted = f"{val * 100:.1f}%"
        elif unit:
            formatted = f"{_fmt(val)} {unit}"
        else:
            formatted = str(val)
        lines.append(f"- **{label}** : `{formatted}`")

    if ctx_dict.get("burn_rate") and ctx_dict.get("cash_balance"):
        br = ctx_dict["burn_rate"]
        cb = ctx_dict["cash_balance"]
        if br and br > 0:
            runway = cb / br
            lines.append(f"- **Runway estimé** : `{runway:.1f} mois`")

    if inco:
        lines.append("\n---")
        lines.append("**Points à clarifier :**")
        for issue in inco:
            lines.append(f"- {issue}")

    if not has_any:
        return ""

    return "\n".join(lines)


# ── Benchmark formatting ───────────────────────────────────────────────────────
import re as _re

_RE_DOCS_GROSS_MARGIN   = _re.compile(r"gross margin of ([\d.]+)%")
_RE_DOCS_CHURN          = _re.compile(r"monthly churn rate of ([\d.]+)%")
_RE_DOCS_EV_MULTIPLE    = _re.compile(r"EV to revenue multiple of ([\d.]+)x")
_RE_DOCS_LTV_CAC        = _re.compile(r"LTV to CAC ratio of ([\d.]+)x")
_RE_DOCS_CAC_PAYBACK    = _re.compile(r"CAC payback period of ([\d.]+) months")
_RE_DOCS_NRR            = _re.compile(r"net revenue retention of ([\d.]+)%")
_RE_DOCS_GROWTH         = _re.compile(r"growing at ([\d.]+)%")


def _parse_docs_extra(docs: list[str]) -> dict:
    """Extract additional metrics not included in BenchmarkResult."""
    import statistics

    def _vals(pattern):
        vals = []
        for doc in docs:
            m = pattern.search(doc)
            if m:
                vals.append(float(m.group(1)))
        return vals

    def _med(vals):
        return round(statistics.median(vals), 2) if vals else None

    return {
        "ltv_cac_ratio":      _med(_vals(_RE_DOCS_LTV_CAC)),
        "cac_payback_months": _med(_vals(_RE_DOCS_CAC_PAYBACK)),
        "nrr":                _med(_vals(_RE_DOCS_NRR)),
        "growth_yoy":         _med(_vals(_RE_DOCS_GROWTH)),
    }


def _format_benchmark_result(bench: Any, ctx: Any) -> str:
    """Return detailed HTML/Markdown benchmark analysis block."""
    if bench is None:
        return ""

    source = getattr(bench, "source", "unknown")
    sim    = getattr(bench, "similarity_score", 0.0)
    docs   = list(getattr(bench, "documents_raw", []) or [])

    ctx_dict = _to_dict(ctx)
    sector   = ctx_dict.get("secteur") or "SaaS"
    extra    = _parse_docs_extra(docs)

    # Determine source badge
    if "Tavily" in source or "tavily" in source:
        badge_html = "<span style='background:#fff3e0;color:#e65100;border:1px solid #ffcc80;border-radius:4px;padding:2px 8px;font-size:0.74rem;font-weight:600'>Tavily live</span>"
    else:
        badge_html = "<span style='background:#e8f5e9;color:#2e7d32;border:1px solid #a5d6a7;border-radius:4px;padding:2px 8px;font-size:0.74rem;font-weight:600'>ChromaDB cache</span>"

    n_docs = len(docs)
    lines = []
    lines.append(
        f"---\n**Analyse sectorielle — {sector}** "
        f"&nbsp;·&nbsp; similarité {sim:.0%} "
        f"&nbsp;{badge_html}&nbsp; "
        f"<span style='color:#aaa;font-size:0.78rem'>{n_docs} doc(s)</span>"
    )

    # ── Section 1 : KPIs calculés ─────────────────────────────────────────────
    lines.append("\n**KPIs calculés depuis vos données**\n")

    burn   = ctx_dict.get("burn_rate")
    cash   = ctx_dict.get("cash_balance")
    rev    = ctx_dict.get("monthly_revenue")
    cogs   = ctx_dict.get("cogs")
    n_cl   = ctx_dict.get("n_clients")
    p_cl   = ctx_dict.get("prix_client")
    churn  = ctx_dict.get("churn_rate")
    mktg   = ctx_dict.get("marketing_budget")
    new_cl = ctx_dict.get("new_clients_month")

    kpi_rows = []

    if burn and cash and burn > 0:
        runway = cash / burn
        kpi_rows.append(("Runway", f"{runway:.1f} mois", "mois avant épuisement du cash"))

    if burn and rev:
        burn_net = burn - rev
        kpi_rows.append(("Burn net", f"{burn_net:,.0f} DT/mois".replace(",", " "), "dépenses − revenus"))

    if rev and burn and burn > 0:
        coverage = rev / burn
        kpi_rows.append(("Couverture revenus", f"{coverage:.0%}", "revenus / burn total"))

    if rev and cogs and n_cl and n_cl > 0:
        total_cogs = cogs * n_cl
        gm = (rev - total_cogs) / rev if rev > 0 else None
        if gm is not None and 0 <= gm <= 0.98:
            kpi_rows.append(("Gross margin", f"{gm:.1%}", "marge brute sur revenus"))

    if p_cl and churn and churn > 0:
        ltv = p_cl / churn
        kpi_rows.append(("LTV estimé", f"{ltv:,.0f} DT".replace(",", " "), "valeur vie client"))
        if mktg and new_cl and new_cl > 0:
            cac = mktg / new_cl
            kpi_rows.append(("CAC", f"{cac:,.0f} DT".replace(",", " "), "coût acquisition client"))
            ratio = ltv / cac
            status_icon = "✓" if ratio >= 3 else ("~" if ratio >= 1.5 else "!")
            kpi_rows.append(("LTV / CAC", f"{ratio:.1f}x {status_icon}", "doit être > 3x"))

    if churn:
        kpi_rows.append(("Churn mensuel", f"{churn:.1%}", "% clients perdus/mois"))

    if kpi_rows:
        tbl = "| KPI | Valeur | Note |\n|-----|--------|------|\n"
        tbl += "\n".join(f"| {r} | {v} | {n} |" for r, v, n in kpi_rows)
        lines.append(tbl)
    else:
        lines.append("_Données insuffisantes pour calculer les KPIs._")

    # ── Section 2 : Comparaison sectorielle ───────────────────────────────────
    lines.append("\n**Comparaison sectorielle**\n")

    churn_med = getattr(bench, "churn_median", None)
    gm_med    = getattr(bench, "gross_margin_median", None)
    ev_mult   = getattr(bench, "valorisation_multiple", None)
    ltv_cac_b = extra.get("ltv_cac_ratio")
    payback_b = extra.get("cac_payback_months")
    nrr_b     = extra.get("nrr")

    def _cmp(founder_val, bench_val, higher_is_better=True) -> str:
        if founder_val is None or bench_val is None:
            return "—"
        diff = founder_val - bench_val
        if abs(diff) / (abs(bench_val) + 1e-9) < 0.05:
            return "Aligné"
        if (diff > 0) == higher_is_better:
            return "Au-dessus"
        return "En dessous"

    cmp_rows = []
    if churn_med:
        founder_churn = churn
        status = _cmp(founder_churn, churn_med, higher_is_better=False)
        cmp_rows.append(("Churn mensuel",
                          f"{founder_churn:.1%}" if founder_churn else "—",
                          f"{churn_med:.1%}",
                          status))
    if gm_med:
        founder_gm = None
        if rev and cogs and n_cl and n_cl > 0:
            tc = cogs * n_cl
            g = (rev - tc) / rev if rev > 0 else None
            founder_gm = g if g is not None and 0 <= g <= 0.98 else None
        status = _cmp(founder_gm, gm_med, higher_is_better=True)
        cmp_rows.append(("Gross margin",
                          f"{founder_gm:.1%}" if founder_gm else "—",
                          f"{gm_med:.1%}",
                          status))
    if ev_mult:
        cmp_rows.append(("Multiple EV/ARR", "—", f"{ev_mult:.1f}x", "Référence marché"))
    if ltv_cac_b:
        founder_ltv_cac = None
        if p_cl and churn and mktg and new_cl and churn > 0 and new_cl > 0:
            founder_ltv_cac = (p_cl / churn) / (mktg / new_cl)
        status = _cmp(founder_ltv_cac, ltv_cac_b, higher_is_better=True)
        cmp_rows.append(("LTV / CAC",
                          f"{founder_ltv_cac:.1f}x" if founder_ltv_cac else "—",
                          f"{ltv_cac_b:.1f}x",
                          status))
    if payback_b:
        cmp_rows.append(("CAC payback", "—", f"{payback_b:.0f} mois", "Référence marché"))
    if nrr_b:
        cmp_rows.append(("NRR", "—", f"{nrr_b:.1f}%", "Référence marché"))

    if cmp_rows:
        tbl2 = "| Métrique | Votre valeur | Médiane secteur | Statut |\n|----------|-------------|-----------------|--------|\n"
        tbl2 += "\n".join(f"| {m} | {fv} | {bv} | {s} |" for m, fv, bv, s in cmp_rows)
        lines.append(tbl2)
    else:
        lines.append("_Benchmarks sectoriels insuffisants pour cette comparaison._")

    # ── Section 3 : Recommandations ───────────────────────────────────────────
    lines.append("\n**Recommandations**\n")

    recs = []

    # Runway
    if burn and cash and burn > 0:
        rw = cash / burn
        if rw < 3:
            recs.append("**Runway critique** (< 3 mois) — priorité absolue : réduire le burn ou déclencher une levée d'urgence.")
        elif rw < 6:
            recs.append("**Runway serré** (< 6 mois) — préparez votre prochaine levée ou bridging maintenant.")

    # Churn vs benchmark
    if churn and churn_med and churn > churn_med * 1.3:
        recs.append(f"**Churn élevé** ({churn:.1%}) vs médiane secteur ({churn_med:.1%}) — investissez dans l'onboarding et le support client.")

    # Gross margin
    if rev and cogs and n_cl and n_cl > 0:
        tc = cogs * n_cl
        gm_val = (rev - tc) / rev if rev > 0 else None
        if gm_val is not None and 0 <= gm_val <= 0.98:
            if gm_val < 0.5:
                recs.append(f"**Gross margin faible** ({gm_val:.1%}) — examinez vos coûts variables et opportunités de pricing.")
            elif gm_med and gm_val < gm_med * 0.85:
                recs.append(f"**Gross margin en dessous** de la médiane secteur ({gm_med:.1%}) — optimisez vos COGS.")

    # LTV/CAC
    if p_cl and churn and mktg and new_cl and churn > 0 and new_cl > 0:
        ltv_v = p_cl / churn
        cac_v = mktg / new_cl
        ratio_v = ltv_v / cac_v
        if ratio_v < 1:
            recs.append(f"**LTV/CAC < 1** ({ratio_v:.1f}x) — chaque client coûte plus qu'il ne rapporte. Révisez le modèle d'acquisition.")
        elif ratio_v < 3:
            recs.append(f"**LTV/CAC sous-optimal** ({ratio_v:.1f}x, cible > 3x) — réduisez le CAC ou augmentez la rétention.")

    # Valorisation
    if ev_mult and rev:
        arr = rev * 12
        valuation_ref = arr * ev_mult
        recs.append(f"**Valorisation de référence** : ARR × {ev_mult:.1f}x = **{valuation_ref:,.0f} DT** (médiane secteur).".replace(",", " "))

    if not recs:
        recs.append("Données insuffisantes pour des recommandations ciblées. Complétez votre profil financier.")

    for r in recs:
        lines.append(f"- {r}")

    return "\n".join(lines)


# ── Answer general questions ───────────────────────────────────────────────────
def _answer_general_question(user_prompt: str, existing_ctx: Any) -> str:
    ctx_dict = _to_dict(existing_ctx)
    parts = []
    if ctx_dict.get("burn_rate"):
        parts.append(f"burn_rate={_fmt(ctx_dict['burn_rate'])} DT/mois")
    if ctx_dict.get("cash_balance"):
        parts.append(f"cash_balance={_fmt(ctx_dict['cash_balance'])} DT")
    if ctx_dict.get("monthly_revenue"):
        parts.append(f"monthly_revenue={_fmt(ctx_dict['monthly_revenue'])} DT/mois")

    ctx_summary = ("Contexte financier actuel : " + ", ".join(parts) + ". ") if parts else ""

    messages = [
        {
            "role": "system",
            "content": (
                "Tu es un assistant CFO pour startups tunisiennes. "
                "Réponds de façon concise, claire et professionnelle en français. "
                + ctx_summary
            ),
        },
        {"role": "user", "content": user_prompt},
    ]

    result = _call_llm_text(messages)
    return result if result.strip() else "Je n'ai pas pu traiter cette demande."


# ── Shared processing logic ────────────────────────────────────────────────────
def _process_financial_context(new_ctx: Any) -> tuple[str, list[str], Any]:
    """Merge context, validate, fetch benchmarks (if valid). Returns (data_text, questions, bench)."""
    parsed_ctx = _merge_contexts(st.session_state.financial_context, new_ctx)
    validation = validate_financial_context(parsed_ctx)
    st.session_state.financial_context = parsed_ctx
    st.session_state.validation_result = validation
    data_text = _format_extracted_data(parsed_ctx, validation)
    questions = _generate_questions_with_llm(parsed_ctx, validation)

    bench = None
    if getattr(validation, "is_valid", False):
        try:
            bench = fetch_benchmarks(parsed_ctx)
        except Exception:
            bench = None

    return data_text, questions, bench


def _render_financial_reply(data_text: str, questions: list[str], bench: Any = None, ctx: Any = None) -> str:
    """Render extracted data + benchmark + stream questions. Returns full reply for session state."""
    full_reply_parts = []
    if data_text:
        st.markdown(data_text, unsafe_allow_html=True)
        full_reply_parts.append(data_text)

    if bench is not None:
        bench_text = _format_benchmark_result(bench, ctx)
        if bench_text:
            st.markdown(bench_text, unsafe_allow_html=True)
            full_reply_parts.append(bench_text)

    if questions:
        st.divider()
        st.markdown("<div class='questions-label'>Questions</div>", unsafe_allow_html=True)
        streamed_questions = []
        for q in questions:
            streamed = st.write_stream(_word_stream(q))
            streamed_questions.append(streamed)
        full_reply_parts.append(
            "\n\nQuestions :\n" + "\n".join(f"- {q}" for q in streamed_questions)
        )
    return "\n\n".join(full_reply_parts) if full_reply_parts else "Aucune donnée extraite."


# ── Streaming generator ────────────────────────────────────────────────────────
def _word_stream(text: str, delay: float = 0.025) -> Generator:
    words = text.split()
    for i, word in enumerate(words):
        yield word + (" " if i < len(words) - 1 else "")
        time.sleep(delay)


# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        "<div style='padding:0.5rem 0 1rem 0'>"
        "<div style='font-size:1.1rem;font-weight:700;color:#fff;letter-spacing:-0.3px'>StartWise</div>"
        "<div style='font-size:0.78rem;color:#666;margin-top:2px'>Assistant CFO</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.divider()

    if st.button("+ Nouvelle conversation", use_container_width=True):
        st.session_state.messages = []
        st.session_state.financial_context = None
        st.session_state.validation_result = None
        st.session_state.last_uploaded_file = None
        st.rerun()

    st.divider()

    ctx = st.session_state.financial_context
    if ctx is not None:
        ctx_dict = _to_dict(ctx)
        val = st.session_state.validation_result
        score = getattr(val, "data_quality_score", 0.0) if val else 0.0
        is_valid = getattr(val, "is_valid", False) if val else False

        status_label = "Complet" if is_valid else "Incomplet"
        status_color = "#4caf50" if is_valid else "#f59e0b"
        st.markdown(
            f"<div style='display:flex;align-items:center;gap:0.5rem;margin-bottom:0.75rem'>"
            f"<div style='width:8px;height:8px;border-radius:50%;background:{status_color}'></div>"
            f"<span style='font-size:0.82rem;color:#aaa'>{status_label} · Qualité {score:.0%}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

        sidebar_metrics = [
            ("Burn Rate", "burn_rate", "DT/m"),
            ("Cash", "cash_balance", "DT"),
            ("Revenue", "monthly_revenue", "DT/m"),
            ("Clients", "n_clients", ""),
            ("Prix/client", "prix_client", "DT"),
            ("Churn", "churn_rate", None),
        ]
        for label, key, unit in sidebar_metrics:
            v = ctx_dict.get(key)
            if v is not None:
                display = f"{v * 100:.1f}%" if key == "churn_rate" else f"{_fmt(v)} {unit}".strip()
                st.markdown(
                    f"<div class='sidebar-metric'>"
                    f"<span class='sidebar-metric-label'>{label}</span>"
                    f"<span class='sidebar-metric-value'>{display}</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

        if ctx_dict.get("burn_rate") and ctx_dict.get("cash_balance") and ctx_dict.get("burn_rate") > 0:
            runway = ctx_dict["cash_balance"] / ctx_dict["burn_rate"]
            st.markdown(
                f"<div class='sidebar-metric'>"
                f"<span class='sidebar-metric-label'>Runway</span>"
                f"<span class='sidebar-metric-value'>{runway:.1f} mois</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

    st.divider()
    st.markdown(
        "<div style='font-size:0.78rem;color:#666;margin-bottom:0.4rem;text-transform:uppercase;letter-spacing:0.5px'>Importer</div>",
        unsafe_allow_html=True,
    )
    uploaded = st.file_uploader(
        label="",
        type=["csv", "xls", "xlsx", "pdf"],
        label_visibility="collapsed",
    )

    if uploaded is not None and uploaded.name != st.session_state.last_uploaded_file:
        st.session_state.last_uploaded_file = uploaded.name
        suffix = Path(uploaded.name).suffix.lower()
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(uploaded.read())
            tmp_path = tmp.name

        user_msg = f"Fichier importé : {uploaded.name}"
        st.session_state.messages.append({"role": "user", "content": user_msg})

        with st.spinner("Extraction en cours..."):
            try:
                new_ctx = parse_founder_input(tmp_path)
            except Exception as exc:
                st.session_state.messages.append(
                    {"role": "assistant", "content": f"Erreur lors de l'extraction : {exc}"}
                )
                new_ctx = None
            finally:
                Path(tmp_path).unlink(missing_ok=True)

        if new_ctx is not None and _has_new_financial_data(new_ctx):
            data_text, questions, bench = _process_financial_context(new_ctx)
            # Store reply without streaming (sidebar context)
            parts = [data_text] if data_text else []
            if bench is not None:
                bench_text = _format_benchmark_result(bench, st.session_state.financial_context)
                if bench_text:
                    parts.append(bench_text)
            if questions:
                parts.append("Questions :\n" + "\n".join(f"- {q}" for q in questions))
            reply = "\n\n".join(parts) if parts else "Aucune donnée extraite du fichier."
        else:
            reply = f"Aucune donnée financière reconnue dans **{uploaded.name}**."

        st.session_state.messages.append({"role": "assistant", "content": reply})
        st.rerun()

    st.divider()
    if st.button("Reinitialiser session", use_container_width=True):
        st.session_state.clear()
        st.rerun()


# ── Main ───────────────────────────────────────────────────────────────────────

# Show welcome screen only when no user messages yet
only_welcome = all(m["role"] == "assistant" for m in st.session_state.messages)
if only_welcome:
    st.markdown(
        "<div style='height:12vh'></div>"
        "<div class='welcome-title' style='"
        "font-size:2.2rem;font-weight:700;color:#0a0a0a;"
        "letter-spacing:-1px;text-align:center;margin-bottom:0.5rem'>"
        "StartWise"
        "</div>"
        "<div class='welcome-sub' style='"
        "font-size:0.92rem;color:#999;text-align:center;"
        "max-width:420px;margin:0 auto 2.5rem auto;line-height:1.6'>"
        "Décrivez votre situation financière.<br>"
        "Je pose uniquement les questions manquantes."
        "</div>"
        "<div style='display:flex;gap:0.6rem;justify-content:center;flex-wrap:wrap;animation:fadeUp 0.5s 0.2s both'>",
        unsafe_allow_html=True,
    )
    chips = [
        "Mon burn rate est de 15 000 DT/mois",
        "J'ai 80 clients à 200 DT/mois",
        "Cash disponible : 120 000 DT",
    ]
    for chip in chips:
        st.markdown(
            f"<span style='background:#f4f4f5;border:1px solid #e4e4e7;"
            f"border-radius:20px;padding:0.35rem 0.9rem;font-size:0.82rem;"
            f"color:#555;cursor:default;white-space:nowrap;transition:background 0.15s'>"
            f"{chip}</span>",
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)

# Display message history
for msg in st.session_state.messages:
    role = "assistant" if msg["role"] == "assistant" else "user"
    with st.chat_message(role, avatar=None):
        st.markdown(msg["content"], unsafe_allow_html=True)

# Chat input
if prompt := st.chat_input("Décrivez votre situation financière..."):
    if not MODULES_OK:
        st.error("Modules non chargés. Vérifiez votre configuration et votre fichier .env")
        st.stop()

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar=None):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar=None):
        with st.spinner("Analyse en cours..."):
            try:
                new_ctx = parse_founder_input(prompt)
            except Exception as exc:
                st.error(f"Erreur lors du parsing : {exc}")
                st.stop()

        if _has_new_financial_data(new_ctx):
            with st.spinner("Génération des questions..."):
                data_text, questions, bench = _process_financial_context(new_ctx)
            full_reply = _render_financial_reply(data_text, questions, bench, st.session_state.financial_context)
            st.session_state.messages.append({"role": "assistant", "content": full_reply})
        else:
            with st.spinner("Réflexion..."):
                reply = _answer_general_question(prompt, st.session_state.financial_context)
            streamed = st.write_stream(_word_stream(reply))
            st.session_state.messages.append({"role": "assistant", "content": streamed})
