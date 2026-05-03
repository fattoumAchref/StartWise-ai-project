import json
import sqlite3

# ====== CONFIG ======
JSON_FILE = ".\data\startup_failure_scores.json"
DB_FILE = ".\data\sf_scores.db"

# ====== LOAD JSON ======
with open(JSON_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

# ====== FIX STRUCTURE ======
if isinstance(data, dict):
    # extract the first list found (e.g. "site1_structured")
    data = next((v for v in data.values() if isinstance(v, list)), [])

# ====== CONNECT DB ======
conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()

# ====== CREATE TABLE ======
cursor.execute("""
CREATE TABLE IF NOT EXISTS startups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    sector TEXT,
    funding REAL,
    causes TEXT,
    market_score REAL,
    scale_score REAL,
    rebuild_score REAL
)
""")

# ====== INSERT DATA ======
for item in data:
    if not isinstance(item, dict):
        continue

    cursor.execute("""
    INSERT INTO startups (
        name, sector, funding, causes,
        market_score, scale_score, rebuild_score
    ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        item.get("startup"),
        item.get("sector"),
        item.get("funding"),
        json.dumps(item.get("causes", [])),
        item.get("scores", {}).get("MARKET"),
        item.get("scores", {}).get("SCALE"),
        item.get("scores", {}).get("REBUILD"),
    ))

# ====== SAVE & CLOSE ======
conn.commit()
conn.close()

print("Data inserted successfully.")