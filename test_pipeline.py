"""
End-to-end pipeline test — simple example.
Run from workspace root: python test_pipeline.py
"""

import sys
sys.stdout.reconfigure(encoding='utf-8')

from orchestrateur.orchestrator import Orchestrator

# ── Simple startup example ──────────────────────────────────────────────────
PROJECT_TEXT = """
I want to build a fintech platform for SME invoice financing in Tunisia.
We already have 120,000 TND annual revenue with 80% growth.
Monthly burn rate is 30,000 TND.
We need 600,000 TND to fund 18 months of development.
Team of 4 people (2 experienced founders + 2 developers).
The SME financing market in Tunisia is around 8 billion TND.
"""

def main():
    orchestrator = Orchestrator()
    result = orchestrator.process(PROJECT_TEXT)

    inv = result["investment"]

    print("\n" + "="*65)
    print("  FINAL INVESTMENT RECOMMENDATION")
    print("="*65)
    print(inv["recommendation"])

    print("\n" + "="*65)
    print("  KEY NUMBERS")
    print("="*65)
    v  = inv["data"]["valuation"]
    s  = inv["data"]["optimal_scenario"]
    d  = inv["data"]["dilution"]
    print(f"  Valuation (pre-money) : {v['final_valuation']:>12,.0f} TND  [{v['method']}]")
    print(f"  Raise                 : {s['raise_amount']:>12,.0f} TND")
    print(f"    Grants              : {s['grants']:>12,.0f} TND")
    print(f"    Equity              : {s['equity']:>12,.0f} TND")
    print(f"    Debt                : {s['debt']:>12,.0f} TND")
    print(f"  Post-money            : {s['post_money']:>12,.0f} TND")
    print(f"  Founder dilution      : {d['founder_dilution_pct']:>11.1f}%")
    print(f"  Confidence score      : {inv['confidence_score']:>12.0%}")

    print("\n" + "="*65)
    print("  ALL SCENARIOS")
    print("="*65)
    for sc in inv["data"]["all_scenarios"]:
        print(f"  {sc['name']:<14} raise: {sc['raise_amount']:>9,.0f} TND  "
              f"dilution: {sc['dilution_pct']:>5.1f}%  score: {sc['score']:.0f}")

if __name__ == "__main__":
    main()
