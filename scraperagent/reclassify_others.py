"""
Re-classify 'other' records using name-only prompt (stronger context).
Updates the enriched CSV in place.
"""

import sys, os, csv, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

TOKENFACTORY_API_KEY = "sk-f042a9ed44984cac8447e241e8a86791"
BASE_URL             = "https://tokenfactory.esprit.tn/api"
MODEL_NAME           = "hosted_vllm/Llama-3.1-70B-Instruct"

ENRICHED_FILE = "data/tunisia_labeled_startups_enriched.csv"

VALID_SECTORS = [
    "fintech", "ecommerce", "marketplace", "saas", "tech",
    "healthtech", "edtech", "agritech", "cleantech", "artisanat",
    "logistics", "travel", "food", "retail", "other"
]

DELAY = 0.5


SYSTEM_PROMPT = (
    "You are an expert at classifying Tunisian startups by sector.\n"
    "You will receive a startup name (may be Arabic, French, or English).\n"
    "Infer the most likely sector from the name meaning, keywords, or context.\n\n"
    'Return ONLY a JSON object like: {"sector": "<sector>", "confidence": "high|medium|low"}\n\n'
    "Valid sectors: fintech, ecommerce, marketplace, saas, tech, healthtech, edtech, "
    "agritech, cleantech, artisanat, logistics, travel, food, retail, other\n\n"
    "Examples:\n"
    '- "Nqollek Haja" (Arabic: deliver something) -> {"sector": "logistics", "confidence": "medium"}\n'
    '- "Tunisia Baits" (fishing bait) -> {"sector": "retail", "confidence": "high"}\n'
    '- "KICK LIGHT" (lighting) -> {"sector": "cleantech", "confidence": "medium"}\n'
    '- "Drest.tn" (dress) -> {"sector": "ecommerce", "confidence": "high"}\n'
    '- "Black Dune Studio" (studio) -> {"sector": "tech", "confidence": "medium"}\n'
    '- "auto-plus" (auto) -> {"sector": "marketplace", "confidence": "medium"}\n\n'
    "No markdown, no explanation. JSON only."
)


def build_llm():
    return ChatOpenAI(
        model=MODEL_NAME, base_url=BASE_URL, api_key=TOKENFACTORY_API_KEY,
        temperature=0.0, max_tokens=100,
    )


def classify(llm, name: str, website: str) -> dict:
    try:
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=f"Startup name: {name}\nWebsite hint: {website}")
        ]
        response = llm.invoke(messages)
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1].lstrip("json").strip()
        result = json.loads(content)
        sector = result.get("sector", "other").lower()
        if sector not in VALID_SECTORS:
            sector = "other"
        return {"sector": sector, "confidence": result.get("confidence", "low")}
    except Exception as e:
        print(f"    [!] Error for '{name}': {type(e).__name__}")
        return {"sector": "other", "confidence": "low"}


def main():
    print("\n" + "="*60)
    print("RE-CLASSIFY 'OTHER' RECORDS")
    print("="*60)

    # Load enriched file
    rows = []
    with open(ENRICHED_FILE, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            rows.append(row)

    others = [r for r in rows if r["sector"] == "other"]
    print(f"\nFound {len(others)} 'other' records to re-classify")

    llm    = build_llm()

    improved = 0
    for i, row in enumerate(others, 1):
        name    = row["name"]
        website = row["website"]

        # Skip null websites — use name only
        if "null" in website or not website:
            website = "(no website)"

        result = classify(llm, name, website)
        time.sleep(DELAY)

        old_sector = row["sector"]
        row["sector"]     = result["sector"]
        row["confidence"] = result["confidence"]

        if result["sector"] != "other":
            improved += 1

        if i % 20 == 0 or i == len(others):
            try:
                print(f"  [{i}/{len(others)}] '{name}' -> {result['sector']} ({result['confidence']})")
            except UnicodeEncodeError:
                print(f"  [{i}/{len(others)}] [name has special chars] -> {result['sector']} ({result['confidence']})")

    # Write back
    with open(ENRICHED_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # Final stats
    remaining_other = sum(1 for r in rows if r["sector"] == "other")
    print(f"\nImproved  : {improved}/{len(others)} records reclassified away from 'other'")
    print(f"Still other: {remaining_other} (truly unclassifiable)")
    print(f"\nDONE: {ENRICHED_FILE} updated in place")


if __name__ == "__main__":
    main()
