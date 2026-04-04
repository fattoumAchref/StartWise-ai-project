# fetch_benchmarks.py — Documentation détaillée

## Rôle dans le projet

Ce fichier implémente la **couche RAG** (Retrieval-Augmented Generation) de l'agent financier.

Son unique responsabilité est de **récupérer les médianes sectorielles** correspondant au profil d'une startup, en interrogeant d'abord une base vectorielle locale (ChromaDB), puis en allant chercher des données fraîches sur le web (Tavily) si la base locale est vide ou insuffisante.

**Il ne produit aucune valeur de sortie calculée.** Il effectue un seul calcul intermédiaire (LTV/CAC) à l'intérieur de `_build_profile` — mais uniquement pour construire un meilleur texte de requête Chroma, cette valeur n'est jamais exposée dans le `BenchmarkResult`. Il ne compare pas les données du fondateur aux benchmarks. Il ne génère pas de recommandations. Il retourne uniquement un `BenchmarkResult` qui sera consommé par les outils de calcul de ton collègue (`calculate_kpis`, `run_monte_carlo`, etc.).

---

## Entrée / Sortie

| | Type | Description |
|---|---|---|
| **Entrée** | `FinancialContext` | Données financières extraites du message du fondateur |
| **Sortie** | `BenchmarkResult` | Médianes sectorielles les plus proches du profil |

```python
# Exemple d'appel
from agent.tools.fetch_benchmarks import fetch_benchmarks
result = fetch_benchmarks(ctx)   # ctx est un FinancialContext
```

---

## Pipeline d'exécution

```
FinancialContext
      │
      ▼
 _phase_to_stage()        [1] convertir la phase en stage Chroma
      │
      ▼
 _build_profile()         [2] construire le texte de requête
      │
      ▼
 _query_chroma()          [3] interroger ChromaDB
      │
      ├── similarité ≥ 0.45 ──────────────────────────────────────┐
      │                                                            │
      └── similarité < 0.45 ──► _refresh_from_tavily()           │
                                       │                          │
                                  _run_async()                    │
                                       │                          │
                              SaaSBenchmarkScraper                │
                              BenchmarkVectorizer.store()         │
                                       │                          │
                              _query_chroma() [re-requête] ───────┘
                                                            │
                                                   top-5 documents
                                                            │
                                                    _parse_doc() × 5   [4]
                                                            │
                                                   _aggregate()        [5]
                                                    _median() × métrique
                                                            │
                                                            ▼
                                                    BenchmarkResult    [6]
```

---

## Constantes globales

```python
SIMILARITY_THRESHOLD = 0.45
TOP_K = 5
```

| Constante | Valeur | Rôle |
|---|---|---|
| `SIMILARITY_THRESHOLD` | `0.45` | Score cosinus minimum acceptable. En dessous, on considère que Chroma n'a pas de donnée pertinente et on déclenche un refresh Tavily. |
| `TOP_K` | `5` | Nombre de documents récupérés depuis Chroma. La médiane est calculée sur ces 5 documents. |

---

## Table de mapping `_PHASE_TO_STAGE`

```python
_PHASE_TO_STAGE = {
    "seed":             "Seed",
    "seed+fundraising": "Seed",
    "fundraising":      "Seed",
    "traction":         "Seed",
    ...
}
```

ChromaDB organise ses benchmarks par **stage de financement** (`Seed`, `Series A`, `Series B`, `Series C`, `Public`). Le `FinancialContext` utilise une enum `Phase` qui ne contient que 4 valeurs : `SEED`, `SEED_RAISING`, `TRACTION`, `FUNDRAISING`. Aucune ne correspond à `Series A`, `Series B` ou `Series C`. Mapper `TRACTION` vers `"Series A"` serait arbitraire — tout est donc mappé vers `"Seed"`, le seul stage qu'on peut affirmer avec certitude.

Elle accepte à la fois les valeurs string (`"traction"`) et les instances `Phase` de l'enum Python, pour éviter les erreurs selon la façon dont `phase_hint` est renseigné.

