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
    from calcul_tools.pipeline import run_analysis_pipeline

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
if "analysis" not in st.session_state:
    st.session_state.analysis = {}
if "last_bench" not in st.session_state:
    st.session_state.last_bench = None
if "last_bench_extra" not in st.session_state:
    st.session_state.last_bench_extra = {}
if "conversations" not in st.session_state:
    st.session_state.conversations = []   # [{id, title, messages, ctx, analysis, bench}]
if "whatif_mode" not in st.session_state:
    st.session_state.whatif_mode = False
if "pending_bench" not in st.session_state:
    st.session_state.pending_bench = None  # bench saved for action buttons
if "shown_sections" not in st.session_state:
    st.session_state.shown_sections = set()  # which action sections user opened


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
    """Fusion additive : chaque champ fourni est conservé, jamais écrasé par None."""
    if existing is None:
        return new
    if new is None:
        return existing

    existing_dict = _to_dict(existing)
    new_dict = _to_dict(new)

    # Toujours fusionner champ par champ — jamais remplacer l'ancien contexte entier
    merged = dict(existing_dict)
    for key, new_val in new_dict.items():
        if new_val is not None and new_val not in ([], ""):
            merged[key] = new_val

    # Pour les champs de qualité, garder le meilleur niveau (REAL > ESTIMATED > ASSUMPTION > MISSING)
    # Cela garantit que le data_quality_score est monotone croissant au fil des messages
    _quality_rank = {"REAL": 3, "ESTIMATED": 2, "ASSUMPTION": 1, "MISSING": 0}
    for qfield in ("burn_quality", "cash_quality", "revenue_quality"):
        old_q = _quality_enum_to_str(existing_dict.get(qfield))
        new_q = _quality_enum_to_str(new_dict.get(qfield))
        if _quality_rank.get(new_q, -1) > _quality_rank.get(old_q, -1):
            merged[qfield] = new_dict[qfield]
        else:
            merged[qfield] = existing_dict.get(qfield)

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
# Données BRUTES que l'entrepreneur peut fournir — jamais de métriques calculées
# Règle : burn_net, LTV, CAC, Runway, Gross Margin ne sont JAMAIS demandés au fondateur
_FIELD_LABELS: dict[str, str] = {
    "burn_rate":         "dépenses mensuelles totales",   # salaires + loyer + marketing + autres
    "cash_balance":      "solde bancaire disponible",
    "monthly_revenue":   "revenus mensuels",
    "n_clients":         "nombre de clients actifs",
    "prix_client":       "prix moyen par client",
    "churn_rate":        "taux de perte clients / mois",  # % clients perdus par mois
    "marketing_budget":  "budget marketing mensuel",
    "new_clients_month": "nouveaux clients acquis / mois",
    "cogs":              "coût variable par client",
    "months_data":       "mois d'historique disponibles",
    "secteur":           "secteur d'activité",
    "pays":              "pays",
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
                "Tu ne poses des questions QUE sur des données brutes que l'entrepreneur connaît : "
                "dépenses, revenus, cash, clients, prix, budget marketing, nouveaux clients, coûts variables. "
                "INTERDIT de demander : burn rate net, LTV, CAC, runway, gross margin, LTV/CAC — ce sont des métriques calculées par l'agent. "
                "Pour chaque champ manquant ou incohérent, génère exactement une question courte, précise et professionnelle en français. "
                f"Tu dois retourner EXACTEMENT {n} lignes, une question par ligne. "
                "Chaque question DOIT se terminer par le nom du champ entre parenthèses, "
                "exemple : 'Quel est votre total de dépenses mensuelles (salaires, loyer, marketing) ? (dépenses mensuelles totales)'. "
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
def _format_extracted_data(ctx: Any, validation: Any, analysis: dict = None) -> str:
    ctx_dict = _to_dict(ctx)
    score = getattr(validation, "data_quality_score", 0.0)
    inco = list(getattr(validation, "incoherences", []) or [])
    is_valid = bool(getattr(validation, "is_valid", False))
    analysis = analysis or {}

    metrics = [
        ("Dépenses mensuelles", "burn_rate", "DT/mois"),
        ("Cash disponible", "cash_balance", "DT"),
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

    # ── Runway : priorité au calcul précis des KPIs, sinon calcul brut ──
    kpis = analysis.get("kpis")
    if kpis is not None and getattr(kpis, "runway_months", None) is not None:
        import math as _math
        runway_val = kpis.runway_months
        alert = getattr(kpis, "cash_out_alert", "")
        alert_icon = {"CRITIQUE": " ⚠️", "ATTENTION": " ⚡", "OK": ""}.get(alert, "")
        if isinstance(runway_val, float) and _math.isinf(runway_val):
            lines.append(f"- **Runway** : `∞` _(startup rentable)_")
        else:
            lines.append(f"- **Runway** : `{runway_val:.1f} mois`{alert_icon}")
    elif ctx_dict.get("burn_rate") and ctx_dict.get("cash_balance"):
        br = ctx_dict["burn_rate"]
        cb = ctx_dict["cash_balance"]
        if br and br > 0:
            lines.append(f"- **Runway estimé** : `{cb / br:.1f} mois`")

    # ── KPIs calculés (uniquement si disponibles) ──────────────────────
    if kpis is not None:
        kpi_lines = []

        # Burn Rate net — ce que la startup perd réellement chaque mois
        burn_net = getattr(kpis, "burn_net", None)
        if burn_net is not None:
            if burn_net == 0:
                _raw_burn = ctx_dict.get("burn_rate") or 0
                _revenue  = ctx_dict.get("monthly_revenue") or 0
                _profit   = _revenue - _raw_burn
                if _profit > 0:
                    kpi_lines.append(f"- **Burn Rate** : `-{_fmt(_profit)} DT/mois` _(startup profitable — excédent de {_fmt(_profit)} DT)_")
                else:
                    kpi_lines.append("- **Burn Rate** : `0 DT/mois` _(revenus = dépenses)_")
            else:
                kpi_lines.append(f"- **Burn Rate** : `{_fmt(burn_net)} DT/mois` _(net après revenus)_")

        if getattr(kpis, "cac", None) is not None:
            kpi_lines.append(f"- **CAC** : `{_fmt(kpis.cac)} DT`")

        if getattr(kpis, "ltv", None) is not None:
            _prix  = ctx_dict.get("prix_client")
            _cogs  = ctx_dict.get("cogs")
            _churn = ctx_dict.get("churn_rate")
            _duree = round(1 / _churn, 1) if _churn and _churn > 0 else None

            if _cogs and _prix and _duree:
                # Les deux LTV quand COGS est connu
                _ltv_rev = round(_prix / _churn, 0)
                kpi_lines.append(
                    f"- **LTV Revenue** : `{_fmt(_ltv_rev)} DT`"
                    f" _({int(_prix)} × {_duree} mois)_"
                )
                kpi_lines.append(
                    f"- **LTV Profit** : `{_fmt(kpis.ltv)} DT`"
                    f" _(({int(_prix)} − {int(_cogs)}) × {_duree} mois)_"
                )
            elif _prix and _duree:
                kpi_lines.append(
                    f"- **LTV** : `{_fmt(kpis.ltv)} DT`"
                    f" _({int(_prix)} × {_duree} mois)_"
                )
            else:
                kpi_lines.append(f"- **LTV** : `{_fmt(kpis.ltv)} DT`")

        if getattr(kpis, "ltv_cac_ratio", None) is not None:
            status = getattr(kpis, "ltv_cac_status", "")
            ratio = kpis.ltv_cac_ratio
            if ratio >= 5:
                insight = f"Excellent (benchmark > 3x) — vous générez {ratio:.1f} DT pour chaque DT investi en acquisition"
            elif ratio >= 3:
                insight = f"Sain (benchmark > 3x) — rentabilité d'acquisition confirmée"
            elif ratio >= 1:
                insight = f"Limite — visez > 3x, actuellement {ratio:.1f}x"
            else:
                insight = f"Critique — vous perdez de l'argent sur chaque client acquis"
            status_icon = {"SAIN": " ✓", "LIMITE": " →", "DANGEREUX": " ✗"}.get(status, "")
            kpi_lines.append(f"- **LTV/CAC** : `{ratio:.1f}x`{status_icon} — _{insight}_")

        if getattr(kpis, "mrr", None) is not None:
            kpi_lines.append(f"- **MRR** : `{_fmt(kpis.mrr)} DT`")

        if getattr(kpis, "gross_margin_pct", None) is not None:
            gm = kpis.gross_margin_pct
            kpi_lines.append(f"- **Gross Margin** : `{gm:.1f}%`")

        # Durée de vie client = 1 / churn (si churn connu)
        churn_val = ctx_dict.get("churn_rate")
        if churn_val and churn_val > 0:
            duree_vie = round(1 / churn_val, 1)
            churn_pct = churn_val * 100
            if churn_val > 0.20:
                churn_insight = "critique — plus d'un client sur cinq perdu chaque mois"
            elif churn_val > 0.10:
                churn_insight = "élevé"
            elif churn_val > 0.05:
                churn_insight = "modéré"
            else:
                churn_insight = "faible"
            kpi_lines.append(
                f"- **Durée de vie client** : `{duree_vie} mois` _(churn {churn_pct:.0f}%/mois — {churn_insight})_"
            )

        if kpi_lines:
            lines.append("\n**KPIs calculés :**")
            lines.extend(kpi_lines)

    # ── Monte Carlo ────────────────────────────────────────────────────
    mc = analysis.get("monte_carlo")
    # Si burn_net = 0 (startup rentable), le MC est trivial — on l'affiche différemment
    is_profitable = kpis is not None and getattr(kpis, "burn_net", None) == 0.0
    if mc is not None and is_profitable:
        lines.append("\n**Simulation Monte Carlo :** _non pertinente (startup rentable — pas de risque d'insolvabilité)_")
    elif mc is not None:
        mc_lines = []
        if getattr(mc, "p50", None) is not None:
            mc_lines.append(
                f"- **Runway médian (p50)** : `{mc.p50:.1f} mois` "
                f"_(p10: {mc.p10:.1f} · p90: {mc.p90:.1f})_"
            )
        if getattr(mc, "proba_survie_12m", None) is not None:
            mc_lines.append(f"- **Survie à 12 mois** : `{mc.proba_survie_12m:.0%}`")
        if mc_lines:
            _growth_used = getattr(mc, "growth_mean_used", None)
            _growth_label = f"croissance revenue {_growth_used*100:.0f}%/mois · volatilité burn ±12%" if _growth_used else "volatilité burn ±12%"
            lines.append(f"\n**Simulation Monte Carlo** _({_growth_label}, {mc.n_simulations} simulations)_ **:**")
            lines.extend(mc_lines)

    # ── Phase ──────────────────────────────────────────────────────────
    phase = analysis.get("phase")
    if phase is not None:
        phase_name = getattr(phase, "value", str(phase))
        lines.append(f"\n**Phase détectée** : `{phase_name}`")

    # ── Champs optionnels manquants (CAC, marge) ───────────────────────
    # S'affiche uniquement en mode ANALYSE (tous les champs requis présents)
    required_present = all(ctx_dict.get(f) is not None for f in (
        "burn_rate", "cash_balance", "monthly_revenue", "n_clients", "prix_client", "churn_rate"
    ))
    if required_present and analysis:
        opt_hints = []
        if ctx_dict.get("marketing_budget") is None or ctx_dict.get("new_clients_month") is None:
            opt_hints.append("**budget marketing** + **nouveaux clients / mois** → calcul du CAC et ratio LTV/CAC")
        if ctx_dict.get("cogs") is None:
            opt_hints.append("**coût variable par client** (livraison, emballage, etc.) → calcul de la marge brute")
        if opt_hints:
            lines.append("\n---")
            lines.append("**Pour compléter l'analyse :**")
            for h in opt_hints:
                lines.append(f"- Précisez : {h}")

    # ── Incoherences ───────────────────────────────────────────────────
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


def _format_benchmark_result(bench: Any, ctx: Any, analysis: dict = None) -> str:
    """
    Comparaison sectorielle RAG — sans recalcul des KPIs (déjà affichés).
    Utilise KPIResult de calcul_tools comme valeurs founder.
    """
    if bench is None:
        return ""

    source = getattr(bench, "source", "unknown")
    sim    = getattr(bench, "similarity_score", 0.0)
    docs   = list(getattr(bench, "documents_raw", []) or [])

    ctx_dict = _to_dict(ctx)
    sector   = ctx_dict.get("secteur") or "SaaS"
    extra    = _parse_docs_extra(docs)

    analysis = analysis or {}
    kpis = analysis.get("kpis")

    # Valeurs founder depuis KPIResult
    churn          = ctx_dict.get("churn_rate")
    rev            = ctx_dict.get("monthly_revenue")
    founder_gm_pct = getattr(kpis, "gross_margin_pct", None) if kpis else None
    founder_gm     = founder_gm_pct / 100 if founder_gm_pct is not None else None
    founder_ltv_cac= getattr(kpis, "ltv_cac_ratio", None)    if kpis else None
    founder_cac    = getattr(kpis, "cac", None)               if kpis else None
    founder_arr    = getattr(kpis, "arr", None)               if kpis else (rev * 12 if rev else None)
    ltv_cac_status = getattr(kpis, "ltv_cac_status", "")      if kpis else ""
    gm_status      = getattr(kpis, "gross_margin_status", "")  if kpis else ""

    # Benchmarks sectoriels (scraping)
    churn_med = getattr(bench, "churn_median", None)
    gm_med    = getattr(bench, "gross_margin_median", None)
    ev_mult   = getattr(bench, "valorisation_multiple", None)
    ltv_cac_b = extra.get("ltv_cac_ratio")
    payback_b = extra.get("cac_payback_months")
    nrr_b     = extra.get("nrr")
    growth_b  = extra.get("growth_yoy")

    if "Tavily" in source or "tavily" in source:
        badge_html = "<span style='background:#fff3e0;color:#e65100;border:1px solid #ffcc80;border-radius:4px;padding:2px 8px;font-size:0.74rem;font-weight:600'>Tavily live</span>"
    else:
        badge_html = "<span style='background:#e8f5e9;color:#2e7d32;border:1px solid #a5d6a7;border-radius:4px;padding:2px 8px;font-size:0.74rem;font-weight:600'>ChromaDB cache</span>"

    lines = []
    lines.append(
        f"---\n**Positionnement sectoriel — {sector}** "
        f"&nbsp;·&nbsp; similarité {sim:.0%} "
        f"&nbsp;{badge_html}&nbsp; "
        f"<span style='color:#aaa;font-size:0.78rem'>{len(docs)} doc(s)</span>"
    )

    # ── Comparaison métrique par métrique avec description précise ────────────
    lines.append("\n**Comparaison vs médiane sectorielle**\n")

    def _gap(f, b): return (f - b) / (abs(b) + 1e-9)
    def _x_label(v):   return f"{v:.1f}x"  if v is not None else "—"

    metric_blocks = []

    # ── Gross Margin ──────────────────────────────────────────────────────────
    if gm_med is not None:
        fv = founder_gm_pct
        fv_str = f"{fv:.1f}%" if fv is not None else "—"
        bv_str = f"{gm_med:.1%}"
        if fv is not None:
            gap = _gap(founder_gm, gm_med)
            if abs(gap) < 0.05:
                status = "Aligné"
                desc = (
                    f"Votre gross margin ({fv:.1f}%) est alignée avec la médiane sectorielle ({gm_med:.1%}). "
                    "Une marge brute saine reflète une structure de coûts variables maîtrisée. "
                    "Cible SaaS B2B : > 70% pour préserver le levier opérationnel au scale."
                )
            elif gap > 0:
                status = "Au-dessus"
                desc = (
                    f"Votre gross margin ({fv:.1f}%) dépasse la médiane sectorielle ({gm_med:.1%}) de {gap:.0%}. "
                    "Cela traduit une pricing power solide ou des coûts de livraison faibles. "
                    "Avantage compétitif lors d'une levée : les VCs valorisent une GM > 70% comme signal de scalabilité."
                )
            else:
                status = "En dessous"
                desc = (
                    f"Votre gross margin ({fv:.1f}%) est inférieure à la médiane ({gm_med:.1%}) de {abs(gap):.0%}. "
                    "Un GM < 60% signale soit des coûts variables élevés (COGS, infrastructure, support), "
                    "soit un sous-pricing. Levier prioritaire : revoir la structure tarifaire ou réduire le coût de livraison."
                )
            icon = {"SAIN": "✓", "FAIBLE": "⚡", "CRITIQUE": "✗"}.get(gm_status, "→")
            metric_blocks.append((f"{icon} Gross Margin", fv_str, bv_str, status, desc))
        else:
            metric_blocks.append(("Gross Margin", "—", bv_str, "—",
                                   f"Médiane sectorielle : {bv_str}. Fournissez vos COGS pour comparer."))

    # ── Churn ─────────────────────────────────────────────────────────────────
    if churn_med is not None and churn is not None:
        gap = _gap(churn, churn_med)
        bv_str = f"{churn_med:.1%}"
        fv_str = f"{churn:.1%}"
        life_months = round(1 / churn, 1) if churn > 0 else None
        if abs(gap) < 0.10:
            status = "Aligné"
            desc = (
                f"Votre churn mensuel ({churn:.1%}) est proche de la médiane ({bv_str}). "
                f"Durée de vie client estimée : {life_months} mois. "
                "Objectif SaaS B2B : < 1%/mois (Net Revenue Retention > 100%)."
            )
        elif gap > 0:
            status = "Au-dessus du marché"
            desc = (
                f"Votre churn ({churn:.1%}) dépasse la médiane sectorielle ({bv_str}) de {gap:.0%}. "
                f"Cela réduit la durée de vie client à {life_months} mois et alourdit mécaniquement le CAC effectif. "
                "Priorités : renforcer l'onboarding, mettre en place des health scores, "
                "et investiguer les churns via exit interviews."
            )
        else:
            status = "En dessous du marché"
            desc = (
                f"Votre churn ({churn:.1%}) est inférieur à la médiane ({bv_str}) — signal fort de rétention. "
                f"Durée de vie client : {life_months} mois. "
                "Une attrition faible amplifie la croissance organique via l'expansion ARR et réduit la pression sur l'acquisition."
            )
        metric_blocks.append(("↩ Churn mensuel", fv_str, bv_str, status, desc))

    # ── LTV / CAC ─────────────────────────────────────────────────────────────
    if ltv_cac_b is not None:
        fv_str = _x_label(founder_ltv_cac)
        bv_str = _x_label(ltv_cac_b)
        if founder_ltv_cac is not None:
            gap = _gap(founder_ltv_cac, ltv_cac_b)
            if abs(gap) < 0.10:
                status = "Aligné"
                desc = (
                    f"Ratio LTV/CAC de {founder_ltv_cac:.1f}x — dans la norme sectorielle ({ltv_cac_b:.1f}x). "
                    "Un ratio > 3x est le standard VC pour valider l'unit economics. "
                    "Cherchez à atteindre 5x+ pour démontrer une efficacité d'acquisition supérieure."
                )
            elif gap > 0:
                status = "Au-dessus"
                desc = (
                    f"Ratio LTV/CAC de {founder_ltv_cac:.1f}x — supérieur à la médiane ({ltv_cac_b:.1f}x). "
                    f"Vous générez {founder_ltv_cac:.1f} DT de valeur pour chaque DT investi en acquisition. "
                    "Position favorable : les VCs utilisent ce ratio comme proxy de la scalabilité du go-to-market."
                )
            else:
                status = "En dessous"
                desc = (
                    f"Ratio LTV/CAC de {founder_ltv_cac:.1f}x — inférieur à la médiane ({ltv_cac_b:.1f}x). "
                    "Chaque DT investi en acquisition génère moins de valeur que vos pairs. "
                    "Leviers : réduire le CAC (canaux organiques, referral), allonger la durée de vie client, "
                    "ou augmenter le prix moyen via upsell."
                )
            icon = {"SAIN": "✓", "LIMITE": "⚡", "DANGEREUX": "✗"}.get(ltv_cac_status, "→")
            metric_blocks.append((f"{icon} LTV / CAC", fv_str, bv_str, status, desc))
        else:
            metric_blocks.append(("LTV / CAC", "—", bv_str, "—",
                                   f"Médiane sectorielle : {bv_str}. Fournissez marketing_budget et new_clients_month."))

    # ── EV / ARR Multiple ─────────────────────────────────────────────────────
    if ev_mult is not None and founder_arr is not None:
        valuation_ref = founder_arr * ev_mult
        desc = (
            f"Le multiple EV/ARR médian pour ce segment est **{ev_mult:.1f}x**. "
            f"Sur la base de votre ARR actuel ({_fmt(founder_arr)} DT), "
            f"la valorisation de référence est **~{_fmt(valuation_ref)} DT**. "
            "Ce multiple reflète les attentes du marché en matière de croissance et de rétention. "
            "Il diminue avec l'augmentation des taux ou la compression des multiples SaaS (post-2022)."
        )
        metric_blocks.append(("◈ Valorisation EV/ARR",
                               f"ARR {_fmt(founder_arr)} DT",
                               f"{ev_mult:.1f}x",
                               f"→ ~{_fmt(valuation_ref)} DT",
                               desc))

    # ── CAC Payback ───────────────────────────────────────────────────────────
    if payback_b is not None:
        cac_val = founder_cac
        desc = (
            f"Le CAC payback médian du secteur est **{payback_b:.0f} mois** "
            "(délai pour récupérer le coût d'acquisition via les revenus). "
        )
        if cac_val and churn and churn > 0:
            desc += f"Votre CAC ({_fmt(cac_val)} DT) implique un payback estimé selon votre pricing. "
        desc += "SaaS B2B sain : < 12 mois. > 18 mois signale un risque de capital intensif."
        metric_blocks.append(("⏱ CAC Payback",
                               f"{_fmt(founder_cac)} DT CAC" if founder_cac else "—",
                               f"{payback_b:.0f} mois",
                               "Référence", desc))

    # ── NRR ───────────────────────────────────────────────────────────────────
    if nrr_b is not None:
        desc = (
            f"Le Net Revenue Retention médian du secteur est **{nrr_b:.1f}%**. "
            "Un NRR > 100% signifie que les revenus existants croissent d'eux-mêmes (expansion, upsell). "
            "C'est l'indicateur le plus valorisé par les investisseurs SaaS growth-stage : "
            "il prouve que la croissance peut s'auto-financer sans acquisition nette."
        )
        metric_blocks.append(("◎ NRR (Net Revenue Retention)", "—", f"{nrr_b:.1f}%", "Référence", desc))

    # ── Croissance YoY ────────────────────────────────────────────────────────
    if growth_b is not None:
        desc = (
            f"La croissance ARR YoY médiane du secteur est **{growth_b:.0f}%**. "
            "Règle empirique : 'Triple, Triple, Double, Double, Double' (T2D3) "
            "pour les SaaS B2B visant une levée Series A/B. "
            "En dessous de la médiane, la croissance organique seule peut ne pas suffire à justifier une valorisation premium."
        )
        metric_blocks.append(("↗ Croissance ARR YoY", "—", f"{growth_b:.0f}%", "Référence", desc))

    if not metric_blocks:
        lines.append("_Benchmarks sectoriels insuffisants. Relancez le scraping via `python run_scraping.py`._")
    else:
        # Tableau synthèse
        lines.append("| Métrique | Votre valeur | Médiane secteur | Positionnement |")
        lines.append("|----------|-------------|-----------------|---------------|")
        for name, fv, bv, status, _ in metric_blocks:
            lines.append(f"| {name} | {fv} | {bv} | {status} |")

        # Descriptions détaillées
        lines.append("")
        for name, fv, bv, status, desc in metric_blocks:
            lines.append(f"**{name.strip('✓✗⚡→↩◈⏱◎↗ ')}** — {desc}\n")

    # ── Recommandations actionnables ──────────────────────────────────────────
    lines.append("\n**Plan d'action prioritaire**\n")
    recs = []

    if gm_status == "CRITIQUE" or (founder_gm is not None and gm_med and founder_gm < gm_med * 0.80):
        recs.append(
            "**[Pricing/COGS]** Gross margin insuffisante — auditez vos coûts variables (hosting, support, ops) "
            "et envisagez une révision tarifaire ou le passage à un modèle d'abonnement annuel (réduit le churn et améliore le cashflow)."
        )
    if churn is not None and churn_med is not None and churn > churn_med * 1.3:
        recs.append(
            f"**[Rétention]** Churn {churn:.1%} vs médiane {churn_med:.1%} — mettez en place un Customer Success "
            "proactif (health scores, QBR), un onboarding structuré sur 30/60/90 jours, "
            "et des alertes de désengagement avant résiliation."
        )
    if ltv_cac_status == "DANGEREUX":
        recs.append(
            f"**[Unit Economics]** LTV/CAC {founder_ltv_cac:.1f}x — en dessous de 1x, le modèle d'acquisition est déficitaire. "
            "Action immédiate : couper les canaux d'acquisition les moins efficients, "
            "augmenter le prix moyen, ou cibler un segment client avec LTV plus élevée."
        )
    elif ltv_cac_status == "LIMITE":
        recs.append(
            f"**[Scalabilité]** LTV/CAC {founder_ltv_cac:.1f}x (cible > 3x) — optimisez les canaux organiques "
            "(SEO, referral, partenariats) pour réduire le CAC sans augmenter le budget marketing."
        )
    if ev_mult and founder_arr:
        valuation_ref = founder_arr * ev_mult
        recs.append(
            f"**[Valorisation]** À {ev_mult:.1f}x ARR, votre valorisation indicative est ~{_fmt(valuation_ref)} DT. "
            "Pour dépasser ce multiple, démontrez une croissance > médiane secteur et un NRR > 110%."
        )

    if not recs:
        recs.append(
            "Vos métriques sont globalement dans la norme sectorielle. "
            "Focus : augmenter la croissance ARR pour accéder à des multiples de valorisation supérieurs."
        )
    for r in recs:
        lines.append(f"- {r}")

    return "\n".join(lines)


def _render_benchmark_charts(bench: Any, ctx: Any, analysis: dict = None) -> None:
    """Renders Plotly comparison charts: founder vs sector medians."""
    try:
        import plotly.graph_objects as go
    except ImportError:
        return

    if bench is None:
        return

    docs   = list(getattr(bench, "documents_raw", []) or [])
    extra  = _parse_docs_extra(docs)
    analysis = analysis or {}
    kpis   = analysis.get("kpis")
    ctx_dict = _to_dict(ctx)

    churn_med = getattr(bench, "churn_median", None)
    gm_med    = getattr(bench, "gross_margin_median", None)
    ltv_cac_b = extra.get("ltv_cac_ratio")

    churn          = ctx_dict.get("churn_rate")
    founder_gm_pct = getattr(kpis, "gross_margin_pct", None) if kpis else None
    founder_ltv_cac= getattr(kpis, "ltv_cac_ratio", None)    if kpis else None

    # ── Graphique 1 : barres côte-à-côte (% metrics) ─────────────────────────
    bar_labels, founder_vals, sector_vals = [], [], []

    if gm_med is not None and founder_gm_pct is not None:
        bar_labels.append("Gross Margin")
        founder_vals.append(round(founder_gm_pct, 1))
        sector_vals.append(round(gm_med * 100, 1))

    if churn_med is not None and churn is not None:
        bar_labels.append("Churn mensuel")
        founder_vals.append(round(churn * 100, 2))
        sector_vals.append(round(churn_med * 100, 2))

    if bar_labels:
        fig1 = go.Figure()
        fig1.add_trace(go.Bar(
            name="Votre startup",
            x=bar_labels, y=founder_vals,
            marker_color="#3b82f6",
            text=[f"{v}%" for v in founder_vals],
            textposition="outside",
        ))
        fig1.add_trace(go.Bar(
            name="Médiane secteur",
            x=bar_labels, y=sector_vals,
            marker_color="#e5e7eb",
            marker_line_color="#9ca3af",
            marker_line_width=1,
            text=[f"{v}%" for v in sector_vals],
            textposition="outside",
        ))
        fig1.update_layout(
            title=dict(text="Comparaison — métriques clés (%)", font=dict(size=13)),
            barmode="group",
            height=300,
            margin=dict(l=10, r=10, t=40, b=10),
            plot_bgcolor="#fafafa",
            paper_bgcolor="#ffffff",
            font=dict(size=11, color="#333"),
            legend=dict(orientation="h", y=-0.28, x=0),
            yaxis=dict(title="%", gridcolor="#f0f0f0"),
        )
        st.plotly_chart(fig1, use_container_width=True)

    # ── Graphique 2 : ratios (LTV/CAC, CAC payback) ───────────────────────────
    ratio_labels, founder_r, sector_r = [], [], []

    if ltv_cac_b is not None and founder_ltv_cac is not None:
        ratio_labels.append("LTV / CAC")
        founder_r.append(round(founder_ltv_cac, 2))
        sector_r.append(round(ltv_cac_b, 2))

    if ratio_labels:
        fig2 = go.Figure()
        # Ligne de référence 3x
        fig2.add_hline(y=3, line_dash="dot", line_color="#f59e0b", line_width=1.5,
                       annotation_text="Cible min 3x", annotation_position="top right",
                       annotation_font_size=10)
        fig2.add_trace(go.Bar(
            name="Votre startup",
            x=ratio_labels, y=founder_r,
            marker_color="#3b82f6",
            text=[f"{v}x" for v in founder_r],
            textposition="outside",
        ))
        fig2.add_trace(go.Bar(
            name="Médiane secteur",
            x=ratio_labels, y=sector_r,
            marker_color="#e5e7eb",
            marker_line_color="#9ca3af",
            marker_line_width=1,
            text=[f"{v}x" for v in sector_r],
            textposition="outside",
        ))
        fig2.update_layout(
            title=dict(text="Comparaison — ratios d'efficacité", font=dict(size=13)),
            barmode="group",
            height=280,
            margin=dict(l=10, r=10, t=40, b=10),
            plot_bgcolor="#fafafa",
            paper_bgcolor="#ffffff",
            font=dict(size=11, color="#333"),
            legend=dict(orientation="h", y=-0.28, x=0),
            yaxis=dict(title="ratio", gridcolor="#f0f0f0"),
        )
        st.plotly_chart(fig2, use_container_width=True)

    # ── Graphique 3 : gauge Gross Margin ─────────────────────────────────────
    if founder_gm_pct is not None:
        fig3 = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=founder_gm_pct,
            delta={"reference": gm_med * 100 if gm_med else 70,
                   "valueformat": ".1f", "suffix": "%"},
            number={"suffix": "%", "font": {"size": 28}},
            title={"text": "Gross Margin vs médiane secteur", "font": {"size": 13}},
            gauge={
                "axis": {"range": [0, 100], "ticksuffix": "%"},
                "bar": {"color": "#3b82f6"},
                "steps": [
                    {"range": [0, 40],  "color": "#fee2e2"},
                    {"range": [40, 60], "color": "#fef3c7"},
                    {"range": [60, 80], "color": "#d1fae5"},
                    {"range": [80, 100],"color": "#a7f3d0"},
                ],
                "threshold": {
                    "line": {"color": "#f59e0b", "width": 3},
                    "thickness": 0.8,
                    "value": gm_med * 100 if gm_med else 70,
                },
            },
        ))
        fig3.update_layout(height=260, margin=dict(l=20, r=20, t=50, b=10),
                           paper_bgcolor="#ffffff")
        st.plotly_chart(fig3, use_container_width=True)


