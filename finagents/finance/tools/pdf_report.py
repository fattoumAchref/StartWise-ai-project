"""
agent/tools/pdf_report.py
Génère un rapport PDF complet pour StartWise.

Sections :
  1. Page de garde
  2. KPIs calculés (calcul_tools)
  3. Projections & Monte Carlo + graphique trajectoires
  4. Analyse sectorielle (RAG) + graphiques comparaison
  5. Recommandations actionnables

Dépendances : fpdf2, kaleido, plotly
"""
from __future__ import annotations

import io
import math
import tempfile
import os
from datetime import datetime
from typing import Any, Optional


# ── Palette ───────────────────────────────────────────────────────────────────
_BLUE      = (37,  99, 235)   # accent principal
_DARK      = (15,  23, 42)    # texte titres
_GRAY      = (100, 116, 139)  # texte secondaire
_LIGHT     = (241, 245, 249)  # fond lignes paires
_GREEN     = (22, 163, 74)
_ORANGE    = (234, 88, 12)
_RED       = (220, 38, 38)
_WHITE     = (255, 255, 255)


def _status_color(status: str) -> tuple:
    s = status.upper()
    if s in ("SAIN", "AU-DESSUS", "OK"):
        return _GREEN
    if s in ("LIMITE", "ATTENTION", "ALIGNÉ", "ALIGNÉ"):
        return _ORANGE
    if s in ("DANGEREUX", "CRITIQUE", "EN DESSOUS"):
        return _RED
    return _GRAY


def _make_chart_png(fig) -> str:
    """
    Exporte un figure Plotly en PNG via kaleido.
    Retourne le chemin d'un fichier temporaire à supprimer après usage.
    """
    import plotly.io as pio
    img_bytes = pio.to_image(fig, format="png", width=700, height=300, scale=2)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    tmp.write(img_bytes)
    tmp.close()
    return tmp.name


def _chart_comparison_bars(metrics: list[tuple]) -> Optional[str]:
    """
    Barres groupées : votre valeur vs médiane secteur.
    metrics = [(label, founder_val, sector_val, unit), ...]
    Retourne chemin PNG temp ou None si plotly indisponible.
    """
    try:
        import plotly.graph_objects as go
    except ImportError:
        return None

    labels   = [m[0] for m in metrics]
    founder  = [m[1] for m in metrics]
    sector   = [m[2] for m in metrics]
    units    = [m[3] for m in metrics]

    founder_text = [f"{v}{u}" if v is not None else "—" for v, u in zip(founder, units)]
    sector_text  = [f"{v}{u}" if v is not None else "—" for v, u in zip(sector,  units)]

    # Replace None with 0 for plotting
    founder_plot = [v if v is not None else 0 for v in founder]
    sector_plot  = [v if v is not None else 0 for v in sector]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Votre startup",
        x=labels, y=founder_plot,
        marker_color="#3b82f6",
        text=founder_text, textposition="outside",
        textfont=dict(size=10),
    ))
    fig.add_trace(go.Bar(
        name="Mediane secteur",
        x=labels, y=sector_plot,
        marker_color="#cbd5e1",
        marker_line_color="#94a3b8", marker_line_width=1,
        text=sector_text, textposition="outside",
        textfont=dict(size=10),
    ))
    fig.update_layout(
        barmode="group",
        plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
        font=dict(family="Helvetica", size=11, color="#0f172a"),
        legend=dict(orientation="h", y=-0.22, x=0, font=dict(size=10)),
        margin=dict(l=30, r=20, t=30, b=50),
        yaxis=dict(gridcolor="#f1f5f9", zeroline=False),
        xaxis=dict(tickfont=dict(size=10)),
        title=dict(text="Comparaison vs mediane sectorielle", font=dict(size=12), x=0),
    )
    return _make_chart_png(fig)


