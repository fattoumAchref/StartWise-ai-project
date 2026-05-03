# Guide d'Intégration A2A — StartWise Bus

> Ce document est destiné aux équipes qui veulent connecter leur agent au bus A2A StartWise.
> Aucune dépendance sur le code de l agent finance n'est requise — seulement des appels HTTP.

---

## 1. Vue d'ensemble

Le bus A2A est un **routeur de messages HTTP/Redis**. Chaque agent a sa propre boîte de réception (inbox). Pour envoyer un message à un ou plusieurs agents, on fait un `POST /publish` avec la liste des destinataires dans le champ `to`. Le bus se charge de déposer le message dans l'inbox de chacun.

```
Ton agent                     Bus A2A :8765                  Autres agents
    │                              │                               │
    │  POST /publish               │                               │
    │  { to: ["finance_agent",     │  LPUSH a2a:finance_agent:inbox│
    │          "investment_agent"] }│  LPUSH a2a:investment_agent:inbox
    │──────────────────────────────▶│──────────────────────────────▶│
    │                              │                               │
    │  POST /inbox/risk_agent/pop  │                               │
    │◀─────────────────────────────│ (messages adressés à toi)     │
```

**Chaque équipe est indépendante.** Le bus ne sait pas ce que chacun fait avec les messages. Personne ne se connaît directement.

---

## 2. Coordonnées du bus

| Paramètre | Valeur |
|---|---|
| URL du bus | `http://localhost:8765` |
| Transport | HTTP (pas de WebSocket, pas de gRPC) |
| Format | JSON |
| Stockage | Redis (TTL 1h par inbox) |

**Vérifier que le bus est actif :**
```bash
curl http://localhost:8765/health
# { "status": "ok", "redis": "localhost:6379", "timestamp": "..." }
```

---

## 3. Agents connus sur le bus

| Agent ID | Équipe | Ce qu'il envoie |
|---|---|---|
| `finance_agent` | StartWise CFO | `financial_analysis` (après chaque analyse) |
| `investment_agent` | StartWise CFO | `investment.recommendation` |
| `risk_agent` | Ton agent | `risk.assessment` (ou ce que tu choisis) |

> **Important :** Pour que notre `finance_agent` envoie ses analyses à ton agent, dis-nous ton URL — on ajoute une ligne dans notre `.env` et c'est automatique.

---

## 4. Endpoints du bus

### `POST /publish` — Envoyer un message

```bash
curl -X POST http://localhost:8765/publish \
  -H "Content-Type: application/json" \
  -d '{
    "message": {
      "message_id": "uuid-optionnel",
      "type": "risk.assessment",
      "from_agent": "risk_agent",
      "to": ["finance_agent", "investment_agent"],
      "timestamp": "2025-05-02T10:00:00Z",
      "context": {
        "project_id": "le-meme-project-id-recu",
        "session_id": "le-meme-session-id-recu"
      },
      "payload": { "data": { ... } }
    }
  }'
```

**Réponse :**
```json
{
  "status": "delivered",
  "message_id": "uuid",
  "from": "risk_agent",
  "routed_to": ["finance_agent", "investment_agent"],
  "timestamp": "2025-05-02T10:00:00Z"
}
```

---

### `POST /inbox/{agent_id}/pop` — Lire et consommer un message

Récupère le prochain message de ton inbox et le supprime (FIFO).

```bash
curl -X POST http://localhost:8765/inbox/risk_agent/pop
```

**Si message disponible :**
```json
{
  "agent_id": "risk_agent",
  "message": { "type": "financial_analysis", "from_agent": "finance_agent", ... }
}
```

**Si inbox vide :**
```json
{
  "agent_id": "risk_agent",
  "message": null
}
```

---

### `GET /inbox/{agent_id}` — Lire sans consommer (non-destructif)

```bash
curl http://localhost:8765/inbox/risk_agent?limit=10
```

Utile pour debugger sans perdre les messages.

---

### `POST /inbox/{agent_id}/ack/{message_id}` — Acquitter un message spécifique

```bash
curl -X POST http://localhost:8765/inbox/risk_agent/ack/uuid-du-message
```

---

### `GET /agents` — Voir tous les agents actifs sur le bus

```bash
curl http://localhost:8765/agents
# { "agents": [{ "agent_id": "finance_agent", "pending_messages": 0 }, ...] }
```