# ── What-if simulation ────────────────────────────────────────────────────────

_SUPPORTED_FIELDS = {
    "burn_rate", "monthly_revenue", "n_clients", "prix_client",
    "churn_rate", "marketing_budget", "new_clients_month", "cash_balance", "cogs",
}

_MOD_LABELS = {
    "burn_rate":         "Dépenses brutes",
    "monthly_revenue":   "Revenue mensuel",
    "n_clients":         "Clients actifs",
    "prix_client":       "Prix/client",
    "churn_rate":        "Churn",
    "marketing_budget":  "Budget marketing",
    "new_clients_month": "Nouveaux clients/mois",
    "cash_balance":      "Cash balance",
    "cogs":              "COGS/client",
}


def _extract_whatif_params(prompt: str, ctx_dict: dict) -> "dict | None":
    """
    Le LLM détecte si c'est une question hypothétique ET retourne l'opération,
    pas la valeur finale. Python applique l'opération — zéro calcul LLM.

    Format retourné :
      {
        "is_whatif": true,
        "modifications": {
          "burn_rate": {"op": "multiply", "factor": 0.7}   ← réduire de 30%
          "n_clients": {"op": "add",      "value": 10}     ← ajouter 10 clients
          "burn_rate": {"op": "set",      "value": 15000}  ← fixer à 15000
        }
      }

    Opérations :
      multiply  → "réduire de X%", "augmenter de X%", "doubler", "tripler"
      add       → "ajouter N clients", "gagner X DT de revenue"
      set       → "si mon burn était X DT", "fixer à X"
    """
    current = ", ".join(
        f"{k}={v}"
        for k, v in ctx_dict.items()
        if v is not None and k in _SUPPORTED_FIELDS
    )
    system = (
        "Tu es un extracteur JSON strict pour questions financieres hypothetiques. "
        "Retourne UNIQUEMENT un objet JSON valide, rien d'autre, pas de texte. "
        "\n"
        "Schema exact :\n"
        "{\"is_whatif\": bool, \"modifications\": {\"champ\": {\"op\": \"multiply|add|set\", \"factor\": float} | {\"op\": \"add|set\", \"value\": float}}}\n"
        "\n"
        "Regles :\n"
        "- 'reduire de 30%'    → {\"op\": \"multiply\", \"factor\": 0.7}\n"
        "- 'augmenter de 20%'  → {\"op\": \"multiply\", \"factor\": 1.2}\n"
        "- 'doubler'           → {\"op\": \"multiply\", \"factor\": 2.0}\n"
        "- 'ajouter 10 clients'→ {\"op\": \"add\", \"value\": 10}\n"
        "- 'fixer burn a 15000'→ {\"op\": \"set\", \"value\": 15000}\n"
        "- Ne JAMAIS calculer la valeur finale — retourner seulement l'operation.\n"
        "- burn_rate = depenses BRUTES totales (salaires+loyer+marketing), pas burn net.\n"
        "- Si pas hypothetique : {\"is_whatif\": false, \"modifications\": {}}\n"
        "\n"
        f"Champs disponibles : {', '.join(_SUPPORTED_FIELDS)}\n"
        f"Valeurs actuelles : {current}"
    )
    raw = _call_llm_text([
        {"role": "system", "content": system},
        {"role": "user",   "content": prompt},
    ])
    if not raw:
        return None
    try:
        import json as _json
        import re as _re
        m = _re.search(r"\{.*\}", raw, _re.DOTALL)
        if not m:
            return None
        data = _json.loads(m.group())
        if not data.get("is_whatif"):
            return None
        mods = data.get("modifications", {})
        return mods if mods else None
    except Exception:
        return None


