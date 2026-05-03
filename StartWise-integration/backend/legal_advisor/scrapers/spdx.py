"""
Scraper licences SPDX — API officielle spdx.org
Aucune donnée statique — tout vient de l'API SPDX.
"""

import httpx

SPDX_API = "https://spdx.org/licenses/licenses.json"

# Licences pertinentes pour les startups (filtre)
RELEVANT_LICENSES = {
    "MIT", "Apache-2.0", "GPL-2.0-only", "GPL-2.0-or-later",
    "GPL-3.0-only", "GPL-3.0-or-later", "AGPL-3.0-only", "AGPL-3.0-or-later",
    "LGPL-2.1-only", "LGPL-3.0-only", "BSD-2-Clause", "BSD-3-Clause",
    "MPL-2.0", "ISC", "EUPL-1.2", "CC0-1.0",
    "CDDL-1.0", "EPL-2.0", "SSPL-1.0",
}


async def scrape_license_detail(spdx_id: str, client: httpx.AsyncClient) -> str:
    """Récupère le texte complet d'une licence depuis spdx.org."""
    try:
        url = f"https://spdx.org/licenses/{spdx_id}.json"
        r = await client.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()
        # Le texte complet est dans licenseText ou licenseTextHtml
        text = data.get("licenseText", "")
        name = data.get("name", spdx_id)
        is_osi = data.get("isOsiApproved", False)
        is_deprecated = data.get("isDeprecatedLicenseId", False)
        return f"Licence : {name} ({spdx_id})\nOSI Approuvée : {is_osi}\nDépréciée : {is_deprecated}\n\n{text[:3000]}"
    except Exception as e:
        print(f"[SPDX] Erreur détail {spdx_id}: {e}")
        return ""


async def scrape_all() -> list[dict]:
    """
    Récupère la liste des licences depuis l'API SPDX officielle.
    Retourne une liste de chunks prêts pour ChromaDB.
    """
    chunks = []

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        try:
            r = await client.get(SPDX_API)
            r.raise_for_status()
            data = r.json()
            licenses = data.get("licenses", [])
            print(f"[SPDX] {len(licenses)} licences disponibles")
        except Exception as e:
            print(f"[SPDX] Erreur liste: {e}")
            return chunks

        for lic in licenses:
            spdx_id = lic.get("licenseId", "")
            if spdx_id not in RELEVANT_LICENSES:
                continue

            name        = lic.get("name", spdx_id)
            is_osi      = lic.get("isOsiApproved", False)
            deprecated  = lic.get("isDeprecatedLicenseId", False)
            detail_url  = lic.get("detailsUrl", "")

            # Récupérer le texte complet
            detail_text = ""
            if detail_url:
                detail_text = await scrape_license_detail(spdx_id, client)

            summary = (
                f"Licence logicielle : {name} (SPDX: {spdx_id})\n"
                f"Approuvée OSI : {is_osi} | Dépréciée : {deprecated}\n"
                f"Référence : {detail_url}\n"
            )
            if detail_text:
                summary += f"\n{detail_text[:2000]}"

            chunks.append({
                "source": f"SPDX:{spdx_id}",
                "source_label": f"Licence {name} ({spdx_id}) — SPDX",
                "content": summary,
                "metadata": {
                    "domain": "LICENCES",
                    "spdx_id": spdx_id,
                    "osi_approved": is_osi,
                    "source_type": "SPDX",
                },
            })
            print(f"[SPDX] {spdx_id} — OK")

    return chunks


def get_all_data() -> dict:
    """Conservé pour compatibilité — retourne vide."""
    return {}


def check_saas_risk(spdx_id: str) -> dict:
    """Évalue le niveau de risque SaaS d'une licence SPDX."""
    sid = (spdx_id or "").upper()
    if "AGPL" in sid or "SSPL" in sid:
        return {
            "spdx_id": spdx_id,
            "risk_level": "CRITIQUE",
            "compatible_saas": False,
            "reason": "Copyleft réseau fort (obligations de divulgation potentiellement bloquantes).",
        }
    if "GPL" in sid and "LGPL" not in sid:
        return {
            "spdx_id": spdx_id,
            "risk_level": "ELEVE",
            "compatible_saas": True,
            "reason": "Copyleft fort; vérifier les modalités de distribution/intégration.",
        }
    if "LGPL" in sid or "MPL" in sid:
        return {
            "spdx_id": spdx_id,
            "risk_level": "MOYEN",
            "compatible_saas": True,
            "reason": "Copyleft modéré; obligations ciblées.",
        }
    return {
        "spdx_id": spdx_id,
        "risk_level": "FAIBLE",
        "compatible_saas": True,
        "reason": "Licence généralement compatible avec un modèle SaaS.",
    }


def check_stack_compatibility(stack: list[str]) -> list[dict]:
    """Détecte des combinaisons de licences potentiellement conflictuelles."""
    stack_upper = [s.upper() for s in (stack or [])]
    conflicts = []
    if any("AGPL" in s for s in stack_upper) and any("PROPRIETARY" in s or "CUSTOM" in s for s in stack_upper):
        conflicts.append({
            "type": "CopyleftNetworkVsProprietary",
            "message": "Présence d'AGPL/SSPL avec composants potentiellement propriétaires.",
        })
    if any("GPL" in s and "LGPL" not in s for s in stack_upper) and any("APACHE-2.0" in s for s in stack_upper):
        conflicts.append({
            "type": "GPLMix",
            "message": "Vérifier la compatibilité exacte des versions GPL avec Apache-2.0.",
        })
    return conflicts