---

## Fonctions — détail

---

### `_phase_to_stage(phase_hint) → str`

**Rôle :** Convertit `phase_hint` (qui peut être une string ou un objet `Phase`) en stage Chroma valide.

**Logique :**
1. Si `phase_hint` est une instance `Phase` → utilise `.value` pour lire la string (`"traction"`, `"seed"`, etc.) puis la cherche dans `_PHASE_TO_STAGE`
2. Si `phase_hint` est déjà une string → normalise en minuscules et cherche dans `_PHASE_TO_STAGE`
3. Si aucune correspondance → retourne `"Seed"` par défaut (cas inconnu = startup débutante)

**Exemples :**
```python
_phase_to_stage(Phase.TRACTION)      # → "Series A"
_phase_to_stage("seed+fundraising")  # → "Seed"
_phase_to_stage("unknown")           # → "Seed"  (fallback)
_phase_to_stage(None)                # → "Seed"  (fallback)
```

---

### `_build_profile(ctx: FinancialContext) → str`

**Rôle :** Construit une phrase en **anglais financier** décrivant le profil de la startup, utilisée comme texte de requête dans ChromaDB.

**Pourquoi en anglais ?** Le modèle d'embedding `intfloat/e5-base-v2` a été entraîné principalement sur des textes anglais financiers. Les documents stockés dans Chroma (scrappés par Tavily depuis des sources US) sont aussi en anglais. Pour que la mesure de similarité soit cohérente, la requête doit être dans le même espace vectoriel que les documents — donc en anglais.

**Format de sortie :**
```
"Series A stage SaaS startup based in TN. $300k ARR.
 monthly churn rate of 5.0%. LTV to CAC ratio of 2.0x.
 monthly burn rate of $40k."
```

**Éléments inclus (si disponibles dans le contexte) :**

| Champ source | Transformation | Exemple dans le profil |
|---|---|---|
| `phase_hint` + `secteur` + `pays` | Toujours présent | `"Series A stage SaaS startup based in TN"` |
| `monthly_revenue` | Multiplié × 12 pour avoir l'ARR, formaté en k$ ou M$ | `"$300k ARR"` |
| `churn_rate` | Multiplié × 100 pour afficher en % | `"monthly churn rate of 5.0%"` |
| `prix_client` + `churn_rate` + `marketing_budget` + `new_clients_month` | LTV = prix_client / churn_rate. CAC = marketing_budget / new_clients_month. Ratio = LTV / CAC — **calcul interne uniquement pour enrichir le texte de requête Chroma, jamais exposé dans BenchmarkResult** | `"LTV to CAC ratio of 2.0x"` |
| `burn_rate` | Divisé par 1000 pour afficher en k$ | `"monthly burn rate of $40k"` |

**Note :** Les valeurs sont converties en USD approximatif (format) mais les montants réels en DT ne sont pas convertis — le format sert uniquement à la recherche de similarité, pas à un calcul précis.

---

### `_parse_doc(doc: str) → dict`

**Rôle :** Extrait les valeurs numériques d'un document Chroma en utilisant des **expressions régulières**.

**Pourquoi des regex et pas le LLM ?** Le format des documents Chroma est entièrement déterministe — il est produit par `BenchmarkVectorizer.to_text()` qui génère toujours la même structure. Utiliser un LLM pour parser un format prévisible serait plus lent, plus coûteux, et moins fiable.

**Format d'un document Chroma :**
```
"Series A stage SaaS B2B company based in US. $1.2M ARR.
 growing at 150.0% year over year. gross margin of 72.0%.
 LTV to CAC ratio of 3.2x. monthly churn rate of 2.5%.
 net revenue retention of 115.0%. CAC payback period of 14 months.
 monthly burn rate of $80k. EV to revenue multiple of 8.0x."
```

**Expressions régulières utilisées :**

