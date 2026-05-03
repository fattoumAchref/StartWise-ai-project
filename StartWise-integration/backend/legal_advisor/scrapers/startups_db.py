"""
Base de données startups tunisiennes.
Sources :
  1. API smartcapital.tn  — 925+ startups labellisées Startup Act (JSON propre)
  2. CSV local            — 1054 startups (complément, données supplémentaires)
  3. API Flywheel AIR/AIR² — startups des programmes d'accélération
  4. API SSO              — incubateurs / accélérateurs tunisiens
"""

import csv
import re
import structlog
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
log = structlog.get_logger("startups_db")

CSV_PATH = "scrapers/data/Base de données  Startup Tunisia (1).csv"

SMARTCAPITAL_API  = "https://startups.smartcapital.tn?lang=fr"
FLYWHEEL_AIR_API  = "https://flywheel.smartcapital.tn/?instrument=air&lang=fr"
FLYWHEEL_AIR2_API = "https://flywheel.smartcapital.tn/?instrument=air2&lang=fr"
SSO_API           = "https://sso.smartcapital.tn?lang=fr"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer":    "https://startup.gov.tn/",
    "Origin":     "https://startup.gov.tn",
}


# ── Utilitaires ───────────────────────────────────────────────────────────────

def _fetch_json(url: str) -> list[dict]:
    import requests
    try:
        r = requests.get(url, headers=_HEADERS, timeout=20, verify=False)
        r.raise_for_status()
        data = r.json()
        log.info("api_ok", url=url, count=len(data))
        return data if isinstance(data, list) else []
    except Exception as e:
        log.warning("api_error", url=url, error=str(e)[:100])
        return []