---

### `GET /log` — Historique des 500 derniers messages

```bash
curl http://localhost:8765/log?limit=20
```

---

### `DELETE /inbox/{agent_id}` — Vider l'inbox (tests uniquement)

```bash
curl -X DELETE http://localhost:8765/inbox/risk_agent
```

---

## 5. Format standard des messages

Tous les messages partagent cette structure :

```json
{
  "message_id":  "string (uuid)",
  "type":        "string — identifie le type de message",
  "from_agent":  "string — id de l'agent émetteur",
  "to":          ["liste", "des", "destinataires"],
  "timestamp":   "ISO 8601 UTC",
  "context": {
    "project_id": "string — même id pour toute la chaîne d'une analyse",
    "session_id": "string — session utilisateur"
  },
  "confidence":  0.0,
  "payload": {
    "data": { ... }
  },
  "metadata": {
    "priority": "low | medium | high",
    "tags": []
  }
}
```

> **Règle importante :** Toujours répercuter le `project_id` et `session_id` reçus dans tes réponses. C'est ce qui permet à chaque équipe de corréler les messages entre agents.

---

## 6. Message que tu recevras de notre finance_agent

**Type :** `financial_analysis`

Voici la structure complète du payload :

```json
{
  "message_id": "uuid",
  "type": "financial_analysis",
  "from_agent": "finance_agent",
  "to": ["risk_agent", "investment_agent"],
  "timestamp": "2025-05-02T10:00:00Z",
  "confidence": 0.72,
  "context": {
    "project_id": "uuid-a-repercuter",
    "session_id": "uuid-a-repercuter"
  },
  "payload": {
    "data": {
      "phase":   "SEED",
      "secteur": "SaaS B2B",
      "pays":    "TN",
      "alertes": [
        "🔴 RUNWAY CRITIQUE : 3 mois — action immédiate requise"
      ],

      "kpis": {
        "burn_net":             5000,
        "runway_months":        9.0,
        "cash_out_alert":       "ATTENTION",
        "cac":                  1200,
        "ltv":                  9600,
        "ltv_cac_ratio":        8.0,
        "ltv_cac_status":       "BON",
        "gross_margin_pct":     72.5,
        "gross_margin_status":  "BON",
        "mrr":                  9600,
        "arr":                  115200,
        "breakeven_months":     14,
        "breakeven_reachable":  true
      },

      "monte_carlo": {
        "p10":              4.5,
        "p50":              9.0,
        "p90":              14.2,
        "proba_survie_12m": 0.68,
        "proba_breakeven":  0.42,
        "mc_tightness":     0.71
      },

      "benchmarks": {
        "cac_median":            1200,
        "ltv_median":            8000,
        "churn_median":          0.03,
        "gross_margin_median":   0.70,
        "valorisation_multiple": 5.5,
        "source":                "chromadb",
        "similarity_score":      0.87
      },

      "confidence_detail": {
        "score":           0.72,
        "data_quality":    0.80,
        "mc_tightness":    0.71,
        "llm_consistency": 0.65,
        "niveau":          "ÉLEVÉ",
        "interpretation":  "Confiance élevée (72%) — projections fiables."
      }
    }
  },
  "metadata": {
    "priority": "medium",
    "tags": ["SEED", "SaaS B2B", "TN"]
  }
}
```

**Champs clés pour une analyse de risque :**

| Champ | Signification |
|---|---|
| `kpis.runway_months` | Mois avant épuisement de trésorerie |
| `kpis.cash_out_alert` | `OK` / `ATTENTION` / `CRITIQUE` |
| `kpis.ltv_cac_ratio` | Ratio LTV/CAC (< 1 = problème grave) |
| `kpis.gross_margin_pct` | Marge brute en % |
| `kpis.breakeven_months` | Mois avant break-even |
| `monte_carlo.proba_survie_12m` | Probabilité de survie à 12 mois (0–1) |
| `monte_carlo.p10` / `p90` | Fourchette pessimiste/optimiste runway |
| `confidence` | Fiabilité des données (0–1) |
| `alertes` | Liste d'alertes déjà détectées |

---

## 7. Ce que tu nous renvoies

Publie ton analyse de risque sur le bus avec `to: ["finance_agent"]` (et les autres équipes que tu veux notifier).