def _apply_operation(current_val: float, op_dict: dict) -> "float | None":
    """
    Applique l'opération en Python — jamais le LLM.
      {"op": "multiply", "factor": 0.7}  → current * 0.7
      {"op": "add",      "value": 10}    → current + 10
      {"op": "set",      "value": 15000} → 15000
    """
    op = op_dict.get("op")
    if op == "multiply":
        factor = op_dict.get("factor")
        if factor is None:
            return None
        return round(current_val * factor, 4)
    if op == "add":
        value = op_dict.get("value")
        if value is None:
            return None
        return round(current_val + value, 4)
    if op == "set":
        value = op_dict.get("value")
        return value
    return None


def _run_whatif_pipeline(ctx: Any, mods: dict) -> str:
    """
    1. Applique chaque opération via _apply_operation (Python, pas LLM)
    2. Relance run_analysis_pipeline avec le contexte modifié
    3. Retourne comparaison avant/après
    """
    from dataclasses import replace as _dc_replace

    ctx_dict = _to_dict(ctx)

    # KPIs actuels (snapshot)
    orig_kpis   = st.session_state.get("analysis", {}).get("kpis")
    orig_runway = getattr(orig_kpis, "runway_months",    None) if orig_kpis else None
    orig_gm     = getattr(orig_kpis, "gross_margin_pct", None) if orig_kpis else None
    orig_ltvcac = getattr(orig_kpis, "ltv_cac_ratio",    None) if orig_kpis else None

    # Appliquer les opérations — Python fait les maths
    computed = {}
    for field, op_dict in mods.items():
        if field not in _SUPPORTED_FIELDS or not hasattr(ctx, field):
            continue
        if not isinstance(op_dict, dict):
            continue
        current_val = ctx_dict.get(field)
        if current_val is None:
            continue
        new_val = _apply_operation(float(current_val), op_dict)
        if new_val is not None:
            computed[field] = new_val

    if not computed:
        return "Impossible d'appliquer les modifications (champs non reconnus ou opération invalide)."

    try:
        modified_ctx = _dc_replace(ctx, **computed)
    except Exception as e:
        return f"Erreur lors de la modification du contexte : {e}"

    # Relancer le vrai pipeline calcul_tools
    try:
        new_analysis = run_analysis_pipeline(modified_ctx)
    except Exception as e:
        return f"Erreur pipeline : {e}"

    new_kpis     = new_analysis.get("kpis")
    new_runway   = getattr(new_kpis, "runway_months",    None) if new_kpis else None
    new_burn_net = getattr(new_kpis, "burn_net",         None) if new_kpis else None
    new_gm       = getattr(new_kpis, "gross_margin_pct", None) if new_kpis else None
    new_ltvcac   = getattr(new_kpis, "ltv_cac_ratio",    None) if new_kpis else None
    new_alertes  = getattr(new_kpis, "alertes",          [])   if new_kpis else []

    def _delta(old, new_v, suffix="", higher_better=True):
        if old is None or new_v is None:
            return ""
        diff = new_v - old
        if abs(diff) < 0.01:
            return " (➖)"
        sign = "+" if diff >= 0 else ""
        icon = "✅" if (diff > 0) == higher_better else "⚠️"
        return f" ({sign}{diff:.1f}{suffix} {icon})"

    lines = ["**Simulation calcul_tools** — résultats précis\n"]

    # Afficher les modifications appliquées avec before → after
    for field, new_val in computed.items():
        lbl      = _MOD_LABELS.get(field, field)
        old_val  = ctx_dict.get(field)
        fmt_old  = f"{old_val:.1%}" if field == "churn_rate" else f"{old_val:,.0f} DT".replace(",", " ")
        fmt_new  = f"{new_val:.1%}" if field == "churn_rate" else f"{new_val:,.0f} DT".replace(",", " ")
        lines.append(f"📌 **{lbl}** : {fmt_old} → **{fmt_new}**")

    lines.append("")

    if new_runway is not None:
        d = _delta(orig_runway, new_runway, " mois")
        lines.append(f"🕐 **Runway** : **{new_runway:.1f} mois**{d}")
    if new_burn_net is not None:
        lines.append(f"🔥 **Burn net** : {new_burn_net:,.0f} DT/mois".replace(",", " "))
    if new_gm is not None:
        d = _delta(orig_gm, new_gm, "%")
        lines.append(f"📊 **Gross Margin** : {new_gm:.1f}%{d}")
    if new_ltvcac is not None:
        d = _delta(orig_ltvcac, new_ltvcac, "x")
        lines.append(f"💰 **LTV/CAC** : {new_ltvcac:.1f}x{d}")
    if new_alertes:
        lines.append("\n**Alertes :**")
        for a in new_alertes[:3]:
            lines.append(f"- {a}")

    return "\n".join(lines)