def _chart_trajectories(scenarios, cash: float, burn: float, revenue: float) -> Optional[str]:
    """
    Courbes de trésorerie projetées sur 24 mois (3 scénarios).
    """
    try:
        import plotly.graph_objects as go
    except ImportError:
        return None

    n_months = 24
    months   = list(range(n_months + 1))

    def _traj(growth):
        c, r = cash, revenue
        cash_s = [c]
        for _ in range(n_months):
            r = r * (1 + growth)
            c = max(c + r - burn, 0.0)
            cash_s.append(round(c))
        return cash_s

    pess_g = getattr(scenarios.pessimiste, "growth_rate", 0.0)
    real_g = getattr(scenarios.realiste,   "growth_rate", 0.05)
    opti_g = getattr(scenarios.optimiste,  "growth_rate", 0.12)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=months, y=_traj(pess_g), name="Pessimiste",
        line=dict(color="#ef4444", dash="dash", width=2)))
    fig.add_trace(go.Scatter(x=months, y=_traj(real_g), name="Realiste",
        line=dict(color="#3b82f6", width=2.5)))
    fig.add_trace(go.Scatter(x=months, y=_traj(opti_g), name="Optimiste",
        line=dict(color="#22c55e", dash="dot", width=2)))
    fig.add_hline(y=0, line_dash="dot", line_color="#1a1a1a", line_width=1,
                  annotation_text="Cash out", annotation_font_size=9)
    fig.update_layout(
        title=dict(text="Tresorerie projetee sur 24 mois (DT)", font=dict(size=12), x=0),
        plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
        font=dict(family="Helvetica", size=10, color="#0f172a"),
        legend=dict(orientation="h", y=-0.22, x=0, font=dict(size=10)),
        margin=dict(l=40, r=20, t=35, b=50),
        xaxis=dict(title="Mois", gridcolor="#f1f5f9"),
        yaxis=dict(title="Cash (DT)", gridcolor="#f1f5f9"),
    )
    return _make_chart_png(fig)


def _chart_gauge_gm(founder_gm: float, sector_gm: float) -> Optional[str]:
    """Gauge Gross Margin avec zones colorées."""
    try:
        import plotly.graph_objects as go
    except ImportError:
        return None

    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=founder_gm,
        delta={"reference": sector_gm, "valueformat": ".1f", "suffix": "%"},
        number={"suffix": "%", "font": {"size": 26}},
        title={"text": "Gross Margin vs mediane secteur", "font": {"size": 11}},
        gauge={
            "axis": {"range": [0, 100], "ticksuffix": "%", "tickfont": {"size": 9}},
            "bar": {"color": "#3b82f6"},
            "steps": [
                {"range": [0, 40],  "color": "#fee2e2"},
                {"range": [40, 60], "color": "#fef3c7"},
                {"range": [60, 80], "color": "#d1fae5"},
                {"range": [80, 100], "color": "#a7f3d0"},
            ],
            "threshold": {
                "line": {"color": "#f59e0b", "width": 3},
                "thickness": 0.8,
                "value": sector_gm,
            },
        },
    ))
    fig.update_layout(
        height=260, width=700,
        margin=dict(l=30, r=30, t=50, b=10),
        paper_bgcolor="#ffffff",
        font=dict(family="Helvetica"),
    )
    return _make_chart_png(fig)


def _chart_ltv_cac_gauge(ltv_cac: float) -> Optional[str]:
    """Gauge LTV/CAC avec zones DANGEREUX / LIMITE / SAIN."""
    try:
        import plotly.graph_objects as go
    except ImportError:
        return None

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=ltv_cac,
        number={"suffix": "x", "font": {"size": 26}},
        title={"text": "Ratio LTV / CAC (cible > 3x)", "font": {"size": 11}},
        gauge={
            "axis": {"range": [0, 10], "tickfont": {"size": 9}},
            "bar": {"color": "#3b82f6"},
            "steps": [
                {"range": [0, 1],  "color": "#fee2e2"},
                {"range": [1, 3],  "color": "#fef3c7"},
                {"range": [3, 5],  "color": "#d1fae5"},
                {"range": [5, 10], "color": "#a7f3d0"},
            ],
            "threshold": {
                "line": {"color": "#f59e0b", "width": 3},
                "thickness": 0.8,
                "value": 3,
            },
        },
    ))
    fig.update_layout(
        height=260, width=700,
        margin=dict(l=30, r=30, t=50, b=10),
        paper_bgcolor="#ffffff",
        font=dict(family="Helvetica"),
    )
    return _make_chart_png(fig)


def _embed_chart(pdf, path: str, w: float = 174, caption: str = "") -> None:
    """Insère une image PNG dans le PDF puis supprime le fichier temp."""
    if path and os.path.exists(path):
        try:
            pdf.image(path, x=18, w=w)
            if caption:
                pdf.set_font("Helvetica", "I", 8)
                pdf.set_text_color(100, 116, 139)
                pdf.cell(0, 5, f"  {caption}", ln=True)
                pdf.set_text_color(15, 23, 42)
            pdf.ln(3)
        finally:
            os.unlink(path)


