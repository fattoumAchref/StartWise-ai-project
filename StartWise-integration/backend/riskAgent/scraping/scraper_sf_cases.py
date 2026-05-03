import json
import re
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

SITE1_URL = "https://www.loot-drop.io/database-view"
OUTPUT_FILE = ".\data\startup_failure_cases.json"


def clean_money(value):
    if not value:
        return 0

    value = value.replace("$", "").replace(",", "").strip().upper()

    try:
        if "B" in value:
            return float(value.replace("B", "")) * 1e9
        elif "M" in value:
            return float(value.replace("M", "")) * 1e6
        elif "K" in value:
            return float(value.replace("K", "")) * 1e3
        else:
            return float(value)
    except:
        return 0


def extract_percentage(style):
    if not style:
        return None

    match = re.search(r"width:\s*(\d+)%", style)
    if match:
        return float(match.group(1)) / 100

    return None


def scrape_site1():

    print("[INFO] Launching browser...")

    options = Options()
    #options.add_argument("--headless")  # enlève si tu veux voir le navigateur
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=options)
    driver.get(SITE1_URL)

    print("[INFO] Waiting for page to load...")
 
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CLASS_NAME, "db-score-fill"))
    )
    
    data = []

    while True:

        print("[INFO] Scraping current page...")

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "db-score-fill"))
        )

        rows = driver.find_elements(By.TAG_NAME, "tr")

        for row in rows:
            cols = row.find_elements(By.TAG_NAME, "td")

            if len(cols) < 6:
                continue

            try:
                startup = cols[0].text.strip()
                sector = cols[1].text.strip()
                funding = clean_money(cols[3].text.strip())
                cause = cols[5].text.strip().lower()

                labels = ["MARKET", "SCALE", "REBUILD"]

                scores = {}

                bars = row.find_elements(By.XPATH, ".//div[contains(@class, 'db-score-fill')]")

                for i, bar in enumerate(bars):
                    style = bar.get_attribute("style")
                    val = extract_percentage(style)
                    scores[labels[i]] = val if val is not None else 0.0

                data.append({
                    "startup": startup,
                    "sector": sector,
                    "funding": funding,
                    "causes": [c.strip() for c in cause.split(",") if c.strip()],
                    "scores": scores
                })

            except Exception as e:
                print("[ERROR] Row parsing failed:", e)

        # =========================
        # NEXT BUTTON
        # =========================
        try:
            next_button = driver.find_element(By.XPATH, "//button[contains(., 'Next')]")

            # stop si désactivé
            if "disabled" in next_button.get_attribute("outerHTML").lower():
                print("[INFO] Last page reached")
                break

            old_page = driver.page_source

            driver.execute_script("arguments[0].click();", next_button)

            # attendre changement réel
            WebDriverWait(driver, 10).until(
                lambda d: d.page_source != old_page
            )

        except:
            print("[INFO] No next button found")
            break

    driver.quit()
    return data


def run_pipeline():

    print("[INFO] Scraping Site 1...")
    site1_data = scrape_site1()

    output = {
        "site1_structured": site1_data
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"[INFO] Data saved to {OUTPUT_FILE}")
    print(f"[INFO] Total records: {len(site1_data)}")


if __name__ == "__main__":
    run_pipeline()