# ── Answer general questions ───────────────────────────────────────────────────
def _answer_general_question(user_prompt: str, existing_ctx: Any) -> str:
    ctx_dict = _to_dict(existing_ctx)

    # ── Détection what-if → pipeline réel (LLM détecte, Python calcule) ──────
    if existing_ctx is not None:
        mods = _extract_whatif_params(user_prompt, ctx_dict)
        if mods:
            return _run_whatif_pipeline(existing_ctx, mods)

    analysis: dict = st.session_state.get("analysis", {})

    # Base financials — burn_rate = dépenses brutes, burn_net = ce qui est vraiment perdu
    parts = []
    raw_burn = ctx_dict.get("burn_rate") or 0
    revenue  = ctx_dict.get("monthly_revenue") or 0
    burn_net_computed = max(0.0, raw_burn - revenue)

    if raw_burn:
        parts.append(f"dépenses_mensuelles={_fmt(raw_burn)} DT/mois")
    if revenue:
        parts.append(f"revenue_mensuel={_fmt(revenue)} DT/mois")
    if raw_burn or revenue:
        if burn_net_computed == 0:
            parts.append("burn_rate=0 DT/mois (startup rentable, revenus couvrent les dépenses)")
        else:
            parts.append(f"burn_rate={_fmt(burn_net_computed)} DT/mois (net = dépenses - revenus)")
    if ctx_dict.get("cash_balance"):
        parts.append(f"cash_balance={_fmt(ctx_dict['cash_balance'])} DT")

    # Enrich with computed KPIs
    kpis = analysis.get("kpis")
    if kpis is not None:
        if getattr(kpis, "runway_months", None) is not None:
            parts.append(f"runway={kpis.runway_months:.1f} mois")
        if getattr(kpis, "cac", None) is not None:
            parts.append(f"CAC={_fmt(kpis.cac)} DT")
        if getattr(kpis, "ltv_cac_ratio", None) is not None:
            parts.append(f"LTV/CAC={kpis.ltv_cac_ratio:.1f}x ({getattr(kpis, 'ltv_cac_status', '')})")
        if getattr(kpis, "gross_margin_pct", None) is not None:
            parts.append(f"gross_margin={kpis.gross_margin_pct:.1f}%")

    # Phase
    phase = analysis.get("phase")
    if phase is not None:
        parts.append(f"phase={getattr(phase, 'value', str(phase))}")

    # Monte Carlo survival
    mc = analysis.get("monte_carlo")
    if mc is not None and getattr(mc, "proba_survie_12m", None) is not None:
        parts.append(f"survie_12m={mc.proba_survie_12m:.0%}")

    # Scenario recommendation
    scenarios = analysis.get("scenarios")
    if scenarios is not None and getattr(scenarios, "recommandation", None):
        parts.append(f"recommandation={scenarios.recommandation}")

    # Benchmarks RAG depuis la mémoire session
    bench      = st.session_state.get("last_bench")
    bench_extra = st.session_state.get("last_bench_extra", {})
    if bench is not None:
        churn_med = getattr(bench, "churn_median", None)
        gm_med    = getattr(bench, "gross_margin_median", None)
        ev_mult   = getattr(bench, "valorisation_multiple", None)
        src       = getattr(bench, "source", "")
        sim       = getattr(bench, "similarity_score", 0.0)
        bench_parts = []
        if gm_med    is not None: bench_parts.append(f"gross_margin_secteur={gm_med:.1%}")
        if churn_med is not None: bench_parts.append(f"churn_secteur={churn_med:.1%}")
        if ev_mult   is not None: bench_parts.append(f"ev_multiple_secteur={ev_mult:.1f}x")
        if bench_extra.get("ltv_cac_ratio"):   bench_parts.append(f"ltv_cac_secteur={bench_extra['ltv_cac_ratio']:.1f}x")
        if bench_extra.get("cac_payback_months"): bench_parts.append(f"cac_payback_secteur={bench_extra['cac_payback_months']:.0f} mois")
        if bench_extra.get("nrr"):             bench_parts.append(f"nrr_secteur={bench_extra['nrr']:.1f}%")
        if bench_extra.get("growth_yoy"):      bench_parts.append(f"croissance_yoy_secteur={bench_extra['growth_yoy']:.0f}%")
        if bench_parts:
            parts.append("Benchmarks secteur (" + src + f", similarité {sim:.0%}) : " + ", ".join(bench_parts))

    ctx_summary = ("Contexte financier actuel : " + ", ".join(parts) + ". ") if parts else ""

    # Historique conversationnel — 6 derniers échanges (3 tours)
    history = st.session_state.get("messages", [])
    history_slice = history[-6:] if len(history) > 6 else history
    chat_messages = [
        {"role": m["role"], "content": m["content"]}
        for m in history_slice
        if m.get("role") in ("user", "assistant") and m.get("content")
    ]

    messages = [
        {
            "role": "system",
            "content": (
                "Tu es un assistant CFO pour startups tunisiennes. "
                "Réponds de façon concise, claire et professionnelle en français. "
                "Utilise le contexte financier et les benchmarks sectoriels fournis pour répondre avec précision. "
                + ctx_summary
            ),
        },
        *chat_messages,
        {"role": "user", "content": user_prompt},
    ]

    result = _call_llm_text(messages)
    return result if result.strip() else "Je n'ai pas pu traiter cette demande."


