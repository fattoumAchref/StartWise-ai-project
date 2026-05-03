"""
a2a_bus/monitor_app.py
======================
Dashboard Streamlit de monitoring du bus A2A.
Visualise en temps réel la communication entre agents.

Lancer :
    streamlit run a2a_bus/monitor_app.py --server.port 8502
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Any, Dict, List

import httpx
import streamlit as st

BUS_URL = "http://localhost:8765"
AGENTS  = ["finance_agent", "investment_agent", "risk_agent", "orchestrator"]

AGENT_COLORS = {
    "finance_agent":    "#1f77b4",
    "investment_agent": "#2ca02c",
    "risk_agent":       "#d62728",
    "orchestrator":     "#9467bd",
}

TYPE_ICONS = {
    "financial_analysis": "📊",
    "investment_scoring": "💰",
    "risk_assessment":    "🛡️",
    "unknown":            "📨",
}

PRIORITY_COLORS = {
    "high":   "#ff4b4b",
    "medium": "#ffa500",
    "low":    "#00cc00",
}

RATING_COLORS = {
    "STRONG_BUY": "#00cc00",
    "BUY":        "#7dbd7d",
    "HOLD":       "#ffa500",
    "PASS":       "#ff4b4b",
}

RISK_COLORS = {
    "CRITIQUE": "#ff0000",
    "ÉLEVÉ":    "#ff4b4b",
    "MOYEN":    "#ffa500",
    "FAIBLE":   "#00cc00",
}


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _get(path: str) -> Any:
    try:
        r = httpx.get(f"{BUS_URL}{path}", timeout=3)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def _bus_ok() -> bool:
    try:
        r = httpx.get(f"{BUS_URL}/health", timeout=2)
        return r.status_code == 200
    except Exception:
        return False


def _format_ts(ts: str) -> str:
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%H:%M:%S")
    except Exception:
        return ts[:8] if ts else "?"


def _agent_badge(agent_id: str) -> str:
    color = AGENT_COLORS.get(agent_id, "#888")
    return f'<span style="background:{color};color:white;padding:2px 8px;border-radius:10px;font-size:12px">{agent_id}</span>'


# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="A2A Bus Monitor — StartWise",
    page_icon="🔗",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
  .msg-card {
    border-radius: 8px;
    padding: 12px 16px;
    margin: 6px 0;
    border-left: 4px solid #ccc;
    background: #1e1e2e;
  }
  .msg-header { font-size: 13px; color: #aaa; margin-bottom: 4px; }
  .msg-body   { font-size: 14px; }
  .arrow      { font-size: 20px; text-align: center; color: #555; }
  .stat-box {
    border-radius: 8px;
    padding: 14px;
    text-align: center;
    background: #1e1e2e;
    border: 1px solid #333;
  }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────────────────────────────────────

col_title, col_refresh = st.columns([5, 1])
with col_title:
    st.title("🔗 A2A Bus Monitor")
    st.caption("Visualisation en temps réel de la communication inter-agents — StartWise")

with col_refresh:
    st.write("")
    auto_refresh = st.toggle("Auto-refresh (3s)", value=False)
    if st.button("🔄 Rafraîchir", use_container_width=True):
        st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
# STATUS BUS
# ─────────────────────────────────────────────────────────────────────────────

bus_alive = _bus_ok()
if not bus_alive:
    st.error("❌ Bus A2A inaccessible — lancer : `uvicorn a2a_bus.bus_server:app --port 8765`")
    st.stop()

st.success(f"✅ Bus A2A connecté — `{BUS_URL}`")

# ─────────────────────────────────────────────────────────────────────────────
# STATS AGENTS
# ─────────────────────────────────────────────────────────────────────────────

st.subheader("📬 État des inboxes")

stats_data = _get("/stats") or {}
inboxes = stats_data.get("inboxes", {})

cols = st.columns(len(AGENTS))
for i, agent_id in enumerate(AGENTS):
    count = inboxes.get(agent_id, 0)
    color = AGENT_COLORS.get(agent_id, "#888")
    with cols[i]:
        st.markdown(f"""
        <div class="stat-box">
          <div style="color:{color};font-weight:bold;font-size:15px">{agent_id}</div>
          <div style="font-size:32px;font-weight:bold;color:{'#ff4b4b' if count > 0 else '#00cc00'}">{count}</div>
          <div style="color:#888;font-size:12px">messages en attente</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown(f"**Total pending :** {stats_data.get('total_pending', 0)} &nbsp;|&nbsp; **Log entries :** {stats_data.get('log_entries', 0)}")

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# ONGLETS PRINCIPAUX
# ─────────────────────────────────────────────────────────────────────────────

