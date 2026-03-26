from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


# ─────────────────────────────────────────
# ENUMS
# ─────────────────────────────────────────

class DataQuality(Enum):
    """Niveau de fiabilité d'une donnée fournie par l'entrepreneur."""
    REAL       = 1.0   # relevé bancaire, export Stripe, facture
    ESTIMATED  = 0.7   # "environ", "à peu près"
    ASSUMPTION = 0.4   # "je pense que", "j'espère"
    MISSING    = 0.1   # absent — valeur par défaut utilisée


class Phase(Enum):
    """Phase de maturité de la startup."""
    SEED         = "seed"          # 0 revenu ou < 6 mois data
    TRACTION     = "traction"      # revenus réguliers, 6m+ data
    FUNDRAISING  = "fundraising"   # cherche investisseurs
    SEED_RAISING = "seed+fundraising"  # seed mais cherche à lever


class AlertLevel(Enum):
    """Niveau de gravité d'une alerte."""
    INFO     = "INFO"
    ATTENTION = "ATTENTION"
    CRITIQUE = "CRITIQUE"


# ─────────────────────────────────────────
# INPUT — ce que l'entrepreneur fournit
# ─────────────────────────────────────────

@dataclass
class FinancialContext:
    """
    Représente toutes les données financières extraites
    depuis le message de l'entrepreneur.
    Produit par : extract_financials
    Consommé par : tous les outils
    """

    # ── Données financières ──
    burn_rate:          Optional[float] = None  # dépenses totales/mois
    cash_balance:       Optional[float] = None  # cash disponible aujourd'hui
    monthly_revenue:    Optional[float] = None  # revenus/mois
    n_clients:          Optional[int]   = None  # clients actifs
    prix_client:        Optional[float] = None  # revenu mensuel par client
    churn_rate:         Optional[float] = None  # % clients perdus/mois (0.05 = 5%)
    marketing_budget:   Optional[float] = None  # budget acquisition/mois
    new_clients_month:  Optional[int]   = None  # nouveaux clients/mois
    cogs:               Optional[float] = None  # coût variable par client/mois
    months_data:        int             = 0     # mois d'historique disponibles

    # ── Contexte startup ──
    secteur:            str             = "unknown"
    pays:               str             = "TN"
    phase_hint:         str             = "unknown"  # ce que le LLM a détecté
    intent_fundraising: bool            = False      # mentionne une levée ?

    # ── Qualité de chaque donnée clé ──
    burn_quality:       DataQuality     = DataQuality.MISSING
    cash_quality:       DataQuality     = DataQuality.MISSING
    revenue_quality:    DataQuality     = DataQuality.MISSING

    # ── Hypothèses détectées par le LLM ──
    hypotheses:         list            = field(default_factory=list)
    # ex: ["croissance x2/mois", "levée dans 3 mois"]


# ─────────────────────────────────────────
# OUTPUTS des outils Personne A
# ─────────────────────────────────────────

@dataclass
class KPIResult:
    """
    Résultat de calculate_kpis.
    Produit par : calculate_kpis
    Consommé par : run_monte_carlo, build_a2a_message, LLM
    """

    # Burn
    burn_net:               float            # dépenses - revenus
    burn_rate_raw:          float            # dépenses brutes

    # Runway
    runway_months:          Optional[float]  # mois avant cash-out
    runway_weeks:           Optional[float]  # idem en semaines
    cash_out_alert:         str              # "CRITIQUE"|"ATTENTION"|"OK"|"INCONNU"

    # CAC
    cac:                    Optional[float]  # coût acquisition client
    cac_quality:            str              # "calculé"|"estimé"|"non disponible"

    # LTV
    ltv:                    Optional[float]  # valeur vie client
    ltv_cac_ratio:          Optional[float]  # doit être > 3
    ltv_cac_status:         str              # "SAIN"|"LIMITE"|"DANGEREUX"|"N/A"

    # Breakeven
    breakeven_clients:      Optional[int]    # nb clients pour couvrir charges
    breakeven_months:       Optional[float]  # mois pour atteindre breakeven
    breakeven_reachable:    Optional[bool]   # atteignable avant cash-out ?

    # Marges
    gross_margin_pct:       Optional[float]  # marge brute %
    gross_margin_status:    str              # "SAIN"|"FAIBLE"|"CRITIQUE"|"N/A"

    # MRR / ARR
    mrr:                    Optional[float]  # Monthly Recurring Revenue
    arr:                    Optional[float]  # Annual Recurring Revenue

    # Alertes
    alertes:                list             = field(default_factory=list)


@dataclass
class MonteCarloResult:
    """
    Résultat de run_monte_carlo.
    Produit par : run_monte_carlo
    Consommé par : compute_confidence_score, build_a2a_message, LLM
    """
    p10:                int    # runway mois — scénario pessimiste (10%)
    p50:                int    # runway mois — scénario médian (50%)
    p90:                int    # runway mois — scénario optimiste (90%)
    proba_survie_12m:   float  # probabilité de survivre 12 mois [0-1]
    proba_breakeven:    float  # probabilité d'atteindre breakeven [0-1]
    mc_tightness:       float  # 1=serré (fiable) · 0=large (incertain) [0-1]
    n_simulations:      int    = 1000
    growth_mean_used:   float  = 0.0   # taux de croissance mensuel moyen utilisé dans la simulation


