"""
StartWise — Investment Agent UI
Run: streamlit run app.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

import streamlit as st
from datetime import datetime
from orchestrateur.orchestrator import Orchestrator

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="StartWise — Investment Agent",
    page_icon="💼",
    layout="wide",
)

st.title("💼 StartWise — Investment Agent")
st.caption("Analyse d'investissement pour startups tunisiennes")

# ── Sidebar — project identity ────────────────────────────────────────────────
with st.sidebar:
    st.header("Projet")
    project_id = st.text_input(
        "Project ID",
        value="my_startup",
        help="Utilisez un ID unique par startup pour un suivi mémoire correct. Ex: fintech_sme_2026"
    )
    user_id = st.text_input("User ID", value="user_001")
    st.divider()
    st.caption("Même Project ID = suivi de progression dans le temps.")
    st.caption("IDs différents = startups différentes, mémoires séparées.")

# ── Sample prompts ────────────────────────────────────────────────────────────
SAMPLES = {
    "— Choisir un exemple —": "",
    "Fintech — Pre-seed": (
        "I want to build a fintech platform for SME invoice financing in Tunisia.\n"
        "We already have 120,000 TND annual revenue with 80% growth.\n"
        "Monthly burn rate is 30,000 TND.\n"
        "We need 600,000 TND to fund 18 months of development.\n"
        "Team of 4 people (2 experienced founders + 2 developers).\n"
        "The SME financing market in Tunisia is around 8 billion TND."
    ),
    "Healthtech — Seed": (
        "Notre startup developpe une application de telemedicine pour les zones rurales en Tunisie.\n"
        "On a 280,000 TND de revenus annuels avec une croissance de 120%.\n"
        "Burn rate mensuel de 40,000 TND.\n"
        "On cherche 800,000 TND pour etendre notre couverture a 5 gouvernorats.\n"
        "Equipe de 5 personnes dont 2 medecins et 3 developpeurs.\n"
        "Le marche de la sante digitale en Tunisie est estime a 1.5 milliard TND."
    ),
    "Agritech — Idea stage": (
        "Je veux creer une plateforme qui connecte les agriculteurs tunisiens aux acheteurs en Europe.\n"
        "Pas encore de revenus, on est en phase de validation.\n"
        "Burn rate de 15,000 TND par mois.\n"
        "On a besoin de 300,000 TND pour construire le MVP.\n"
        "Equipe de 3 personnes.\n"
        "Le marche export agricole tunisien depasse 3 milliards TND par an."
    ),
    "SaaS — Growth": (
        "We built a B2B SaaS platform for HR management in North Africa.\n"
        "Annual revenue is 2,500,000 TND with 90% growth.\n"
        "Monthly burn rate is 120,000 TND.\n"
        "We are raising 3,000,000 TND for Series A.\n"
        "Team of 18 people including 3 experienced founders.\n"
        "The HR software market in North Africa is estimated at 12 billion TND."
    ),
    "Logistics — Scale": (
        "Notre plateforme logistique last-mile realise 3,500,000 TND de revenus annuels avec 70% de croissance.\n"
        "Burn rate mensuel de 200,000 TND.\n"
        "On leve 5,000,000 TND pour automatiser nos entrepots et lancer au Maroc.\n"
        "Equipe de 35 personnes dont 4 fondateurs experimentes.\n"
        "Le marche logistique e-commerce en Afrique du Nord depasse 20 milliards TND."
    ),
}

sample_choice = st.selectbox("Charger un exemple", list(SAMPLES.keys()))

# ── Text input ────────────────────────────────────────────────────────────────
default_text = SAMPLES[sample_choice] if sample_choice != "— Choisir un exemple —" else ""
project_text = st.text_area(
    "Description du projet startup",
    value=default_text,
    height=200,
    placeholder="Décrivez votre startup : secteur, revenus, burn rate, montant à lever, équipe, marché...",
)

run_btn = st.button("Analyser", type="primary", use_container_width=True)

# ── Run pipeline ──────────────────────────────────────────────────────────────
if run_btn:
    if not project_text.strip():
        st.warning("Veuillez entrer une description de projet.")
        st.stop()

    with st.spinner("Analyse en cours..."):
        try:
            orchestrator = Orchestrator()
            result = orchestrator.process(project_text, user_id=user_id, project_id=project_id)
        except Exception as e:
            st.error(f"Erreur pipeline : {e}")
            st.stop()

    inv  = result["investment"]
    data = inv["data"]
    v    = data["valuation"]
    s    = data["optimal_scenario"]
    d    = data["dilution"]

    # ── Narrative ─────────────────────────────────────────────────────────────
    st.divider()
    st.subheader("Analyse")
    narrative_lines = inv["recommendation"].split("RECOMMANDATION D'INVESTISSEMENT")[0]
    narrative_clean = narrative_lines.replace("ANALYSIS", "").replace("-"*55, "").strip()
    st.info(narrative_clean)

    # ── Key metrics ───────────────────────────────────────────────────────────
    st.subheader("Chiffres clés")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Valorisation pre-money", f"{v['final_valuation']:,.0f} TND", v["method"])
    col2.metric("Levée recommandée",      f"{s['raise_amount']:,.0f} TND")
    col3.metric("Dilution fondateurs",    f"{d['founder_dilution_pct']:.1f}%")
    col4.metric("Score de confiance",     f"{inv['confidence_score']*100:.0f}%")

    # ── Stage + sector ────────────────────────────────────────────────────────
    col_a, col_b = st.columns(2)
    col_a.metric("Stade", data.get("stage", "—").upper())
    col_b.metric("Secteur", data.get("sector") or data.get("industry", "—"))

    # ── Funding breakdown ─────────────────────────────────────────────────────
    st.subheader("Structure de la levée")
    col_g, col_e, col_d = st.columns(3)
    col_g.metric("Subventions", f"{s['grants']:,.0f} TND",
                 f"{s['grants']/s['raise_amount']*100:.0f}% de la levée")
    col_e.metric("Equity",      f"{s['equity']:,.0f} TND",
                 f"{s['equity']/s['raise_amount']*100:.0f}% de la levée")
    col_d.metric("Dette",       f"{s['debt']:,.0f} TND",
                 f"{s['debt']/s['raise_amount']*100:.0f}% de la levée")

    # ── Valuation methods ─────────────────────────────────────────────────────
    st.subheader("Méthodes de valorisation")
    show_dcf = data.get("stage") not in ("idea", "pre-seed")
    vm_col1, vm_col2, vm_col3 = st.columns(3)
    vm_col1.metric("Revenue Multiple", f"{v['revenue_multiple']:,.0f} TND" if v.get("revenue_multiple") else "N/A")
    vm_col2.metric("DCF 5 ans",        f"{v['dcf']:,.0f} TND" if (v.get("dcf") and show_dcf) else "Non utilisé (stade trop précoce)")
    vm_col3.metric("Scorecard",        f"{v['scorecard']:,.0f} TND" if v.get("scorecard") else "N/A")

    # ── Scenarios ─────────────────────────────────────────────────────────────
    st.subheader("Scénarios de levée")
    scenarios = data.get("all_scenarios", [])
    if scenarios:
        import pandas as pd
        df = pd.DataFrame([{
            "Scénario":  sc["name"].capitalize(),
            "Levée (TND)":    f"{sc['raise_amount']:,.0f}",
            "Dilution":       f"{sc['dilution_pct']:.1f}%",
            "Score":          sc["score"],
        } for sc in sorted(scenarios, key=lambda x: x["score"], reverse=True)])
        st.dataframe(df, use_container_width=True, hide_index=True)

    # ── Dilution detail ───────────────────────────────────────────────────────
    st.subheader("Dilution détaillée")
    d_col1, d_col2, d_col3 = st.columns(3)
    d_col1.metric("Avant le tour",  f"{d['founder_before_pct']:.1f}%")
    d_col2.metric("Après le tour",  f"{d['founder_after_pct']:.1f}%")
    d_col3.metric("Post-money",     f"{d['post_money']:,.0f} TND")

    # ── Grants ────────────────────────────────────────────────────────────────
    grants_list = data.get("available_grants", [])
    if grants_list:
        st.subheader("Subventions éligibles")
        for g in grants_list:
            st.success(f"**{g['name']}** — {g['amount']:,.0f} TND")

    # ── Strategy rationale ────────────────────────────────────────────────────
    rationale = s.get("rationale") or ""
    if rationale and "unavailable" not in rationale:
        st.subheader("Pourquoi ce scénario ?")
        st.write(rationale)

    # ── Data warnings ─────────────────────────────────────────────────────────
    warnings = data.get("data_warnings", "")
    if warnings and "No issues" not in warnings and "unavailable" not in warnings:
        st.subheader("Points d'attention")
        st.warning(warnings)

    # ── Next steps ────────────────────────────────────────────────────────────
    st.subheader("Prochaines étapes")
    full_rec = inv["recommendation"]
    if "PROCHAINES ETAPES" in full_rec:
        steps_block = full_rec.split("PROCHAINES ETAPES")[1].split("NOTES")[0].strip()
        for line in steps_block.strip().splitlines():
            line = line.strip()
            if line:
                st.markdown(f"- {line}")

    # ── Progress report ───────────────────────────────────────────────────────
    progress = inv.get("progress_report")
    if progress and "unavailable" not in progress:
        st.divider()
        st.subheader("Progression depuis la dernière session")
        # Warn if sectors differ (memory mixing different startups)
        from agents.investment.memory.store import get_project_history
        history = get_project_history(project_id)
        if len(history) >= 2:
            prev_sector = history[-2].get("sector", "")
            curr_sector = data.get("sector") or data.get("industry", "")
            if prev_sector and curr_sector and prev_sector != curr_sector:
                st.warning(
                    f"Attention : la session précédente concernait le secteur **{prev_sector}** "
                    f"et la session actuelle **{curr_sector}**. "
                    f"Changez le Project ID pour séparer ces deux startups."
                )
        st.info(progress)

    # ── Comparable transactions ───────────────────────────────────────────────
    comparables = data.get("comparable_deals", [])
    if comparables:
        st.divider()
        st.subheader("Transactions comparables en Tunisie")
        import pandas as pd
        df_comp = pd.DataFrame([{
            "Entreprise":  c["company"],
            "Secteur":     c["sector"],
            "Tour":        c["round_type"],
            "Montant (TND)": f"{c['amount_tnd']:,.0f}",
            "Investisseurs": c["investors"],
            "Date":        c["date"],
            "Similarité":  f"{c['similarity']}%",
        } for c in comparables])
        st.dataframe(df_comp, use_container_width=True, hide_index=True)
        st.caption("Source : données de financement tunisiennes (Kaggle). Montants convertis USD→TND.")

    # ── Investor matching ─────────────────────────────────────────────────────
    investors = data.get("matched_investors", [])
    if investors:
        st.divider()
        st.subheader("Investisseurs recommandés")
        for inv_item in investors:
            fit = inv_item.get("fit_score", 0)
            fit_color = "🟢" if fit >= 70 else "🟡" if fit >= 40 else "🔴"
            with st.expander(
                f"{fit_color} **{inv_item['name']}** — {inv_item['type'].replace('_',' ').title()} "
                f"| {inv_item['check_min']:,.0f}–{inv_item['check_max']:,.0f} TND "
                f"| Fit : {fit}/100"
            ):
                st.markdown(f"**Stades :** {', '.join(inv_item['stages'])}")
                st.markdown(f"**Secteurs :** {', '.join(inv_item['sectors'])}")
                st.markdown(f"**Note :** {inv_item['note']}")
                if inv_item.get("website") and inv_item["website"] != "N/A":
                    st.markdown(f"**Site :** {inv_item['website']}")

    # ── Term sheet ────────────────────────────────────────────────────────────
    term_sheet = data.get("term_sheet", "")
    if term_sheet and "unavailable" not in term_sheet:
        st.divider()
        with st.expander("📄 Term sheet (draft)"):
            st.markdown(term_sheet)
            import json as _json
            st.download_button(
                "Télécharger le term sheet",
                data=term_sheet,
                file_name=f"term_sheet_{project_id}_{datetime.now().strftime('%Y%m%d')}.txt",
                mime="text/plain",
                use_container_width=True,
            )

    # ── Multi-round dilution waterfall ────────────────────────────────────────
    multi_round = data.get("multi_round_dilution", [])
    if multi_round:
        st.divider()
        st.subheader("Dilution sur 3 tours de financement")
        import pandas as pd
        df_mr = pd.DataFrame([{
            "Tour":           r["round_name"],
            "Levée (TND)":    f"{r['raise_amount']:,.0f}",
            "Pre-money":      f"{r['pre_money']:,.0f}",
            "Post-money":     f"{r['post_money']:,.0f}",
            "Part investisseur": f"{r['investor_pct']:.1f}%",
            "Ownership fondateurs": f"{r['founder_pct']:.1f}%",
        } for r in multi_round])
        st.dataframe(df_mr, use_container_width=True, hide_index=True)
        # Visual ownership bar
        final_founder = multi_round[-1]["founder_pct"]
        st.caption(
            f"Après {len(multi_round)} tours : fondateurs = **{final_founder:.1f}%** "
            f"| investisseurs + pool = **{100 - final_founder:.1f}%**"
        )

    # ── Sensitivity analysis ──────────────────────────────────────────────────
    sensitivity = data.get("sensitivity", [])
    if sensitivity:
        st.divider()
        st.subheader("Analyse de sensibilité (±20% sur les hypothèses clés)")
        import pandas as pd
        df_sens = pd.DataFrame([{
            "Hypothèse":    s["assumption"],
            "Valeur base":  s["base_value"],
            "-20%":         f"{s['minus_20']:,.0f} TND",
            "Base":         f"{s['base']:,.0f} TND",
            "+20%":         f"{s['plus_20']:,.0f} TND",
            "Impact":       s["impact"].upper(),
            "Variation":    f"±{abs(s['plus_20'] - s['minus_20']) / s['base'] * 50:.0f}%",
        } for s in sensitivity])
        st.dataframe(df_sens, use_container_width=True, hide_index=True)
        st.caption("La variation montre l'amplitude de la fourchette de valorisation pour chaque hypothèse.")

    # ── Exit scenarios ────────────────────────────────────────────────────────
    exit_sc = data.get("exit_scenarios", [])
    if exit_sc:
        st.divider()
        st.subheader("Scénarios de sortie — Année 5")
        rev_y5 = exit_sc[0]["revenue_year5"] if exit_sc else 0
        st.caption(f"Revenus projetés en année 5 : **{rev_y5:,.0f} TND** (croissance décroissante)")
        ex_cols = st.columns(3)
        colors = {"Pessimiste": "🔴", "Realiste": "🟡", "Optimiste": "🟢"}
        for i, ex in enumerate(exit_sc):
            with ex_cols[i]:
                icon = colors.get(ex["name"], "⚪")
                st.metric(
                    f"{icon} {ex['name']}",
                    f"{ex['founder_proceeds']:,.0f} TND",
                    f"{ex['roi_multiple']:.1f}x ROI",
                )
                st.caption(
                    f"Multiple sortie : {ex['exit_multiple']}x\n"
                    f"Valeur entreprise : {ex['exit_valuation']:,.0f} TND"
                )

    # ── Raw recommendation (expandable) ──────────────────────────────────────
    with st.expander("Voir la recommandation complète (texte brut)"):
        st.text(inv["recommendation"])

    # ── PDF download ──────────────────────────────────────────────────────────
    st.divider()
    col_pdf, col_json = st.columns(2)

    with col_pdf:
        try:
            from utils.pdf_report import generate_pdf
            pdf_bytes = generate_pdf(inv, project_id, user_id)
            st.download_button(
                label="Télécharger le rapport PDF",
                data=pdf_bytes,
                file_name=f"startwise_{project_id}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                mime="application/pdf",
                use_container_width=True,
                type="primary",
            )
        except Exception as e:
            st.error(f"Erreur PDF : {type(e).__name__}: {e}")

    with col_json:
        import json
        a2a = inv.get("a2a_message", {})
        if a2a:
            st.download_button(
                label="Télécharger le message A2A (JSON)",
                data=json.dumps(a2a, indent=2, ensure_ascii=False),
                file_name=f"a2a_{project_id}_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
                mime="application/json",
                use_container_width=True,
            )
