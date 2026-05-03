"""
a2a_bus/run_mocks.py
====================
Lance les agents simulés en mode continu.
Ils écoutent leurs inboxes et répondent automatiquement dès qu'un message arrive.

Lancer :
    python -m a2a_bus.run_mocks                   # mock investment + mock risk
    python -m a2a_bus.run_mocks --real-investment  # real InvestmentAgent + mock risk
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
import threading

import redis

from a2a_bus.dev.mock_agents import MockInvestmentAgent

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

REDIS_HOST    = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT    = int(os.getenv("REDIS_PORT", "6379"))
BRPOP_TIMEOUT = 5


class ContinuousMockAgent:
    """
    Wrapper qui fait tourner un mock agent en boucle BRPOP.
    Réveillé instantanément dès qu'un message arrive dans Redis.
    """

    def __init__(self, mock):
        self.mock  = mock
        self._r    = redis.Redis(
            host=REDIS_HOST, port=REDIS_PORT, db=0,
            decode_responses=True,
        )
        self._inbox_key = f"a2a:{mock.AGENT_ID}:inbox"

    def run(self):
        logger.info("[%s] démarré — écoute %s", self.mock.AGENT_ID, self._inbox_key)
        while True:
            try:
                result = self._r.brpop(self._inbox_key, timeout=BRPOP_TIMEOUT)
                if result is None:
                    continue

                _, raw = result
                msg = json.loads(raw)

                if msg.get("type") != "financial_analysis":
                    logger.debug("[%s] type ignoré : %s", self.mock.AGENT_ID, msg.get("type"))
                    continue

                logger.info(
                    "[%s] reçu financial_analysis (id=%s…)",
                    self.mock.AGENT_ID, msg.get("message_id", "?")[:8],
                )

                # BRPOP a déjà consommé le message — traiter directement, pas d'ACK
                if isinstance(self.mock, MockInvestmentAgent):
                    response = self.mock._score(msg)
                else:
                    response = self.mock._assess(msg)

                self.mock.client.publish_raw(response)
                data = response.get("payload", {}).get("data", {})
                if "rating" in data:
                    logger.info(
                        "[%s] répondu → %s (score %s/100)",
                        self.mock.AGENT_ID, data["rating"], data["score"],
                    )
                elif "risk_level" in data:
                    logger.info(
                        "[%s] répondu → risque %s (score %s/100)",
                        self.mock.AGENT_ID, data["risk_level"], data["risk_score"],
                    )

            except redis.exceptions.ConnectionError:
                logger.error("[%s] Redis déconnecté — retry dans 3s", self.mock.AGENT_ID)
                time.sleep(3)
            except Exception as e:
                logger.exception("[%s] erreur : %s", self.mock.AGENT_ID, e)


def main():
    use_real_investment = "--real-investment" in sys.argv

    print("=" * 55)
    if use_real_investment:
        print("  Real InvestmentAgent on A2A bus")
    else:
        print("  Mock InvestmentAgent on A2A bus")
    print("  Ctrl+C pour arreter")
    print("=" * 55)

    if use_real_investment:
        from finagents.investment.bus_adapter import get_investment_bus_adapter
        get_investment_bus_adapter()
        print("  [investment_agent] real agent started")
    else:
        inv_runner = ContinuousMockAgent(MockInvestmentAgent())
        t_inv = threading.Thread(target=inv_runner.run, name="mock-investment", daemon=True)
        t_inv.start()
        print("  [investment_agent] mock agent started")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nAgents arretes.")


if __name__ == "__main__":
    main()
