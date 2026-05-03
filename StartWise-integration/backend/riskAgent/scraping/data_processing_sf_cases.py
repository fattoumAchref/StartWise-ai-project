import json
import re
from riskAgent.config.llm_client import create_llm_client

# =========================================================
# LABEL SPACE
# =========================================================
CAUSES = [
    "market",
    "funding",
    "competition",
    "execution",
    "product",
    "legal",
    "unit_economics",
    "technical_dependency",
    "team",
    "bad_timing"
]

# =========================================================
# LLM CLIENT
# =========================================================
def query_llm(prompt):
    client, model_name = create_llm_client()

    response = client.chat.completions.create(
        model=model_name,
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )

    return response.choices[0].message.content

def has_useful_details(details):
    if not details:
        return False

    # check si AU MOINS un champ utile existe
    useful_fields = [
        "category",
        "country",
        "started",
        "closed",
        "funding_total",
        "content",
        "industry",
        "founder"
    ]

    for f in useful_fields:
        value = details.get(f, "")
        if value and str(value).strip():
            return True

    return False

def remove_known_noise(text):
    if not text:
        return ""

    text = re.sub(
        r"Ad\s+Don't be the average security professional.*?Join 40,000\+ founders\.",
        "",
        text,
        flags=re.IGNORECASE | re.DOTALL
    )

    text = re.sub(
        r"90% of startups fail\..*?Growth\.",
        "",
        text,
        flags=re.IGNORECASE | re.DOTALL
    )

    return text.strip()


def clean_text(text):
    if not text:
        return ""

    text = remove_known_noise(text)

    # normalize whitespace
    text = re.sub(r"\n+", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


# =========================================================
# TEXT BUILDER (CRITICAL FIX)
# =========================================================
def build_text(item):
    details = item.get("details", {})

    summary = item.get("summary", "")
    content = details.get("content", "")

    text = summary if summary else content

    return clean_text(text)


# =========================================================
# LLM LABELING
# =========================================================
def label_startup(description):

    prompt = f"""
You analyze why startups fail.

Startup description:
{description}

Choose ONLY from:
{CAUSES}

Rules:
- return ONLY valid JSON array
- max 4 labels
- if unclear: ["other"]
- no explanation

Return:
["cause1", "cause2"]
"""

    raw = query_llm(prompt)

    try:
        start = raw.find("[")
        end = raw.rfind("]") + 1
        return json.loads(raw[start:end])
    except:
        return ["other"]


# =========================================================
# PROCESS ONE ITEM
# =========================================================
def process_item(item):

    details = item.get("details", {})

    text = build_text(item)

    if not text:
        return None

    causes = label_startup(text)

    return {
        "startup": item.get("startup", ""),
        "sector": details.get("category", ""),
        "country": details.get("country", ""),
        "funding": details.get("funding_total", ""),
        "cause": causes,
        "description": text,
        "founded": details.get("started", ""),
        "closed": details.get("closed", "")
    }


# =========================================================
# MAIN PIPELINE
# =========================================================
def run(input_file=".\data\startup_failure_cases.json",
        output_file=".\data\startup_failure_cases_cleaned.json"):

    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    results = []

    total = len(data)
    rejected_no_details = 0
    rejected_empty_text = 0

    for item in data:

        details = item.get("details", {})

        # -------------------------
        # FIXED FILTER
        # -------------------------
        if not has_useful_details(details):
            rejected_no_details += 1
            continue

        text = build_text(item)

        if not text or len(text) < 50:
            rejected_empty_text += 1
            continue

        print(f"[PROCESSING] {item.get('startup')}")

        causes = label_startup(text)

        results.append({
            "startup": item.get("startup", ""),
            "sector": details.get("category", ""),
            "country": details.get("country", ""),
            "funding": details.get("funding_total", ""),
            "cause": causes,
            "description": text,
            "founded": details.get("started", ""),
            "closed": details.get("closed", "")
        })

    # -------------------------
    # STATS
    # -------------------------
    kept = len(results)
    rejected_total = total - kept

    print("\n========== DATASET STATS ==========")
    print(f"Total: {total}")
    print(f"Kept: {kept}")
    print(f"Rejected: {rejected_total}")
    print(f"  - No useful details: {rejected_no_details}")
    print(f"  - Empty text: {rejected_empty_text}")
    print("==================================\n")

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({"structured_data": results}, f, indent=2, ensure_ascii=False)

    print(f"[DONE] Clean dataset saved → {output_file}")


if __name__ == "__main__":
    run()