**Notre système accepte n'importe quel type de message** — il est classifié automatiquement par LLM. Voici le format recommandé :

```json
{
  "message_id": "uuid",
  "type": "risk.assessment",
  "from_agent": "risk_agent",
  "to": ["finance_agent", "investment_agent"],
  "timestamp": "2025-05-02T10:05:00Z",
  "context": {
    "project_id": "MEME-QUE-RECU",
    "session_id": "MEME-QUE-RECU"
  },
  "confidence": 0.80,
  "payload": {
    "data": {
      "risk_score":      0.65,
      "risk_level":      "MEDIUM",
      "main_risks": [
        "Runway < 12 mois — risque de trésorerie élevé",
        "LTV/CAC acceptable mais burn rate non soutenable",
        "Probabilité de survie 12m à 68% — sous le seuil critique (75%)"
      ],
      "mitigation":      "Lever 50 000 TND dans les 60 jours ou réduire burn de 30%",
      "recommendation":  "Procéder avec prudence — lever urgent"
    }
  },
  "metadata": {
    "priority": "high"
  }
}
```

**Champs que notre UI affiche :**

| Champ | Affiché comme |
|---|---|
| `risk_level` | Badge `LOW / MEDIUM / HIGH / CRITICAL` |
| `risk_score` | Score numérique (0–1) |
| `main_risks` | Liste de points de risque |
| `mitigation` | Recommandation textuelle |
| `recommendation` | Résumé affiché dans le panel agent |

---

## 8. Implémenter la boucle d'écoute (Python)

```python
import httpx
import time
import uuid
from datetime import datetime, timezone

BUS_URL  = "http://localhost:8765"
AGENT_ID = "risk_agent"

def listen():
    print(f"[{AGENT_ID}] Démarrage — écoute sur {BUS_URL}/inbox/{AGENT_ID}/pop")
    while True:
        try:
            r = httpx.post(f"{BUS_URL}/inbox/{AGENT_ID}/pop", timeout=10)
            r.raise_for_status()
            data = r.json()
            msg  = data.get("message")

            if msg is None:
                time.sleep(2)
                continue

            msg_type = msg.get("type", "")
            from_agent = msg.get("from_agent") or msg.get("from", "?")
            print(f"[{AGENT_ID}] Message reçu : type={msg_type} from={from_agent}")

            if msg_type == "financial_analysis":
                handle_financial_analysis(msg)
            else:
                print(f"[{AGENT_ID}] Type non géré : {msg_type} — ignoré")

        except Exception as e:
            print(f"[{AGENT_ID}] Erreur bus : {e}")
            time.sleep(5)


def handle_financial_analysis(msg: dict):
    payload   = msg.get("payload", {}).get("data", {})
    context   = msg.get("context", {})
    kpis      = payload.get("kpis", {})
    mc        = payload.get("monte_carlo", {})

    # ── Ton pipeline d'analyse risk ici ──────────────────────────────────────
    risk_score = compute_risk_score(kpis, mc)
    risk_level = score_to_level(risk_score)
    risks      = detect_risks(kpis, mc)
    mitigation = generate_mitigation(risks)
    # ─────────────────────────────────────────────────────────────────────────

    response = {
        "message_id": str(uuid.uuid4()),
        "type":        "risk.assessment",
        "from_agent":  AGENT_ID,
        "to":          ["finance_agent"],   # + autres agents si besoin
        "timestamp":   datetime.now(timezone.utc).isoformat(),
        "context": {
            "project_id": context.get("project_id", ""),
            "session_id": context.get("session_id", ""),
        },
        "confidence": risk_score,
        "payload": {
            "data": {
                "risk_score":     risk_score,
                "risk_level":     risk_level,
                "main_risks":     risks,
                "mitigation":     mitigation,
                "recommendation": f"Niveau de risque {risk_level} — {mitigation}",
            }
        },
        "metadata": {
            "priority": "high" if risk_level in ("HIGH", "CRITICAL") else "medium"
        }
    }

    r = httpx.post(f"{BUS_URL}/publish", json={"message": response}, timeout=10)
    r.raise_for_status()
    print(f"[{AGENT_ID}] Réponse publiée → {response['to']}")


# ── Fonctions à implémenter par linaa ────────────────────────────────────

def compute_risk_score(kpis: dict, mc: dict) -> float:
    # Exemple simple — à remplacer par ton modèle
    runway  = kpis.get("runway_months", 12)
    survie  = mc.get("proba_survie_12m", 0.5)
    margin  = kpis.get("gross_margin_pct", 50) / 100
    return round(1 - (0.4 * min(runway / 18, 1) + 0.4 * survie + 0.2 * margin), 2)

def score_to_level(score: float) -> str:
    if score >= 0.80: return "CRITICAL"
    if score >= 0.60: return "HIGH"
    if score >= 0.40: return "MEDIUM"
    return "LOW"

def detect_risks(kpis: dict, mc: dict) -> list:
    risks = []
    if kpis.get("runway_months", 99) < 6:
        risks.append(f"Runway critique : {kpis['runway_months']} mois")
    if mc.get("proba_survie_12m", 1) < 0.5:
        risks.append(f"Probabilité de survie à 12 mois : {mc['proba_survie_12m']:.0%}")
    if kpis.get("ltv_cac_ratio", 99) < 1:
        risks.append("LTV/CAC < 1 : modèle économique non rentable")
    return risks or ["Aucun risque critique détecté"]

def generate_mitigation(risks: list) -> str:
    if not risks or risks[0].startswith("Aucun"):
        return "Continuer le monitoring habituel"
    return "Réduire le burn rate et accélérer la levée de fonds"


if __name__ == "__main__":
    listen()
```

