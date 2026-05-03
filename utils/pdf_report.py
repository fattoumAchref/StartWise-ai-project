"""
PDF Report Generator — StartWise Investment Agent
Includes: core analysis + comparable deals + investor matching +
          term sheet + multi-round dilution + sensitivity + exit scenarios
"""

from io import BytesIO
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether,
)

# ── Palette ───────────────────────────────────────────────────────────────────
PRIMARY  = colors.HexColor("#0F172A")
ACCENT   = colors.HexColor("#2563EB")
GREEN    = colors.HexColor("#059669")
RED      = colors.HexColor("#DC2626")
ORANGE   = colors.HexColor("#D97706")
PURPLE   = colors.HexColor("#7C3AED")
LIGHT_BG = colors.HexColor("#F0F7FF")
GRAY     = colors.HexColor("#64748B")
LGRAY    = colors.HexColor("#F1F5F9")
WHITE    = colors.white


# ── Style factory ─────────────────────────────────────────────────────────────
def _s(name, **kw):
    defaults = dict(fontName="Helvetica", fontSize=10, leading=14,
                    textColor=colors.black, spaceAfter=4)
    defaults.update(kw)
    return ParagraphStyle(name, **defaults)

TITLE    = _s("T", fontSize=22, fontName="Helvetica-Bold", textColor=PRIMARY, leading=26, spaceAfter=2)
SUBTITLE = _s("ST", fontSize=11, textColor=GRAY, spaceAfter=10)
H1       = _s("H1", fontSize=13, fontName="Helvetica-Bold", textColor=PRIMARY, spaceBefore=16, spaceAfter=5)
H2       = _s("H2", fontSize=11, fontName="Helvetica-Bold", textColor=ACCENT, spaceBefore=10, spaceAfter=4)
BODY     = _s("B", fontSize=9.5, leading=14, spaceAfter=5)
SMALL    = _s("SM", fontSize=8.5, textColor=GRAY, leading=12)
WARN     = _s("W", fontSize=9.5, textColor=ORANGE, fontName="Helvetica-Oblique", leading=13)
FOOTER   = _s("F", fontSize=8, textColor=GRAY, alignment=1)