def generate_pdf_report(
    ctx: Any,
    validation: Any,
    analysis: dict,
    bench: Any,
    extra: dict,
) -> bytes:
    """
    Génère le rapport PDF et retourne les bytes.
    Compatible avec st.download_button.
    """
    try:
        from fpdf import FPDF
    except ImportError:
        raise ImportError("fpdf2 requis : pip install fpdf2")

    from dataclasses import asdict

    def _clean(text: str) -> str:
        """Replace non-latin1 characters so Helvetica core font doesn't crash."""
        t = (text
             .replace("\u2014", "-").replace("\u2013", "-")
             .replace("\u2212", "-")                          # U+2212 MINUS SIGN (math)
             .replace("\u2019", "'").replace("\u2018", "'")
             .replace("\u201c", '"').replace("\u201d", '"')
             .replace("\u2022", "*").replace("\u2026", "...")
             .replace("\u00e9", "e").replace("\u00e8", "e")
             .replace("\u00ea", "e").replace("\u00e0", "a")
             .replace("\u00e2", "a").replace("\u00f4", "o")
             .replace("\u00fb", "u").replace("\u00ee", "i")
             .replace("\u00ef", "i").replace("\u00e7", "c")
             .replace("\u00c9", "E").replace("\u00c0", "A")
             .replace("\u00d4", "O"))
        # Catch-all : any remaining non-latin1 char → "?"
        return "".join(c if ord(c) < 256 else "?" for c in t)

    def _to_dict(obj):
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

    def _fmt(v, suffix=""):
        if v is None:
            return "—"
        if isinstance(v, float) and math.isinf(v):
            return "∞"
        if isinstance(v, float):
            return f"{v:,.0f}{suffix}".replace(",", " ")
        return f"{v}{suffix}"

    ctx_dict   = _to_dict(ctx)
    kpis       = analysis.get("kpis")
    mc         = analysis.get("monte_carlo")
    phase      = analysis.get("phase")
    scenarios  = analysis.get("scenarios")
    score      = getattr(validation, "data_quality_score", 0.0)
    is_valid   = getattr(validation, "is_valid", False)
    alertes    = getattr(kpis, "alertes", []) if kpis else []
    inco       = list(getattr(validation, "incoherences", []) or [])

    sector     = ctx_dict.get("secteur") or "SaaS"
    pays       = ctx_dict.get("pays") or "TN"
    date_str   = datetime.now().strftime("%d/%m/%Y")

    # ── Valeurs founder ───────────────────────────────────────────────────────
    churn       = ctx_dict.get("churn_rate")
    rev         = ctx_dict.get("monthly_revenue")
    burn        = ctx_dict.get("burn_rate")
    cash        = ctx_dict.get("cash_balance")
    n_cl        = ctx_dict.get("n_clients")
    p_cl        = ctx_dict.get("prix_client")
    mktg        = ctx_dict.get("marketing_budget")
    new_cl      = ctx_dict.get("new_clients_month")
    cogs_val    = ctx_dict.get("cogs")

    runway      = getattr(kpis, "runway_months", None) if kpis else None
    burn_net    = getattr(kpis, "burn_net", None)      if kpis else None
    gm_pct      = getattr(kpis, "gross_margin_pct", None) if kpis else None
    ltv         = getattr(kpis, "ltv", None)           if kpis else None
    cac         = getattr(kpis, "cac", None)           if kpis else None
    ltv_cac     = getattr(kpis, "ltv_cac_ratio", None) if kpis else None
    mrr         = getattr(kpis, "mrr", None)           if kpis else rev
    arr         = getattr(kpis, "arr", None)           if kpis else (rev * 12 if rev else None)
    breakeven   = getattr(kpis, "breakeven_months", None) if kpis else None
    run_alert   = getattr(kpis, "cash_out_alert", "")  if kpis else ""
    ltv_status  = getattr(kpis, "ltv_cac_status", "")  if kpis else ""
    gm_status   = getattr(kpis, "gross_margin_status", "") if kpis else ""

    # Métriques avancées calculées
    burn_multiple = None
    if burn_net and new_cl and p_cl:
        net_new_arr = new_cl * p_cl * 12
        if net_new_arr > 0:
            burn_multiple = round(burn_net / (net_new_arr / 12), 2)

    arpu = None
    if mrr and n_cl and n_cl > 0:
        arpu = round(mrr / n_cl, 2)

    magic_number = None
    if mktg and mktg > 0 and new_cl and p_cl:
        net_new_arr_q = new_cl * p_cl * 3  # quarterly
        magic_number = round(net_new_arr_q / mktg, 2)

    grr = None
    if churn is not None:
        grr = max(0.0, 1 - churn * 12)

    # Benchmarks RAG
    churn_med = getattr(bench, "churn_median", None)    if bench else None
    gm_med    = getattr(bench, "gross_margin_median", None) if bench else None
    ev_mult   = getattr(bench, "valorisation_multiple", None) if bench else None
    ltv_cac_b = extra.get("ltv_cac_ratio")
    payback_b = extra.get("cac_payback_months")
    nrr_b     = extra.get("nrr")
    growth_b  = extra.get("growth_yoy")
    sim       = getattr(bench, "similarity_score", 0.0) if bench else 0.0
    src       = getattr(bench, "source", "—")           if bench else "—"

    # ── PDF ───────────────────────────────────────────────────────────────────
    class _PDF(FPDF):
        def normalize_text(self, text: str) -> str:  # type: ignore[override]
            return _clean(text)

    pdf = _PDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(18, 18, 18)

    def _header_bar(title: str):
        pdf.set_fill_color(*_BLUE)
        pdf.set_text_color(*_WHITE)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 9, f"  {title}", fill=True, ln=True)
        pdf.set_text_color(*_DARK)
        pdf.ln(3)

    def _row(label: str, value: str, alt: bool = False, color: tuple = None):
        pdf.set_font("Helvetica", "", 9)
        if alt:
            pdf.set_fill_color(*_LIGHT)
        else:
            pdf.set_fill_color(*_WHITE)
        pdf.set_text_color(*_GRAY)
        pdf.cell(72, 7, f"  {label}", fill=True)
        if color:
            pdf.set_text_color(*color)
        else:
            pdf.set_text_color(*_DARK)
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(0, 7, f"  {value}", fill=True, ln=True)
        pdf.set_text_color(*_DARK)

    def _cmp_row(metric, founder, sector_val, status, alt=False):
        pdf.set_font("Helvetica", "", 9)
        fill = _LIGHT if alt else _WHITE
        pdf.set_fill_color(*fill)
        pdf.set_text_color(*_DARK)
        pdf.cell(55, 7, f"  {metric}", fill=True)
        pdf.set_text_color(*_GRAY)
        pdf.cell(40, 7, f"  {founder}", fill=True)
        pdf.cell(40, 7, f"  {sector_val}", fill=True)
        c = _status_color(status)
        pdf.set_text_color(*c)
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(0, 7, f"  {status}", fill=True, ln=True)
        pdf.set_text_color(*_DARK)

    def _bullet(text: str):
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*_DARK)
        pdf.multi_cell(0, 6, f"  •  {text}", ln=True)
        pdf.ln(1)

    # ════════════════════════════════════════════════════════════════════════
    # PAGE 1 — COUVERTURE
    # ════════════════════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.set_fill_color(*_BLUE)
    pdf.rect(0, 0, 210, 60, "F")

    pdf.set_y(18)
    pdf.set_text_color(*_WHITE)
    pdf.set_font("Helvetica", "B", 28)
    pdf.cell(0, 12, "StartWise", ln=True, align="C")
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 8, "Rapport d'analyse financiere — CFO IA", ln=True, align="C")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, date_str, ln=True, align="C")

    pdf.set_y(70)
    pdf.set_text_color(*_DARK)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 9, "Contexte de la startup", ln=True)
    pdf.set_draw_color(*_BLUE)
    pdf.line(18, pdf.get_y(), 192, pdf.get_y())
    pdf.ln(4)

    info_rows = [
        ("Secteur", sector),
        ("Pays", pays),
        ("Phase detectee", str(getattr(phase, "value", phase)) if phase else "—"),
        ("Qualite des donnees", f"{score:.0%}"),
        ("Statut", "Valide" if is_valid else "Incomplet"),
        ("Source benchmarks", src),
        ("Similarite RAG", f"{sim:.0%}"),
    ]
    for i, (lbl, val) in enumerate(info_rows):
        _row(lbl, val, alt=(i % 2 == 0))

    # Données brutes résumé
    pdf.ln(6)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 9, "Donnees financieres fournies", ln=True)
    pdf.set_draw_color(*_BLUE)
    pdf.line(18, pdf.get_y(), 192, pdf.get_y())
    pdf.ln(4)

    raw_rows = [
        ("Burn Rate (depenses)", _fmt(burn, " DT/mois")),
        ("Cash Balance", _fmt(cash, " DT")),
        ("Revenue mensuel (MRR)", _fmt(mrr, " DT/mois")),
        ("Clients actifs", _fmt(n_cl)),
        ("Prix par client", _fmt(p_cl, " DT")),
        ("Churn mensuel", f"{churn:.1%}" if churn else "—"),
        ("Budget marketing", _fmt(mktg, " DT/mois")),
        ("Nouveaux clients/mois", _fmt(new_cl)),
        ("COGS par client", _fmt(cogs_val, " DT")),
    ]
    for i, (lbl, val) in enumerate(raw_rows):
        if val != "—":
            _row(lbl, val, alt=(i % 2 == 0))

    # ════════════════════════════════════════════════════════════════════════
    # PAGE 2 — KPIs CALCULÉS
    # ════════════════════════════════════════════════════════════════════════
    pdf.add_page()
    _header_bar("KPIs calcules par le moteur financier (calcul_tools)")

    kpi_data = [
        ("Runway", f"{runway:.1f} mois" if runway and not math.isinf(runway) else ("∞" if runway else "—"), run_alert or "OK"),
        ("Burn net mensuel", _fmt(burn_net, " DT/mois"), ""),
        ("MRR", _fmt(mrr, " DT"), ""),
        ("ARR", _fmt(arr, " DT"), ""),
        ("Gross Margin", f"{gm_pct:.1f}%" if gm_pct is not None else "—", gm_status),
        ("LTV", _fmt(ltv, " DT"), ""),
        ("CAC", _fmt(cac, " DT"), ""),
        ("LTV / CAC", f"{ltv_cac:.1f}x" if ltv_cac else "—", ltv_status),
        ("Breakeven", f"{breakeven:.1f} mois" if breakeven else "—", ""),
        ("ARPU (rev/client)", _fmt(arpu, " DT"), ""),
        ("Burn Multiple", f"{burn_multiple:.2f}x" if burn_multiple else "—", ""),
        ("Magic Number", f"{magic_number:.2f}" if magic_number else "—", ""),
        ("GRR estime", f"{grr:.1%}" if grr is not None else "—", ""),
    ]

    for i, (lbl, val, status) in enumerate(kpi_data):
        c = _status_color(status) if status else None
        _row(lbl, val, alt=(i % 2 == 0), color=c)

    if alertes:
        pdf.ln(5)
        _header_bar("Alertes calcul_tools")
        for a in alertes:
            lvl = "CRITIQUE" if "CRITIQUE" in a else ("ATTENTION" if "ATTENTION" in a else "INFO")
            pdf.set_text_color(*_status_color(lvl))
            pdf.set_font("Helvetica", "B", 8)
            pdf.cell(20, 6, f"  [{lvl}]")
            pdf.set_text_color(*_DARK)
            pdf.set_font("Helvetica", "", 8)
            clean = a.split(":", 1)[-1].strip() if ":" in a else a
            pdf.multi_cell(0, 6, clean, ln=True)

    # ════════════════════════════════════════════════════════════════════════
    # PAGE 3 — PROJECTIONS & MONTE CARLO
    # ════════════════════════════════════════════════════════════════════════
    pdf.add_page()
    _header_bar("Projections scenaristes (24 mois)")

    if scenarios:
        scen_rows = [
            ("Pessimiste", getattr(scenarios.pessimiste, "growth_rate", None),
             getattr(scenarios.pessimiste, "revenue_12m", None),
             getattr(scenarios.pessimiste, "cash_12m", None)),
            ("Realiste",   getattr(scenarios.realiste,   "growth_rate", None),
             getattr(scenarios.realiste,   "revenue_12m", None),
             getattr(scenarios.realiste,   "cash_12m", None)),
            ("Optimiste",  getattr(scenarios.optimiste,  "growth_rate", None),
             getattr(scenarios.optimiste,  "revenue_12m", None),
             getattr(scenarios.optimiste,  "cash_12m", None)),
        ]
        colors = [_RED, _BLUE, _GREEN]
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_fill_color(*_LIGHT)
        pdf.set_text_color(*_DARK)
        pdf.cell(50, 7, "  Scenario", fill=True)
        pdf.cell(40, 7, "  Croissance/mois", fill=True)
        pdf.cell(40, 7, "  Revenue 12 mois", fill=True)
        pdf.cell(0,  7, "  Cash 12 mois", fill=True, ln=True)
        for i, (name, gr, a12, a24) in enumerate(scen_rows):
            pdf.set_text_color(*colors[i])
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(50, 7, f"  {name}")
            pdf.set_text_color(*_DARK)
            pdf.set_font("Helvetica", "", 9)
            pdf.cell(40, 7, f"  {gr*100:.1f}%/mois" if gr else "  —")
            pdf.cell(40, 7, f"  {_fmt(a12)} DT" if a12 else "  —")
            pdf.cell(0,  7, f"  {_fmt(a24)} DT" if a24 else "  —", ln=True)
    else:
        pdf.set_font("Helvetica", "I", 10)
        pdf.cell(0, 8, "  Projections non disponibles (donnees insuffisantes).", ln=True)

    pdf.ln(6)
    _header_bar("Simulation Monte Carlo")

    if mc:
        p50 = getattr(mc, "p50", None)
        p10 = getattr(mc, "p10", None)
        p90 = getattr(mc, "p90", None)
        proba_surv = getattr(mc, "proba_survie_12m", None)
        proba_be   = getattr(mc, "proba_breakeven", None)
        n_sim      = getattr(mc, "n_simulations", None)
        growth_mu  = getattr(mc, "growth_mean_used", None)
        if p50 is not None:
            _row("Runway median (P50)", f"{p50} mois")
        if p10 is not None:
            _row("Runway pessimiste (P10)", f"{p10} mois", alt=True)
        if p90 is not None:
            _row("Runway optimiste (P90)", f"{p90} mois")
        if proba_surv is not None:
            _row("Probabilite survie 12 mois", f"{proba_surv:.0%}", alt=True,
                 color=_GREEN if proba_surv > 0.7 else _RED)
        if proba_be is not None:
            _row("Probabilite breakeven", f"{proba_be:.0%}",
                 color=_GREEN if proba_be > 0.5 else _ORANGE)
        if n_sim is not None:
            _row("Nb simulations", str(n_sim), alt=True)
        if growth_mu:
            _row("Taux croissance utilise", f"{growth_mu*100:.1f}%/mois")
    else:
        pdf.set_font("Helvetica", "I", 10)
        pdf.cell(0, 8, "  Monte Carlo non disponible.", ln=True)

    # ── Graphique trajectoires trésorerie ────────────────────────────────────
    if scenarios and cash is not None and burn is not None and rev is not None:
        traj_path = _chart_trajectories(scenarios, float(cash or 0), float(burn or 0), float(rev or 0))
        if traj_path:
            pdf.ln(4)
            _embed_chart(pdf, traj_path, caption="Trajectoires tresorerie 24 mois — scenarios pessimiste / realiste / optimiste")

    # ════════════════════════════════════════════════════════════════════════
    # PAGE 4 — ANALYSE SECTORIELLE (RAG)
    # ════════════════════════════════════════════════════════════════════════
    pdf.add_page()
    _header_bar(f"Positionnement sectoriel — {sector} | {src} | similarite {sim:.0%}")

    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(*_BLUE)
    pdf.set_text_color(*_WHITE)
    pdf.cell(55, 7, "  Metrique", fill=True)
    pdf.cell(40, 7, "  Votre valeur", fill=True)
    pdf.cell(40, 7, "  Mediane secteur", fill=True)
    pdf.cell(0,  7, "  Statut", fill=True, ln=True)
    pdf.set_text_color(*_DARK)

    def _cmp_status(f, b, higher_better=True):
        if f is None or b is None:
            return "—"
        gap = (f - b) / (abs(b) + 1e-9)
        if abs(gap) < 0.05:
            return "Aligne"
        return "Au-dessus" if (gap > 0) == higher_better else "En dessous"

    cmp_data = []
    if gm_med is not None:
        fv = f"{gm_pct:.1f}%" if gm_pct is not None else "—"
        st = _cmp_status(gm_pct / 100 if gm_pct else None, gm_med)
        cmp_data.append(("Gross Margin", fv, f"{gm_med:.1%}", st))
    if churn_med is not None and churn is not None:
        st = _cmp_status(churn, churn_med, higher_better=False)
        cmp_data.append(("Churn mensuel", f"{churn:.1%}", f"{churn_med:.1%}", st))
    if ltv_cac_b is not None:
        fv = f"{ltv_cac:.1f}x" if ltv_cac else "—"
        st = _cmp_status(ltv_cac, ltv_cac_b)
        cmp_data.append(("LTV / CAC", fv, f"{ltv_cac_b:.1f}x", st))
    if ev_mult and arr:
        val_ref = arr * ev_mult
        cmp_data.append(("EV/ARR Multiple", f"ARR {_fmt(arr)} DT",
                          f"{ev_mult:.1f}x → ~{_fmt(val_ref)} DT", "Reference"))
    if payback_b:
        cmp_data.append(("CAC Payback", "—", f"{payback_b:.0f} mois", "Reference"))
    if nrr_b:
        cmp_data.append(("NRR", "—", f"{nrr_b:.1f}%", "Reference"))
    if growth_b:
        cmp_data.append(("Croissance ARR YoY", "—", f"{growth_b:.0f}%", "Reference"))
    if burn_multiple is not None:
        cmp_data.append(("Burn Multiple", f"{burn_multiple:.2f}x",
                          "< 1.5x ideal", "SAIN" if burn_multiple < 1.5 else "ATTENTION"))
    if magic_number is not None:
        cmp_data.append(("Magic Number", f"{magic_number:.2f}",
                          "> 0.75 sain", "SAIN" if magic_number >= 0.75 else "ATTENTION"))
    if grr is not None:
        cmp_data.append(("GRR estime", f"{grr:.1%}", "> 85% SaaS B2B",
                          "SAIN" if grr >= 0.85 else "ATTENTION"))

    for i, (m, fv, bv, st) in enumerate(cmp_data):
        _cmp_row(m, fv, bv, st, alt=(i % 2 == 0))

    # Descriptions
    pdf.ln(5)
    _header_bar("Analyse detaillee par metrique")
    descriptions = {
        "Gross Margin": (
            "La marge brute mesure l'efficacite de creation de valeur avant les charges fixes. "
            "SaaS B2B cible : > 70%. Une GM elevee traduit une pricing power forte et une scalabilite "
            "sans cout variable proportionnel."
        ),
        "Churn mensuel": (
            "Le taux d'attrition mensuel determine la duree de vie client et amplifie ou reduit le LTV. "
            "SaaS B2B cible : < 1%/mois (< 12% annuel). Un churn eleve detruit la valeur cumulee "
            "et alourdit mecaniquement le CAC effectif."
        ),
        "LTV / CAC": (
            "Le ratio LTV/CAC mesure l'efficacite du capital investi en acquisition. "
            "Standard VC : > 3x. En dessous de 1x, le modele est economiquement deficitaire. "
            "Au-dessus de 5x, vous avez un levier pour accelerer l'acquisition."
        ),
        "Burn Multiple": (
            "Burn Multiple = Burn Net / Net New ARR. Mesure combien de cash est brule pour "
            "chaque DT de nouvel ARR genere. < 1x = tres efficace, 1-1.5x = bon, > 2x = attention."
        ),
        "Magic Number": (
            "Magic Number = (Net New ARR Q) / Depenses S&M Q. "
            "Mesure l'efficacite commerciale. > 0.75 = sain, > 1.5 = exceptionnel."
        ),
        "GRR estime": (
            "Gross Revenue Retention = revenus conserves sans expansion. "
            "Approxime depuis le churn. SaaS B2B sain : > 85%. "
            "Un GRR eleve implique que la base de revenus est stable avant tout upsell."
        ),
    }
    for key, desc in descriptions.items():
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*_BLUE)
        pdf.cell(0, 6, f"  {key}", ln=True)
        pdf.set_text_color(*_DARK)
        pdf.set_font("Helvetica", "", 8)
        pdf.multi_cell(0, 5, f"  {desc}", ln=True)
        pdf.ln(2)

    # ── Graphiques comparaison sectorielle ───────────────────────────────────
    bar_metrics: list[tuple] = []
    if gm_pct is not None and gm_med is not None:
        bar_metrics.append(("Gross Margin", round(gm_pct, 1), round(gm_med * 100, 1), "%"))
    if churn is not None and churn_med is not None:
        bar_metrics.append(("Churn mensuel", round(churn * 100, 2), round(churn_med * 100, 2), "%"))
    if ltv_cac is not None and ltv_cac_b is not None:
        bar_metrics.append(("LTV/CAC", round(ltv_cac, 2), round(ltv_cac_b, 2), "x"))

    if bar_metrics:
        bars_path = _chart_comparison_bars(bar_metrics)
        if bars_path:
            pdf.ln(3)
            _embed_chart(pdf, bars_path, caption="Metriques cles — startup vs mediane sectorielle")

    if gm_pct is not None and gm_med is not None:
        gm_path = _chart_gauge_gm(gm_pct, round(gm_med * 100, 1))
        if gm_path:
            pdf.ln(2)
            _embed_chart(pdf, gm_path, caption="Gross Margin — position vs benchmark secteur")

    if ltv_cac is not None:
        ltv_path = _chart_ltv_cac_gauge(ltv_cac)
        if ltv_path:
            pdf.ln(2)
            _embed_chart(pdf, ltv_path, caption="LTV/CAC — ratio actuel vs cible 3x")

    # ════════════════════════════════════════════════════════════════════════
    # PAGE 5 — RECOMMANDATIONS
    # ════════════════════════════════════════════════════════════════════════
    pdf.add_page()
    _header_bar("Plan d'action recommande")

    recs = []

    if run_alert == "CRITIQUE":
        recs.append(("[URGENT] Runway critique", _RED,
            f"Avec {runway:.1f} mois de runway, declenchez immediatement un plan de reduction du burn "
            "ou initiez une levee d'urgence (bridge note, prêt RBF). "
            "Chaque semaine compte."))
    elif run_alert == "ATTENTION":
        recs.append(("[PRIORITE] Runway serré", _ORANGE,
            f"Runway de {runway:.1f} mois. Preparez votre dossier de levee maintenant "
            "(data room, deck, pipeline investisseurs). Le processus prend 3-6 mois."))

    if churn is not None and churn_med is not None and churn > churn_med * 1.3:
        recs.append(("[RETENTION] Churn superieur au marche", _ORANGE,
            f"Churn {churn:.1%} vs mediane {churn_med:.1%}. "
            "Implementez un programme Customer Success : health scores, "
            "onboarding structure 30/60/90j, QBR trimestriels. "
            "Reduire le churn de moitie double generalement le LTV."))

    if gm_status == "CRITIQUE":
        recs.append(("[PRICING] Gross margin critique", _RED,
            f"GM de {gm_pct:.1f}% bien en dessous des 60% SaaS. "
            "Auditez vos couts variables (infra, support, livraison) et "
            "envisagez une revalorisation tarifaire ou migration vers abonnement annuel."))

    if ltv_status == "DANGEREUX":
        recs.append(("[UNIT ECONOMICS] LTV/CAC < 1", _RED,
            f"Ratio {ltv_cac:.1f}x — chaque client acquis est economiquement deficitaire. "
            "Coupez les canaux d'acquisition les moins efficaces, "
            "augmentez l'ARPU via upsell ou ciblez un segment a LTV plus elevee."))
    elif ltv_status == "LIMITE":
        recs.append(("[CROISSANCE] LTV/CAC sous-optimal", _ORANGE,
            f"Ratio {ltv_cac:.1f}x (cible > 3x). Privilegiez les canaux organiques "
            "(SEO, referral, communaute) pour reduire le CAC sans augmenter le budget."))

    if burn_multiple is not None and burn_multiple > 2:
        recs.append(("[EFFICACITE] Burn Multiple eleve", _ORANGE,
            f"Burn Multiple de {burn_multiple:.2f}x — vous brulez {burn_multiple:.1f} DT "
            "pour chaque DT de nouvel ARR. Cible SaaS efficace : < 1.5x. "
            "Reevaluez l'allocation du burn entre acquisition et infrastructure."))

    if ev_mult and arr:
        val_ref = arr * ev_mult
        recs.append(("[VALORISATION] Reference de marche", _BLUE,
            f"Au multiple sectoriel de {ev_mult:.1f}x ARR, votre valorisation indicative "
            f"est ~{_fmt(val_ref)} DT. Pour depasser ce multiple, "
            "ciblez une croissance ARR > mediane et un NRR > 110%."))

    if not recs:
        recs.append(("Bonne sante globale", _GREEN,
            "Vos metriques sont globalement dans la norme sectorielle. "
            "Focus : accelerer la croissance ARR et documenter le NRR "
            "pour acceder a des multiples de valorisation superieurs."))

    for title, color, desc in recs:
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*color)
        pdf.cell(0, 7, f"  {title}", ln=True)
        pdf.set_text_color(*_DARK)
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(0, 6, f"  {desc}", ln=True)
        pdf.ln(3)

    if inco:
        pdf.ln(3)
        _header_bar("Incoherences detectees dans les donnees")
        for ic in inco:
            _bullet(ic)

    # ── Pied de page ──────────────────────────────────────────────────────────
    pdf.set_y(-20)
    pdf.set_font("Helvetica", "I", 7)
    pdf.set_text_color(*_GRAY)
    pdf.cell(0, 5,
        f"StartWise CFO Agent — Rapport genere le {date_str} — "
        "Usage confidentiel. Valeurs indicatives basees sur les donnees fournies.",
        align="C", ln=True)

    return pdf.output()
