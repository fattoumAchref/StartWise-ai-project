# StartWise CFO — Financial Agent

Agent d'analyse financière conversationnel pour startups tunisiennes.
Il extrait les données depuis une conversation naturelle avec le fondateur, exécute un pipeline de calcul complet, et produit une sortie structurée pour les agents downstream (risk, investment, orchestrateur).

---

## Lancer l'application

```bash
pip install -r requirements.txt
streamlit run app.py
```

Variables d'environnement requises dans `.env` :

```bash
ESPRIT_API_KEY=...        # LLM Llama-3.1-70B-Instruct (Esprit institutional API)
TAVILY_API_KEY=...        # Web search pour rafraîchir les benchmarks
```

---

## Vue d'ensemble : qui fait quoi

```
Fondateur (chat / PDF / CSV)
         │
         ▼
   agent/tools/parser.py          ← extrait les données → FinancialContext
         │
         ▼
   calcul_tools/pipeline.py       ← orchestre les 8 étapes de calcul
         │
    ┌────┴──────────────────────────────────────────────┐
    │  1. validate_inputs.py   → qualité + cohérence    │
    │  2. calculate_kpis.py    → burn, runway, LTV...   │
    │  3. route_by_phase.py    → phase de maturité      │
    │  4. scenario_projection  → 3 scénarios            │
    │  5. monte_carlo.py       → P10 / P50 / P90        │
    │  6. seasonality_trend.py → tendance + saisonnalité│
    │  7. scenario_comparator  → KPIs vs benchmarks     │
    │  8. confidence_a2a.py    → score + message A2A    │
    └───────────────────────────────────────────────────┘
         │
         ├──→  app.py              (Streamlit UI)
         └──→  A2AMessage          (risk_agent / investment_agent / orchestrateur)
```

---

## Structure des fichiers et logique détaillée

### `models/data_models.py` — Source de vérité des types

Contient **toutes** les dataclasses partagées entre les modules. Aucune logique ici — uniquement des structures de données.

| Type | Rôle |
|---|---|
| `FinancialContext` | Toutes les données extraites du fondateur (burn, cash, clients, secteur…) |
| `RevenueDataPoint` | Un point mensuel `{date, revenue}` pour l'historique |
| `KPIResult` | Résultat des calculs KPI (runway, LTV, CAC, gross margin…) |
| `MonteCarloResult` | P10/P50/P90, probabilité de survie, tightness score |
| `BenchmarkResult` | Médianes sectorielles (churn, gross margin, LTV, CAC en TND) |
| `ValidationResult` | Score de qualité, incohérences, questions à poser |
| `ScenarioComparatorResult` | Comparaison KPIs startup vs benchmarks |
| `ConfidenceResult` | Score de confiance pondéré [0–1] + interprétation |
| `A2AMessage` | Message structuré envoyé aux agents downstream |
| `Phase` | Enum : `SEED / TRACTION / FUNDRAISING / SEED_RAISING` |
| `DataQuality` | Enum : `REAL(1.0) / ESTIMATED(0.7) / ASSUMPTION(0.4) / MISSING(0.1)` |

**Relations clés :**
- `FinancialContext` est l'entrée de **tous** les outils de calcul
- `KPIResult` est consommé par `monte_carlo`, `scenario_comparator`, `confidence_a2a`
- `A2AMessage` agrège `KPIResult + MonteCarloResult + BenchmarkResult + ConfidenceResult`

---

### `agent/tools/parser.py` — Extraction LLM

**Rôle :** Transformer n'importe quelle entrée fondateur en `FinancialContext`.

**Logique :**
1. Détecte si l'entrée est un fichier (PDF / CSV / XLSX) ou du texte brut
2. Pour le texte : envoie au LLM Esprit avec un prompt JSON structuré
3. Pour PDF : extrait le texte via PyMuPDF puis passe au LLM
4. Pour CSV/XLSX : lit les colonnes par alias (ex: `ca`, `mrr`, `revenue` → `monthly_revenue`)
5. Reconstruit un `FinancialContext` avec `_build_context()`

