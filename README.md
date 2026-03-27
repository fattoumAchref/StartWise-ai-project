# agentfinance - Scraping Files Overview

Ce README decrit ce que fait chaque scraper principal et comment il collecte les donnees.

## `scraping/saas_benchmarks.py`

Ce fichier cherche des benchmarks SaaS B2B par stade: `Seed`, `Series A`, `Series B`, `Series C`, `Public`.

Ce qu'il cherche:
- `growth_rate_yoy`
- `gross_margin`
- `net_revenue_retention`
- `churn_rate_monthly`
- `ltv_cac_ratio`
- `cac_payback_months`
- `arr`
- `ev_revenue_multiple`
- `burn_rate`

Comment il le fait:
1. Envoie des requetes web a Tavily (2 requetes par stage).
2. Concatene les extraits retournes (titre, url, contenu).
3. Envoie ce texte a un LLM via endpoint OpenAI-compatible Esprit.
4. Le LLM retourne un JSON structure par stage et metrique.
5. Sauvegarde le resultat dans `data/benchmarks_cache.json` (cache 7 jours).

Important:
- Pas de fallback chiffre en dur.
- Si l'extraction echoue, les donnees peuvent etre partielles ou vides.
- Un cache vide est ignore au run suivant.

Variables d'environnement utilisees:
- `TAVILY_API_KEY`
- `ESPRIT_API_KEY`
- `ESPRIT_BASE_URL` (ex: `https://tokenfactory.esprit.tn/api`)
- `ESPRIT_MODEL` (ex: `hosted_vllm/Llama-3.1-70B-Instruct`)
- `ESPRIT_VERIFY_SSL` (`true`/`false`)

## `scraping/yahoo_finance.py`

Ce fichier cherche des donnees de societes SaaS cotees en bourse via Yahoo Finance.

Tickers suivis:
- `CRM`, `SNOW`, `DDOG`, `MDB`, `BILL`, `ZM`

Ce qu'il cherche:
- `ev_revenue_multiple`
- `gross_margin`
- `growth_rate_yoy`

Comment il le fait:
1. Utilise `yfinance` pour lire `Ticker.info`.
2. Extrait les champs financiers utiles.
3. Construit des objets `CompanyBenchmark` avec stage `Public`.
4. Retourne la liste des benchmarks Yahoo.

Variables d'environnement:
- Aucune obligatoire pour ce scraper.

## `scraping/news_scraper.py`

Ce fichier cherche des news tech/finance via flux RSS TechCrunch.

Sources RSS:
- `https://techcrunch.com/tag/saas/feed/`
- `https://techcrunch.com/tag/fintech/feed/`
- `https://techcrunch.com/tag/funding/feed/`

Ce qu'il cherche pour chaque article:
- titre
- resume (tronque)
- source
- url
- date de publication
- secteur

Comment il le fait:
1. Lit les flux RSS avec `feedparser`.
2. Parse les entrees recentes de chaque flux.
3. Convertit la date si possible.
4. Retourne la liste d'objets `NewsItem`.

Variables d'environnement:
- Aucune obligatoire pour ce scraper.
