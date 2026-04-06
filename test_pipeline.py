"""
End-to-end pipeline test — simple example.
Run from workspace root: python test_pipeline.py
"""

import sys
sys.stdout.reconfigure(encoding='utf-8')

from orchestrateur.orchestrator import Orchestrator

# ── Simple startup example ──────────────────────────────────────────────────
PROJECT_TEXT = """
Je veux creer une plateforme qui connecte les agriculteurs tunisiens directement
aux acheteurs en Europe pour vendre leurs produits bio (huile d'olive, dattes, harissa).
j ai 15,000 TND comme revenu, on est en phase de validation.
Burn rate de 15,000 TND par mois.
On a besoin de 300,000 TND pour construire le MVP et valider le marche.
Equipe de 3 personnes (1 fondateur agricole + 2 developpeurs).
Le marche export agricole tunisien depasse 3 milliards TND par an.
"""

def main():
    orchestrator = Orchestrator()
    # Fixed IDs so memory tracks this project across runs
    result = orchestrator.process(PROJECT_TEXT, user_id="user_001", project_id="agritech_demo")

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

    # Show progress report if this is not the first session
    if inv.get("progress_report"):
        print("\n" + "="*65)
        print("  PROGRESS SINCE LAST SESSION")
        print("="*65)
        print(inv["progress_report"])

if __name__ == "__main__":
    main()
