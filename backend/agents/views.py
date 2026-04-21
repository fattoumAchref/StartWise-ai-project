import json
import os
import httpx
from django.http import StreamingHttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .graph import compiled_graph
from .document_processor import extract_text
from .notion_service import export_to_notion
from .telegram_service import format_creative_message, send_telegram_message, send_telegram_photo, send_telegram_photo_bytes

@csrf_exempt
@require_http_methods(["POST"])
def analyze_project(request):
    """
    Stream agent results back to frontend using Server-Sent Events (SSE).
    Each agent update is sent as a JSON event.
    """
    try:
        body = json.loads(request.body)
        project_description = body.get("description", "")
        competitor_images = body.get("competitor_images", [])
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    if not project_description:
        return JsonResponse({"error": "Project description required"}, status=400)

    def event_stream():
        initial_state = {
            "project_description": project_description,
            "trend_result": {},
            "vision_result": {},
            "emotion_result": {},
            "creative_result": {},
            "self_correction_score": 0.0,
            "correction_attempts": 0,
            "final_report": {},
            "messages": []
        }

        # Stream events as LangGraph executes each node
        for step in compiled_graph.stream(initial_state):
            for node_name, node_output in step.items():
                event_data = {
                    "node": node_name,
                    "status": "completed",
                    "data": node_output
                }
                yield f"data: {json.dumps(event_data)}\n\n"

        yield "data: {\"node\": \"done\", \"status\": \"finished\"}\n\n"

    response = StreamingHttpResponse(
        event_stream(),
        content_type="text/event-stream"
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    response["Access-Control-Allow-Origin"] = "http://localhost:5173"
    response["Access-Control-Allow-Headers"] = "Content-Type"
    return response


@csrf_exempt
@require_http_methods(["POST"])
def analyze_project_sync(request):
    """Synchronous fallback: run full graph and return complete result."""
    try:
        body = json.loads(request.body)
        project_description = body.get("description", "")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    initial_state = {
        "project_description": project_description,
        "trend_result": {},
        "vision_result": {},
        "emotion_result": {},
        "creative_result": {},
        "self_correction_score": 0.0,
        "correction_attempts": 0,
        "final_report": {},
        "messages": []
    }

    final_state = compiled_graph.invoke(initial_state)

    return JsonResponse({
        "trend": final_state.get("trend_result", {}),
        "vision": final_state.get("vision_result", {}),
        "emotion": final_state.get("emotion_result", {}),
        "creative": final_state.get("creative_result", {}),
        "self_correction_score": final_state.get("self_correction_score", 0),
        "correction_attempts": final_state.get("correction_attempts", 0),
        "messages": final_state.get("messages", [])
    })


@csrf_exempt
@require_http_methods(["POST"])
def upload_document(request):
    """Extract text from an uploaded PDF or TXT file (max 5 MB)."""
    file = request.FILES.get('file')
    if not file:
        return JsonResponse({"error": "Aucun fichier fourni."}, status=400)

    MAX_SIZE = 5 * 1024 * 1024  # 5 MB
    file_bytes = file.read()
    if len(file_bytes) > MAX_SIZE:
        return JsonResponse({"error": "Fichier trop volumineux (max 5 Mo)."}, status=400)

    text = extract_text(file_bytes, file.name)

    # Tronque à 8 000 caractères pour ne pas saturer le contexte LLM
    MAX_CHARS = 8000
    truncated = len(text) > MAX_CHARS
    text = text[:MAX_CHARS]

    print(f"[UPLOAD] {file.name} — {len(text)} chars extraits{' (tronqué)' if truncated else ''}")

    return JsonResponse({
        "text": text,
        "filename": file.name,
        "chars": len(text),
        "truncated": truncated,
    })


# ─────────────────────────────────────────────────────────────
#  Agent Commercial — Envoi de mail (Resend)
# ─────────────────────────────────────────────────────────────

@csrf_exempt
@require_http_methods(["POST"])
def send_email(request):
    """
    Envoie un mail de prospection via Resend.com après validation du fondateur.
    Body JSON : { to_email, subject, body, from_name }
    """
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    to_email  = body.get("to_email", "").strip()
    subject   = body.get("subject", "").strip()
    content   = body.get("body", "").strip()
    from_name = body.get("from_name", "StartWise").strip()

    if not to_email or not subject or not content:
        return JsonResponse({"error": "to_email, subject et body sont requis."}, status=400)

    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
        return JsonResponse({"error": "RESEND_API_KEY non configurée. Ajoutez-la dans votre .env."}, status=500)

    from_email = os.getenv("RESEND_FROM_EMAIL", "onboarding@resend.dev")

    try:
        resp = httpx.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "from": f"{from_name} <{from_email}>",
                "to": [to_email],
                "subject": subject,
                "text": content,
            },
            timeout=15.0,
        )
        resp.raise_for_status()
        data = resp.json()
        print(f"[COMMERCIAL] Mail envoyé → {to_email} | id={data.get('id')}")
        return JsonResponse({"success": True, "resend_id": data.get("id"), "to": to_email})

    except httpx.HTTPStatusError as e:
        error_body = e.response.text
        print(f"[COMMERCIAL] Resend erreur HTTP {e.response.status_code}: {error_body}")
        return JsonResponse({"error": f"Resend API error {e.response.status_code}: {error_body}"}, status=502)
    except Exception as e:
        print(f"[COMMERCIAL] send_email exception: {e}")
        return JsonResponse({"error": str(e)}, status=500)


