# StartWise CFO — Agent d'analyse financière pour startups

Agent conversationnel qui analyse la situation financière d'une startup tunisienne à partir d'une conversation naturelle avec le fondateur, et produit des KPIs fiables, des projections et des visualisations.

---

## Lancer l'application

```bash
pip install -r requirements.txt
streamlit run app.py
```

---

## Architecture

```
app.py                        # Interface Streamlit + orchestration
agent/
  tools/
    parser.py                 # Extraction LLM → FinancialContext
    validator.py              # Validation de cohérence
    fetch_benchmarks.py       # RAG : ChromaDB + Tavily + Yahoo Finance
models/
  data_models.py              # Dataclasses : FinancialContext, KPIResult, etc.
calcul_tools/
  pipeline.py                 # Orchestration des 5 étapes
  validate_inputs.py          # Validation + score de qualité
  calculate_kpis.py           # Burn net, runway, LTV, CAC, gross margin
  route_by_phase.py           # Détection de phase (seed / traction / fundraising)
  scenario_projection.py      # 3 scénarios déterministes (pessimiste/réaliste/optimiste)
  monte_carlo.py              # Simulation probabiliste P10/P50/P90
  scenario_comparator.py      # Comparaison benchmarks sectoriels
  seasonality_trend.py        # Tendances saisonnières
scraping/
  saas_benchmarks.py          # Tavily + LLM extraction
  yahoo_finance.py            # Données cotées (CRM, SNOW, DDOG...)
  news_scraper.py             # RSS TechCrunch (saas, fintech, funding)
  market_data.py              # Taux de change BCE
```

## `scraping/yahoo_finance.py`

Tickers suivis : `CRM`, `SNOW`, `DDOG`, `MDB`, `BILL`, `ZM`

Métriques extraites : `ev_revenue_multiple`, `gross_margin`, `growth_rate_yoy`

Intégré dans le RAG pour les stages **Public** et **Series C**.

## Pipeline de calcul

```
validate_inputs → calculate_kpis → route_by_phase
→ scenario_projection → run_monte_carlo
```

Le Monte Carlo utilise le taux de croissance du scénario réaliste — pas de valeurs hardcodées par secteur.

---

## Flux conversationnel

| Mode | Condition | Comportement |
|---|---|---|
| **COLLECTE** | Champs requis manquants | L'agent pose des questions ciblées |
| **ANALYSE** | Tous les champs requis présents | Pipeline complet, KPIs + visualisations |

Champs requis : `burn_rate`, `cash_balance`, `monthly_revenue`, `n_clients`, `prix_client`, `churn_rate`

---

## KPIs produits

- **Burn Rate** net (dépenses − revenus), affiché négatif si startup profitable
- **Runway** en mois
- **LTV Revenue** et **LTV Profit** (si COGS connu)
- **CAC** et ratio **LTV/CAC** avec interprétation (Excellent / Sain / Limite / Critique)
- **Gross Margin**, **MRR**, **ARR**
- **Durée de vie client** avec qualification du churn (faible / modéré / élevé / critique)
- **Monte Carlo** P10/P50/P90 avec hypothèses affichées (taux de croissance + volatilité)

---

## Variables d'environnement

```
ESPRIT_API_KEY=...   # Clé API Esprit (LLM Llama-3.1-70B-Instruct)
```

---

## Prochaine phase

- Intégration benchmarks secteur via scraping (`scenario_comparator.py`)
- Analyse de tendance sur données historiques (`seasonality_trend.py`)
- RAG ChromaDB + sentence-transformers