| Regex | Cible dans le doc | Valeur retournée |
|---|---|---|
| `gross margin of ([\d.]+)%` | `"gross margin of 72.0%"` | `0.72` (divisé par 100) |
| `monthly churn rate of ([\d.]+)%` | `"monthly churn rate of 2.5%"` | `0.025` (divisé par 100) |
| `EV to revenue multiple of ([\d.]+)x` | `"EV to revenue multiple of 8.0x"` | `8.0` (valeur brute) |
| `LTV to CAC ratio of ([\d.]+)x` | `"LTV to CAC ratio of 3.2x"` | `3.2` (valeur brute) |
| `CAC payback period of ([\d.]+) months` | `"CAC payback period of 14 months"` | `14.0` (valeur brute) |

**Normalisation :** Les valeurs en pourcentage (`gross_margin`, `churn_rate_monthly`) sont automatiquement converties en décimaux (72% → 0.72) pour être cohérentes avec le reste du projet.

**Résultat retourné :**
```python
{
    "gross_margin":        0.72,
    "churn_rate_monthly":  0.025,
    "ev_revenue_multiple": 8.0,
    "ltv_cac_ratio":       3.2,
    "cac_payback_months":  14.0,
}
```
Si une métrique est absente du document, sa valeur est `None`.

---

### `_median(values: list[Optional[float]]) → Optional[float]`

**Rôle :** Calcule la médiane d'une liste de valeurs en ignorant les `None`.

**Pourquoi la médiane et pas la moyenne ?** La médiane est robuste aux valeurs extrêmes. Si un des 5 documents récupérés contient un churn de 40% (valeur aberrante), la médiane ne sera pas faussée contrairement à la moyenne.

**Comportement :**
- Filtre tous les `None` avant le calcul
- Si aucune valeur valide → retourne `None` (pas de données disponibles)
- Arrondit à 4 décimales

```python
_median([0.025, 0.030, None, 0.028, 0.020])  # → 0.0265
_median([None, None, None])                   # → None
```

---

### `_aggregate(parsed_docs: list[dict]) → dict`

**Rôle :** Reçoit la liste des dictionnaires produits par `_parse_doc()` (un par document Chroma) et calcule la **médiane de chaque métrique** sur l'ensemble des documents.

**Métriques agrégées :**

| Clé dans le résultat | Source dans les docs | Usage dans `BenchmarkResult` |
|---|---|---|
| `gross_margin` | `gross margin of X%` | → `gross_margin_median` |
| `churn_rate_monthly` | `monthly churn rate of X%` | → `churn_median` |
| `ev_revenue_multiple` | `EV to revenue multiple of Xx` | → `valorisation_multiple` |
| `ltv_cac_ratio` | `LTV to CAC ratio of Xx` | stocké dans `documents_raw` uniquement |
| `cac_payback_months` | `CAC payback period of X months` | stocké dans `documents_raw` uniquement |

**Exemple avec 3 documents :**
```python
doc1 = {"gross_margin": 0.72, "churn_rate_monthly": 0.025, ...}
doc2 = {"gross_margin": 0.68, "churn_rate_monthly": 0.030, ...}
doc3 = {"gross_margin": 0.75, "churn_rate_monthly": None,  ...}

_aggregate([doc1, doc2, doc3])
# → {
#     "gross_margin":        0.72,   # médiane de [0.72, 0.68, 0.75]
#     "churn_rate_monthly":  0.0275, # médiane de [0.025, 0.030] (None ignoré)
#     ...
# }
```

---

### `_run_async(coro) → Any`

**Rôle :** Exécute une coroutine `async` depuis un contexte **synchrone**, en étant compatible avec Streamlit.

**Problème résolu :** Streamlit possède son propre event loop Python qui tourne en permanence. Si on appelle `asyncio.run()` directement depuis le code Streamlit, Python lève une erreur `RuntimeError: This event loop is already running` car on ne peut pas imbriquer deux event loops.

**Solution :** Lancer la coroutine dans un **thread séparé** (qui a son propre event loop vierge) via `ThreadPoolExecutor`. Le thread principal attend la fin de l'exécution via `.result()`.