def _normalize_name(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").strip().lower())


def _clean(val) -> str:
    if not val or str(val).strip() in ("n.a.", "n.a", "N/A", "undefined", "null", ""):
        return ""
    return str(val).strip()


# ── Parseurs par source ───────────────────────────────────────────────────────

def _parse_smartcapital(data: list[dict]) -> list[dict]:
    results = []
    for s in data:
        name = _clean(s.get("name"))
        if not name:
            continue
        founders = s.get("founders") or []
        if isinstance(founders, list):
            founders_str = ", ".join(f for f in founders if f and f.strip())
        else:
            founders_str = _clean(str(founders))
        results.append({
            "name":         name,
            "sector":       _clean(s.get("sector") or s.get("industry")),
            "description":  _clean(s.get("desc")),
            "founders":     founders_str,
            "website":      _clean(s.get("website")),
            "email":        _clean(s.get("email")),
            "phone":        _clean(s.get("phone")),
            "label_date":   _clean(s.get("label")),
            "creation_year":_clean(s.get("creation_year")),
            "source":       "Startup Act — base labellisées",
        })
    return results


def _parse_flywheel(data: list[dict], program: str) -> list[dict]:
    results = []
    for s in data:
        name = _clean(s.get("id"))
        if not name:
            continue
        founders = s.get("founders_list") or []
        if isinstance(founders, list):
            founders_str = ", ".join(f for f in founders if f and f.strip())
        else:
            founders_str = _clean(str(founders))
        results.append({
            "name":         name,
            "sector":       _clean(s.get("sector")),
            "description":  _clean(s.get("desc")),
            "founders":     founders_str,
            "website":      _clean(s.get("website")),
            "email":        "",
            "phone":        "",
            "label_date":   _clean(s.get("session")),
            "creation_year":_clean(s.get("creation_year")),
            "source":       f"Smart Capital — programme {program}",
            "location":     _clean(s.get("location")),
        })
    return results


def _parse_csv() -> list[dict]:
    """Lit le CSV local (utf-8 avec BOM, délimiteur ;)."""
    results = []
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            with open(CSV_PATH, encoding=enc, errors="replace") as f:
                reader = csv.reader(f, delimiter=";")
                rows = list(reader)
            if len(rows) < 2:
                continue
            # header row
            header = [h.strip() for h in rows[0]]
            # Colonnes attendues : Logo Nom Secteur Année Label Site Desc Founders Email Tel
            col_name   = _find_col(header, ["nom", "name"])
            col_sector = _find_col(header, ["secteur", "sector", "industrie"])
            col_desc   = _find_col(header, ["rés", "desc", "résumé", "summary"])
            col_founder= _find_col(header, ["founder", "fondateur"])
            col_website= _find_col(header, ["site", "web", "url"])
            col_label  = _find_col(header, ["label"])
            col_year   = _find_col(header, ["ann", "year", "création"])
            col_email  = _find_col(header, ["courriel", "email"])

            for row in rows[1:]:
                if col_name is None or col_name >= len(row):
                    continue
                name = _clean(row[col_name])
                if not name:
                    continue
                results.append({
                    "name":         name,
                    "sector":       _clean(row[col_sector]) if col_sector is not None and col_sector < len(row) else "",
                    "description":  _clean(row[col_desc])   if col_desc   is not None and col_desc   < len(row) else "",
                    "founders":     _clean(row[col_founder]) if col_founder is not None and col_founder < len(row) else "",
                    "website":      _clean(row[col_website]) if col_website is not None and col_website < len(row) else "",
                    "email":        _clean(row[col_email])   if col_email  is not None and col_email  < len(row) else "",
                    "phone":        "",
                    "label_date":   _clean(row[col_label])  if col_label  is not None and col_label  < len(row) else "",
                    "creation_year":_clean(row[col_year])   if col_year   is not None and col_year   < len(row) else "",
                    "source":       "CSV — base startups Tunisie",
                })
            log.info("csv_ok", rows=len(results), encoding=enc)
            return results
        except Exception as e:
            log.warning("csv_error", enc=enc, error=str(e)[:80])
            continue
    return results


def _parse_sso(data: list[dict]) -> list[dict]:
    """Incubateurs / accélérateurs tunisiens."""
    results = []
    for s in data:
        name = _clean(s.get("name") or s.get("program_name"))
        if not name:
            continue
        sectors = s.get("sectors") or []
        sector_str = ", ".join(str(x) for x in sectors) if isinstance(sectors, list) else _clean(str(sectors))
        perks = s.get("perks") or []
        perks_str = ", ".join(str(x) for x in perks) if isinstance(perks, list) else ""
        desc = _clean(s.get("programs"))
        results.append({
            "name":         name,
            "sector":       sector_str,
            "description":  desc,
            "founders":     "",
            "website":      _clean(s.get("website")),
            "email":        _clean(s.get("email")),
            "phone":        _clean(s.get("phone")),
            "label_date":   _clean(s.get("launched")),
            "creation_year":_clean(s.get("launched")),
            "source":       "Smart Capital — incubateurs/accélérateurs",
            "region":       _clean(s.get("region")),
            "offer":        _clean(s.get("offer")),
            "perks":        perks_str,
            "stage_entry":  ", ".join(s.get("stage_entry") or []),
        })
    return results


def _find_col(header: list[str], keywords: list[str]) -> int | None:
    for i, h in enumerate(header):
        h_low = h.lower()
        if any(k.lower() in h_low for k in keywords):
            return i
    return None


# ── Fusion & déduplication ────────────────────────────────────────────────────

def _merge(all_records: list[dict]) -> list[dict]:
    """Fusionne les sources : garde le premier record par nom normalisé et complète les champs vides."""
    merged: dict[str, dict] = {}
    for rec in all_records:
        key = _normalize_name(rec["name"])
        if not key:
            continue
        if key not in merged:
            merged[key] = dict(rec)
        else:
            # Complète les champs vides avec les données d'autres sources
            existing = merged[key]
            for field in ["sector", "description", "founders", "website", "email", "phone", "label_date", "creation_year"]:
                if not existing.get(field) and rec.get(field):
                    existing[field] = rec[field]
    return list(merged.values())


# ── Formatage en chunks ───────────────────────────────────────────────────────

def _to_chunk(rec: dict) -> dict:
    lines = [f"Startup : {rec['name']}"]
    if rec.get("sector"):
        lines.append(f"Secteur : {rec['sector']}")
    if rec.get("creation_year"):
        lines.append(f"Année de création : {rec['creation_year']}")
    if rec.get("label_date"):
        lines.append(f"Label Startup Act : {rec['label_date']}")
    if rec.get("founders"):
        lines.append(f"Fondateurs : {rec['founders']}")
    if rec.get("website"):
        lines.append(f"Site web : {rec['website']}")
    if rec.get("description"):
        lines.append(f"Description : {rec['description'][:500]}")
    if rec.get("location"):
        lines.append(f"Localisation : {rec['location']}")
    if rec.get("region"):
        lines.append(f"Région : {rec['region']}")
    if rec.get("perks"):
        lines.append(f"Services offerts : {rec['perks']}")
    if rec.get("source"):
        lines.append(f"Source : {rec['source']}")

    content = "\n".join(lines)
    return {
        "content":      content,
        "source_label": f"Startup : {rec['name']} — {rec.get('sector', '')}",
        "metadata": {
            "domain":      "ENTREPRISES",
            "source_type": "STARTUPS_DB",
            "name":        rec["name"],
            "sector":      rec.get("sector", ""),
            "website":     rec.get("website", ""),
        },
    }


# ── Point d'entrée ────────────────────────────────────────────────────────────

async def scrape_all() -> list[dict]:
    log.info("startups_db_start")

    all_records: list[dict] = []

    # 1. API smartcapital — base principale
    sc_data = _fetch_json(SMARTCAPITAL_API)
    all_records.extend(_parse_smartcapital(sc_data))
    log.info("smartcapital_done", count=len(sc_data))

    # 2. CSV local — données supplémentaires
    csv_records = _parse_csv()
    all_records.extend(csv_records)
    log.info("csv_done", count=len(csv_records))

    # 3. Flywheel AIR (programme d'accélération)
    air_data = _fetch_json(FLYWHEEL_AIR_API)
    all_records.extend(_parse_flywheel(air_data, "AIR"))
    log.info("flywheel_air_done", count=len(air_data))

    # 4. Flywheel AIR²
    air2_data = _fetch_json(FLYWHEEL_AIR2_API)
    all_records.extend(_parse_flywheel(air2_data, "AIR²"))
    log.info("flywheel_air2_done", count=len(air2_data))

    # 5. SSO — incubateurs/accélérateurs
    sso_data = _fetch_json(SSO_API)
    all_records.extend(_parse_sso(sso_data))
    log.info("sso_done", count=len(sso_data))

    # Fusion & déduplication
    merged = _merge(all_records)
    log.info("merged", before=len(all_records), after=len(merged))

    # Conversion en chunks
    chunks = [_to_chunk(r) for r in merged]
    log.info("startups_db_done", chunks=len(chunks))
    return chunks
