from typing import Any

from models.data_models import DataQuality, FinancialContext, ValidationResult


def _quality_to_score(value: Any) -> float:
    if isinstance(value, DataQuality):
        try:
            return float(value.value)
        except Exception:
            return 0.1

    if isinstance(value, str):
        key = value.strip().upper()
        mapping = {
            "REAL": 1.0,
            "ESTIMATED": 0.7,
            "ASSUMPTION": 0.4,
            "MISSING": 0.1,
        }
        return mapping.get(key, 0.1)

    return 0.1


def _empty_validation_result() -> ValidationResult:
    return ValidationResult(
        is_valid=False,
        data_quality_score=0.1,
        incoherences=[],
        missing_critical=["burn_rate manquant — calcul du runway impossible", "cash_balance manquant — calcul du runway impossible", "monthly_revenue manquant — calcul du breakeven impossible"],
        questions_to_ask=[
            "Quelles sont vos depenses totales par mois ? Incluez salaires, loyer, marketing, abonnements et tout autre cout fixe ou variable.",
            "Quel est votre solde bancaire disponible aujourd'hui ?",
            "Quel est votre chiffre d'affaires mensuel actuel ?",
            "Combien de clients actifs payants avez-vous actuellement ?",
            "Quel pourcentage de vos clients perdez-vous chaque mois en moyenne ?",
        ],
    )


def validate_financial_context(context: FinancialContext) -> ValidationResult:
    try:
        score = (
            _quality_to_score(context.burn_quality)
            + _quality_to_score(context.cash_quality)
            + _quality_to_score(context.revenue_quality)
        ) / 3.0

        incoherences: list[str] = []
        missing_critical: list[str] = []
        questions_to_ask: list[str] = []

        # Dépenses < revenus → startup rentable, PAS une incoherence
        # On pose juste une question de vérification dans questions_to_ask
        if (
            context.burn_rate is not None
            and context.monthly_revenue is not None
            and context.burn_rate < context.monthly_revenue
        ):
            questions_to_ask.append(
                "Vos revenus dépassent vos dépenses — avez-vous bien inclus tous vos coûts (salaires, loyer, infrastructure) ?"
            )

        if context.churn_rate is not None and context.churn_rate > 0.20:
            incoherences.append(
                "Churn mensuel supérieur à 20% — niveau critique, la startup perd plus d'un client sur cinq chaque mois"
            )

        if (
            context.prix_client is not None
            and context.n_clients is not None
            and context.monthly_revenue is not None
        ):
            expected_revenue = context.prix_client * context.n_clients
            if context.monthly_revenue != 0:
                relative_gap = abs(expected_revenue - context.monthly_revenue) / abs(context.monthly_revenue)
                if relative_gap > 0.20:
                    incoherences.append(
                        "Incohérence détectée : prix_client × n_clients ne correspond pas à monthly_revenue déclaré"
                    )

        # Runway critique — utilise le burn NET (dépenses - revenus), pas le burn brut
        if context.burn_rate is not None and context.cash_balance is not None:
            burn_net = max(0.0, context.burn_rate - (context.monthly_revenue or 0.0))
            if burn_net > 0 and context.cash_balance < burn_net:
                incoherences.append(
                    "Cash disponible inférieur au burn net mensuel — runway inférieur à 1 mois, situation critique"
                )

        # All required fields — analysis cannot proceed without them
        REQUIRED: list[tuple[str, str | None, str]] = [
            ("burn_rate",       context.burn_rate,       "burn_rate manquant — calcul du runway impossible"),
            ("cash_balance",    context.cash_balance,    "cash_balance manquant — calcul du runway impossible"),
            ("monthly_revenue", context.monthly_revenue, "monthly_revenue manquant — calcul du breakeven impossible"),
            ("n_clients",       context.n_clients,       "n_clients manquant — calcul du CAC et LTV impossible"),
            ("prix_client",     context.prix_client,     "prix_client manquant — vérification de cohérence revenue impossible"),
            ("churn_rate",      context.churn_rate,      "churn_rate manquant — calcul du LTV impossible"),
        ]

        for _, value, message in REQUIRED:
            if value is None:
                missing_critical.append(message)

        is_valid = len(missing_critical) == 0 and len(incoherences) == 0 and score >= 0.4

        return ValidationResult(
            is_valid=is_valid,
            data_quality_score=score,
            incoherences=incoherences,
            missing_critical=missing_critical,
            questions_to_ask=questions_to_ask,
        )
    except Exception:
        return _empty_validation_result()


if __name__ == "__main__":
    sample_context = FinancialContext(
        burn_rate=40000.0,
        cash_balance=120000.0,
        monthly_revenue=25000.0,
        n_clients=50,
        prix_client=500.0,
        churn_rate=0.06,
        marketing_budget=None,
        new_clients_month=None,
        cogs=None,
        months_data=6,
        secteur="SaaS",
        pays="TN",
        phase_hint=None,
        intent_fundraising=True,
        burn_quality=DataQuality.ESTIMATED,
        cash_quality=DataQuality.REAL,
        revenue_quality=DataQuality.ESTIMATED,
        hypotheses=[],
    )
    result = validate_financial_context(sample_context)
    print(result)
