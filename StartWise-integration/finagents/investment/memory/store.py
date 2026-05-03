"""
Investment Agent Memory — SQLite-based project history.
Tracks startup analyses across sessions to enable progress comparison.
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import Optional


DB_PATH = os.path.join(os.path.dirname(__file__), "investment_memory.db")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist."""
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS analyses (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id    TEXT NOT NULL,
                user_id       TEXT NOT NULL,
                timestamp     TEXT NOT NULL,
                sector        TEXT,
                stage         TEXT,
                annual_revenue REAL,
                growth_rate   REAL,
                funding_asked REAL,
                valuation     REAL,
                dilution      REAL,
                confidence    REAL,
                optimal_scenario TEXT,
                grants_available REAL,
                method_used   TEXT,
                raw_snapshot  TEXT   -- full JSON of the result
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_id    ON analyses(user_id);
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_project_id ON analyses(project_id);
        """)


def save_analysis(project_id: str, user_id: str, result: dict):
    """
    Persist one analysis result to the database.

    Args:
        project_id : unique project identifier
        user_id    : user who submitted the project
        result     : full investment result dict (from InvestmentRecommendation.to_dict())
    """
    init_db()

    data    = result.get("data", {})
    val     = data.get("valuation", {})
    scen    = data.get("optimal_scenario", {})
    dil     = data.get("dilution", {})
    grants  = sum(g.get("amount", 0) for g in data.get("available_grants", []))

    with _connect() as conn:
        conn.execute("""
            INSERT INTO analyses (
                project_id, user_id, timestamp,
                sector, stage, annual_revenue, growth_rate,
                funding_asked, valuation, dilution, confidence,
                optimal_scenario, grants_available, method_used,
                raw_snapshot
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            project_id,
            user_id,
            datetime.utcnow().isoformat(),
            data.get("sector") or data.get("industry"),
            data.get("stage"),
            data.get("annual_revenue"),
            data.get("growth_rate"),
            scen.get("raise_amount"),
            val.get("final_valuation"),
            dil.get("founder_dilution_pct"),
            result.get("confidence_score"),
            scen.get("name"),
            grants,
            val.get("method"),
            json.dumps(result),
        ))
    print(f"[Memory] Saved analysis for {project_id} (user: {user_id})")


def get_project_history(project_id: str) -> list:
    """Return all past analyses for a given project, oldest first."""
    init_db()
    with _connect() as conn:
        rows = conn.execute("""
            SELECT * FROM analyses
            WHERE project_id = ?
            ORDER BY timestamp ASC
        """, (project_id,)).fetchall()
    return [dict(r) for r in rows]


def get_user_history(user_id: str, limit: int = 10) -> list:
    """Return the most recent analyses for a user."""
    init_db()
    with _connect() as conn:
        rows = conn.execute("""
            SELECT * FROM analyses
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (user_id, limit)).fetchall()
    return [dict(r) for r in rows]


def get_sector_stats(sector: str) -> dict:
    """
    Aggregate stats across all analyses for a sector.
    Useful for improving benchmark accuracy over time.
    """
    init_db()
    with _connect() as conn:
        row = conn.execute("""
            SELECT
                COUNT(*)            AS total,
                AVG(valuation)      AS avg_valuation,
                AVG(dilution)       AS avg_dilution,
                AVG(funding_asked)  AS avg_funding,
                AVG(confidence)     AS avg_confidence
            FROM analyses
            WHERE sector = ?
        """, (sector,)).fetchone()
    return dict(row) if row else {}
