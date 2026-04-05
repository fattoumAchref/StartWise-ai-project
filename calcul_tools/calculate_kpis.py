# tools/calculate_kpis.py — Calculs déterministes purs
# Aucun LLM ici — uniquement des maths Python

from models.data_models import FinancialContext, KPIResult, DataQuality

# Gross margin thresholds per sector: (healthy_min_pct, warning_min_pct)
# Below warning_min → CRITIQUE ; between warning and healthy → FAIBLE ; above healthy → SAIN
_GROSS_MARGIN_THRESHOLDS: dict = {
    "saas":          (60, 40),
    "marketplace":   (45, 25),
    "ecommerce":     (35, 20),
    "food_delivery": (25, 10),
    "fintech":       (50, 30),
    "edtech":        (55, 35),
    "hrtech":        (50, 30),
    "default":       (50, 30),
}


def _gross_margin_status(pct: float, secteur: str, phase_hint=None) -> tuple[str, str | None]:
    """
    Return (status, alerte_msg | None) using sector-aware AND stage-aware thresholds.

    Seed discount: early-stage startups carry unoptimized infrastructure COGS
    (AWS, tooling, manual ops) that improve as they scale. Penalizing them with
    mature-company thresholds produces misleading CRITIQUE alerts.
    Thresholds are relaxed by 15pp healthy / 10pp warning for Seed phases.
    """
    key = (secteur or "default").lower().replace(" ", "_").replace("-", "_")
    healthy_min, warning_min = _GROSS_MARGIN_THRESHOLDS.get(key, _GROSS_MARGIN_THRESHOLDS["default"])

    # Stage awareness: relax thresholds for Seed
    phase_str = (
        phase_hint.value if hasattr(phase_hint, "value") else str(phase_hint or "")
    ).lower()
    is_seed = "seed" in phase_str
    if is_seed:
        healthy_min = max(healthy_min - 15, warning_min + 5)
        warning_min = max(warning_min - 10, 5)
        stage_note = f" (seuil seed assoupli — COGS non encore optimisés)"
    else:
        stage_note = ""

    if pct >= healthy_min:
        return "SAIN", None
    if pct >= warning_min:
        return "FAIBLE", (
            f"ATTENTION : marge brute = {pct}% (cible {key} > {healthy_min}%{stage_note})"
        )
    return "CRITIQUE", (
        f"CRITIQUE : marge brute = {pct}% — sous le seuil minimum {key} ({warning_min}%{stage_note})"
    )
# ─────────────────────────────────────────
# FONCTION PRINCIPALE
# ─────────────────────────────────────────