---

## 9. Exposer ton Agent Card (recommandé)

Si tu as un serveur FastAPI, expose cet endpoint pour que les autres équipes te découvrent automatiquement :

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/.well-known/agent.json")
def agent_card():
    return {
        "id":           "risk_agent",
        "name":         "Risk Analysis Agent",
        "version":      "1.0",
        "description":  "Analyse les risques financiers d'une startup",
        "skills":       ["risk_analysis", "risk_scoring", "mitigation_planning"],
        "input_modes":  ["data"],
        "output_modes": ["data", "text"],
        "bus_inbox":    "a2a:risk_agent:inbox"
    }
```

---

## 10. Checklist d'intégration

```
[ ] Bus accessible : GET http://localhost:8765/health → { "status": "ok" }
[ ] Inbox vide au départ : POST /inbox/risk_agent/pop → { "message": null }
[ ] Envoyer un message test vers finance_agent
[ ] Vérifier réception : GET /inbox/finance_agent (non-destructif)
[ ] Recevoir financial_analysis depuis finance_agent
[ ] Publier risk.assessment en retour avec le même project_id + session_id
[ ] Vérifier dans GET /log que le message apparaît bien
```

---

## 11. Tester sans l'équipe StartWise (mode offline)

Tu peux te publier un `financial_analysis` fictif à toi-même pour tester ton pipeline :

```bash
curl -X POST http://localhost:8765/publish \
  -H "Content-Type: application/json" \
  -d '{
    "message": {
      "type": "financial_analysis",
      "from_agent": "finance_agent",
      "to": ["risk_agent"],
      "context": { "project_id": "test-001", "session_id": "sess-001" },
      "confidence": 0.55,
      "payload": {
        "data": {
          "phase": "SEED",
          "secteur": "SaaS B2B",
          "pays": "TN",
          "alertes": ["🔴 RUNWAY CRITIQUE : 3 mois"],
          "kpis": {
            "burn_net": 8000,
            "runway_months": 3.5,
            "cash_out_alert": "CRITIQUE",
            "ltv_cac_ratio": 0.8,
            "gross_margin_pct": 45.0,
            "mrr": 4000,
            "breakeven_months": 24,
            "breakeven_reachable": false
          },
          "monte_carlo": {
            "p10": 1.5,
            "p50": 3.5,
            "p90": 6.0,
            "proba_survie_12m": 0.28,
            "proba_breakeven": 0.12,
            "mc_tightness": 0.45
          }
        }
      }
    }
  }'
```

Ensuite consomme depuis ton inbox :

```bash
curl -X POST http://localhost:8765/inbox/risk_agent/pop
```

---

## 12. Contact

Pour nous signaler ton URL et port :

- Notre `finance_agent` t'enverra automatiquement les `financial_analysis` dès qu'on ajoute `RISK_AGENT_URL=http://localhost:<ton-port>` dans notre `.env`
- Notre inbox pour recevoir tes réponses : `finance_agent` → `to: ["finance_agent"]`
