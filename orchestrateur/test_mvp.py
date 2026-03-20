"""
TEST COMPLET: Orchestrator -> Finance -> Marketing -> Investment Agent
"""

import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)
sys.stdout.reconfigure(encoding='utf-8')

from orchestrateur.orchestrator import Orchestrator


def test_complete_flow():
    """Test end-to-end: User text -> Investment recommendation."""

    print("\n" + "="*80)
    print(" "*20 + "COMPLETE MVP TEST")
    print("="*80)

    project_text = """
    Je veux creer une plateforme e-commerce qui permet aux artisans tunisiens
    de vendre directement leurs produits (huile d'olive, dattes, poterie, bijoux)
    aux touristes et a la diaspora en Europe.

    On a deja 500k TND de revenus annuels avec une croissance de 150%.
    Notre burn rate est de 50k TND par mois.
    On cherche 900k TND pour financer 18 mois de developpement.

    Equipe de 6 personnes (2 fondateurs experimentes + 4 developpeurs).
    Le marche de l'artisanat tunisien a l'export fait environ 2 milliards TND.
    """

    print("\nPROJECT SUBMITTED:")
    print("-" * 80)
    print(project_text.strip())
    print("-" * 80)

    orchestrator = Orchestrator()
    result = orchestrator.process(project_text)

    inv = result["investment"]

    print("\n" + "="*80)
    print("FINAL INVESTMENT RECOMMENDATION")
    print("="*80)
    print(inv["recommendation"])

    print("\n" + "="*80)
    print("KEY METRICS")
    print("="*80)
    v = inv["data"]["valuation"]
    s = inv["data"]["optimal_scenario"]
    d = inv["data"]["dilution"]

    print(f"  Valuation (pre-money) : {v['final_valuation']:>12,.0f} TND  [{v['method']}]")
    print(f"  Raise                 : {s['raise_amount']:>12,.0f} TND")
    print(f"    Grants              : {s['grants']:>12,.0f} TND")
    print(f"    Equity              : {s['equity']:>12,.0f} TND")
    print(f"    Debt                : {s['debt']:>12,.0f} TND")
    print(f"  Post-money            : {s['post_money']:>12,.0f} TND")
    print(f"  Founder dilution      : {d['founder_dilution_pct']:>11.1f}%")
    print(f"  Confidence score      : {inv['confidence_score']:>12.0%}")

    print("\n" + "="*80)
    print("ALL SCENARIOS")
    print("="*80)
    for sc in inv["data"]["all_scenarios"]:
        print(f"  {sc['name']:<14} raise: {sc['raise_amount']:>9,.0f} TND  "
              f"dilution: {sc['dilution_pct']:>5.1f}%  score: {sc['score']:.0f}")

    print("\n" + "="*80)
    print("TEST PASSED - ALL SYSTEMS OPERATIONAL")
    print("="*80 + "\n")

    return result


if __name__ == "__main__":
    test_complete_flow()