```python
# Ce qu'on veut faire (mais qui plante dans Streamlit) :
asyncio.run(scraper.as_benchmarks())   # ❌ RuntimeError

# Ce qu'on fait à la place :
with ThreadPoolExecutor(max_workers=1) as pool:
    return pool.submit(asyncio.run, coro).result()   # ✅
```

---

### `_refresh_from_tavily(stage: str) → bool`

**Rôle :** Déclenche le pipeline de scraping web pour récupérer des benchmarks frais et les stocker dans ChromaDB.

**Quand est-elle appelée ?** Uniquement quand `best_similarity < SIMILARITY_THRESHOLD` dans `fetch_benchmarks()` — c'est-à-dire quand Chroma est vide ou ne contient pas de données suffisamment proches du profil de la startup.

**Pipeline interne :**

1. Instancie `SaaSBenchmarkScraper` (qui initialise Tavily et le LLM Esprit)
2. Appelle `scraper.as_benchmarks()` via `_run_async()` — ce qui déclenche :
   - Des recherches Tavily sur le web (ex: `"SaaS Series A benchmarks 2025 gross margin churn"`)
   - L'extraction structurée des métriques par le LLM Esprit
   - Le formatage en objets `CompanyBenchmark`
3. Filtre les benchmarks sur le `stage` demandé (pour ne stocker que ce qui est pertinent)
4. Si aucun benchmark ne correspond exactement au stage → stocke tout (mieux que rien)
5. Appelle `BenchmarkVectorizer.store()` qui vectorise et persiste dans Chroma

**Valeur de retour :**
- `True` → au moins un benchmark a été stocké, on peut re-interroger Chroma
- `False` → échec (Tavily indisponible, LLM KO, résultats vides) → `fetch_benchmarks()` retournera un `BenchmarkResult` vide

**Gestion d'erreur :** Toute exception est capturée et loggée — la fonction ne lève jamais d'exception pour ne pas bloquer l'interface Streamlit.

---

### `_query_chroma(profile: str, stage: str, n: int = 5) → list[dict]`

**Rôle :** Interroge ChromaDB et retourne les `n` documents les plus proches du profil, filtrés par stage.

**Étapes internes :**
1. Instancie `BenchmarkVectorizer` (qui charge le modèle E5 et se connecte à Chroma)
2. Vérifie que la collection n'est pas vide (`collection.count() == 0`) — si vide, retourne `[]` immédiatement sans interroger (évite une erreur Chroma)
3. Appelle `BenchmarkVectorizer.query_top()` qui :
   - Encode le profil avec E5 (préfixe `"query: "` pour les modèles E5)
   - Filtre sur `{"stage": stage}` dans les métadonnées
   - Retourne les n documents triés par similarité décroissante

**Format de chaque résultat retourné :**
```python
{
    "doc":        "Series A stage SaaS B2B company...",  # texte du document
    "similarity": 0.87,   # score cosinus transformé [0-1] (1 = identique)
    "stage":      "Series A",
    "source":     "tavily_websearch",
    "confidence": 0.90,   # score de fiabilité attribué lors du scraping
    "year":       2025,
}
```

**Gestion d'erreur :** Toute exception (connexion Chroma, modèle E5 non chargé, filtre invalide) retourne `[]` — jamais d'exception propagée.

---

### `fetch_benchmarks(ctx: FinancialContext) → BenchmarkResult`

**Rôle :** Fonction principale et unique point d'entrée public du fichier. Orchestre toutes les fonctions ci-dessus.

**Paramètre :** `ctx` — le `FinancialContext` produit par `parse_founder_input()` après que le fondateur a soumis ses données.

**Étapes d'exécution détaillées :**

**Étape 1 — Préparation**
```python
stage = _phase_to_stage(ctx.phase_hint)   # ex: "Series A"
profile = _build_profile(ctx)             # ex: "Series A stage SaaS..."
```