tab_flow, tab_inbox, tab_log = st.tabs(["🔄 Flux de messages", "📥 Inboxes détaillées", "📜 Log du bus"])

# ── TAB 1 : Flux de messages ─────────────────────────────────────────────────
with tab_flow:
    log_data = _get("/log?limit=30") or {}
    log_entries = log_data.get("log", [])

    if not log_entries:
        st.info("Aucun message publié pour l'instant. Lance `python -m a2a_bus.test_a2a` pour tester.")
    else:
        st.markdown(f"**{len(log_entries)} derniers messages publiés :**")

        for entry in log_entries:
            msg_type = entry.get("type", "unknown")
            icon     = TYPE_ICONS.get(msg_type, "📨")
            from_ag  = entry.get("from", "?")
            to_list  = entry.get("to", [])
            priority = entry.get("priority", "low")
            ts       = _format_ts(entry.get("timestamp", ""))
            msg_id   = entry.get("message_id", "?")[:12]
            border   = PRIORITY_COLORS.get(priority, "#ccc")

            from_color = AGENT_COLORS.get(from_ag, "#888")
            to_badges  = " → ".join(
                f'<span style="background:{AGENT_COLORS.get(a,"#555")};color:white;'
                f'padding:1px 6px;border-radius:8px;font-size:11px">{a}</span>'
                for a in to_list
            )

            st.markdown(f"""
            <div class="msg-card" style="border-left-color:{border}">
              <div class="msg-header">
                {icon} &nbsp;
                <code style="color:#ccc">{msg_id}…</code>
                &nbsp;·&nbsp; <span style="color:#aaa">{ts}</span>
                &nbsp;·&nbsp; <span style="background:{PRIORITY_COLORS.get(priority,'#888')};
                  color:white;padding:1px 6px;border-radius:8px;font-size:11px">{priority}</span>
              </div>
              <div class="msg-body">
                <span style="color:{from_color};font-weight:bold">{from_ag}</span>
                &nbsp;→&nbsp; {to_badges}
                &nbsp;&nbsp; <span style="color:#ddd">{icon} {msg_type}</span>
              </div>
            </div>
            """, unsafe_allow_html=True)

