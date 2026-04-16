# Agent Légal IA — Tunisie

Conseiller juridique intelligent pour startups et entreprises tunisiennes.
Aucune connaissance juridique préalable requise.

---

## Ce que fait l'agent

| Module | Ce qu'il fait |
|--------|--------------|
| **Création** | Choisit la forme juridique (SARL/SA/SUARL), génère les statuts et la checklist RNE |
| **Protection IP** | Vérifie si un nom de marque est disponible à l'INNORPI (similarité phonétique), audite les licences logicielles |
| **Contrats** | Génère CDI, CDD, NDA, Prestation de services, Pacte d'actionnaires — analyse un contrat reçu et détecte les clauses dangereuses |
| **Levée de fonds** | Explique BSA Air / Convertible / Equity, calcule la dilution, traduit un term sheet |
| **Conformité** | Score de conformité 0–100, alertes INPDP / CNSS / TVA / Travail, calendrier des échéances |

---

## Stack technique

- **LLM** : Claude Sonnet 4.6 (Anthropic)
- **Embeddings** : text-embedding-3-large (OpenAI)
- **Reranker** : rerank-multilingual-v3.0 (Cohere)
- **Vector Store** : Qdrant
- **Base de données** : PostgreSQL + SQLAlchemy async
- **API** : FastAPI + WebSocket
- **Scraping** : Playwright + BeautifulSoup + httpx

---

## Structure des fichiers

```
agent-legal/
│
├── main.py              # Point d'entrée — lance FastAPI, init DB + Qdrant
├── api.py               # Toutes les routes REST + WebSocket
├── config.py            # Paramètres chargés depuis .env
├── database.py          # Connexion PostgreSQL async
├── models.py            # Toutes les tables SQL (un seul fichier)
├── vector_store.py      # Client Qdrant + 6 collections
├── embeddings.py        # Stratégies d'embedding + normaliseur phonétique
├── requirements.txt
├── .env.example
│
├── scrapers/
│   ├── jort.py          # Journal Officiel (lois, décrets, arrêtés)
│   ├── innorpi.py       # Marques déposées
│   ├── dgi_cnss.py      # Taux fiscaux + cotisations sociales
│   ├── jurisprudence.py # Décisions des tribunaux tunisiens
│   └── spdx.py          # Licences logicielles (MIT, GPL, AGPL...)
│
├── rag/
│   ├── pipeline.py      # Orchestrateur principal du pipeline RAG
│   ├── reformulator.py  # Question → sous-requêtes structurées (Claude)
│   ├── retriever.py     # Recherche vectorielle parallèle dans Qdrant
│   ├── reranker.py      # Cross-encoder Cohere + ajustements légaux
│   └── generator.py     # Génération de réponse finale (Claude)
│
└── modules/
    ├── creation.py      # Arbre de décision forme juridique + génération statuts
    ├── ip_protection.py # Vérification marque + audit licences
    ├── contracts.py     # Génération et analyse de contrats
    ├── fundraising.py   # Dilution, term sheet, instruments de financement
    └── compliance.py    # Score conformité + alertes + paie
```

---

## Installation

### 1. Cloner et installer les dépendances

```bash
cd "agent legal"
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/Mac

pip install -r requirements.txt
playwright install chromium
```

### 2. Configurer les variables d'environnement

```bash
copy .env.example .env
```

Ouvrir `.env` et remplir :

```env
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
COHERE_API_KEY=...
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/agent_legal
QDRANT_URL=http://localhost:6333
JWT_SECRET=une-cle-secrete-longue
```

### 3. Démarrer PostgreSQL et Qdrant

**PostgreSQL** (si pas installé) : https://www.postgresql.org/download/windows/

Créer la base de données :
```bash
psql -U postgres -c "CREATE DATABASE agent_legal;"
```