# ─────────────────────────────────────────────────────────────
#  Agent Commercial — Programmer un post social (Meta Graph API)
# ─────────────────────────────────────────────────────────────

@csrf_exempt
@require_http_methods(["POST"])
def schedule_post(request):
    """
    Publie ou programme un post Facebook/Instagram via Meta Graph API.
    Body JSON : { platform ("facebook"|"instagram"), content, page_id, access_token }
    Nécessite : META_PAGE_ID + META_ACCESS_TOKEN dans .env (ou passés en body).
    """
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    platform     = body.get("platform", "facebook").lower()
    content      = body.get("content", "").strip()
    page_id      = body.get("page_id") or os.getenv("META_PAGE_ID", "")
    access_token = body.get("access_token") or os.getenv("META_ACCESS_TOKEN", "")

    if not content:
        return JsonResponse({"error": "content est requis."}, status=400)

    if not page_id or not access_token:
        # Mode démo : retourne succès simulé si pas de clés configurées
        print(f"[COMMERCIAL] META non configuré — mode démo pour {platform}")
        return JsonResponse({
            "success": True,
            "demo": True,
            "message": f"Post {platform} prêt (META_PAGE_ID / META_ACCESS_TOKEN non configurés — mode démo).",
            "content_preview": content[:120],
        })

    try:
        if platform == "facebook":
            url = f"https://graph.facebook.com/v19.0/{page_id}/feed"
            payload = {"message": content, "access_token": access_token}
        else:
            # Instagram — nécessite un Instagram Business Account lié à la Page
            url = f"https://graph.facebook.com/v19.0/{page_id}/media"
            # Étape 1 : créer le container (caption only, sans image)
            container_resp = httpx.post(
                url,
                json={"caption": content, "media_type": "REELS", "access_token": access_token},
                timeout=15.0,
            )
            container_resp.raise_for_status()
            creation_id = container_resp.json().get("id")
            # Étape 2 : publier le container
            publish_resp = httpx.post(
                f"https://graph.facebook.com/v19.0/{page_id}/media_publish",
                json={"creation_id": creation_id, "access_token": access_token},
                timeout=15.0,
            )
            publish_resp.raise_for_status()
            print(f"[COMMERCIAL] Instagram publié | id={publish_resp.json().get('id')}")
            return JsonResponse({"success": True, "platform": "instagram", "post_id": publish_resp.json().get("id")})

        resp = httpx.post(url, json=payload, timeout=15.0)
        resp.raise_for_status()
        post_id = resp.json().get("id")
        print(f"[COMMERCIAL] {platform} publié | id={post_id}")
        return JsonResponse({"success": True, "platform": platform, "post_id": post_id})

    except httpx.HTTPStatusError as e:
        error_body = e.response.text
        print(f"[COMMERCIAL] Meta Graph erreur {e.response.status_code}: {error_body}")
        return JsonResponse({"error": f"Meta API error {e.response.status_code}: {error_body}"}, status=502)
    except Exception as e:
        print(f"[COMMERCIAL] schedule_post exception: {e}")
        return JsonResponse({"error": str(e)}, status=500)


# ─────────────────────────────────────────────────────────────
#  Notion Planner — Export vers la Roadmap Notion
# ─────────────────────────────────────────────────────────────

@csrf_exempt
@require_http_methods(["POST"])
def export_notion(request):
    """
    Génère ~15 tâches marketing actionnables via LLM, puis les crée
    dans la base Notion "Roadmap StartWise".
    Body JSON : { project_description, agents_results, lang }
    """
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    project_desc = body.get("project_description", "").strip()
    all_results  = body.get("agents_results", {})
    lang         = body.get("lang", "fr")

    if not project_desc:
        return JsonResponse({"error": "project_description est requis."}, status=400)

    print(f"[NOTION] Export demandé — projet: {project_desc[:80]}...")
    result = export_to_notion(project_desc, all_results, lang)

    if result.get("success"):
        print(f"[NOTION] {result['tasks_created']}/{result['tasks_total']} tâches créées")
        return JsonResponse(result, status=200)
    else:
        print(f"[NOTION] Échec : {result.get('error')}")
        return JsonResponse(result, status=500)


