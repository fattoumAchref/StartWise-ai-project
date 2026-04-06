"""
PDF Report Generator for Investment Agent.
Uses reportlab — install with: pip install reportlab
"""

from io import BytesIO
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)


# ── Color palette ─────────────────────────────────────────────────────────────
PRIMARY   = colors.HexColor("#1B4F72")   # dark blue
ACCENT    = colors.HexColor("#2E86C1")   # medium blue
LIGHT_BG  = colors.HexColor("#EBF5FB")  # light blue bg
GREEN     = colors.HexColor("#1E8449")
ORANGE    = colors.HexColor("#D35400")
GRAY      = colors.HexColor("#717D7E")
WHITE     = colors.white


def generate_pdf(inv: dict, project_id: str, user_id: str) -> bytes:
    """
    Generate a PDF investment report.

    Args:
        inv        : investment result dict (from InvestmentRecommendation.to_dict())
        project_id : project identifier
        user_id    : user identifier

    Returns:
        PDF as bytes
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm,  bottomMargin=2*cm,
    )

    styles = getSampleStyleSheet()
    story  = []

    # ── Custom styles ─────────────────────────────────────────────────────────
    title_style = ParagraphStyle("Title",
        fontSize=22, textColor=PRIMARY, spaceAfter=4,
        fontName="Helvetica-Bold", leading=26)

    subtitle_style = ParagraphStyle("Subtitle",
        fontSize=11, textColor=GRAY, spaceAfter=12,
        fontName="Helvetica")

    section_style = ParagraphStyle("Section",
        fontSize=13, textColor=PRIMARY, spaceBefore=14, spaceAfter=6,
        fontName="Helvetica-Bold", borderPad=4)

    body_style = ParagraphStyle("Body",
        fontSize=10, textColor=colors.black, spaceAfter=6,
        fontName="Helvetica", leading=15)

    warning_style = ParagraphStyle("Warning",
        fontSize=10, textColor=ORANGE, spaceAfter=6,
        fontName="Helvetica-Oblique", leading=14)

    data  = inv.get("data", {})
    v     = data.get("valuation", {})
    s     = data.get("optimal_scenario", {})
    d     = data.get("dilution", {})
    stage = data.get("stage", "—").upper()
    sector= data.get("sector") or data.get("industry", "—")

    # ── Header ────────────────────────────────────────────────────────────────
    story.append(Paragraph("StartWise", title_style))
    story.append(Paragraph("Rapport d'Analyse d'Investissement", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=2, color=PRIMARY))
    story.append(Spacer(1, 0.3*cm))

    meta = [
        ["Projet", project_id],
        ["Utilisateur", user_id],
        ["Date", datetime.utcnow().strftime("%d/%m/%Y %H:%M UTC")],
        ["Stade", stage],
        ["Secteur", sector],
    ]
    meta_table = Table(meta, colWidths=[4*cm, 12*cm])
    meta_table.setStyle(TableStyle([
        ("FONTNAME",  (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTNAME",  (1,0), (1,-1), "Helvetica"),
        ("FONTSIZE",  (0,0), (-1,-1), 10),
        ("TEXTCOLOR", (0,0), (0,-1), PRIMARY),
        ("TEXTCOLOR", (1,0), (1,-1), colors.black),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 0.4*cm))

    # ── Narrative ─────────────────────────────────────────────────────────────
    narrative = inv.get("recommendation", "")
    if "INVESTMENT RECOMMENDATION" in narrative:
        narrative = narrative.split("INVESTMENT RECOMMENDATION")[0]
    narrative = narrative.replace("ANALYSIS", "").replace("-"*55, "").strip()

    if narrative and "unavailable" not in narrative:
        story.append(Paragraph("Analyse", section_style))
        story.append(HRFlowable(width="100%", thickness=0.5, color=ACCENT))
        story.append(Spacer(1, 0.2*cm))
        story.append(Paragraph(narrative, body_style))

    # ── Key metrics ───────────────────────────────────────────────────────────
    story.append(Paragraph("Chiffres Clés", section_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=ACCENT))
    story.append(Spacer(1, 0.2*cm))

    metrics = [
        ["Indicateur", "Valeur"],
        ["Valorisation pre-money", f"{v.get('final_valuation', 0):,.0f} TND  [{v.get('method', '')}]"],
        ["Levée recommandée",      f"{s.get('raise_amount', 0):,.0f} TND"],
        ["Dilution fondateurs",    f"{d.get('founder_dilution_pct', 0):.1f}%"],
        ["Score de confiance",     f"{inv.get('confidence_score', 0)*100:.0f}%"],
        ["Post-money",             f"{d.get('post_money', 0):,.0f} TND"],
    ]
    _add_table(story, metrics, col_widths=[8*cm, 8*cm], header=True)

    # ── Funding structure ─────────────────────────────────────────────────────
    story.append(Paragraph("Structure de la Levée", section_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=ACCENT))
    story.append(Spacer(1, 0.2*cm))

    raise_amt = s.get("raise_amount", 1)
    funding = [
        ["Composante", "Montant (TND)", "Part"],
        ["Subventions", f"{s.get('grants', 0):,.0f}", f"{s.get('grants',0)/raise_amt*100:.0f}%"],
        ["Equity",      f"{s.get('equity', 0):,.0f}", f"{s.get('equity',0)/raise_amt*100:.0f}%"],
        ["Dette",       f"{s.get('debt', 0):,.0f}",   f"{s.get('debt',0)/raise_amt*100:.0f}%"],
        ["TOTAL",       f"{raise_amt:,.0f}", "100%"],
    ]
    _add_table(story, funding, col_widths=[6*cm, 6*cm, 4*cm], header=True, total_row=True)

    # ── Valuation methods ─────────────────────────────────────────────────────
    story.append(Paragraph("Méthodes de Valorisation", section_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=ACCENT))
    story.append(Spacer(1, 0.2*cm))

    show_dcf = data.get("stage", "") not in ("idea", "pre-seed")
    val_rows = [["Méthode", "Valeur (TND)", "Utilisée"]]
    if v.get("revenue_multiple"):
        val_rows.append(["Revenue Multiple", f"{v['revenue_multiple']:,.0f}", "Oui"])
    if v.get("dcf"):
        val_rows.append(["DCF 5 ans", f"{v['dcf']:,.0f}", "Oui" if show_dcf else "Non (stade précoce)"])
    if v.get("scorecard"):
        val_rows.append(["Scorecard", f"{v['scorecard']:,.0f}", "Oui"])
    val_rows.append(["FINAL (pondéré)", f"{v.get('final_valuation',0):,.0f}", "—"])
    _add_table(story, val_rows, col_widths=[6*cm, 6*cm, 4*cm], header=True, total_row=True)

    # ── Scenarios ─────────────────────────────────────────────────────────────
    story.append(Paragraph("Scénarios de Levée", section_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=ACCENT))
    story.append(Spacer(1, 0.2*cm))

    sc_rows = [["Scénario", "Levée (TND)", "Dilution", "Score"]]
    for sc in sorted(data.get("all_scenarios", []), key=lambda x: x.get("score", 0), reverse=True):
        sc_rows.append([
            sc["name"].capitalize(),
            f"{sc['raise_amount']:,.0f}",
            f"{sc['dilution_pct']:.1f}%",
            f"{sc['score']:.0f}",
        ])
    _add_table(story, sc_rows, col_widths=[4*cm, 5*cm, 4*cm, 3*cm], header=True)

    # ── Dilution detail ───────────────────────────────────────────────────────
    story.append(Paragraph("Détail de la Dilution", section_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=ACCENT))
    story.append(Spacer(1, 0.2*cm))

    dil_rows = [
        ["Indicateur", "Valeur"],
        ["Ownership avant le tour",  f"{d.get('founder_before_pct', 0):.1f}%"],
        ["Ownership après le tour",  f"{d.get('founder_after_pct', 0):.1f}%"],
        ["Dilution totale",          f"{d.get('founder_dilution_pct', 0):.1f}%  (incl. 10% option pool)"],
        ["Part investisseur",        f"{d.get('new_investor_pct', 0):.1f}%"],
    ]
    _add_table(story, dil_rows, col_widths=[8*cm, 8*cm], header=True)

    # ── Grants ────────────────────────────────────────────────────────────────
    grants_list = data.get("available_grants", [])
    if grants_list:
        story.append(Paragraph("Subventions Eligibles", section_style))
        story.append(HRFlowable(width="100%", thickness=0.5, color=ACCENT))
        story.append(Spacer(1, 0.2*cm))
        g_rows = [["Programme", "Montant (TND)"]]
        for g in grants_list:
            g_rows.append([g["name"], f"{g['amount']:,.0f}"])
        total_g = sum(g["amount"] for g in grants_list)
        g_rows.append(["TOTAL", f"{total_g:,.0f}"])
        _add_table(story, g_rows, col_widths=[10*cm, 6*cm], header=True, total_row=True)

    # ── Rationale ─────────────────────────────────────────────────────────────
    rationale = s.get("rationale", "")
    if rationale and "unavailable" not in rationale:
        story.append(Paragraph("Justification de la Stratégie", section_style))
        story.append(HRFlowable(width="100%", thickness=0.5, color=ACCENT))
        story.append(Spacer(1, 0.2*cm))
        story.append(Paragraph(rationale, body_style))

    # ── Next steps ────────────────────────────────────────────────────────────
    full_rec = inv.get("recommendation", "")
    if "PROCHAINES ETAPES" in full_rec:
        story.append(Paragraph("Prochaines Etapes", section_style))
        story.append(HRFlowable(width="100%", thickness=0.5, color=ACCENT))
        story.append(Spacer(1, 0.2*cm))
        steps_block = full_rec.split("PROCHAINES ETAPES")[1].split("NOTES")[0].strip()
        for line in steps_block.splitlines():
            line = line.strip()
            if line:
                story.append(Paragraph(f"• {line}", body_style))

    # ── Data warnings ─────────────────────────────────────────────────────────
    warnings = data.get("data_warnings", "")
    if warnings and "No issues" not in warnings and "unavailable" not in warnings:
        story.append(Paragraph("Points d'Attention", section_style))
        story.append(HRFlowable(width="100%", thickness=0.5, color=ORANGE))
        story.append(Spacer(1, 0.2*cm))
        story.append(Paragraph(warnings, warning_style))

    # ── Progress report ───────────────────────────────────────────────────────
    progress = inv.get("progress_report", "")
    if progress and "unavailable" not in progress:
        story.append(Paragraph("Progression depuis la Derniere Session", section_style))
        story.append(HRFlowable(width="100%", thickness=0.5, color=ACCENT))
        story.append(Spacer(1, 0.2*cm))
        story.append(Paragraph(progress, body_style))

    # ── Footer ────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.5*cm))
    story.append(HRFlowable(width="100%", thickness=1, color=PRIMARY))
    story.append(Paragraph(
        f"Généré par StartWise Investment Agent — {datetime.utcnow().strftime('%d/%m/%Y')}",
        ParagraphStyle("Footer", fontSize=8, textColor=GRAY, alignment=1)
    ))

    doc.build(story)
    return buffer.getvalue()


def _add_table(story, rows, col_widths, header=True, total_row=False):
    """Helper to add a styled table."""
    t = Table(rows, colWidths=col_widths)
    style = [
        ("FONTSIZE",    (0,0), (-1,-1), 10),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("TOPPADDING",  (0,0), (-1,-1), 5),
        ("GRID",        (0,0), (-1,-1), 0.3, colors.HexColor("#BDC3C7")),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [WHITE, LIGHT_BG]),
    ]
    if header:
        style += [
            ("BACKGROUND",  (0,0), (-1,0), PRIMARY),
            ("TEXTCOLOR",   (0,0), (-1,0), WHITE),
            ("FONTNAME",    (0,0), (-1,0), "Helvetica-Bold"),
        ]
    if total_row:
        style += [
            ("BACKGROUND",  (0,-1), (-1,-1), colors.HexColor("#D6EAF8")),
            ("FONTNAME",    (0,-1), (-1,-1), "Helvetica-Bold"),
        ]
    t.setStyle(TableStyle(style))
    story.append(t)
    story.append(Spacer(1, 0.3*cm))