**Extraction de l'historique :** Si le fondateur mentionne plusieurs mois (`"janvier 1200, février 1450"`), le LLM les extrait en liste `[{date, revenue}]` → stockée dans `revenue_history: list[RevenueDataPoint]`.

**Inférences automatiques :**
- `prix_client` manquant → `monthly_revenue / n_clients`
- `monthly_revenue` manquant → `prix_client × n_clients`
- `churn_rate` en % (ex: `7`) → normalisé en décimal (`0.07`)
- `DataQuality` attribuée selon le vocabulaire : *"exactement"* → `REAL`, *"environ"* → `ESTIMATED`, *"je pense"* → `ASSUMPTION`

**Dépendances :** `models/data_models.py`, LLM Esprit API

---

### `agent/tools/fetch_benchmarks.py` — Couche RAG

**Rôle :** Récupérer les benchmarks sectoriels les plus proches du profil du fondateur.

**Pipeline RAG :**
```
1. Construire un profil texte depuis FinancialContext
   ex: "Seed stage SaaS startup based in TN. $36k ARR. Monthly churn 5%."

2. Interroger ChromaDB (E5 embeddings, top-5 documents similaires)

3. Si similarité max < 0.45 → refresh Tavily (une seule fois par session)
   → scrape SaaSBenchmarkScraper + YahooFinanceScraper
   → vectorise dans ChromaDB → re-requête

4. Extraire médianes par regex depuis les documents :
   gross_margin, churn_rate, EV/revenue multiple, LTV/CAC ratio, CAC payback

5. Estimer CAC/LTV en TND (currency-agnostic) :
   cac_tnd = cac_payback_months × prix_client
   ltv_tnd = cac_tnd × ltv_cac_ratio
```

**Pourquoi TND ?** Les benchmarks globaux sont en USD. Plutôt que de convertir (taux flottant), on utilise des **ratios dimensionnels** (mois de payback, ratio LTV/CAC) multipliés par le `prix_client` local pour produire des valeurs directement en TND.

**Limitation documentée :** Quand `cac_tnd` / `ltv_tnd` sont estimés par cette méthode, le champ `BenchmarkResult.source` reçoit un suffixe d'avertissement :
> *"· CAC/LTV estimés en DT (ratio dimensionless × prix_client — valable uniquement si segment de prix similaire au benchmark)"*
Cela prévient les agents downstream que la valeur absolue s'effondre si le benchmark ciblait un segment enterprise vs. SMB.

**Dépendances :** `pipeline/vectorizer.py`, `scraping/saas_benchmarks.py`, `scraping/yahoo_finance.py`, `models/data_models.py`

---

### `agent/tools/confidence_a2a.py` — Score de confiance + sortie A2A

**Rôle :** Produire une mesure de fiabilité des projections et assembler le message pour les agents downstream.

**`compute_confidence_score()`** — score pondéré [0–1] :

| Composante | Poids | Source |
|---|---|---|
| Qualité des données | 40% | `ValidationResult.data_quality_score` (moyenne des `DataQuality` enum) |
| Tightness Monte Carlo | 35% | `MonteCarloResult.mc_tightness` (resserrement P10/P90) |
| Cohérence logique | 25% | 0 incohérence → 1.0 · 1 → 0.65 · 2 → 0.35 · 3+ → 0.10 |

Interprétation : ≥0.70 → **ÉLEVÉ** · ≥0.45 → **MOYEN** · <0.45 → **FAIBLE**

**`build_a2a_message()`** — assemble `A2AMessage` :
- Porte : `kpis`, `monte_carlo`, `benchmarks`, `confidence`, liste d'alertes
- Alertes critiques de runway remontées en tête de liste
- Consommateurs : `risk_agent`, `investment_agent`, `orchestrateur`

**Dépendances :** `models/data_models.py`

---

### `calcul_tools/pipeline.py` — Orchestrateur

**Rôle :** Chaîner les 8 étapes dans le bon ordre, gérer les dépendances entre étapes, logger les erreurs.

**Signature :**
```python
run_analysis_pipeline(
    context: FinancialContext,
    benchmarks: Optional[BenchmarkResult] = None,   # active steps 7+8
) -> dict
```

