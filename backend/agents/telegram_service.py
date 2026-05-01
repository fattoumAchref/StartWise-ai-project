# backend/agents/telegram_service.py
# ============================================================
#  Service Telegram — StartWise
# ============================================================
#  Envoie un message formaté Markdown vers un chat Telegram
#  via l'API Bot de Telegram (gratuit, sans limite de taux sévère).
# ============================================================

import os
import httpx
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_API       = "https://api.telegram.org/bot{token}/sendMessage"
TELEGRAM_PHOTO_API = "https://api.telegram.org/bot{token}/sendPhoto"


def _fmt_list(items: list, emoji: str = "•") -> str:
    """Formate une liste Python en lignes Telegram."""
    if not items:
        return "_Aucun élément_"
    return "\n".join(f"{emoji} {str(item)}" for item in items if item)


def format_creative_message(project_desc: str, creative: dict) -> str:
    """
    Formate le contenu du Creative Director pour Telegram.
    Utilise le Markdown Telegram (gras **…**, italique _…_).
    """
    lines = []

    # ── En-tête
    lines.append("🚀 *StartWise — Rapport Stratégique*")
    lines.append("")
    lines.append(f"📌 *Projet :* {project_desc[:200]}")
    lines.append("")

    # ── Score de disruption
    scores = creative.get("disruption_scores", {})
    if scores:
        lines.append("📊 *Scores de Disruption*")
        for key, val in scores.items():
            label = key.replace("_", " ").title()
            bar = "▓" * int((val or 0) // 10) + "░" * (10 - int((val or 0) // 10))
            lines.append(f"  _{label}_ : {bar} {val}/100")
        lines.append("")

    # ── Killer Features
    features = creative.get("killer_features", [])
    if features:
        lines.append("⚡ *Killer Features*")
        for f in features[:5]:
            lines.append(f"  ✅ {f}")
        lines.append("")

    # ── Phases d'exécution
    phases = creative.get("execution_phases", [])
    if phases:
        lines.append("🗺️ *Plan d'Exécution*")
        for i, phase in enumerate(phases[:3], 1):
            name = phase.get("phase_name", f"Phase {i}")
            duration = phase.get("duration", "")
            lines.append(f"  *Phase {i} — {name}*" + (f" _{duration}_" if duration else ""))
            phase_features = phase.get("killer_features", [])[:3]
            for pf in phase_features:
                lines.append(f"    › {pf}")
        lines.append("")

    # ── Roadmap phases
    roadmap = creative.get("roadmap_phases", [])
    if roadmap:
        lines.append("📅 *Roadmap*")
        for rp in roadmap[:4]:
            phase_name = rp.get("phase", "")
            timing = rp.get("timing", "")
            goal = rp.get("goal", "")
            if phase_name:
                lines.append(f"  🔹 *{phase_name}*" + (f" — _{timing}_" if timing else ""))
                if goal:
                    lines.append(f"      {goal}")
        lines.append("")

    # ── Recommandation finale
    rec = creative.get("final_recommendation", "")
    if rec:
        lines.append("💡 *Recommandation Finale*")
        lines.append(f"_{rec[:400]}_")
        lines.append("")

    # ── Pied de message
    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("_Généré par StartWise AI · agents.startwise.io_")

    return "\n".join(lines)


def send_telegram_photo_bytes(image_bytes: bytes, caption: str, parse_mode: str = "Markdown") -> dict:
    """
    Envoie une photo depuis des bytes (image locale, data URI décodée, etc.)
    via multipart/form-data — fonctionne sans URL publique accessible.
    """
    token   = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    if not token or not chat_id:
        return {
            "success": False,
            "error": "TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID manquant dans le .env",
        }

    url = TELEGRAM_PHOTO_API.format(token=token)

    if len(caption) > 1024:
        caption = caption[:1020] + "\n_…_"

    try:
        resp = httpx.post(
            url,
            data={"chat_id": chat_id, "caption": caption, "parse_mode": parse_mode},
            files={"photo": ("prototype.webp", image_bytes, "image/webp")},
            timeout=30.0,
        )
        resp.raise_for_status()
        data   = resp.json()
        msg_id = data.get("result", {}).get("message_id")
        print(f"[TELEGRAM] Photo (bytes) envoyée ✓ | message_id={msg_id}")
        return {"success": True, "message_id": msg_id}

    except httpx.HTTPStatusError as e:
        err = e.response.text
        if parse_mode == "Markdown" and "can't parse" in err.lower():
            return send_telegram_photo_bytes(image_bytes, caption, parse_mode="")
        print(f"[TELEGRAM] sendPhoto bytes erreur HTTP {e.response.status_code}: {err}")
        return {"success": False, "error": f"HTTP {e.response.status_code}: {err[:200]}"}
    except Exception as e:
        print(f"[TELEGRAM] sendPhoto bytes exception: {e}")
        return {"success": False, "error": str(e)}


def send_telegram_photo(photo_url: str, caption: str, parse_mode: str = "Markdown") -> dict:
    """
    Envoie une photo vers le chat Telegram avec une légende.
    Le jury voit l'image immédiatement sur son téléphone.
    Retourne { success, message_id } ou { success: False, error }.
    """
    token   = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    if not token or not chat_id:
        return {
            "success": False,
            "error": "TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID manquant dans le .env",
        }

    url = TELEGRAM_PHOTO_API.format(token=token)

    # Telegram limite les légendes à 1024 caractères
    if len(caption) > 1024:
        caption = caption[:1020] + "\n_…_"

    try:
        resp = httpx.post(
            url,
            json={
                "chat_id":    chat_id,
                "photo":      photo_url,
                "caption":    caption,
                "parse_mode": parse_mode,
            },
            timeout=20.0,
        )
        resp.raise_for_status()
        data   = resp.json()
        msg_id = data.get("result", {}).get("message_id")
        print(f"[TELEGRAM] Photo envoyée ✓ | message_id={msg_id}")
        return {"success": True, "message_id": msg_id}

    except httpx.HTTPStatusError as e:
        err = e.response.text
        if parse_mode == "Markdown" and "can't parse" in err.lower():
            print("[TELEGRAM] Fallback texte brut pour photo (Markdown parsing error)")
            return send_telegram_photo(photo_url, caption, parse_mode="")
        print(f"[TELEGRAM] sendPhoto erreur HTTP {e.response.status_code}: {err}")
        return {"success": False, "error": f"HTTP {e.response.status_code}: {err[:200]}"}
    except Exception as e:
        print(f"[TELEGRAM] sendPhoto exception: {e}")
        return {"success": False, "error": str(e)}


def send_telegram_message(text: str, parse_mode: str = "Markdown") -> dict:
    """
    Envoie un message vers le chat Telegram configuré dans .env.
    Retourne { success, message_id } ou { success: False, error }.
    """
    token   = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    if not token or not chat_id:
        return {
            "success": False,
            "error": "TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID manquant dans le .env",
        }

    url = TELEGRAM_API.format(token=token)

    # Telegram limite les messages à 4096 caractères
    if len(text) > 4096:
        text = text[:4090] + "\n_…_"

    try:
        resp = httpx.post(
            url,
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True,
            },
            timeout=15.0,
        )
        resp.raise_for_status()
        data = resp.json()
        msg_id = data.get("result", {}).get("message_id")
        print(f"[TELEGRAM] Message envoyé ✓ | message_id={msg_id}")
        return {"success": True, "message_id": msg_id}

    except httpx.HTTPStatusError as e:
        err = e.response.text
        # Fallback : réessayer sans Markdown si erreur de parsing
        if parse_mode == "Markdown" and "can't parse" in err.lower():
            print("[TELEGRAM] Fallback texte brut (Markdown parsing error)")
            return send_telegram_message(text, parse_mode="")
        print(f"[TELEGRAM] Erreur HTTP {e.response.status_code}: {err}")
        return {"success": False, "error": f"HTTP {e.response.status_code}: {err[:200]}"}
    except Exception as e:
        print(f"[TELEGRAM] Exception: {e}")
        return {"success": False, "error": str(e)}