@dataclass
class ValidationResult:
    """
    Résultat de validate_inputs.
    Produit par : validate_inputs
    Consommé par : boucle ReAct
    """
    is_valid:             bool   # peut-on continuer ?
    data_quality_score:   float  # moyenne qualité données [0-1]
    incoherences:         list   = field(default_factory=list)
    missing_critical:     list   = field(default_factory=list)
    questions_to_ask:     list   = field(default_factory=list)
    # questions_to_ask : ce que l'agent doit demander à l'entrepreneur


@dataclass
class BenchmarkResult:
    """
    Résultat de fetch_benchmarks.
    Produit par : fetch_benchmarks
    Consommé par : run_monte_carlo, LLM, Scenario Comparator
    """
    cac_median:             Optional[float] = None
    ltv_median:             Optional[float] = None
    churn_median:           Optional[float] = None
    gross_margin_median:    Optional[float] = None
    valorisation_multiple:  Optional[float] = None  # ex: 4.2x ARR
    source:                 str             = "unknown"
    similarity_score:       float           = 0.0   # score Chroma [0-1]
    documents_raw:          list            = field(default_factory=list)


@dataclass
class ConfidenceResult:
    """
    Résultat de compute_confidence_score.
    Produit par : compute_confidence_score (Personne A)
    Consommé par : build_a2a_message, moteur de fusion
    """
    score:          float   # score final [0.0 - 1.0]
    # Détail des 3 composantes
    data_quality:   float   # contribution DQ  (×0.40)
    mc_tightness:   float   # contribution MC  (×0.35)
    llm_consistency: float  # contribution LLC (×0.25)
    # Interprétation
    niveau:         str     # "ÉLEVÉ"|"MOYEN"|"FAIBLE"
    interpretation: str     # phrase lisible pour l'entrepreneur


# ─────────────────────────────────────────
# MESSAGE A2A — ce qui part sur le bus
# ─────────────────────────────────────────

@dataclass
class A2AMessage:
    """
    Message envoyé sur le bus A2A vers les autres agents.
    Produit par : build_a2a_message
    Consommé par : Risk Agent, Investment Agent, Orchestrateur
    """
    # Identité
    message_id:     str             # UUID unique
    timestamp:      str             # ISO 8601
    from_agent:     str             = "finance_agent"
    to_agents:      list            = field(default_factory=lambda: [
                                        "risk_agent",
                                        "investment_agent",
                                        "orchestrator"
                                    ])

    # Contexte
    phase:          str             = "unknown"
    secteur:        str             = "unknown"
    pays:           str             = "TN"

    # Résultats
    kpis:           Optional[KPIResult]         = None
    monte_carlo:    Optional[MonteCarloResult]   = None
    benchmarks:     Optional[BenchmarkResult]    = None
    confidence:     Optional[ConfidenceResult]   = None

    # Alertes consolidées
    alertes:        list            = field(default_factory=list)

    # Comportement
    requires_reply: bool            = False
    # True si l'agent attend une réponse avant de répondre à l'entrepreneur


# ─────────────────────────────────────────
# TEST RAPIDE
# python models/data_models.py
# ─────────────────────────────────────────

if __name__ == "__main__":
    print("Test instanciation FinancialContext...")
    ctx = FinancialContext(
        burn_rate       = 12000,
        cash_balance    = 80000,
        monthly_revenue = 750,
        n_clients       = 15,
        prix_client     = 50,
        secteur         = "food_delivery",
        pays            = "TN",
        burn_quality    = DataQuality.ESTIMATED,
        cash_quality    = DataQuality.REAL,
        revenue_quality = DataQuality.REAL,
        hypotheses      = ["croissance x2/mois"]
    )
    print(f"  burn_rate        : {ctx.burn_rate}")
    print(f"  cash_quality     : {ctx.cash_quality}")
    print(f"  cash_quality val : {ctx.cash_quality.value}")
    print(f"  data_quality_score (manual) : "
          f"{round((ctx.burn_quality.value + ctx.cash_quality.value + ctx.revenue_quality.value)/3, 2)}")

    print()
    print("Test Phase enum...")
    p = Phase.SEED
    print(f"  Phase : {p.value}")

    print()
    print("Test A2AMessage...")
    import uuid
    from datetime import datetime
    msg = A2AMessage(
        message_id = str(uuid.uuid4()),
        timestamp  = datetime.utcnow().isoformat(),
        phase      = Phase.SEED.value,
        secteur    = "food_delivery",
    )
    print(f"  message_id : {msg.message_id}")
    print(f"  to_agents  : {msg.to_agents}")
    print(f"  requires_reply : {msg.requires_reply}")

    print()
    print("Tous les modèles OK.")