# ── Champs bruts requis — jamais calculés, toujours demandés au fondateur ──────
# Minimum pour lancer l'analyse de base (runway + burn)
_FIELDS_MINIMUM = {"burn_rate", "cash_balance"}
# Champs complets pour tous les KPIs (LTV, CAC, breakeven, scénarios)
_FIELDS_FULL = {"burn_rate", "cash_balance", "monthly_revenue", "n_clients", "prix_client", "churn_rate"}


def _missing_fields(ctx: Any) -> list[str]:
    """Retourne les champs de _FIELDS_FULL encore absents du contexte cumulatif."""
    d = _to_dict(ctx)
    return [f for f in _FIELDS_FULL if d.get(f) is None]


# ── Shared processing logic ────────────────────────────────────────────────────
def _process_financial_context(new_ctx: Any) -> tuple[str, list[str], Any]:
    """
    Fusion cumulative + pipeline de calcul + RAG benchmarks.
    Returns (data_text, questions, bench).
    """
    parsed_ctx = _merge_contexts(st.session_state.financial_context, new_ctx)

    # Pipeline de calcul (gère les données partielles sans planter)
    analysis: dict = {}
    try:
        analysis = run_analysis_pipeline(parsed_ctx)
    except Exception:
        analysis = {}

    # Validation — fallback si le pipeline n'en produit pas
    validation = analysis.get("validation")
    if validation is None:
        validation = validate_financial_context(parsed_ctx)

    st.session_state.financial_context = parsed_ctx
    st.session_state.validation_result = validation
    st.session_state.analysis = analysis

    data_text = _format_extracted_data(parsed_ctx, validation, analysis)

    # Mode COLLECTE vs ANALYSE
    still_missing = _missing_fields(parsed_ctx)
    if not still_missing:
        questions = []
    else:
        from models.data_models import ValidationResult as _VR
        missing_only = [
            m for m in (getattr(validation, "missing_critical", []) or [])
            if any(f in m.lower() for f in still_missing)
        ]
        validation_filtered = _VR(
            is_valid=validation.is_valid,
            data_quality_score=validation.data_quality_score,
            incoherences=list(getattr(validation, "incoherences", []) or []),
            missing_critical=missing_only,
            questions_to_ask=list(getattr(validation, "questions_to_ask", []) or []),
        )
        questions = _generate_questions_with_llm(parsed_ctx, validation_filtered)

    # RAG benchmark — seulement si données complètes
    bench = None
    if getattr(validation, "is_valid", False):
        try:
            bench = fetch_benchmarks(parsed_ctx)
        except Exception:
            bench = None

    # ── Mémoire session : sauvegarder bench + extra pour les follow-ups ──────
    if bench is not None:
        st.session_state.last_bench = bench
        docs  = list(getattr(bench, "documents_raw", []) or [])
        st.session_state.last_bench_extra = _parse_docs_extra(docs)

    return data_text, questions, bench