def calculate_kpis(context: FinancialContext) -> KPIResult:
    """
    Calcule tous les KPIs financiers depuis le FinancialContext.
    Aucun LLM. Aucune hypothèse inventée.
    Si une donnée manque → le KPI est None et une alerte est levée.

    Exemple:
        ctx = FinancialContext(
            burn_rate=12000, cash_balance=80000,
            monthly_revenue=750, n_clients=15,
            prix_client=50, churn_rate=0.05,
            marketing_budget=2000, new_clients_month=8
        )
        result = calculate_kpis(ctx)
        # result.runway_months → 7.1
        # result.ltv           → 1000.0
        # result.cac           → 250.0
        # result.ltv_cac_ratio → 4.0  (SAIN)
    """
    alertes = []

    # ── 1. BURN NET ──────────────────────────────────────────
    burn_rate   = context.burn_rate or 0.0
    revenue     = context.monthly_revenue or 0.0
    burn_net    = burn_rate - revenue

    if burn_net <= 0:
        # La startup est rentable — le burn rate est 0, pas de cash consommé
        burn_net = 0.0
        alertes.append(
            f"INFO : startup rentable — revenus ({revenue}) > dépenses ({burn_rate}) "
            f"→ profit mensuel de {round(revenue - burn_rate, 2)} DT, burn rate = 0"
        )

    # ── 2. RUNWAY ────────────────────────────────────────────
    cash = context.cash_balance

    if cash is None:
        runway_months = None
        runway_weeks  = None
        alertes.append("MANQUE : cash_balance absent — runway impossible à calculer")
        cash_out_alert = "INCONNU"
    elif burn_net == 0:
        runway_months  = float('inf')
        runway_weeks   = float('inf')
        cash_out_alert = "OK"
    else:
        runway_months  = round(cash / burn_net, 1)
        runway_weeks   = round((cash / burn_net) * 4.33, 1)

        if runway_months < 3:
            cash_out_alert = "CRITIQUE"
            alertes.append(
                f"CRITIQUE : runway = {runway_months} mois — "
                "chercher des fonds immédiatement"
            )
        elif runway_months < 6:
            cash_out_alert = "ATTENTION"
            alertes.append(
                f"ATTENTION : runway = {runway_months} mois — "
                "commencer à lever maintenant"
            )
        else:
            cash_out_alert = "OK"

    # ── 3. CAC ───────────────────────────────────────────────
    marketing = context.marketing_budget
    new_clients = context.new_clients_month

    if marketing is not None and new_clients and new_clients > 0:
        cac = round(marketing / new_clients, 2)
        cac_quality = "calculé"
    else:
        # CAC cannot be fabricated. 20%-of-burn is an arbitrary invention that
        # poisons LTV/CAC ratio and the downstream confidence score.
        # A startup with organic growth has marketing_budget=0 → real CAC≈0,
        # not "20% of burn". Return None and flag explicitly.
        cac = None
        cac_quality = "non disponible"
        if marketing is None and new_clients and new_clients > 0:
            alertes.append(
                "MANQUE : marketing_budget absent — CAC non calculable. "
                "Fournissez votre budget acquisition pour débloquer ce KPI."
            )
        elif not new_clients:
            alertes.append(
                "MANQUE : new_clients_month absent — CAC non calculable."
            )

    # ── 4. LTV ───────────────────────────────────────────────
    prix    = context.prix_client
    churn   = context.churn_rate
    cogs    = context.cogs or 0.0

    ltv_is_assumed = False   # flag propagated to ltv_cac_status

    if prix is not None and churn and churn > 0:
        marge_mensuelle = prix - cogs
        ltv = round(marge_mensuelle / churn, 2)
        # Warn: simplified perpetuity formula — only valid under steady-state churn
        alertes.append(
            "INFO : LTV = (prix−cogs)/churn — formule perpétuité simplifiée. "
            "Invalide si churn volatil, expansion revenue (NRR>100%), ou effets cohorte présents."
        )
    elif prix is not None and context.n_clients and revenue > 0:
        # ⚠ STRONG ASSUMPTION: silently using 5% churn inflates LTV and makes
        # projections optimistic. Flag loudly — this degrades confidence score.
        churn_estime = 0.05
        marge_mensuelle = prix - cogs
        ltv = round(marge_mensuelle / churn_estime, 2)
        ltv_is_assumed = True
        alertes.append(
            "⚠ HYPOTHÈSE FORTE : churn_rate absent — LTV calculé avec 5% par défaut "
            "(benchmark SaaS médian). Cette hypothèse peut surestimer la LTV de 2×–5× "
            "si le churn réel est plus élevé. Fournissez votre taux de churn."
        )
    else:
        ltv = None
        alertes.append("MANQUE : prix_client absent — LTV non calculable")

    # ── 5. LTV/CAC RATIO ────────────────────────────────────
    if ltv is not None and cac is not None and cac > 0:
        ltv_cac_ratio = round(ltv / cac, 2)

        if ltv_cac_ratio >= 3:
            ltv_cac_status = "SAIN"
        elif ltv_cac_ratio >= 1:
            ltv_cac_status = "LIMITE"
            alertes.append(
                f"ATTENTION : LTV/CAC = {ltv_cac_ratio} "
                "(doit être > 3 pour être sain)"
            )
        else:
            ltv_cac_status = "DANGEREUX"
            alertes.append(
                f"CRITIQUE : LTV/CAC = {ltv_cac_ratio} "
                "— tu perds de l'argent sur chaque client"
            )
    else:
        ltv_cac_ratio  = None
        ltv_cac_status = "N/A"

    # If LTV was built on assumed churn, mark ratio as estimated regardless of value
    if ltv_is_assumed and ltv_cac_status not in ("N/A",):
        ltv_cac_status = f"{ltv_cac_status} (LTV estimée)"

    # ── 6. BREAKEVEN ─────────────────────────────────────────
    # Breakeven = mois où revenue >= burn_rate
    # Si on connaît le taux de croissance des clients

    if prix is not None and burn_rate > 0:
        # Marge contribution par client = prix - cogs_variable
        marge_par_client = prix - (context.cogs or 0.0)
        if marge_par_client <= 0:
            alertes.append(
                f"CRITIQUE : COGS ({context.cogs}) ≥ prix client ({prix}) — "
                "marge unitaire négative, modèle économique non viable"
            )
            marge_par_client = max(prix * 0.01, 0.01)  # minimal floor to avoid /0

        # Coûts fixes = burn_rate total - coûts variables actuels (cogs × n_clients)
        # burn_rate inclut déjà cogs×n_clients → il faut les isoler pour le breakeven
        cogs_variables_actuels = (context.cogs or 0.0) * (context.n_clients or 0)
        couts_fixes = max(burn_rate - cogs_variables_actuels, burn_rate * 0.5)
        # Plancher à 50% du burn : si cogs > burn (erreur saisie), on reste conservateur

        breakeven_clients = int(couts_fixes / marge_par_client) + 1
        n_clients_actuels = context.n_clients or 0
        clients_manquants = max(0, breakeven_clients - n_clients_actuels)

        # Si on connaît le rythme d'acquisition
        if new_clients and new_clients > 0 and clients_manquants > 0:
            breakeven_months  = round(clients_manquants / new_clients, 1)
            breakeven_reachable = (
                runway_months is not None
                and runway_months != float('inf')
                and breakeven_months < runway_months
            )
            if not breakeven_reachable:
                alertes.append(
                    f"CRITIQUE : breakeven dans {breakeven_months} mois "
                    f"mais runway = {runway_months} mois — "
                    "impossible d'atteindre le breakeven sans financement"
                )
        elif clients_manquants == 0:
            breakeven_months  = 0.0
            breakeven_reachable = True
            alertes.append("INFO : startup déjà au breakeven")
        else:
            breakeven_months  = None
            breakeven_reachable = None
    else:
        breakeven_clients   = None
        breakeven_months    = None
        breakeven_reachable = None

    # ── 7. GROSS MARGIN ──────────────────────────────────────
    # Formule : (revenue - total_cogs) / revenue × 100
    # total_cogs = cogs_par_client × n_clients
    # Nécessite context.cogs et n_clients (ou n_clients inféré depuis prix)
    if revenue > 0 and context.cogs is not None:
        n_cli_gm = context.n_clients
        if n_cli_gm is None and prix is not None and prix > 0:
            n_cli_gm = max(1, round(revenue / prix))  # inféré depuis revenue/prix
        if n_cli_gm is not None:
            total_cogs_gm    = context.cogs * n_cli_gm
            gross_margin_pct = round((revenue - total_cogs_gm) / revenue * 100, 1)
            gross_margin_status, gm_alerte = _gross_margin_status(
                gross_margin_pct,
                context.secteur or "default",
                phase_hint=context.phase_hint,
            )
            if gm_alerte:
                alertes.append(gm_alerte)
        else:
            gross_margin_pct    = None
            gross_margin_status = "N/A"
            alertes.append("MANQUE : n_clients absent — gross margin non calculable")
    elif revenue > 0:
        gross_margin_pct    = None
        gross_margin_status = "N/A"
        alertes.append("MANQUE : cogs absent — gross margin non calculable")
    else:
        gross_margin_pct    = None
        gross_margin_status = "N/A"

    # ── 8. MRR / ARR ─────────────────────────────────────────
    if revenue > 0:
        mrr = round(revenue, 2)
        arr = round(revenue * 12, 2)
    elif prix is not None and context.n_clients:
        mrr = round(prix * context.n_clients, 2)
        arr = round(mrr * 12, 2)
    else:
        mrr = None
        arr = None

    return KPIResult(
        burn_net            = round(burn_net, 2),
        burn_rate_raw       = round(burn_rate, 2),
        runway_months       = runway_months,
        runway_weeks        = runway_weeks,
        cash_out_alert      = cash_out_alert,
        cac                 = cac,
        cac_quality         = cac_quality,
        ltv                 = ltv,
        ltv_cac_ratio       = ltv_cac_ratio,
        ltv_cac_status      = ltv_cac_status,
        breakeven_clients   = breakeven_clients,
        breakeven_months    = breakeven_months,
        breakeven_reachable = breakeven_reachable,
        gross_margin_pct    = gross_margin_pct,
        gross_margin_status = gross_margin_status,
        mrr                 = mrr,
        arr                 = arr,
        alertes             = alertes,
    )


