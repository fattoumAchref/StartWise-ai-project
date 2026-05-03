import requests
from bs4 import BeautifulSoup, Tag
import json
import time
import re

BASE_URL = "https://www.failory.com"
START_URL = "https://www.failory.com/failures"
OUTPUT_FILE = ".\data\startup_failure_scores.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


# =========================================================
# STEP 1 → GET CATEGORY LINKS
# =========================================================
def get_category_links():
    soup = BeautifulSoup(requests.get(START_URL, headers=HEADERS).text, "html.parser")

    links = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]

        if "/startups/" in href:
            if href.startswith("/"):
                href = BASE_URL + href

            links.add(href)

    return list(links)


# =========================================================
# STEP 2 → SCRAPE CATEGORY PAGE
# =========================================================
def scrape_category(url):
    soup = BeautifulSoup(requests.get(url, headers=HEADERS).text, "html.parser")

    startups = []

    for tag in soup.find_all(["h2", "h3"]):
        name = tag.get_text(strip=True)

        if len(name) < 3 or "Failed Startups" in name:
            continue

        block = ""
        detail_url = None

        for sibling in tag.next_siblings:

            if not isinstance(sibling, Tag):
                continue

            if sibling.name in ["h2", "h3"]:
                break

            text = sibling.get_text(" ", strip=True)
            if text:
                block += text + "\n"

            link = sibling.find("a", href=True)
            if link:
                href = link["href"]

                if href.startswith("/"):
                    href = BASE_URL + href

                if any(x in href for x in ["/cemetery/", "/interview/"]):
                    detail_url = href

        if len(block) < 50:
            continue

        cause_match = re.search(r"Specific cause of failure:\s*(.*)", block)
        funding_match = re.search(r"Funding Amount:\s*(.*)", block)

        startups.append({
            "startup": name,
            "summary": block.strip(),
            "cause": cause_match.group(1).strip() if cause_match else "",
            "funding": funding_match.group(1).strip() if funding_match else "",
            "detail_url": detail_url,
            "category_url": url
        })

    return startups


# =========================================================
# HELPERS
# =========================================================
def extract_field(text, field):
    pattern = rf"{field}:\s*\n?\s*(.*)"
    match = re.search(pattern, text)
    return match.group(1).strip() if match else ""

def extract_category_from_url(category_url):
    if not category_url:
        return ""

    match = re.search(r"/startups/([a-z0-9-]+)-failures", category_url)

    if match:
        return match.group(1).strip()

    return ""

def extract_details_from_category_page(category_url, startup_name):
    try:
        soup = BeautifulSoup(requests.get(category_url, headers=HEADERS).text, "html.parser")

        for tag in soup.find_all(["h2", "h3"]):
            name = tag.get_text(strip=True)

            if name != startup_name:
                continue

            details_started = False
            details_lines = []

            for sibling in tag.next_siblings:
                if not isinstance(sibling, Tag):
                    continue

                if sibling.name in ["h2", "h3"]:
                    break

                text = sibling.get_text(" ", strip=True)

                if not text:
                    continue

                # detect start of structured section
                if "Details of the startup" in text:
                    details_started = True
                    continue

                if details_started:
                    # stop when reaching end sentence
                    if "read more" in text.lower():
                        break

                    details_lines.append(text)

            # 🔥 PARSE LINE BY LINE
            # 🔥 JOIN ALL TEXT INTO ONE STRING
            full_text = " ".join(details_lines)
            full_text = re.sub(r"\s+", " ", full_text)

            data = {
                "category": "",
                "country": "",
                "started": "",
                "closed": "",
                "cause_detailed": "",
                "funding_total": "",
                "founder": "",
                "industry": "",
                "content": full_text
            }

            def extract_between(start, end_list, text):
                pattern = rf"{start}:\s*(.*?)(?={'|'.join(end_list)}:|$)"
                match = re.search(pattern, text)
                return match.group(1).strip() if match else ""

            fields = ["Founder", "Country", "Industry", "Started in", "Closed in", "Funding Amount", "Specific cause of failure"]

            data["founder"] = extract_between("Founder", fields, full_text)
            data["country"] = extract_between("Country", fields, full_text)
            data["industry"] = extract_between("Industry", fields, full_text)
            data["started"] = extract_between("Started in", fields, full_text)
            data["closed"] = extract_between("Closed in", fields, full_text)
            data["funding_total"] = extract_between("Funding Amount", fields, full_text)
            data["cause_detailed"] = extract_between("Specific cause of failure", fields, full_text)
            data["category"] = extract_category_from_url(category_url)

            return data

        return {}

    except Exception as e:
        print("Error:", e)
        return {}


# =========================================================
# STEP 3 → SCRAPE DETAIL PAGE (cemetery only)
# =========================================================
def scrape_details(url):
    try:
        soup = BeautifulSoup(requests.get(url, headers=HEADERS).text, "html.parser")

        text = soup.get_text("\n")

        data = {
            "category": extract_field(text, "Category"),
            "country": extract_field(text, "Country"),
            "started": extract_field(text, "Started"),
            "closed": extract_field(text, "Closed"),
            "cause_detailed": extract_field(text, "Cause"),
            "funding_total": extract_field(text, "Total Funding Amount")
        }

        paragraphs = soup.find_all("p")
        clean_text = "\n".join(p.get_text(strip=True) for p in paragraphs)

        data["content"] = clean_text

        return data

    except Exception:
        return {}


# =========================================================
# MAIN PIPELINE
# =========================================================
def run():
    all_data = []
    seen = set()

    categories = get_category_links()
    print(f"[INFO] Found {len(categories)} categories")

    for cat_url in categories:
        print(f"[INFO] Category: {cat_url}")

        startups = scrape_category(cat_url)

        for s in startups:
            name = s["startup"]

            if name in seen:
                continue
            seen.add(name)

            if s["detail_url"]:
                if "/interview/" in s["detail_url"]:
                    # 👉 CORRECT: re-scrape from category page
                    s["details"] = extract_details_from_category_page(
                        s["category_url"],
                        s["startup"]
                    )
                else:
                    print(f"   → scraping details: {s['detail_url']}")
                    s["details"] = scrape_details(s["detail_url"])
                    time.sleep(1)
            else:
                s["details"] = ""

            all_data.append(s)

        time.sleep(1)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_data, f, indent=2, ensure_ascii=False)

    print(f"[DONE] {len(all_data)} startups saved in {OUTPUT_FILE}.")


if __name__ == "__main__":
    run()