**Qdrant** (télécharger l'exécutable) : https://qdrant.tech/documentation/quick-start/

```bash
# Windows — télécharger qdrant.exe et lancer :
qdrant.exe
# Qdrant tourne sur http://localhost:6333
```

### 4. Lancer l'API

```bash
uvicorn main:app --reload
```

L'API est disponible sur `http://localhost:8000`
La documentation Swagger sur `http://localhost:8000/docs`

---

## Comment tester

### Option A — Swagger UI (le plus simple)

Ouvrir `http://localhost:8000/docs` dans le navigateur.
Toutes les routes sont listées et testables directement sans écrire de code.

---

### Option B — curl / terminal

#### 1. Créer un compte et récupérer le token

```bash
# Créer un compte
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "fondateur@startup.tn", "password": "monmotdepasse", "full_name": "Ahmed Ben Ali"}'

# Se connecter — récupérer le token JWT
curl -X POST http://localhost:8000/auth/login \
  -F "username=fondateur@startup.tn" \
  -F "password=monmotdepasse"

# Réponse : {"access_token": "eyJ...", "token_type": "bearer"}
# Copier le token pour les requêtes suivantes
TOKEN="eyJ..."
```

---

#### 2. Tester le chat général

```bash
curl -X POST http://localhost:8000/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Quelle est la différence entre une SARL et une SA en Tunisie ?",
    "language": "fr"
  }'
```

Réponse attendue :
```json
{
  "answer": "**Réponse directe**\nLa SARL...",
  "sources": ["Art. 93 CSC — Loi n°2000-93", "Art. 160 CSC"],
  "intent": "creation",
  "requires_lawyer": false
}
```

---

#### 3. Tester la recommandation de forme juridique

```bash
curl -X POST "http://localhost:8000/creation/recommend-form" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "nb_founders": 3,
    "has_fundraising_plans": true,
    "sector": "technologie",
    "capital_available_tnd": 5000
  }'
```

Réponse attendue : recommandation SA avec étapes, coûts et délais.

---

#### 4. Tester la vérification de marque (le plus critique)

```bash
curl -X POST http://localhost:8000/ip/check-trademark \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "TakwinTech",
    "nice_classes": [9, 35, 42]
  }'
```

Réponse attendue :
```json
{
  "candidate": "TakwinTech",
  "risk_level": "ELEVE",
  "can_register": false,
  "conflicts": [
    {
      "name": "Takween",
      "phonetic_similarity": 0.87,
      "class_overlap": true,
      "holder": "Société XYZ",
      "nice_classes": [35, 42]
    }
  ],
  "recommendation": "🟠 RISQUE ÉLEVÉ — Des marques similaires existent..."
}
```

---

#### 5. Tester l'audit de licences logicielles

```bash
curl -X POST http://localhost:8000/ip/audit-licenses \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "stack": ["MIT", "Apache-2.0", "AGPL-3.0-only"],
    "business_model": "saas"
  }'
```

Réponse attendue : risque CRITIQUE sur AGPL-3.0-only avec explication et action recommandée.

---

#### 6. Tester l'analyse d'un contrat

```bash
curl -X POST http://localhost:8000/contracts/analyze \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "contract_text": "...Le salarié s'\''engage à une clause de non-concurrence de 5 ans. La responsabilité de l'\''employeur est totalement exclue. Juridiction exclusive : tribunaux de Paris...",
    "contract_type": "CDI"
  }'
```

Réponse attendue : 3 clauses dangereuses détectées (non-concurrence excessive, exclusion responsabilité, juridiction étrangère), risque CRITIQUE.

---

#### 7. Tester la génération d'un contrat NDA

```bash
curl -X POST http://localhost:8000/contracts/generate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "contract_type": "NDA",
    "variables": {
      "party_a_name": "StartupTN SARL",
      "party_b_name": "Client SA",
      "purpose": "Discussion de partenariat commercial",
      "duration_years": 2,
      "governing_law": "droit tunisien"
    },
    "language": "fr"
  }'
```

---

#### 8. Tester le calcul de dilution

```bash
curl -X POST http://localhost:8000/fundraising/dilution \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "pre_money_tnd": 1000000,
    "investment_tnd": 200000,
    "cap_table": {
      "Ahmed (CEO)": 60,
      "Sara (CTO)": 40
    }
  }'
```

Réponse attendue :
```json
{
  "post_money_tnd": 1200000,
  "investor_pct": 16.67,
  "founders_before": {"Ahmed (CEO)": 60, "Sara (CTO)": 40},
  "founders_after": {"Ahmed (CEO)": 50.0, "Sara (CTO)": 33.33}
}
```

---

#### 9. Tester le rapport de conformité

```bash
curl -X POST http://localhost:8000/compliance/report \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "StartupTN SARL",
    "legal_form": "SARL",
    "employees_count": 3,
    "has_users_data": true,
    "has_inpdp_declaration": false,
    "has_written_contracts": true,
    "vat_registered": true,
    "startup_label": false,
    "last_cnss_declaration": "2026-03-15",
    "last_tva_declaration": null
  }'
```

Réponse attendue : score ~65/100, 2 alertes CRITICAL (INPDP manquant, TVA non déclarée).

---

#### 10. Tester le calcul de paie

```bash
curl -X POST http://localhost:8000/compliance/payroll \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "employees": [
      {"name": "Ahmed Ben Ali", "gross_salary_tnd": 2500},
      {"name": "Sara Trabelsi", "gross_salary_tnd": 3200}
    ]
  }'
```

Réponse : détail CNSS patronal (16.57%), salarial (9.18%), TFP, FOPROLOS et coût employeur total pour chaque employé.

---

#### 11. Tester les taux fiscaux en vigueur

```bash
curl http://localhost:8000/data/tax-rates
```

Pas besoin de token — données publiques.

---

#### 12. Tester l'analyse d'une licence

```bash
curl http://localhost:8000/data/license/AGPL-3.0-only
```

Réponse : `risk_level: CRITIQUE`, `compatible_saas: false`, explication et action recommandée.

---

### Option C — Python directement (sans API)

Pour tester un module sans lancer le serveur :

```python
# test_quick.py
import asyncio
from modules.creation import recommend_legal_form
from modules.compliance import ComplianceModule
from scrapers.dgi_cnss import calculate_employer_cost
from scrapers.spdx import check_saas_risk, check_stack_compatibility
from embeddings import PhoneticNormalizer

# 1. Recommandation forme juridique (synchrone)
result = recommend_legal_form(nb_founders=2, has_fundraising_plans=True)
print(f"Forme recommandée : {result.recommended_form}")
print(f"Raison : {result.reason}")

# 2. Rapport de conformité (synchrone)
compliance = ComplianceModule()
report = compliance.generate_report(
    company_name="StartupTN",
    legal_form="SARL",
    employees_count=3,
    has_inpdp_declaration=False,
    vat_registered=True,
)
print(f"\nScore conformité : {report.score}/100 ({report.score_label})")
for alert in report.alerts:
    print(f"  [{alert.severity}] {alert.title}")

# 3. Coût employeur (synchrone)
cout = calculate_employer_cost(gross_salary=2500)
print(f"\nSalaire brut : {cout['gross_salary_tnd']} TND")
print(f"Coût total employeur : {cout['total_employer_cost_tnd']} TND")
print(f"Net avant IRPP : {cout['net_salary_before_irpp_tnd']} TND")

# 4. Audit licences (synchrone)
audit = check_stack_compatibility(["MIT", "Apache-2.0", "AGPL-3.0-only"])
print(f"\nRisque stack : {audit['overall_risk']}")
print(f"SaaS compatible : {audit['saas_compatible']}")

# 5. Similarité phonétique (synchrone)
ph = PhoneticNormalizer()
score = ph.similarity_score("TakwinTech", "Takween")
print(f"\nSimilarité phonétique TakwinTech / Takween : {score:.2f}")

# 6. Test pipeline RAG complet (async — nécessite les clés API)
async def test_rag():
    from rag.pipeline import rag_pipeline, RAGRequest
    response = await rag_pipeline.run(RAGRequest(
        query="Quelles sont les obligations CNSS d'une startup de 5 employés ?",
        language="fr",
    ))
    print(f"\nRéponse RAG : {response.answer[:200]}...")
    print(f"Sources : {response.sources}")

asyncio.run(test_rag())
```

```bash
python test_quick.py
```

---

## Workflow complet — de la question à la réponse

```
Fondateur pose une question
           │
           ▼
    [Reformulateur]
    Claude décompose la question en N sous-requêtes
    chacune ciblant la bonne collection Qdrant
           │
           ▼
    [Retriever — parallèle]
    Toutes les sous-requêtes s'exécutent en même temps
    Chaque requête → embed → search Qdrant top-20
    Résultats agrégés + dédupliqués
           │
           ▼
    [Reranker]
    Cross-encoder Cohere (ar/fr/en) : top-20 → top-5
    Pénalité si texte ABROGÉ (-0.8)
    Pénalité si texte > 2 ans (-0.2)
    Bonus si bon domaine (+0.3)
           │
           ▼
    [Générateur]
    Prompt = chunks + métadonnées + contexte entreprise
    Règles : citer sources, signaler abrogés, recommander avocat
           │
           ▼
    Réponse structurée avec base légale + action + ⚖️ avocat
```

---

## Limites importantes

- Les données INNORPI sont scrappées — une marque déposée très récemment peut ne pas apparaître avant le prochain scraping
- Le droit tunisien évolue avec chaque loi de finances : relancer le scraping DGI chaque janvier
- Les documents générés (statuts, pacte d'actionnaires) **doivent être validés par un avocat** avant toute signature définitive
- L'agent ne représente pas les parties devant les tribunaux

---

## Sources légales utilisées

| Source | Données | Fréquence de mise à jour |
|--------|---------|--------------------------|
| JORT (legislation.tn) | Lois, décrets, arrêtés, circulaires | Quotidienne |
| INNORPI | Marques déposées classes Nice 1-45 | Hebdomadaire |
| DGI | Taux TVA, IS, IRPP, barèmes | Annuelle (après loi de finances) |
| CNSS | Taux cotisations, calendrier | Annuelle |
| Jurisprudence | TPI Tunis, Cour de Cassation | Manuelle |
| SPDX | Licences logicielles | Trimestrielle |