**Retourne un dict avec 10 clés :**
```
validation, kpis, monte_carlo, phase, active_models,
scenarios, seasonality, comparator, confidence, a2a_message
```

**Conditions de déclenchement par étape :**

| Étape | Condition |
|---|---|
| 1. validate_inputs | Toujours |
| 2. calculate_kpis | `burn_rate` + `cash_balance` présents |
| 3–5. phase / scenarios / MC | `kpis` non-None |
| 6. seasonality | `monthly_revenue` présent OU `revenue_history` non-vide |
| 7. comparator | `benchmarks` fourni + `kpis` + `scenarios` non-None |
| 8. confidence + A2A | Toujours (après toutes les autres étapes) |

**Gestion d'erreurs :** Chaque étape est dans un `try/except` qui logue via `logger.warning()`. Une étape qui échoue ne bloque pas les suivantes — le dict retourne `None` pour cette clé.

---

### `calcul_tools/validate_inputs.py` — Validation

**Rôle :** Vérifier la cohérence des données avant tout calcul.

**Checks effectués :**
- Champs critiques manquants (`burn_rate`, `cash_balance`) → `is_valid = False`
- Incohérence revenue : `n_clients × prix_client ≠ monthly_revenue` (tolérance 15%)
- `churn_rate` hors `[0, 1]` → probablement saisi en % (ex: `5` au lieu de `0.05`)
- `churn > 20%` → critique métier
- `prix_client ≤ 0` → invalide
- `cash < burn_net` → moins d'un mois de runway
- `burn = 0` ET `revenue = 0` → données suspectes

**Score de qualité** = moyenne des `DataQuality.value` des 3 champs principaux :
`(burn_quality + cash_quality + revenue_quality) / 3`

---

### `calcul_tools/calculate_kpis.py` — Calculs KPI

**Rôle :** Calculs déterministes purs. Aucun LLM, aucune hypothèse inventée.

**Formules :**

```
burn_net          = max(0, burn_rate − monthly_revenue)
runway_months     = cash_balance / burn_net
cac               = marketing_budget / new_clients_month
                    (None + alerte explicite si marketing_budget absent — pas de fabrication)
ltv               = (prix_client − cogs) / churn_rate
                    (churn estimé à 5% si absent — ⚠ HYPOTHÈSE FORTE, ltv_cac_status suffixé)
ltv_cac_ratio     = ltv / cac
gross_margin_pct  = (revenue − cogs × n_clients) / revenue × 100
breakeven_clients = fixed_costs / margin_per_client
breakeven_months  = clients_manquants / new_clients_month
```

**`ltv_cac_status` quand LTV est estimée :** Si `churn_rate` est absent et que la LTV a été calculée avec 5% par défaut, `ltv_cac_status` reçoit le suffixe `" (LTV estimée)"` (ex : `"SAIN (LTV estimée)"`) pour signaler aux consommateurs downstream que le ratio repose sur une hypothèse forte.

**Seuils gross margin par secteur (stage-aware) :**

Thresholds de maturité : pour la phase Seed, les seuils sont assouplis de −15pp (healthy) / −10pp (warning) car les COGS infrastructure ne sont pas encore optimisés.

| Secteur | Sain (mature) | Attention | Critique | Sain (seed) |
|---|---|---|---|---|
| SaaS | ≥ 60% | ≥ 40% | < 40% | ≥ 45% |
| Fintech | ≥ 50% | ≥ 30% | < 30% | ≥ 35% |
| EdTech | ≥ 55% | ≥ 35% | < 35% | ≥ 40% |
| HRTech | ≥ 50% | ≥ 30% | < 30% | ≥ 35% |
| Marketplace | ≥ 45% | ≥ 25% | < 25% | ≥ 30% |
| E-commerce | ≥ 35% | ≥ 20% | < 20% | ≥ 20% |
| Food delivery | ≥ 25% | ≥ 10% | < 10% | ≥ 10% |

Le `phase_hint` du `FinancialContext` est passé à `_gross_margin_status()` pour activer l'assouplissement automatiquement.