def _render_analysis_charts(ctx: Any, analysis: dict) -> None:
    """
    Affiche les visualisations financières quand l'analyse est complète.
    2 graphiques côte à côte :
      - Trésorerie projetée sur 24 mois (3 scénarios)
      - Revenus projetés sur 24 mois (3 scénarios + ligne breakeven)
    """
    try:
        import plotly.graph_objects as go
    except ImportError:
        st.caption("_Installez plotly pour les visualisations : `pip install plotly`_")
        return

    scenarios = analysis.get("scenarios")
    kpis      = analysis.get("kpis")
    if scenarios is None or kpis is None:
        return

    ctx_dict = _to_dict(ctx)
    cash    = ctx_dict.get("cash_balance") or 0.0
    burn    = ctx_dict.get("burn_rate")    or 0.0
    revenue = ctx_dict.get("monthly_revenue") or 0.0
    n_months = 24
    months   = list(range(n_months + 1))

    pess_g = getattr(scenarios.pessimiste, "growth_rate", 0.0)
    real_g = getattr(scenarios.realiste,   "growth_rate", 0.08)
    opti_g = getattr(scenarios.optimiste,  "growth_rate", 0.15)

    def _trajectory(growth):
        cash_s, rev_s = [cash], [revenue]
        c, r = cash, revenue
        for _ in range(n_months):
            r = r * (1 + growth)
            net = r - burn
            c = max(c + net, 0.0)
            cash_s.append(round(c, 0))
            rev_s.append(round(r, 0))
        return cash_s, rev_s

    pess_cash, pess_rev = _trajectory(pess_g)
    real_cash, real_rev = _trajectory(real_g)
    opti_cash, opti_rev = _trajectory(opti_g)

    _layout = dict(
        height=300,
        margin=dict(l=10, r=10, t=36, b=10),
        plot_bgcolor="#fafafa",
        paper_bgcolor="#ffffff",
        font=dict(size=11, color="#333"),
        legend=dict(orientation="h", y=-0.28, x=0),
        xaxis=dict(title="Mois", gridcolor="#f0f0f0"),
    )

    col1, col2 = st.columns(2)

    with col1:
        fig_cash = go.Figure()
        fig_cash.add_trace(go.Scatter(x=months, y=pess_cash, name="Pessimiste",
            line=dict(color="#ef4444", dash="dash", width=2)))
        fig_cash.add_trace(go.Scatter(x=months, y=real_cash, name="Réaliste",
            line=dict(color="#3b82f6", width=2.5)))
        fig_cash.add_trace(go.Scatter(x=months, y=opti_cash, name="Optimiste",
            line=dict(color="#22c55e", dash="dot", width=2)))
        fig_cash.add_hline(y=0, line_dash="dot", line_color="#1a1a1a", line_width=1,
            annotation_text="Cash out", annotation_position="bottom right",
            annotation_font_size=10)
        fig_cash.update_layout(
            title=dict(text="Trésorerie projetée (24 mois)", font=dict(size=13)),
            yaxis=dict(title="Cash (DT)", gridcolor="#f0f0f0"), **_layout)
        st.plotly_chart(fig_cash, use_container_width=True)

    with col2:
        fig_rev = go.Figure()
        fig_rev.add_trace(go.Scatter(x=months, y=pess_rev, name="Pessimiste",
            line=dict(color="#ef4444", dash="dash", width=2)))
        fig_rev.add_trace(go.Scatter(x=months, y=real_rev, name="Réaliste",
            line=dict(color="#3b82f6", width=2.5)))
        fig_rev.add_trace(go.Scatter(x=months, y=opti_rev, name="Optimiste",
            line=dict(color="#22c55e", dash="dot", width=2)))
        if burn > 0:
            fig_rev.add_hline(y=burn, line_dash="dot", line_color="#f59e0b", line_width=1.5,
                annotation_text="Breakeven", annotation_position="top right",
                annotation_font_size=10)
        fig_rev.update_layout(
            title=dict(text="Revenus projetés (24 mois)", font=dict(size=13)),
            yaxis=dict(title="Revenue (DT)", gridcolor="#f0f0f0"), **_layout)
        st.plotly_chart(fig_rev, use_container_width=True)