# ── TAB 2 : Inboxes détaillées ───────────────────────────────────────────────
with tab_inbox:
    selected_agent = st.selectbox(
        "Choisir un agent",
        AGENTS,
        format_func=lambda x: f"{x} ({inboxes.get(x, 0)} msgs)"
    )

    inbox_data = _get(f"/inbox/{selected_agent}?limit=20") or {}
    messages   = inbox_data.get("messages", [])

    if not messages:
        color = AGENT_COLORS.get(selected_agent, "#888")
        st.markdown(f'<p style="color:{color}">Inbox de <b>{selected_agent}</b> est vide.</p>', unsafe_allow_html=True)
    else:
        color = AGENT_COLORS.get(selected_agent, "#888")
        st.markdown(f'<p style="color:{color}"><b>{selected_agent}</b> — {len(messages)} message(s) en attente</p>', unsafe_allow_html=True)

        for msg in messages:
            msg_type = msg.get("type", "unknown")
            icon     = TYPE_ICONS.get(msg_type, "📨")
            from_ag  = msg.get("from") or msg.get("from_agent", "?")
            conf     = msg.get("confidence", 0)
            priority = msg.get("metadata", {}).get("priority", "low")
            ts       = _format_ts(msg.get("timestamp", ""))
            data     = msg.get("payload", {}).get("data", {})

            with st.expander(f"{icon} `{msg.get('message_id','?')[:14]}…` — {msg_type} — {ts}", expanded=True):
                c1, c2, c3 = st.columns(3)
                c1.metric("De", from_ag)
                c2.metric("Confiance", f"{conf:.0%}")
                c3.metric("Priorité", priority.upper())

                if msg_type == "financial_analysis":
                    kpis = data.get("kpis", {}) or {}
                    mc   = data.get("monte_carlo", {}) or {}
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Phase",       data.get("phase", "?"))
                    m2.metric("Runway",      f"{kpis.get('runway_months','?')} mois")
                    m3.metric("LTV/CAC",     f"{kpis.get('ltv_cac_ratio','?')}x")
                    m4.metric("Survie 12m",  f"{(mc.get('proba_survie_12m') or 0):.0%}")
                    alertes = data.get("alertes", [])
                    if alertes:
                        for a in alertes:
                            st.warning(a)

                elif msg_type == "investment_scoring":
                    rating = data.get("rating", "?")
                    score  = data.get("score", 0)
                    rcol   = RATING_COLORS.get(rating, "#888")
                    st.markdown(f'<div style="font-size:22px;font-weight:bold;color:{rcol}">{rating} — {score}/100</div>', unsafe_allow_html=True)
                    st.caption(data.get("recommendation", ""))
                    for reason in data.get("reasons", []):
                        st.markdown(f"• {reason}")

                elif msg_type == "risk_assessment":
                    risk_level = data.get("risk_level", "?")
                    risk_score = data.get("risk_score", 0)
                    rcol = RISK_COLORS.get(risk_level, "#888")
                    st.markdown(f'<div style="font-size:22px;font-weight:bold;color:{rcol}">Risque {risk_level} — {risk_score}/100</div>', unsafe_allow_html=True)
                    for r in data.get("risks", []):
                        lvl   = r.get("level", "?")
                        rtype = r.get("type", "?")
                        det   = r.get("detail", "?")
                        lcol  = RISK_COLORS.get(lvl, "#888")
                        st.markdown(f'<span style="color:{lcol}">▶ [{lvl}]</span> **{rtype}** — {det}', unsafe_allow_html=True)

                else:
                    st.json(data)

# ── TAB 3 : Log brut ────────────────────────────────────────────────────────
with tab_log:
    limit = st.slider("Nombre d'entrées", 5, 100, 20)
    log_raw = _get(f"/log?limit={limit}") or {}
    entries = log_raw.get("log", [])

    filter_type = st.multiselect(
        "Filtrer par type",
        options=["financial_analysis", "investment_scoring", "risk_assessment"],
        default=[],
    )

    if filter_type:
        entries = [e for e in entries if e.get("type") in filter_type]

    if not entries:
        st.info("Aucune entrée dans le log.")
    else:
        for e in entries:
            from_ag  = e.get("from", "?")
            to_list  = e.get("to", [])
            msg_type = e.get("type", "?")
            priority = e.get("priority", "?")
            ts       = _format_ts(e.get("timestamp", ""))
            msg_id   = e.get("message_id", "?")[:12]

            pcolor = PRIORITY_COLORS.get(priority, "#888")
            fcolor = AGENT_COLORS.get(from_ag, "#888")

            st.markdown(
                f"`{ts}` &nbsp; `{msg_id}…` &nbsp; "
                f'<span style="color:{fcolor}">{from_ag}</span> → '
                f'`{", ".join(to_list)}` &nbsp; '
                f'<span style="color:#ddd">{TYPE_ICONS.get(msg_type,"📨")} {msg_type}</span> &nbsp; '
                f'<span style="background:{pcolor};color:white;padding:1px 5px;border-radius:6px;font-size:11px">{priority}</span>',
                unsafe_allow_html=True,
            )

    st.divider()
    if st.button("🗑️ Vider tous les logs et inboxes (reset test)"):
        for agent in AGENTS:
            try:
                httpx.delete(f"{BUS_URL}/inbox/{agent}", timeout=3)
            except Exception:
                pass
        st.success("Inboxes vidées.")
        st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
# AUTO REFRESH
# ─────────────────────────────────────────────────────────────────────────────
if auto_refresh:
    time.sleep(3)
    st.rerun()