**Cas limites gérés :**
- `burn_net ≤ 0` → startup profitable, `runway = ∞`
- `cac = None` → KPI non calculable (jamais fabriqué depuis % du burn)
- `cogs ≥ prix_client` → alerte CRITIQUE marge unitaire négative (ne calcule pas un faux breakeven)
- `churn_rate = 0` → LTV non calculable (division par zéro évitée)

---

### `calcul_tools/route_by_phase.py` — Détection de phase

**Rôle :** Classifier la startup dans une phase de maturité basée sur les données numériques uniquement.

**Logique (priorité décroissante) :**
```
intent_fundraising=True + revenue>0 + ≥6 mois data → FUNDRAISING
intent_fundraising=True                              → SEED_RAISING
revenue > 0 + ≥6 mois data                          → TRACTION
sinon                                                → SEED
```

**Point important :** `mois_data = max(months_data déclaré, len(revenue_history))`.
Si le fondateur fournit 8 mois d'historique via CSV mais ne mentionne pas le nombre de mois, la phase est quand même correctement classifiée en `TRACTION`.

**`get_active_models(phase)`** retourne quels modules activer :

| Phase | Monte Carlo | Prophet | DCF | Cap Table |
|---|---|---|---|---|
| SEED | ✓ | ✗ | ✗ | ✗ |
| TRACTION | ✓ | ✓ | ✗ | ✗ |
| FUNDRAISING | ✓ | ✓ | ✓ | ✓ |
| SEED_RAISING | ✓ | ✗ | ✓ | ✓ |

---

### `calcul_tools/scenario_projection.py` — Projections 3 scénarios

**Rôle :** Projeter revenus et trésorerie sur 24 mois dans 3 hypothèses.

**Taux de croissance par scénario :**
- **Pessimiste** : 0% (pas de croissance)
- **Réaliste** : taux sectoriel (SaaS 8%, marketplace 10%, food delivery 12%…)
- **Optimiste** : hypothèse fondateur ÷ 2 (plafonnée à 15–20%)

Chaque scénario produit : `growth_rate`, `cash_final_24m`, `revenue_final_24m`, `survie_12m`

---

### `calcul_tools/monte_carlo.py` — Simulation probabiliste

**Rôle :** Quantifier l'incertitude sur le runway.

**Paramètres de simulation (1000 itérations) :**
- Croissance mensuelle : loi normale centrée sur `growth_mean` (taux réaliste), σ = 15%
- Volatilité burn : ±12% mensuel
- Retourne P10 / P50 / P90 du runway (mois)
- `mc_tightness` = 1 − (P90 − P10) / P50 → proche de 1 = résultats concentrés = fiable

---

### `calcul_tools/seasonality_trend.py` — Tendance + saisonnalité hybride

**Rôle :** Prévoir les revenus en fusionnant données client et signal sectoriel externe.

**Philosophie :** Toujours produire un résultat — jamais silencieux. La confiance s'adapte à la quantité de données disponibles.