def generate_pdf(inv: dict, project_id: str, user_id: str) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm,  bottomMargin=2*cm,
    )

    data   = inv.get("data", {})
    v      = data.get("valuation", {})
    s      = data.get("optimal_scenario", {}) or {}
    d      = data.get("dilution", {}) or {}
    stage  = (data.get("stage") or "—").upper()
    sector = data.get("sector") or data.get("industry", "—")
    priority = d.get("priority") or data.get("priority", "OPTIMIZATION")

    story = []

    # ══════════════════════════════════════════════════════════════════════════
    # PAGE 1 — COVER + SUMMARY
    # ══════════════════════════════════════════════════════════════════════════
    story.append(Paragraph("StartWise", TITLE))
    story.append(Paragraph("Rapport d'Analyse d'Investissement", SUBTITLE))
    story.append(HRFlowable(width="100%", thickness=2, color=PRIMARY))
    story.append(Spacer(1, 0.3*cm))

    # Meta table
    meta = [
        ["Projet",      project_id],
        ["Utilisateur", user_id],
        ["Date",        datetime.utcnow().strftime("%d/%m/%Y %H:%M UTC")],
        ["Stade",       stage],
        ["Secteur",     sector],
        ["Priorite",    priority],
        ["Confiance",   f"{inv.get('confidence_score', 0)*100:.0f}%"],
    ]
    _tbl(story, meta, [4*cm, 12*cm], header=False)

    # Narrative
    narrative = inv.get("recommendation", "")
    for sep in ["RECOMMANDATION D INVESTISSEMENT", "RECOMMANDATION D'INVESTISSEMENT"]:
        if sep in narrative:
            narrative = narrative.split(sep)[0]
            break
    narrative = narrative.replace("ANALYSE", "").replace("-"*55, "").strip()
    if narrative and "unavailable" not in narrative:
        _section(story, "Analyse")
        story.append(Paragraph(narrative, BODY))

    # Key metrics
    _section(story, "Chiffres Cles")
    raise_amt = s.get("raise_amount", 1) or 1
    runway    = d.get("runway_months", s.get("runway_months", 0))
    metrics = [
        ["Indicateur",              "Valeur"],
        ["Valorisation pre-money",  f"{v.get('final_valuation',0):,.0f} TND  [{v.get('method','')}]"],
        ["Levee recommandee",       f"{raise_amt:,.0f} TND"],
        ["Cash existant",           f"{d.get('current_cash', 0):,.0f} TND"],
        ["Runway total",            f"{runway:.1f} mois" if runway and runway < 99 else "infini"],
        ["Dilution fondateurs",     f"{d.get('founder_dilution_pct',0):.1f}%"],
        ["Ownership apres tour",    f"{d.get('founder_after_pct',0):.1f}%"],
        ["Post-money",              f"{d.get('post_money',0):,.0f} TND"],
        ["Score de confiance",      f"{inv.get('confidence_score',0)*100:.0f}%"],
    ]
    _tbl(story, metrics, [8*cm, 8*cm])

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 2 — FUNDING STRUCTURE + VALUATION
    # ══════════════════════════════════════════════════════════════════════════
    _section(story, "Structure de la Levee")
    funding = [
        ["Composante", "Montant (TND)", "Part"],
        ["Subventions", f"{s.get('grants',0):,.0f}", f"{s.get('grants',0)/raise_amt*100:.0f}%"],
        ["Equity",      f"{s.get('equity',0):,.0f}", f"{s.get('equity',0)/raise_amt*100:.0f}%"],
        ["Dette",       f"{s.get('debt',0):,.0f}",   f"{s.get('debt',0)/raise_amt*100:.0f}%"],
        ["TOTAL",       f"{raise_amt:,.0f}",          "100%"],
    ]
    _tbl(story, funding, [6*cm, 6*cm, 4*cm], total_row=True)

    _section(story, "Methodes de Valorisation")
    show_dcf = (data.get("stage") or "") not in ("idea",)
    val_rows = [["Methode", "Valeur (TND)", "Utilisee"]]
    if v.get("revenue_multiple"):
        val_rows.append(["Revenue Multiple", f"{v['revenue_multiple']:,.0f}", "Oui"])
    if v.get("dcf"):
        val_rows.append(["DCF 5 ans", f"{v['dcf']:,.0f}", "Oui" if show_dcf else "Non (stade precoce)"])
    if v.get("scorecard"):
        val_rows.append(["Scorecard", f"{v['scorecard']:,.0f}", "Oui"])
    val_rows.append(["FINAL (pondere)", f"{v.get('final_valuation',0):,.0f}", "—"])
    _tbl(story, val_rows, [6*cm, 6*cm, 4*cm], total_row=True)

    _section(story, "Scenarios de Levee")
    sc_rows = [["Scenario", "Levee (TND)", "Dilution", "Runway", "Score"]]
    for sc in sorted(data.get("all_scenarios", []), key=lambda x: x.get("score",0), reverse=True):
        rw = sc.get("runway_months", 0)
        sc_rows.append([
            sc["name"].capitalize(),
            f"{sc['raise_amount']:,.0f}",
            f"{sc['dilution_pct']:.1f}%",
            f"{rw:.0f}m" if rw < 99 else "inf",
            f"{sc['score']:.0f}",
        ])
    _tbl(story, sc_rows, [4*cm, 4*cm, 3*cm, 3*cm, 2*cm])

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 3 — DILUTION + GRANTS + RATIONALE
    # ══════════════════════════════════════════════════════════════════════════
    _section(story, "Detail de la Dilution  [equity / (pre-money + equity)]")
    dil_rows = [
        ["Indicateur",           "Valeur"],
        ["Avant le tour",        f"{d.get('founder_before_pct',80):.1f}%"],
        ["Part investisseur",    f"{d.get('new_investor_pct',0):.1f}%"],
        ["Option pool",          f"{d.get('option_pool_pct',10):.0f}%"],
        ["Apres le tour",        f"{d.get('founder_after_pct',0):.1f}%"],
        ["Dilution totale",      f"{d.get('founder_dilution_pct',0):.1f}%"],
    ]
    _tbl(story, dil_rows, [8*cm, 8*cm])

    grants_list = data.get("available_grants", [])
    if grants_list:
        _section(story, "Subventions Eligibles")
        g_rows = [["Programme", "Montant (TND)"]]
        for g in grants_list:
            g_rows.append([g["name"], f"{g['amount']:,.0f}"])
        g_rows.append(["TOTAL", f"{sum(g['amount'] for g in grants_list):,.0f}"])
        _tbl(story, g_rows, [10*cm, 6*cm], total_row=True)

    rationale = s.get("rationale", "")
    if rationale and "unavailable" not in rationale:
        _section(story, "Justification de la Strategie")
        story.append(Paragraph(rationale, BODY))

    # Next steps
    full_rec = inv.get("recommendation", "")
    if "PROCHAINES ETAPES" in full_rec:
        _section(story, "Prochaines Etapes")
        steps_block = full_rec.split("PROCHAINES ETAPES")[1].split("NOTES")[0].strip()
        for line in steps_block.splitlines():
            line = line.strip()
            if line and not line.startswith("-"):
                story.append(Paragraph(f"• {line}", BODY))

    # ══════════════════════════════════════════════════════════════════════════
    # PAGE 2 — DEAL INTELLIGENCE
    # ══════════════════════════════════════════════════════════════════════════
    comparables = data.get("comparable_deals", [])
    investors   = data.get("matched_investors", [])
    term_sheet  = data.get("term_sheet", "")

    if comparables or investors or term_sheet:
        story.append(PageBreak())
        story.append(Paragraph("Intelligence Marche", TITLE))
        story.append(HRFlowable(width="100%", thickness=2, color=PRIMARY))
        story.append(Spacer(1, 0.3*cm))

    if comparables:
        _section(story, "Transactions Comparables en Tunisie")
        story.append(Paragraph(
            "Deals similaires identifies dans la base de donnees de financement tunisienne (Kaggle).",
            SMALL))
        story.append(Spacer(1, 0.2*cm))
        comp_rows = [["Entreprise", "Secteur", "Tour", "Montant (TND)", "Investisseurs", "Similarite"]]
        for c in comparables:
            investors_short = c["investors"][:35] + "..." if len(c["investors"]) > 35 else c["investors"]
            comp_rows.append([
                c["company"],
                c["sector"],
                c["round_type"],
                f"{c['amount_tnd']:,.0f}",
                investors_short,
                f"{c['similarity']}%",
            ])
        _tbl(story, comp_rows, [3*cm, 2.5*cm, 2*cm, 3*cm, 4.5*cm, 1.5*cm])

    if investors:
        _section(story, "Investisseurs Recommandes")
        story.append(Paragraph(
            "Classes par score de compatibilite (stage + secteur + taille du cheque).",
            SMALL))
        story.append(Spacer(1, 0.2*cm))
        inv_rows = [["Investisseur", "Type", "Cheque (TND)", "Stades", "Fit"]]
        for i in investors[:6]:
            inv_rows.append([
                i["name"],
                i["type"].replace("_", " ").title(),
                f"{i['check_min']:,.0f} - {i['check_max']:,.0f}",
                ", ".join(i["stages"]),
                f"{i['fit_score']}/100",
            ])
        _tbl(story, inv_rows, [4*cm, 3*cm, 4*cm, 3*cm, 2*cm])

        # Notes per investor
        story.append(Spacer(1, 0.2*cm))
        for i in investors[:4]:
            story.append(Paragraph(
                f"<b>{i['name']}</b> — {i['note']}",
                SMALL))

    if term_sheet and "unavailable" not in term_sheet:
        _section(story, "Term Sheet (Draft)")
        story.append(Paragraph(
            "Document indicatif. A faire valider par un avocat specialise en droit des societes tunisien.",
            WARN))
        story.append(Spacer(1, 0.2*cm))
        # Split term sheet into paragraphs
        for line in term_sheet.split("\n"):
            line = line.strip()
            if not line:
                story.append(Spacer(1, 0.15*cm))
            elif line.startswith("#") or line.isupper():
                story.append(Paragraph(line.lstrip("#").strip(), H2))
            else:
                story.append(Paragraph(line, BODY))

    # ══════════════════════════════════════════════════════════════════════════
    # PAGE 3 — ROBUSTNESS ANALYSIS
    # ══════════════════════════════════════════════════════════════════════════
    multi_round = data.get("multi_round_dilution", [])
    sensitivity = data.get("sensitivity", [])
    exit_sc     = data.get("exit_scenarios", [])

    if multi_round or sensitivity or exit_sc:
        story.append(PageBreak())
        story.append(Paragraph("Analyse de Robustesse", TITLE))
        story.append(HRFlowable(width="100%", thickness=2, color=PRIMARY))
        story.append(Spacer(1, 0.3*cm))

    if multi_round:
        _section(story, "Dilution sur 3 Tours de Financement")
        story.append(Paragraph(
            "Projection de l'ownership des fondateurs apres chaque tour successif.",
            SMALL))
        story.append(Spacer(1, 0.2*cm))
        mr_rows = [["Tour", "Levee (TND)", "Pre-money", "Post-money", "Part invest.", "Ownership fondateurs"]]
        for r in multi_round:
            mr_rows.append([
                r["round_name"],
                f"{r['raise_amount']:,.0f}",
                f"{r['pre_money']:,.0f}",
                f"{r['post_money']:,.0f}",
                f"{r['investor_pct']:.1f}%",
                f"{r['founder_pct']:.1f}%",
            ])
        _tbl(story, mr_rows, [3.5*cm, 2.5*cm, 2.5*cm, 2.5*cm, 2.5*cm, 3*cm])
        if multi_round:
            final = multi_round[-1]["founder_pct"]
            story.append(Paragraph(
                f"Apres {len(multi_round)} tours : fondateurs = {final:.1f}% | "
                f"investisseurs + pool = {100-final:.1f}%",
                SMALL))

    if sensitivity:
        _section(story, "Analyse de Sensibilite (+/-20% sur les hypotheses cles)")
        story.append(Paragraph(
            "Impact d'une variation de 20% sur chaque hypothese sur la valorisation finale.",
            SMALL))
        story.append(Spacer(1, 0.2*cm))
        sens_rows = [["Hypothese", "Valeur base", "-20% → Valorisation", "Base", "+20% → Valorisation", "Impact"]]
        for s_row in sensitivity:
            variation = abs(s_row["plus_20"] - s_row["minus_20"]) / s_row["base"] * 50 if s_row["base"] > 0 else 0
            sens_rows.append([
                s_row["assumption"],
                s_row["base_value"],
                f"{s_row['minus_20']:,.0f} TND",
                f"{s_row['base']:,.0f} TND",
                f"{s_row['plus_20']:,.0f} TND",
                f"{s_row['impact'].upper()} (±{variation:.0f}%)",
            ])
        _tbl(story, sens_rows, [3*cm, 2.5*cm, 3*cm, 3*cm, 3*cm, 2*cm])

    if exit_sc:
        _section(story, "Scenarios de Sortie — Annee 5")
        rev_y5 = exit_sc[0]["revenue_year5"] if exit_sc else 0
        story.append(Paragraph(
            f"Revenus projetes en annee 5 : {rev_y5:,.0f} TND (croissance decroissante).",
            SMALL))
        story.append(Spacer(1, 0.2*cm))
        exit_rows = [["Scenario", "Multiple sortie", "Valeur entreprise (TND)", "Part fondateurs (TND)", "ROI"]]
        for e in exit_sc:
            exit_rows.append([
                e["name"],
                f"{e['exit_multiple']}x",
                f"{e['exit_valuation']:,.0f}",
                f"{e['founder_proceeds']:,.0f}",
                f"{e['roi_multiple']:.1f}x",
            ])
        _tbl(story, exit_rows, [3*cm, 3*cm, 4*cm, 4*cm, 2*cm])
        story.append(Paragraph(
            "Le ROI est calcule par rapport a la valorisation pre-money actuelle.",
            SMALL))

    # ══════════════════════════════════════════════════════════════════════════
    # WARNINGS + FOOTER
    # ══════════════════════════════════════════════════════════════════════════
    warnings = data.get("data_warnings", "")
    if warnings and "No issues" not in warnings and "unavailable" not in warnings:
        _section(story, "Points d'Attention", color=ORANGE)
        story.append(Paragraph(warnings, WARN))

    story.append(Spacer(1, 0.5*cm))
    story.append(HRFlowable(width="100%", thickness=1, color=PRIMARY))
    story.append(Paragraph(
        f"Genere par StartWise Investment Agent — {datetime.utcnow().strftime('%d/%m/%Y')} — "
        f"Document confidentiel. Ne pas diffuser sans autorisation.",
        FOOTER,
    ))

    doc.build(story)
    return buffer.getvalue()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _section(story, title: str, color=ACCENT):
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph(title, H1))
    story.append(HRFlowable(width="100%", thickness=0.5, color=color))
    story.append(Spacer(1, 0.2*cm))


def _tbl(story, rows, col_widths, header=True, total_row=False):
    t = Table(rows, colWidths=col_widths, repeatRows=1 if header else 0)
    style = [
        ("FONTSIZE",      (0,0), (-1,-1), 9),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("TOPPADDING",    (0,0), (-1,-1), 4),
        ("GRID",          (0,0), (-1,-1), 0.3, colors.HexColor("#CBD5E1")),
        ("ROWBACKGROUNDS",(0,1), (-1,-1), [WHITE, LGRAY]),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
    ]
    if header:
        style += [
            ("BACKGROUND", (0,0), (-1,0), PRIMARY),
            ("TEXTCOLOR",  (0,0), (-1,0), WHITE),
            ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE",   (0,0), (-1,0), 9),
        ]
    if total_row:
        style += [
            ("BACKGROUND", (0,-1), (-1,-1), colors.HexColor("#DBEAFE")),
            ("FONTNAME",   (0,-1), (-1,-1), "Helvetica-Bold"),
        ]
    t.setStyle(TableStyle(style))
    story.append(t)
    story.append(Spacer(1, 0.25*cm))
