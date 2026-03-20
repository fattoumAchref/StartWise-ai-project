"""
Startup Enrichment Script
Reads tunisia_labeled_startups_2026.csv, classifies each startup's sector
using the LLM, and outputs an enriched CSV ready for the investment agent.
"""

import sys
import os
import csv
import json
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

# ── Config ────────────────────────────────────────────────────────────────────
TOKENFACTORY_API_KEY = "sk-f042a9ed44984cac8447e241e8a86791"
BASE_URL             = "https://tokenfactory.esprit.tn/api"
MODEL_NAME           = "hosted_vllm/Llama-3.1-70B-Instruct"

INPUT_FILE  = "data/tunisia_labeled_startups_2026.csv"
OUTPUT_FILE = "data/tunisia_labeled_startups_enriched.csv"

# Allowed sectors (must match investment agent config)
VALID_SECTORS = [
    "fintech", "ecommerce", "marketplace", "saas", "tech",
    "healthtech", "edtech", "agritech", "cleantech", "artisanat",
    "logistics", "travel", "food", "retail", "other"
]

# How many startups to process (set to None for all 932)
LIMIT = None  # process all 930

# Delay between LLM calls in seconds (avoid rate limiting)
DELAY = 0.5
# ─────────────────────────────────────────────────────────────────────────────


def build_llm():
    return ChatOpenAI(
        model=MODEL_NAME,
        base_url=BASE_URL,
        api_key=TOKENFACTORY_API_KEY,
        temperature=0.0,
        max_tokens=100,
    )


def build_prompt():
    return ChatPromptTemplate.from_messages([
        ("system", f"""You are a startup sector classifier.
Given a startup name and website URL, return ONLY a JSON object with two keys:
- "sector": one of {VALID_SECTORS}
- "confidence": "high", "medium", or "low"

Rules:
- Choose the single best matching sector
- Use "other" only if nothing fits
- Return ONLY valid JSON, no explanation, no markdown"""),
        ("user", "Startup name: {name}\nWebsite: {website}")
    ])


def classify_startup(llm, prompt, name: str, website: str) -> dict:
    """Call LLM to classify one startup. Returns sector + confidence."""
    try:
        chain = prompt | llm
        response = chain.invoke({"name": name, "website": website})
        content = response.content.strip()

        # Strip markdown if present
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        content = content.strip()

        result = json.loads(content)

        sector = result.get("sector", "other").lower()
        if sector not in VALID_SECTORS:
            sector = "other"

        return {
            "sector": sector,
            "confidence": result.get("confidence", "low")
        }

    except Exception as e:
        print(f"    [!] LLM error for '{name}': {e}")
        return {"sector": "other", "confidence": "low"}


def infer_sector_from_url(website: str) -> str:
    """
    Quick keyword-based fallback before calling LLM.
    Saves API calls for obvious cases.
    """
    url = website.lower()
    keyword_map = {
        "fintech":   ["pay", "finance", "bank", "credit", "loan", "wallet", "fintech"],
        "healthtech":["health", "med", "doctor", "clinic", "pharma", "care", "dental"],
        "edtech":    ["learn", "edu", "school", "academy", "cours", "teach", "code"],
        "ecommerce": ["shop", "store", "market", "buy", "sell", "commerce"],
        "agritech":  ["farm", "agri", "food", "crop", "harvest", "green"],
        "logistics": ["deliver", "logis", "transport", "cargo", "ship", "fleet"],
        "travel":    ["travel", "trip", "tour", "hotel", "booking"],
        "artisanat": ["artisan", "handmade", "craft", "fouta", "pottery"],
        "cleantech": ["solar", "energy", "clean", "eco", "green", "water"],
    }
    for sector, keywords in keyword_map.items():
        if any(kw in url for kw in keywords):
            return sector
    return None


def load_input(path: str) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8-sig") as f:  # utf-8-sig strips BOM automatically
        # Skip any blank lines before the header
        lines = [line for line in f if line.strip()]
    
    reader = csv.DictReader(lines)
    for row in reader:
        name    = row.get("Name", "").strip()
        website = row.get("Website", "").strip()
        year    = row.get("Year Founded", "").strip()
        label   = row.get("Label Date", "").strip()
        if name:
            rows.append({
                "name":         name,
                "website":      website,
                "year_founded": year,
                "label_date":   label,
            })
    return rows


def save_output(path: str, rows: list[dict]):
    fieldnames = [
        "name", "sector", "confidence",
        "has_startup_act_label",
        "year_founded", "label_date", "website"
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    print("\n" + "="*70)
    print("STARTUP ENRICHMENT AGENT")
    print("="*70)

    # Load
    print(f"\n[1/4] Loading {INPUT_FILE}...")
    startups = load_input(INPUT_FILE)
    total = len(startups)
    print(f"      OK {total} startups loaded")

    if LIMIT:
        startups = startups[:LIMIT]
        print(f"      → Processing first {LIMIT} (LIMIT set)")

    # Build LLM
    print("\n[2/4] Connecting to LLM...")
    llm    = build_llm()
    prompt = build_prompt()
    print("      OK LLM ready")

    # Classify
    print(f"\n[3/4] Classifying {len(startups)} startups...")
    results = []
    skipped_by_keyword = 0

    for i, s in enumerate(startups, 1):
        name    = s["name"]
        website = s["website"]

        # Try keyword shortcut first
        quick = infer_sector_from_url(website)
        if quick:
            sector     = quick
            confidence = "medium"
            skipped_by_keyword += 1
        else:
            # Call LLM
            classified = classify_startup(llm, prompt, name, website)
            sector     = classified["sector"]
            confidence = classified["confidence"]
            time.sleep(DELAY)

        results.append({
            "name":                 name,
            "sector":               sector,
            "confidence":           confidence,
            "has_startup_act_label": True,
            "year_founded":         s["year_founded"],
            "label_date":           s["label_date"],
            "website":              website,
        })

        # Progress every 20
        if i % 20 == 0 or i == len(startups):
            print(f"      [{i}/{len(startups)}] last: {name} → {sector}")

    # Stats
    sector_counts = {}
    for r in results:
        sector_counts[r["sector"]] = sector_counts.get(r["sector"], 0) + 1

    # Save
    print(f"\n[4/4] Saving to {OUTPUT_FILE}...")
    save_output(OUTPUT_FILE, results)
    print(f"      OK {len(results)} records saved")

    # Summary
    print("\n" + "="*70)
    print("ENRICHMENT COMPLETE")
    print("="*70)
    print(f"\nTotal processed : {len(results)}")
    print(f"Keyword-inferred: {skipped_by_keyword} (no LLM call needed)")
    print(f"LLM-classified  : {len(results) - skipped_by_keyword}")
    print("\nSector breakdown:")
    for sector, count in sorted(sector_counts.items(), key=lambda x: -x[1]):
        bar = "#" * (count // 3)
        print(f"  {sector:<15} {count:>4}  {bar}")

    print(f"\nDONE: Output ready: {OUTPUT_FILE}")
    print("   -> You can now use this file in your investment agent\n")


if __name__ == "__main__":
    main()