**Gating data-driven (remplace l'ancien gating par phase) :**

| Points historiques | Niveau | Poids client | Poids externe |
|---|---|---|---|
| 0 | NONE | 0% | 100% |
| 1–2 | VERY_LOW | 20% | 80% |
| 3–5 | LOW | 40% | 60% |
| 6–11 | MEDIUM | 65% | 35% |
| 12+ | HIGH | 85% | 15% |

**Forecast client** (si données présentes) :
- Prophet si installé (`pip install prophet`) — détecte saisonnalité annuelle
- Fallback régression linéaire sur taux de croissance moyen mois/mois

**Forecast externe** (`scraping/sector_calendar.py`) :
- Indices mensuels par secteur (Jan–Déc, normalisés autour de 1.0)
- Ajustements MENA : Ramadan (−18%), post-Eid (+12%), etc.
- Cache Yahoo Finance 30 jours dans `data/sector_seasonality_cache.json`

**Blend final :** `forecast = w_client × forecast_client + w_externe × forecast_externe`

**Détection d'anomalies :** Mois où le revenu réel s'écarte de >25% du schéma sectoriel attendu → signalé dans `anomaly_months`.

**Champ `reasoning`** — explication en langage naturel générée automatiquement :
> *"Confiance faible — 4 mois de données. Le signal sectoriel (60%) compense le manque d'historique. Tendance en hausse de 8.2%/mois. Saisonnalité détectée — pics prévus en Nov, Déc."*

---

### `calcul_tools/scenario_comparator.py` — Comparaison vs benchmarks

**Rôle :** Comparer les KPIs de la startup aux médianes sectorielles.

**KPIs comparés :**
- CAC (`lower_is_better=True`)
- LTV (`lower_is_better=False`)
- Churn mensuel (`lower_is_better=True`)
- Gross margin (`lower_is_better=False`)
- LTV/CAC ratio (seuil universel ≥ 3)

**Statuts :** `AU_DESSUS` · `DANS_LA_NORME` (±15%) · `EN_DESSOUS` · `N/A`

**Score global** = nb KPIs au-dessus ou dans la norme / nb KPIs comparables → [0–1]

**Fallback `_default_benchmarks()`** : Si Chroma ne retourne rien, utilise des benchmarks hardcodés convertis en TND (×3.10 DT/USD) pour 7 secteurs : `saas`, `marketplace`, `ecommerce`, `food_delivery`, `fintech`, `edtech`, `hrtech`.

---

### `scraping/sector_calendar.py` — Indices de saisonnalité sectorielle

**Rôle :** Fournir un signal externe de saisonnalité sans appel API au moment de l'analyse.

**Architecture hybride (offline-first) :**
```
1. Vérifier cache disque (data/sector_seasonality_cache.json, TTL 30 jours)
   ↓ cache absent ou expiré
2. Fetch Yahoo Finance quarterly revenue pour les tickers du secteur
   (CRM, SNOW, DDOG pour SaaS ; ETSY, ABNB pour marketplace…)
   → calculer les poids Q1/Q2/Q3/Q4 → interpoler en 12 indices mensuels
   ↓ Yahoo Finance échoue ou tickers absents
3. Fallback indices statiques hardcodés (recherches sectorielles SaaStr, a16z, OpenView)
```

**Ajustements MENA** : Si `pays` ∈ `{TN, MA, DZ, EG, SA, AE…}` :
- Mois du Ramadan → ×0.82 (baisse activité commerciale)
- Mois post-Ramadan/Eid → ×1.12 (rebond consommation)

---

### `app.py` — Interface Streamlit + orchestration

**Rôle :** Interface conversationnelle, gestion de session, orchestration du pipeline, rendu des résultats.

**Deux modes de conversation :**

| Mode | Condition | Comportement |
|---|---|---|
| **COLLECTE** | `burn_rate` ou `cash_balance` absent | Pose des questions ciblées |
| **ANALYSE** | Les deux présents | Lance `run_analysis_pipeline()` + affiche KPIs |

**Flux d'un message :**
```
Message fondateur
    → parse_founder_input()          (parser.py)
    → merge avec context session     (monotone : qualité ne peut qu'augmenter)
    → run_analysis_pipeline(ctx)     (pipeline.py)
    → fetch_benchmarks(ctx)          (fetch_benchmarks.py, si données valides)
    → scenario_comparator(...)       (wiré dans app.py avec benchmarks)
    → rendu UI : KPIs + alertes + boutons d'action
```

**Sections révélées à la demande :**
- 📈 Graphiques : projection trésorerie + revenus 24 mois (Plotly)
- 📊 Benchmarks : comparaison KPI vs médianes sectorielles
- 📅 Saisonnalité : forecast 3m/6m/12m + indice sectoriel + anomalies
- 📄 Rapport PDF : rapport complet avec graphiques exportés

---

## Flux de données complet

```
FinancialContext
    ├── validate_inputs ──────────────────────→ ValidationResult
    │                                                │
    ├── calculate_kpis ───────────────────────→ KPIResult
    │                                                │
    ├── route_by_phase ───────────────────────→ Phase
    │       (max(months_data, len(revenue_history)))  │
    │                                                │
    ├── scenario_projection ──────────────────→ ScenarioProjectionResult
    │                                                │
    ├── monte_carlo ──────────────────────────→ MonteCarloResult
    │       (growth_mean = taux réaliste du scénario)│
    │                                                │
    ├── seasonality_trend ────────────────────→ SeasonalityResult
    │       (revenue_history + sector_calendar)      │
    │                                                │
    ├── [benchmarks] → scenario_comparator ──→ ScenarioComparatorResult
    │                                                │
    └── compute_confidence_score ─────────────→ ConfidenceResult
            (ValidationResult + MonteCarloResult     │
             + nb incohérences)                      │
                                                     ▼
                                              A2AMessage
                                    ┌─────────────────────────┐
                                    │ risk_agent              │
                                    │ investment_agent        │
                                    │ orchestrateur           │
                                    └─────────────────────────┘
```

---

## Dépendances entre modules

```
data_models.py          ← importé par TOUT le monde (pas de dépendances sortantes)

parser.py               → data_models
fetch_benchmarks.py     → data_models, pipeline/vectorizer, scraping/*
confidence_a2a.py       → data_models

validate_inputs.py      → data_models
calculate_kpis.py       → data_models
route_by_phase.py       → data_models
scenario_projection.py  → data_models
monte_carlo.py          → data_models
seasonality_trend.py    → data_models, scraping/sector_calendar
scenario_comparator.py  → data_models, scenario_projection

pipeline.py             → tous les calcul_tools + agent/tools/confidence_a2a

app.py                  → pipeline, parser, fetch_benchmarks, scenario_comparator
                          agent/tools/pdf_report, models/data_models
```

**Règle :** `data_models.py` n'importe rien du projet. `pipeline.py` est le seul module qui importe l'ensemble des outils de calcul.

---

## Sous-agents LLM internes

Le CFO agent contient **5 appels LLM internes**, chacun avec un rôle précis. Tout le reste (calculs, simulations) est du Python pur — aucun LLM.

| Agent | Fichier | Rôle |
|---|---|---|
| **Extraction** | `parser.py` | Texte/PDF/CSV → `FinancialContext` JSON structuré |
| **Question generator** | `app.py` | Champs manquants → questions ciblées en français (interdit de demander LTV, CAC, runway — métriques calculées) |
| **CFO conversationnel** | `app.py` | Réponses aux questions de suivi, basées sur KPIs + benchmarks injectés |
| **What-if parser** | `app.py` | Détecte les hypothèses (*"si je réduis le burn de 30%"*) → JSON d'opérations `{op: multiply, factor: 0.7}` |
| **Benchmark extractor** | `saas_benchmarks.py` | Résultats Tavily → métriques numériques par stage → ChromaDB |

**Principe :** Le LLM fait uniquement ce que les maths ne peuvent pas faire (comprendre du langage). Toutes les décisions financières reposent sur du code déterministe auditable.

---

## Format du message A2A

```json
{
  "message_id": "uuid",
  "type": "financial_analysis",
  "from": "finance_agent",
  "to": ["risk_agent", "investment_agent", "orchestrator"],
  "timestamp": "ISO-8601",
  "context": {
    "project_id": "uuid",
    "session_id": "uuid"
  },
  "payload": {
    "data": {
      "phase": "traction",
      "secteur": "saas",
      "pays": "TN",
      "kpis": { "runway_months": 8.2, "ltv_cac_ratio": 3.4, ... },
      "monte_carlo": { "p10": 4, "p50": 8, "p90": 14, ... },
      "benchmarks": { "churn_median": 0.05, "gross_margin_median": 0.72, ... },
      "confidence_detail": { "niveau": "MOYEN", "score": 0.61, ... },
      "alertes": ["🟠 RUNWAY ATTENTION : 8 mois — préparer la levée"]
    }
  },
  "confidence": 0.61,
  "metadata": {
    "priority": "medium",
    "requires_response": false,
    "tags": ["traction", "saas", "TN"]
  }
}
```

`priority` est dérivé automatiquement : `CRITIQUE runway → high` · `ATTENTION → medium` · sinon `low`
