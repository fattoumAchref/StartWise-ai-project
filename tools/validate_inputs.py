# tools/validate_inputs.py - Validation et qualité des données
# Aucun LLM ici — logique Python pure

from models.data_models import (
    FinancialContext,
    ValidationResult,
    DataQuality,
)


# ─────────────────────────────────────────
# CHAMPS CRITIQUES — sans eux on ne peut rien calculer
# ─────────────────────────────────────────

CRITICAL_FIELDS = {
    "burn_rate":    "burn_rate absent — impossible de calculer burn net et runway",
    "cash_balance": "cash_balance absent — impossible de calculer runway",
}

# Champs importants mais pas bloquants
IMPORTANT_FIELDS = {
    "monthly_revenue":   "monthly_revenue absent — burn net surestimé",
    "n_clients":         "n_clients absent — CAC et LTV non calculables",
    "prix_client":       "prix_client absent — LTV et breakeven non calculables",
    "churn_rate":        "churn_rate absent — LTV estimé avec benchmark 5%",
    "marketing_budget":  "marketing_budget absent — CAC estimé à 20% du burn",
    "new_clients_month": "new_clients_month absent — breakeven en mois non calculable",
}


def validate_inputs(context: FinancialContext) -> ValidationResult:
    """
    Vérifie la cohérence et la qualité des données du FinancialContext.
    Produit un data_quality_score et une liste d'incohérences.

    Règles :
    - Champs critiques manquants → is_valid = False
    - Incohérences détectées     → is_valid = False
    - Champs importants manquants → alertes mais is_valid = True
    - data_quality_score = moyenne des qualités des 3 champs principaux

    Exemple :
        ctx = FinancialContext(burn_rate=12000, cash_balance=80000,
                               monthly_revenue=750,
                               burn_quality=DataQuality.ESTIMATED,
                               cash_quality=DataQuality.REAL,
                               revenue_quality=DataQuality.REAL)
        r = validate_inputs(ctx)
        # r.is_valid            → True
        # r.data_quality_score  → 0.9
        # r.incoherences        → []
    """

    incoherences    = []
    missing_critical = []
    missing_important = []
    questions_to_ask = []

    # ── 1. CHAMPS CRITIQUES ──────────────────────────────────
    for field, msg in CRITICAL_FIELDS.items():
        if getattr(context, field) is None:
            missing_critical.append(msg)
            questions_to_ask.append(_question_for(field))

    # ── 2. CHAMPS IMPORTANTS ─────────────────────────────────
    for field, msg in IMPORTANT_FIELDS.items():
        if getattr(context, field) is None:
            missing_important.append(msg)
            # On pose la question seulement pour les plus importants
            if field in ("monthly_revenue", "n_clients", "prix_client"):
                questions_to_ask.append(_question_for(field))

    # ── 3. INCOHÉRENCES LOGIQUES ─────────────────────────────

    burn  = context.burn_rate
    cash  = context.cash_balance
    rev   = context.monthly_revenue
    price = context.prix_client
    n_cli = context.n_clients
    churn = context.churn_rate

    # 3a. Revenue implicite vs déclaré
    # Si on connaît prix et n_clients, le revenue doit être cohérent
    if price is not None and n_cli is not None and rev is not None:
        revenue_implicite = price * n_cli
        ecart = abs(revenue_implicite - rev)
        tolerance = max(revenue_implicite * 0.15, 50)  # 15% de tolérance
        if ecart > tolerance:
            incoherences.append(
                f"Revenue incohérent : {n_cli} clients × {price} = {revenue_implicite} "
                f"mais monthly_revenue déclaré = {rev} "
                f"(écart de {round(ecart)} — tolérance {round(tolerance)})"
            )
            questions_to_ask.append(
                f"Vous avez {n_cli} clients à {price}/mois soit {revenue_implicite} "
                f"mais vous déclarez {rev} de revenus. Pouvez-vous clarifier ?"
            )

    # 3b. Burn rate vs dépenses listées (si disponibles)
    # On ne peut pas vérifier ici car les dépenses détaillées
    # ne sont pas dans FinancialContext — on signale juste si burn = 0
    if burn is not None and burn == 0 and rev is not None and rev == 0:
        incoherences.append(
            "burn_rate=0 ET monthly_revenue=0 — "
            "la startup ne dépense et ne gagne rien, données suspectes"
        )

    # 3c. Churn impossible
    if churn is not None and (churn < 0 or churn > 1):
        incoherences.append(
            f"churn_rate={churn} invalide — "
            "doit être entre 0 et 1 (ex: 0.05 pour 5%/mois)"
        )
        questions_to_ask.append(
            f"Le taux de churn {churn} semble invalide. "
            "Entrez une valeur entre 0 et 1 (ex: 0.05 pour 5%/mois)"
        )

    # 3d. Prix client négatif
    if price is not None and price <= 0:
        incoherences.append(
            f"prix_client={price} invalide — doit être positif"
        )

    # 3e. Burn > cash × 6 → runway très court, on avertit
    if burn is not None and cash is not None and burn > 0:
        runway_brut = cash / burn
        if runway_brut < 1:
            incoherences.append(
                f"Moins d'1 mois de runway brut "
                f"(cash={cash} / burn={burn} = {round(runway_brut, 1)} mois) — "
                "vérifiez les chiffres"
            )

    # 3f. Revenue > burn sans être en phase profitable déclarée
    if rev is not None and burn is not None and rev > burn * 2:
        incoherences.append(
            f"Revenue ({rev}) > 2× burn ({burn}) — "
            "startup très profitable, vérifiez que le burn inclut bien tous les coûts"
        )

    # ── 4. DATA QUALITY SCORE ────────────────────────────────
    # Moyenne des qualités des 3 champs principaux
    qualities = [
        context.burn_quality.value,
        context.cash_quality.value,
        context.revenue_quality.value,
    ]
    data_quality_score = round(sum(qualities) / len(qualities), 3)

    # ── 5. DÉCISION is_valid ─────────────────────────────────
    # Bloquant si : champs critiques manquants OU incohérences détectées
    is_valid = len(missing_critical) == 0 and len(incoherences) == 0

    # Dédupliquer les questions
    questions_to_ask = list(dict.fromkeys(questions_to_ask))

    return ValidationResult(
        is_valid           = is_valid,
        data_quality_score = data_quality_score,
        incoherences       = incoherences,
        missing_critical   = missing_critical + missing_important,
        questions_to_ask   = questions_to_ask,
    )


def _question_for(field: str) -> str:
    """Génère une question claire pour l'entrepreneur."""
    questions = {
        "burn_rate":         "Quel est votre total de dépenses mensuelles (loyer, salaires, marketing, etc.) ?",
        "cash_balance":      "Quel est le montant total de cash disponible sur votre compte bancaire aujourd'hui ?",
        "monthly_revenue":   "Quel est votre revenu total du dernier mois ?",
        "n_clients":         "Combien de clients payants avez-vous actuellement ?",
        "prix_client":       "Quel est le montant moyen payé par chaque client par mois ?",
        "churn_rate":        "Quel pourcentage de vos clients partent chaque mois ? (ex: 5 pour 5%)",
        "marketing_budget":  "Combien dépensez-vous en marketing et acquisition client par mois ?",
        "new_clients_month": "Combien de nouveaux clients gagnez-vous par mois en moyenne ?",
    }
    return questions.get(field, f"Pouvez-vous préciser la valeur de {field} ?")