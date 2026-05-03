# Changements — branche `nour`

## Vue d'ensemble

Intégration d'un pipeline de calcul financier complet dans l'agent StartWise CFO, corrections de logique financière, et refonte de l'affichage des KPIs.

---

## 1. Nouveau répertoire `calcul_tools/`

Remplacement du répertoire `tools/` (supprimé) par `calcul_tools/` qui contient les outils de calcul utilisables depuis le Founder Chat Flow (sans dépendance au scraping).

| Fichier | Rôle |
|---|---|
| `pipeline.py` | Orchestre les 5 étapes dans le bon ordre |
| `validate_inputs.py` | Validation et score de qualité des données |
| `calculate_kpis.py` | Burn net, runway, LTV, CAC, gross margin, MRR |
| `route_by_phase.py` | Détection de la phase startup (seed / traction / fundraising…) |
| `scenario_projection.py` | 3 scénarios déterministes (pessimiste / réaliste / optimiste) |
| `monte_carlo.py` | Simulation probabiliste — P10/P50/P90 du runway |
| `scenario_comparator.py` | _(réservé — benchmarks scraping — prochaine phase)_ |
| `seasonality_trend.py` | _(réservé — données historiques — prochaine phase)_ |

### Ordre du pipeline (`pipeline.py`)

```
validate_inputs → calculate_kpis → route_by_phase
→ scenario_projection → run_monte_carlo (avec growth réaliste)
```

Le Monte Carlo est calculé **après** les scénarios pour utiliser le taux de croissance du scénario réaliste (cohérence garantie entre p50 et scénario réaliste).

---

## 2. Corrections de logique financière

### `calcul_tools/calculate_kpis.py`

- **Burn net** : `burn_net = max(0, burn_rate - monthly_revenue)` — une startup rentable a un burn net de 0, pas négatif
- **Gross Margin** : corrigé `cogs is not None` (bug : `cogs = context.cogs or 0.0` rendait le test toujours vrai → affichait 100% de marge quand COGS inconnu)
- **Breakeven** : coûts fixes = `burn_rate - cogs × n_clients` (pas le burn total)
- **LTV** : `(prix - cogs) / churn` quand COGS connu, sinon `prix / churn`

### `calcul_tools/validate_inputs.py`

- `burn < revenue` n'est plus une incohérence → déplacé en `questions_to_ask` (vérification douce)
- Seuil cash critique : utilise `burn_net` (pas le burn brut) pour éviter les faux positifs sur les startups rentables
- `CRITICAL_FIELDS` = seulement `burn_rate` + `cash_balance` (les autres sont `IMPORTANT_FIELDS`, non bloquants)

### `calcul_tools/scenario_projection.py`

- `mc` rendu optionnel (il n'était pas utilisé dans les calculs)
- Cap croissance optimiste : `min(hypothese / 2, 0.30)` (corrigé depuis 0.50)
- Runway final : utilise `cash_sim` et `rev_sim` en fin de simulation (pas les valeurs initiales)
- Formatage `float('inf')` → `"∞ (startup rentable)"`

### `calcul_tools/monte_carlo.py`

- Suppression du taux de croissance hardcodé par secteur
- Reçoit `growth_mean` du scénario réaliste via le pipeline
- Stocke `growth_mean_used` dans `MonteCarloResult` pour la transparence de l'affichage

### `agent/tools/validator.py`

- Même corrections que `validate_inputs.py` (burn<revenue, cash<burn_net)

---

## 3. Modèle de données (`models/data_models.py`)

- `MonteCarloResult` : ajout du champ `growth_mean_used: float` — taux de croissance utilisé dans la simulation

---

## 4. Interface (`app.py`)

### Flux deux modes
- **Mode COLLECTE** : champs requis manquants → l'agent pose des questions ciblées uniquement sur les champs manquants
- **Mode ANALYSE** : tous les champs requis présents → pipeline complet, aucune question répétée

### Fusion de contexte (`_merge_contexts`)
- Fusion toujours champ par champ (bug corrigé : remplacement total si ≥ 3 champs)
- Score de qualité **monotone croissant** : garde le meilleur niveau par champ (`REAL > ESTIMATED > ASSUMPTION > MISSING`)

### Affichage des KPIs
- **Burn Rate** : affiche le burn net ; si startup rentable affiche `-X DT/mois (startup profitable)`
- **LTV** : double affichage LTV Revenue + LTV Profit quand COGS connu, avec formule
- **LTV/CAC** : interprétation (Excellent ≥ 5x / Sain ≥ 3x / Limite / Critique) avec explication
- **Durée de vie client** : qualifié (faible / modéré / élevé / critique) selon le taux de churn
- **Gross Margin** : affiché sans benchmark secteur (les benchmarks viendront avec le scraping)

### Monte Carlo
- Affiche les hypothèses : `(croissance revenue X%/mois · volatilité burn ±12%, 1000 simulations)`
- Si startup rentable : `non pertinente (startup rentable — pas de risque d'insolvabilité)`

### Labels
- "Burn Rate" → "Dépenses mensuelles" (dans la sidebar et les métriques)
- Prompt LLM : interdit de demander burn net, LTV, CAC, runway, gross margin (métriques calculées)

### Visualisations Plotly
- Graphique trésorerie projetée 24 mois (3 scénarios)
- Graphique revenus projetés 24 mois avec ligne breakeven

---

## 5. Dépendances

- Ajout de `plotly` dans `requirements.txt`

---

## Prochaine phase (non traité)

- `scenario_comparator.py` — comparaison avec benchmarks secteur (nécessite scraping)
- `seasonality_trend.py` — analyse de tendance (nécessite données historiques)
- Intégration ChromaDB + sentence-transformers pour RAG benchmarks