# ─────────────────────────────────────────
# TESTS INTÉGRÉS — lance ce fichier directement
# python tools/calculate_kpis.py
# ─────────────────────────────────────────

if __name__ == "__main__":

    print("=" * 55)
    print("TEST 1 — Startup Tunis (cas de base)")
    print("=" * 55)
    ctx1 = FinancialContext(
        burn_rate          = 12000,
        cash_balance       = 80000,
        monthly_revenue    = 750,
        n_clients          = 15,
        prix_client        = 50,
        churn_rate         = 0.05,
        marketing_budget   = 2000,
        new_clients_month  = 8,
        burn_quality       = DataQuality.ESTIMATED,
        cash_quality       = DataQuality.REAL,
        revenue_quality    = DataQuality.REAL,
    )
    r1 = calculate_kpis(ctx1)
    print(f"Burn net         : {r1.burn_net} DT/mois")
    print(f"Runway           : {r1.runway_months} mois ({r1.runway_weeks} semaines)")
    print(f"Alerte runway    : {r1.cash_out_alert}")
    print(f"CAC              : {r1.cac} DT ({r1.cac_quality})")
    print(f"LTV              : {r1.ltv} DT")
    print(f"LTV/CAC          : {r1.ltv_cac_ratio} → {r1.ltv_cac_status}")
    print(f"Breakeven        : {r1.breakeven_clients} clients / {r1.breakeven_months} mois")
    print(f"Breakeven OK ?   : {r1.breakeven_reachable}")
    print(f"MRR / ARR        : {r1.mrr} / {r1.arr} DT")
    print(f"Alertes ({len(r1.alertes)})     :")
    for a in r1.alertes:
        print(f"  → {a}")

    print()
    print("=" * 55)
    print("TEST 2 — Startup critique (runway < 3 mois)")
    print("=" * 55)
    ctx2 = FinancialContext(
        burn_rate       = 15000,
        cash_balance    = 20000,
        monthly_revenue = 3000,
        n_clients       = 10,
        prix_client     = 300,
        churn_rate      = 0.10,
        new_clients_month = 2,
    )
    r2 = calculate_kpis(ctx2)
    print(f"Runway           : {r2.runway_months} mois → {r2.cash_out_alert}")
    print(f"LTV/CAC          : {r2.ltv_cac_ratio} → {r2.ltv_cac_status}")
    print(f"Breakeven OK ?   : {r2.breakeven_reachable}")
    print(f"Alertes ({len(r2.alertes)})     :")
    for a in r2.alertes:
        print(f"  → {a}")

    print()
    print("=" * 55)
    print("TEST 3 — Données minimales (beaucoup de None)")
    print("=" * 55)
    ctx3 = FinancialContext(
        burn_rate    = 8000,
        cash_balance = 50000,
    )
    r3 = calculate_kpis(ctx3)
    print(f"Runway           : {r3.runway_months} mois")
    print(f"CAC              : {r3.cac}")
    print(f"LTV              : {r3.ltv}")
    print(f"Alertes ({len(r3.alertes)})     :")
    for a in r3.alertes:
        print(f"  → {a}")

    print()
    print("=" * 55)
    print("TEST 4 — Startup déjà profitable")
    print("=" * 55)
    ctx4 = FinancialContext(
        burn_rate       = 10000,
        cash_balance    = 120000,
        monthly_revenue = 15000,
        n_clients       = 50,
        prix_client     = 300,
        churn_rate      = 0.03,
        cogs            = 30,
        marketing_budget = 1500,
        new_clients_month = 5,
    )
    r4 = calculate_kpis(ctx4)
    print(f"Burn net         : {r4.burn_net} (négatif = profitable)")
    print(f"Runway           : {r4.runway_months} mois")
    print(f"Gross margin     : {r4.gross_margin_pct}% → {r4.gross_margin_status}")
    print(f"LTV/CAC          : {r4.ltv_cac_ratio} → {r4.ltv_cac_status}")
    print(f"Alertes ({len(r4.alertes)})     :")
    for a in r4.alertes:
        print(f"  → {a}")