**Étape 2 — Requête initiale Chroma**
```python
results = _query_chroma(profile, stage)
best_similarity = max(r["similarity"] for r in results, default=0.0)
```
On récupère les 5 docs les plus proches et on note le meilleur score de similarité.

**Étape 3 — Décision refresh**
```python
if best_similarity < 0.45:
    refreshed = _refresh_from_tavily(stage)
    if refreshed:
        results = _query_chroma(profile, stage)  # re-requête après refresh
```
Si le score est trop bas (< 0.45), Chroma n'a rien d'utile. On va scraper Tavily, on stocke les nouveaux benchmarks dans Chroma, puis on ré-interroge.

**Étape 4 — Cas d'échec total**
```python
if not results:
    return BenchmarkResult(source="unavailable", similarity_score=0.0)
```
Si après tout ça on n'a toujours rien (Tavily KO, Chroma inaccessible, etc.), on retourne un `BenchmarkResult` vide avec `source="unavailable"`. Cela permet aux outils en aval de gérer l'absence de benchmarks sans planter.

**Étape 5 — Extraction et agrégation**
```python
parsed = [_parse_doc(r["doc"]) for r in results]   # regex sur chaque doc
agg = _aggregate(parsed)                            # médiane par métrique
```

**Étape 6 — Construction du BenchmarkResult**
```python
return BenchmarkResult(
    cac_median=None,                              # non disponible (USD absolu)
    ltv_median=None,                              # non disponible (USD absolu)
    churn_median=agg["churn_rate_monthly"],       # ex: 0.025 = 2.5%
    gross_margin_median=agg["gross_margin"],      # ex: 0.72 = 72%
    valorisation_multiple=agg["ev_revenue_multiple"],  # ex: 8.0 = 8x ARR
    source=source_label,                          # ex: "tavily_websearch"
    similarity_score=round(best_similarity, 3),  # ex: 0.87
    documents_raw=[r["doc"] for r in results],   # textes bruts pour audit
)
```

**Pourquoi `cac_median` et `ltv_median` sont `None` ?**
Les benchmarks dans Chroma sont des données globales (US, sources SaaS internationales) exprimées en USD. Retourner une valeur en USD comme médiane pour une startup tunisienne (qui raisonne en DT) serait trompeur. Ces champs sont laissés à `None` pour que le collègue puisse les calculer directement depuis les données du fondateur.

---

## Dépendances

| Module | Utilisé pour |
|---|---|
| `pipeline.vectorizer.BenchmarkVectorizer` | Requête et stockage ChromaDB |
| `scraping.saas_benchmarks.SaaSBenchmarkScraper` | Scraping Tavily + extraction LLM |
| `models.data_models.FinancialContext` | Type d'entrée |
| `models.data_models.BenchmarkResult` | Type de sortie |
| `models.data_models.Phase` | Mapping phase → stage |
| `statistics` (stdlib) | Calcul de médiane |
| `re` (stdlib) | Parsing regex des documents |
| `concurrent.futures` (stdlib) | Exécution async dans Streamlit |

---

## Variables d'environnement requises

| Variable | Obligatoire | Usage |
|---|---|---|
| `ESPRIT_API_KEY` | Oui (pour refresh Tavily) | Authentification LLM Esprit pour extraction des métriques scrappées |
| `TAVILY_API_KEY` | Oui (pour refresh Tavily) | Clé API recherche web Tavily |
| `CHROMA_PATH` | Non (défaut: `./chroma_db`) | Chemin de la base vectorielle persistante |
| `EMBEDDING_MODEL` | Non (défaut: `intfloat/e5-base-v2`) | Modèle d'embedding pour ChromaDB |

---

## Test rapide

```bash
cd c:/Users/ASUS/Desktop/agentfinance
python -m agent.tools.fetch_benchmarks
```

Attendu en sortie (si Chroma est alimenté) :
```
── BenchmarkResult ──────────────────────────────
  source              : tavily_websearch
  similarity_score    : 0.82
  churn_median        : 0.025
  gross_margin_median : 0.72
  valorisation_x      : 8.0
  docs récupérés      : 5
```
