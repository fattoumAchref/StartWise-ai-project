"""
Output formatter - structured data + LLM narrative recommendation.
"""

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from agents.investment.models import InvestmentRecommendation
from agents.investment.config import TOKENFACTORY_API_KEY, BASE_URL, MODEL_NAME


class OutputFormatter:
    """Formats final investment recommendation with LLM-generated narrative."""

    NEXT_STEPS = {
        "idea": [
            "Rejoindre un incubateur (Flat6Labs, Cogite, ou StartupHouse)",
            "Valider votre idée avec 20+ clients potentiels",
            "Postuler à la subvention Smart Capital Pre-Seed (50k TND)",
        ],
        "pre-seed": [
            "Obtenir le label Startup Act sur startup.gov.tn",
            "Pitcher auprès des business angels et family offices",
            "Construire le MVP et atteindre les 10 premiers clients payants",
        ],
        "seed": [
            "Obtenir le label Startup Act (si pas encore labellisé)",
            "Cibler les accélérateurs : Flat6Labs, Wamda, Sawari Ventures",
            "Préparer un pitch deck avec les métriques de traction",
        ],
        "early": [
            "Approcher les VCs seed : AfricInvest, BIAT Capital, Algebra Ventures",
            "Postuler à la subvention BTS Innovation si tech/export",
            "Préparer un modèle financier sur 18 mois pour la due diligence",
        ],
        "growth": [
            "Cibler les VCs Series A : Partech Africa, AfricInvest, Endeavor",
            "Explorer le financement par dette via BTS ou Amen Bank",
            "Considérer la subvention FAMEX pour l'expansion à l'export",
        ],
        "scale": [
            "Engager des fonds de growth equity et des VCs internationaux",
            "Explorer les partenariats stratégiques ou opportunités d'acquisition",
            "Se préparer à une éventuelle introduction en bourse",
        ],
    }

    def __init__(self):
        self.llm = ChatOpenAI(
            model=MODEL_NAME,
            base_url=BASE_URL,
            api_key=TOKENFACTORY_API_KEY,
            temperature=0.4,
            max_tokens=400,
        )

    def format(self, valuation, optimal_scenario, all_scenarios, dilution, data) -> InvestmentRecommendation:
        structured = self._build_structured(valuation, optimal_scenario, dilution, data)
        narrative  = self._generate_narrative(valuation, optimal_scenario, dilution, data)
        confidence = self._calculate_confidence(data, valuation)

        # Combine: narrative first, then structured data
        full_text = narrative + "\n\n" + structured

        return InvestmentRecommendation(
            recommendation=full_text,
            confidence_score=confidence,
            valuation=valuation,
            optimal_scenario=optimal_scenario,
            all_scenarios=all_scenarios,
            dilution=dilution,
        )

    def _generate_narrative(self, valuation, scenario, dilution, data) -> str:
        """LLM writes a personalized investment narrative."""
        try:
            stage   = data.get("stage", "seed")
            sector  = data.get("sector") or data.get("industry", "tech")
            grants  = data.get("available_grants", [])
            grants_total = sum(g.get("amount", 0) for g in grants)
            warnings = data.get("data_warnings", "")
            rationale = getattr(scenario, "rationale", "")

            prompt = ChatPromptTemplate.from_messages([
                ("system",
                 "Tu es un conseiller en investissement senior spécialisé dans les startups tunisiennes. "
                 "Rédige une analyse d'investissement concise et professionnelle en 3-4 phrases. "
                 "Mentionne la valorisation, le montant recommandé, l'impact sur la dilution et l'opportunité clé. "
                 "Sois direct et actionnable. La devise est le TND (Dinar Tunisien). "
                 "Écris en prose fluide, sans listes ni puces."),
                ("user",
                 "Stade: {stage} | Secteur: {sector}\n"
                 "Valorisation pre-money: {valuation} TND ({method})\n"
                 "Levée recommandée: {raise_amt} TND "
                 "(subventions: {grants} TND, equity: {equity} TND, dette: {debt} TND)\n"
                 "Dilution fondateurs: {dilution}% (ownership post-tour: {after}%)\n"
                 "Subventions disponibles: {grants_total} TND\n"
                 "Justification stratégie: {rationale}\n"
                 "Notes données: {warnings}")
            ])
            chain = prompt | self.llm
            response = chain.invoke({
                "stage":        stage,
                "sector":       sector,
                "valuation":    f"{valuation.final_valuation:,.0f}",
                "method":       valuation.method_used,
                "raise_amt":    f"{scenario.raise_amount:,.0f}",
                "grants":       f"{scenario.grants:,.0f}",
                "equity":       f"{scenario.equity:,.0f}",
                "debt":         f"{scenario.debt:,.0f}",
                "dilution":     f"{dilution.founder_dilution_pct:.1f}",
                "after":        f"{dilution.founder_after_pct:.1f}",
                "grants_total": f"{grants_total:,.0f}",
                "rationale":    rationale or "N/A",
                "warnings":     warnings or "None",
            })
            return "ANALYSIS\n" + "-"*55 + "\n" + response.content.strip()
        except Exception as e:
            return f"(narrative unavailable: {e})"

    def _build_structured(self, valuation, scenario, dilution, data) -> str:
        """Deterministic structured section — no LLM, always reliable."""
        sector = data.get("sector") or data.get("industry", "N/A")
        stage  = data.get("stage", "seed")

        sample_size = data.get("market_sample_size", 0)
        act_rate    = data.get("startup_act_rate")
        market_line = f"Données marché : {sample_size} startups {sector} similaires en Tunisie"
        if act_rate is not None:
            market_line += f" | Taux Startup Act: {act_rate*100:.0f}%"

        # Valuation breakdown — hide DCF for idea/pre-seed
        show_dcf = stage not in ("idea", "pre-seed")
        methods = []
        if valuation.revenue_multiple:
            methods.append(f"Revenue multiple: {valuation.revenue_multiple:,.0f} TND")
        if valuation.dcf and show_dcf:
            methods.append(f"DCF            : {valuation.dcf:,.0f} TND")
        if valuation.scorecard:
            methods.append(f"Scorecard      : {valuation.scorecard:,.0f} TND")
        methods_text = "\n  ".join(methods) if methods else "N/A"

        # Grants
        grants_list = data.get("available_grants", [])
        if grants_list:
            total_grants = sum(g.get("amount", 0) for g in grants_list)
            grants_text = "\n".join(f"  - {g['name']}: {g['amount']:,.0f} TND" for g in grants_list)
            grants_text += f"\n  Total potential: {total_grants:,.0f} TND"
        else:
            grants_text = "  - No matching grants found"

        # Strategy rationale from LLM (if available)
        rationale = getattr(scenario, "rationale", None)
        rationale_line = f"\n  Pourquoi: {rationale}" if rationale else ""

        # Data warnings from input handler
        warnings = data.get("data_warnings", "")
        warnings_line = f"\nDATA NOTES\n  {warnings}" if warnings and "No issues" not in warnings else ""

        # Next steps
        steps = self.NEXT_STEPS.get(stage, self.NEXT_STEPS["seed"])
        steps_text = "\n".join(f"{i+1}. {s}" for i, s in enumerate(steps))

        # Safe percentage helpers — avoid division by zero when raise_amount = 0
        # (cash-flow positive startup seeking 0 external funding)
        def _pct(part, total):
            return f"{part / total * 100:.0f}%" if total else "—"

        return f"""RECOMMANDATION D'INVESTISSEMENT
{'='*55}
Stade        : {stage.upper()}
Secteur      : {sector}
{market_line}

VALORISATION  ({valuation.method_used})
  {methods_text}
  >> Final: {valuation.final_valuation:,.0f} TND (pre-money)

STRATEGIE OPTIMALE  ({scenario.name.upper()})
  Levée totale : {scenario.raise_amount:,.0f} TND
  Subventions  : {scenario.grants:,.0f} TND  ({_pct(scenario.grants, scenario.raise_amount)})
  Equity       : {scenario.equity:,.0f} TND  ({_pct(scenario.equity, scenario.raise_amount)})
  Dette        : {scenario.debt:,.0f} TND  ({_pct(scenario.debt, scenario.raise_amount)})
  Post-money   : {scenario.post_money:,.0f} TND{rationale_line}

DILUTION
  Avant le tour : {dilution.founder_before_pct:.1f}%
  Après le tour : {dilution.founder_after_pct:.1f}%
  Dilué de      : {dilution.founder_dilution_pct:.1f}%  (incl. 10% option pool)

SUBVENTIONS ELIGIBLES
{grants_text}

PROCHAINES ETAPES
{steps_text}{warnings_line}""".strip()

    def _calculate_confidence(self, data: dict, valuation) -> float:
        confidence = 0.60
        if data.get("annual_revenue", 0) > 0:
            confidence += 0.10
        if valuation.method_used == "hybrid_dcf":
            confidence += 0.10
        elif valuation.method_used == "hybrid":
            confidence += 0.05
        if data.get("team_score", 0) >= 0.7:
            confidence += 0.05
        if data.get("market_score", 0) >= 0.7:
            confidence += 0.05
        if data.get("market_sample_size", 0) >= 10:
            confidence += 0.05
        return min(round(confidence, 2), 0.95)