def _render_pdf_download(ctx: Any, analysis: dict, bench: Any) -> None:
    """Renders a PDF download button with the full financial report."""
    try:
        from agent.tools.pdf_report import generate_pdf_report
    except ImportError:
        return

    docs  = list(getattr(bench, "documents_raw", []) or [])
    extra = _parse_docs_extra(docs)
    validation = st.session_state.get("validation_result")
    if validation is None:
        return

    st.divider()
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(
            "<span style='font-size:0.85rem;color:#666'>"
            "Téléchargez le rapport complet avec toutes les analyses, "
            "projections et comparaisons sectorielles.</span>",
            unsafe_allow_html=True,
        )
    with col2:
        try:
            pdf_bytes = generate_pdf_report(ctx, validation, analysis, bench, extra)
            date_str = __import__("datetime").datetime.now().strftime("%Y%m%d")
            st.download_button(
                label="Rapport PDF",
                data=bytes(pdf_bytes),
                file_name=f"startwise_rapport_{date_str}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        except Exception as exc:
            st.caption(f"_PDF non disponible : {exc}_")


def _render_action_buttons(ctx: Any, analysis: dict, bench: Any) -> None:
    """
    Affiche les boutons d'action proposés après les KPIs.
    Chaque bouton révèle une section supplémentaire (graphiques / benchmarks / PDF).
    L'état est persisté dans st.session_state.shown_sections.
    """
    has_charts    = analysis.get("scenarios") is not None
    has_bench     = bench is not None
    has_pdf       = bench is not None and ctx is not None

    if not (has_charts or has_bench or has_pdf):
        return

    st.markdown(
        "<div style='font-size:0.82rem;color:#666;margin:0.75rem 0 0.4rem 0'>"
        "Je peux aussi afficher :</div>",
        unsafe_allow_html=True,
    )

    btn_cols = st.columns(3)
    with btn_cols[0]:
        if has_charts:
            active = "charts" in st.session_state.shown_sections
            label  = "📈 Graphiques ✓" if active else "📈 Graphiques"
            if st.button(label, key="action_charts", use_container_width=True):
                s = set(st.session_state.shown_sections)
                s.discard("charts") if active else s.add("charts")
                st.session_state.shown_sections = s
                st.rerun()
    with btn_cols[1]:
        if has_bench:
            active = "bench" in st.session_state.shown_sections
            label  = "📊 Benchmarks ✓" if active else "📊 Benchmarks"
            if st.button(label, key="action_bench", use_container_width=True):
                s = set(st.session_state.shown_sections)
                s.discard("bench") if active else s.add("bench")
                st.session_state.shown_sections = s
                st.rerun()
    with btn_cols[2]:
        if has_pdf:
            if st.button("📄 Rapport PDF", key="action_pdf", use_container_width=True):
                s = set(st.session_state.shown_sections)
                s.add("pdf")
                st.session_state.shown_sections = s
                st.rerun()

    # ── Sections révélées ─────────────────────────────────────────────────────
    if "charts" in st.session_state.shown_sections and has_charts:
        st.divider()
        _render_analysis_charts(ctx, analysis)

    if "bench" in st.session_state.shown_sections and has_bench:
        st.divider()
        bench_text = _format_benchmark_result(bench, ctx, analysis)
        if bench_text:
            st.markdown(bench_text, unsafe_allow_html=True)
        _render_benchmark_charts(bench, ctx, analysis)

    if "pdf" in st.session_state.shown_sections and has_pdf:
        _render_pdf_download(ctx, analysis, bench)
        s = set(st.session_state.shown_sections)
        s.discard("pdf")
        st.session_state.shown_sections = s


def _render_financial_reply(data_text: str, questions: list[str], bench: Any = None, ctx: Any = None) -> str:
    """
    Affiche les KPIs + questions toujours.
    Les graphiques / benchmarks / PDF sont proposés via boutons d'action.
    """
    full_reply_parts = []

    if data_text:
        st.markdown(data_text, unsafe_allow_html=True)
        full_reply_parts.append(data_text)

    # Sauvegarder bench pour les boutons d'action (persistant)
    analysis = st.session_state.get("analysis", {})
    if bench is not None:
        st.session_state.pending_bench = bench

    # Proposer les actions (graphiques / benchmarks / PDF)
    _effective_ctx   = ctx or st.session_state.get("financial_context")
    _effective_bench = bench or st.session_state.pending_bench
    _render_action_buttons(_effective_ctx, analysis, _effective_bench)

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


# ── Conversation history helpers ──────────────────────────────────────────────

def _save_current_conversation() -> None:
    """Sauvegarde la conversation active dans l'historique session."""
    msgs = st.session_state.messages
    if not msgs or all(m["role"] == "assistant" for m in msgs):
        return
    first_user = next((m["content"] for m in msgs if m["role"] == "user"), "")
    title = (first_user[:45] + "…") if len(first_user) > 45 else first_user
    st.session_state.conversations.append({
        "id":       len(st.session_state.conversations),
        "title":    title or "Conversation",
        "messages": list(msgs),
        "ctx":      st.session_state.financial_context,
        "analysis": dict(st.session_state.analysis),
        "bench":    st.session_state.last_bench,
        "extra":    dict(st.session_state.last_bench_extra),
    })


def _restore_conversation(conv: dict) -> None:
    """Restaure une conversation sauvegardée."""
    st.session_state.messages         = list(conv["messages"])
    st.session_state.financial_context = conv["ctx"]
    st.session_state.analysis          = conv.get("analysis", {})
    st.session_state.last_bench        = conv.get("bench")
    st.session_state.last_bench_extra  = conv.get("extra", {})
    st.session_state.validation_result = None
    st.session_state.pending_bench     = conv.get("bench")
    st.session_state.shown_sections    = set()


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
        _save_current_conversation()
        st.session_state.messages          = []
        st.session_state.financial_context = None
        st.session_state.validation_result = None
        st.session_state.last_uploaded_file = None
        st.session_state.analysis          = {}
        st.session_state.last_bench        = None
        st.session_state.last_bench_extra  = {}
        st.session_state.pending_bench     = None
        st.session_state.shown_sections    = set()
        st.rerun()

    # ── Historique des conversations ───────────────────────────────────────────
    if st.session_state.conversations:
        st.markdown(
            "<div style='font-size:0.75rem;color:#555;text-transform:uppercase;"
            "letter-spacing:0.5px;margin:0.5rem 0 0.3rem 0'>Conversations</div>",
            unsafe_allow_html=True,
        )
        for conv in reversed(st.session_state.conversations):
            col_a, col_b = st.columns([5, 1])
            with col_a:
                if st.button(
                    conv["title"],
                    key=f"conv_{conv['id']}",
                    use_container_width=True,
                ):
                    _restore_conversation(conv)
                    st.rerun()
            with col_b:
                if st.button("✕", key=f"del_{conv['id']}", help="Supprimer"):
                    st.session_state.conversations = [
                        c for c in st.session_state.conversations
                        if c["id"] != conv["id"]
                    ]
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
            ("Dépenses", "burn_rate", "DT/m"),
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

        # Runway: use net burn from KPIs if available, otherwise gross burn as fallback
        _analysis = st.session_state.get("analysis", {})
        _kpis = _analysis.get("kpis") if _analysis else None
        if _kpis is not None and getattr(_kpis, "runway_months", None) is not None:
            _rw = _kpis.runway_months
            _rw_display = "∞" if _rw == float("inf") else f"{_rw:.1f} mois"
            st.markdown(
                f"<div class='sidebar-metric'>"
                f"<span class='sidebar-metric-label'>Runway (net)</span>"
                f"<span class='sidebar-metric-value'>{_rw_display}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
        elif ctx_dict.get("burn_rate") and ctx_dict.get("cash_balance") and ctx_dict.get("burn_rate") > 0:
            runway = ctx_dict["cash_balance"] / ctx_dict["burn_rate"]
            st.markdown(
                f"<div class='sidebar-metric'>"
                f"<span class='sidebar-metric-label'>Runway (brut)</span>"
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
                bench_text = _format_benchmark_result(bench, st.session_state.financial_context, st.session_state.get("analysis", {}))
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
    if st.button("Reinitialiser tout", use_container_width=True):
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

# ── Boutons d'action persistants (rendus à chaque rerun) ──────────────────────
_pa_ctx      = st.session_state.financial_context
_pa_analysis = st.session_state.get("analysis", {})
_pa_bench    = st.session_state.pending_bench
if _pa_ctx is not None and (_pa_analysis or _pa_bench):
    _render_action_buttons(_pa_ctx, _pa_analysis, _pa_bench)

# ── Bouton What-if dans la zone prompt (CSS fixed bottom) ─────────────────────
_wi_active = st.session_state.whatif_mode
_wi_label  = "⚡ What-if  ●" if _wi_active else "⚡ What-if"
_wi_bg     = "#fef3c7" if _wi_active else "#f4f4f5"
_wi_border = "1.5px solid #f59e0b" if _wi_active else "1px solid #d1d5db"
_wi_color  = "#92400e" if _wi_active else "#6b7280"

st.markdown(
    f"""<style>
    /* Cible le bouton what-if par son key Streamlit */
    div[data-testid="stMainBlockContainer"] div[data-testid="stVerticalBlock"]
      > div[data-testid="stVerticalBlock"]:last-of-type
      div.stButton > button {{
        background: {_wi_bg} !important;
        border: {_wi_border} !important;
        color: {_wi_color} !important;
        border-radius: 20px !important;
        font-size: 0.78rem !important;
        font-weight: 600 !important;
        padding: 0.2rem 0.85rem !important;
        height: auto !important;
        line-height: 1.4 !important;
    }}
    </style>""",
    unsafe_allow_html=True,
)
# Le bouton Streamlit — positionné juste avant st.chat_input (qui s'ancre en bas)
_wi_c1, _ = st.columns([1, 7])
with _wi_c1:
    if st.button(_wi_label, key="whatif_toggle"):
        st.session_state.whatif_mode = not st.session_state.whatif_mode
        st.rerun()

# Chat input
_placeholder = "Simulez un scénario… ex: Si je réduis mon burn de 30%" if st.session_state.whatif_mode else "Décrivez votre situation financière..."
if prompt := st.chat_input(_placeholder):
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

        # Mode what-if : forcer le routing vers la simulation même sans mots-clés
        force_whatif = st.session_state.whatif_mode and st.session_state.financial_context is not None

        if force_whatif:
            with st.spinner("Simulation en cours..."):
                reply = _answer_general_question(prompt, st.session_state.financial_context)
            streamed = st.write_stream(_word_stream(reply))
            st.session_state.messages.append({"role": "assistant", "content": streamed})
            # Désactiver le mode après la simulation
            st.session_state.whatif_mode = False
        elif _has_new_financial_data(new_ctx):
            with st.spinner("Génération des questions..."):
                data_text, questions, bench = _process_financial_context(new_ctx)
            full_reply = _render_financial_reply(data_text, questions, bench, st.session_state.financial_context)
            st.session_state.messages.append({"role": "assistant", "content": full_reply})
        else:
            with st.spinner("Réflexion..."):
                reply = _answer_general_question(prompt, st.session_state.financial_context)
            streamed = st.write_stream(_word_stream(reply))
            st.session_state.messages.append({"role": "assistant", "content": streamed})