# ─────────────────────────────────────────────────────────────
#  Telegram — Envoyer le rapport Creative Director
# ─────────────────────────────────────────────────────────────

@csrf_exempt
@require_http_methods(["POST"])
def send_telegram(request):
    """
    Formate et envoie le rapport du Creative Director sur Telegram.
    Body JSON : { project_description, creative_result }
    """
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    project_desc   = body.get("project_description", "").strip()
    creative       = body.get("creative_result", {})
    prototype_url  = body.get("prototype_url", "").strip()

    if not project_desc and not creative:
        return JsonResponse({"error": "project_description ou creative_result requis."}, status=400)

    text = format_creative_message(project_desc, creative)

    # Si un prototype existe → sendPhoto (image principale + rapport en légende)
    if prototype_url:
        if prototype_url.startswith("http"):
            # URL publique → sendPhoto standard
            result = send_telegram_photo(prototype_url, text)
        elif prototype_url.startswith("data:"):
            # Data URI base64 → décoder et envoyer en bytes (pas besoin d'URL publique)
            import base64 as _b64
            try:
                _header, _b64_data = prototype_url.split(",", 1)
                image_bytes = _b64.b64decode(_b64_data)
                result = send_telegram_photo_bytes(image_bytes, text)
                print(f"[TELEGRAM] Prototype décodé ({len(image_bytes)//1024}KB) envoyé en bytes")
            except Exception as _e:
                print(f"[TELEGRAM] Erreur décodage data URI: {_e} — envoi texte uniquement")
                result = send_telegram_message(text)
        else:
            result = send_telegram_message(text)
    else:
        result = send_telegram_message(text)

    if result.get("success"):
        return JsonResponse(result, status=200)
    else:
        return JsonResponse(result, status=502)


# ─────────────────────────────────────────────────────────────
#  Logo Feedback Loop — Régénération avec instructions fondateur
# ─────────────────────────────────────────────────────────────

@csrf_exempt
@require_http_methods(["POST"])
def regenerate_logo(request):
    """
    Régénère l'icône logo en incorporant le feedback du fondateur.
    Body JSON : { original_prompt, feedback, brand_primary }
    Retourne : { image_uri }
    """
    import asyncio
    from .inference import image_client as unified_image

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    original_prompt = body.get("original_prompt", "").strip()
    feedback        = body.get("feedback", "").strip()
    brand_primary   = body.get("brand_primary", "#6366f1").strip()

    if not feedback:
        return JsonResponse({"error": "feedback est requis."}, status=400)

    enhanced_prompt = (
        f"{original_prompt}. "
        f"Brand color: {brand_primary}. "
        f"Revised style: {feedback}. "
        f"No text, no letters, no words, no numbers. Ultra sharp, high definition."
    )[:400]

    print(f"[LOGO REGEN] Prompt: {enhanced_prompt[:120]}...")

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        image_uri = loop.run_until_complete(
            unified_image.generate(enhanced_prompt, seed=99, label="logo_regen")
        )
        loop.close()
    except Exception as e:
        print(f"[LOGO REGEN] Erreur: {e}")
        return JsonResponse({"error": str(e)}, status=500)

    if not image_uri:
        return JsonResponse({"error": "Génération échouée. Réessayez dans quelques secondes."}, status=503)

    return JsonResponse({"image_uri": image_uri})


# ─────────────────────────────────────────────────────────────
#  Prototype Commercial — Visuel produit ultra-réaliste (FLUX.1)
# ─────────────────────────────────────────────────────────────

@csrf_exempt
@require_http_methods(["POST"])
def generate_prototype(request):
    """
    Génère un visuel prototype ultra-réaliste via FLUX.1-schnell.
    Body JSON : { project_description, style_hint? }
    Retourne : { image_uri }
    """
    import asyncio
    from .inference import flux_client

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    project_desc = body.get("project_description", "").strip()
    style_hint   = body.get("style_hint", "").strip()

    if not project_desc:
        return JsonResponse({"error": "project_description est requis."}, status=400)

    prompt = (
        f"Ultra-realistic professional product photo of {project_desc[:100]}. "
        "Studio lighting, clean background, commercial photography style, 8K resolution. "
        "No text, no logos, no people, no UI elements. "
        + (f"{style_hint}. " if style_hint else "")
        + "Photorealistic, product visualization, high detail, sharp focus, editorial quality."
    )[:400]

    print(f"[PROTOTYPE] Génération: {prompt[:120]}...")

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        image_uri = loop.run_until_complete(
            flux_client.generate(prompt, seed=77, label="prototype")
        )
        loop.close()
    except Exception as e:
        print(f"[PROTOTYPE] Erreur: {e}")
        return JsonResponse({"error": str(e)}, status=500)

    if not image_uri:
        return JsonResponse({"error": "Génération échouée. Réessayez dans quelques secondes."}, status=503)

    return JsonResponse({"image_uri": image_uri})