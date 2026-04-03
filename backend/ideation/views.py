from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from django.http import FileResponse, HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .services.image_generation import ImageGenerationError, image_generation_service
from .services.logo_generation import logo_generation_service
from .services.orchestrator import orchestrator
from .services.schemas import ImageAssetState, QuestionState
from .services.session_store import session_store


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _json_body(request: HttpRequest) -> dict:
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid JSON body") from exc


def _bad_request(message: str, status: int = 400) -> JsonResponse:
    return JsonResponse({"detail": message}, status=status)


def _error_response(message: str, status: int = 500) -> JsonResponse:
    """Generic server-side error response — logs at ERROR level."""
    logger.error("Returning %s: %s", status, message)
    return JsonResponse({"detail": message}, status=status)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@require_http_methods(["GET"])
def health_check(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "healthy", "service": "startwise-ideation-django"})


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(["POST"])
def init_session(request: HttpRequest) -> JsonResponse:
    try:
        payload = _json_body(request)
    except ValueError as exc:
        return _bad_request(str(exc))

    session_id = str(payload.get("session_id", "")).strip()
    description = str(payload.get("description", "")).strip()
    if not session_id:
        return _bad_request("session_id is required")
    if not description:
        return _bad_request("description is required")

    session = session_store.create(session_id=session_id, description=description)

    try:
        question, keywords, sources = orchestrator.generate_next_question(session)
    except Exception as exc:
        logger.warning("Question generation failed, using mock fallback: %s", exc)
        question, keywords = orchestrator._mock_next_question(session)
        sources = []

    session.questions.append(QuestionState(question=question, keywords=keywords, sources=sources))
    session_store.save(session)
    return JsonResponse(session.to_dict())


@csrf_exempt
@require_http_methods(["POST"])
def respond(request: HttpRequest) -> JsonResponse:
    try:
        payload = _json_body(request)
    except ValueError as exc:
        return _bad_request(str(exc))

    session_id = str(payload.get("session_id", "")).strip()
    response_text = str(payload.get("response", "")).strip()
    question_index = payload.get("question_index")
    if not session_id:
        return _bad_request("session_id is required")
    if not response_text:
        return _bad_request("response is required")
    if not isinstance(question_index, int):
        return _bad_request("question_index must be an integer")

    session = session_store.get(session_id)
    if not session:
        return _bad_request("Session not found", status=404)
    if question_index < 0 or question_index >= len(session.questions):
        return _bad_request("Invalid question_index")

    question = session.questions[question_index]
    question.response = response_text

    try:
        is_ok, reason = orchestrator.evaluate_answer(session, question_index, response_text)
    except Exception as exc:
        logger.warning("Answer evaluation failed, using mock fallback: %s", exc)
        is_ok, reason = orchestrator._mock_evaluate_answer(question.question, response_text)

    question.is_satisfactory = is_ok
    question.satisfaction_reason = reason

    has_more_questions = False
    next_question: str | None = None
    next_sources: list[dict] | None = None

    if is_ok and len(session.questions) < orchestrator.max_questions:
        try:
            next_question, next_keywords, next_source_items = orchestrator.generate_next_question(session)
        except Exception as exc:
            logger.warning("Next question generation failed, using mock fallback: %s", exc)
            next_question, next_keywords = orchestrator._mock_next_question(session)
            next_source_items = []

        session.questions.append(
            QuestionState(question=next_question, keywords=next_keywords, sources=next_source_items)
        )
        next_sources = [item.to_dict() for item in next_source_items] if next_source_items else None
        has_more_questions = True

    session_store.save(session)
    return JsonResponse(
        {
            "question": next_question,
            "question_sources": next_sources,
            "has_more_questions": has_more_questions,
            "question_satisfaction": {
                "is_satisfactory": is_ok,
                "reason": reason,
            },
        }
    )


@require_http_methods(["GET"])
def keywords(request: HttpRequest, session_id: str, question_index: int) -> JsonResponse:
    session = session_store.get(session_id)
    if not session:
        return _bad_request("Session not found", status=404)
    if question_index < 0 or question_index >= len(session.questions):
        return _bad_request("Invalid question_index")

    question = session.questions[question_index]
    if not question.keywords:
        try:
            question.keywords = orchestrator.generate_keywords(question.question, session)
        except Exception as exc:
            logger.warning("Keyword generation failed, using mock fallback: %s", exc)
            question.keywords = orchestrator._mock_keywords(question.question)
        session_store.save(session)

    return JsonResponse({"keywords": question.keywords})


@csrf_exempt
@require_http_methods(["POST"])
def suggest(request: HttpRequest) -> JsonResponse:
    try:
        payload = _json_body(request)
    except ValueError as exc:
        return _bad_request(str(exc))

    session_id = str(payload.get("session_id", "")).strip()
    question_index = payload.get("question_index")
    selected_keywords = payload.get("selected_keywords", [])

    if not session_id:
        return _bad_request("session_id is required")
    if not isinstance(question_index, int):
        return _bad_request("question_index must be an integer")
    if not isinstance(selected_keywords, list):
        return _bad_request("selected_keywords must be a list")

    session = session_store.get(session_id)
    if not session:
        return _bad_request("Session not found", status=404)
    if question_index < 0 or question_index >= len(session.questions):
        return _bad_request("Invalid question_index")

    clean_keywords = [str(k).strip() for k in selected_keywords if str(k).strip()]

    try:
        answer = orchestrator.suggest_answer(
            session=session,
            question_index=question_index,
            selected_keywords=clean_keywords,
        )
    except Exception as exc:
        logger.warning("Suggest answer failed, using mock fallback: %s", exc)
        answer = (
            "We will use "
            + ", ".join(clean_keywords)
            + " to shape a practical first version and validate the riskiest assumption quickly."
        )

    return JsonResponse({"answer": answer})


@require_http_methods(["GET", "DELETE"])
@csrf_exempt
def session_detail(request: HttpRequest, session_id: str) -> JsonResponse:
    session = session_store.get(session_id)
    if request.method == "GET":
        if not session:
            return _bad_request("Session not found", status=404)
        return JsonResponse(session.to_dict())

    if not session:
        return _bad_request("Session not found", status=404)
    session_store.delete(session_id)
    return JsonResponse({"message": "Session deleted"})


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

@require_http_methods(["GET"])
def summary(request: HttpRequest, session_id: str) -> JsonResponse:
    return _build_summary_response(session_id)


@csrf_exempt
@require_http_methods(["POST"])
def summary_with_image(request: HttpRequest, session_id: str) -> JsonResponse:
    return _build_summary_response(session_id, include_image=True)


def _build_summary_response(
    session_id: str, include_image: bool = False
) -> JsonResponse:
    session = session_store.get(session_id)
    if not session:
        return _bad_request("Session not found", status=404)

    if not session.summary:
        try:
            session.summary = orchestrator.generate_summary(session)
        except Exception as exc:
            logger.warning("Summary generation failed, using mock: %s", exc)
            session.summary = orchestrator._mock_summary(session)
        image_generation_service.persist_summary(session.summary)

    response_summary = session.summary
    if include_image:
        response_summary = _build_summary_with_image(session, session.summary)

    session_store.save(session)
    payload: dict = {"summary": response_summary}
    if include_image and session.background_image:
        payload["background_image"] = session.background_image.to_dict()
    return JsonResponse(payload)


def _build_summary_with_image(session, summary_text: str) -> str:
    if session.background_image and session.background_image.status == "success":
        return image_generation_service.append_metadata_to_summary(
            summary_text,
            session.background_image.to_dict(),
        )

    try:
        prompt = orchestrator.generate_image_prompt(session.description, summary_text)
    except Exception as exc:
        logger.warning("Image prompt generation failed, using fallback: %s", exc)
        prompt = orchestrator._mock_image_prompt(session.description)

    try:
        image_result = image_generation_service.generate_image(
            business_idea=session.description,
            prompt=prompt,
        )
        session.background_image = ImageAssetState.from_dict(image_result.to_dict())
        return image_generation_service.append_metadata_to_summary(
            summary_text,
            image_result.to_dict(),
        )
    except ImageGenerationError as exc:
        logger.warning(
            "Image generation failed for session %s: %s", session.session_id, exc
        )
        session.background_image = ImageAssetState(
            business_idea=session.description,
            generated_at=datetime.now(timezone.utc).isoformat(),
            status="error",
            error=str(exc),
        )
        return image_generation_service.strip_image_metadata(summary_text)
    except Exception as exc:
        logger.exception(
            "Unexpected error during image generation for session %s", session.session_id
        )
        session.background_image = ImageAssetState(
            business_idea=session.description,
            generated_at=datetime.now(timezone.utc).isoformat(),
            status="error",
            error="Unexpected error",
        )
        return image_generation_service.strip_image_metadata(summary_text)


# ---------------------------------------------------------------------------
# Standalone image generation
# ---------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(["POST"])
def generate_image(request: HttpRequest) -> JsonResponse:
    try:
        payload = _json_body(request)
    except ValueError as exc:
        return _bad_request(str(exc))

    business_idea = str(payload.get("business_idea", "")).strip()
    business_summary = str(payload.get("business_summary", "")).strip()
    if not business_idea:
        return _bad_request("business_idea is required")
    if not business_summary:
        return _bad_request("business_summary is required")

    cleaned_summary = image_generation_service.strip_image_metadata(business_summary)

    # Prompt generation — fall back gracefully if the orchestrator / agents are down.
    try:
        prompt = orchestrator.generate_image_prompt(business_idea, cleaned_summary)
    except Exception as exc:
        logger.warning(
            "generate_image_prompt raised %s — using mock fallback prompt", exc
        )
        prompt = orchestrator._mock_image_prompt(business_idea)

    # Image generation — surface a clean error instead of an unhandled 500/502.
    try:
        image_result = image_generation_service.generate_image(
            business_idea=business_idea,
            prompt=prompt,
        )
    except ImageGenerationError as exc:
        logger.error("ImageGenerationError in generate_image view: %s", exc)
        return JsonResponse(
            {
                "status": "error",
                "business_idea": business_idea,
                "error": str(exc),
            },
            status=502,
        )
    except Exception as exc:
        logger.exception("Unexpected error in generate_image view")
        return JsonResponse(
            {
                "status": "error",
                "business_idea": business_idea,
                "error": "An unexpected server error occurred. Please try again.",
            },
            status=500,
        )

    return JsonResponse(image_result.to_dict())


@require_http_methods(["GET"])
def image_output(request: HttpRequest) -> JsonResponse:
    payload = image_generation_service.latest_image_output()
    if not payload:
        return _bad_request("No generated image output found", status=404)
    return JsonResponse(payload)


@require_http_methods(["GET"])
def serve_image(request: HttpRequest, filename: str) -> FileResponse | JsonResponse:
    try:
        file_path = image_generation_service.resolve_image_path(filename)
    except ImageGenerationError as exc:
        return _bad_request(str(exc), status=404)

    response = FileResponse(
        file_path.open("rb"),
        content_type=image_generation_service.guess_content_type(filename),
    )
    response["Cache-Control"] = "public, max-age=31536000, immutable"
    return response


# ---------------------------------------------------------------------------
# Session reset
# ---------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(["POST"])
def reset_session(request: HttpRequest) -> JsonResponse:
    try:
        payload = _json_body(request)
    except ValueError as exc:
        return _bad_request(str(exc))

    session_id = str(payload.get("session_id", "")).strip()
    index = payload.get("index")
    if not session_id:
        return _bad_request("session_id is required")
    if not isinstance(index, int):
        return _bad_request("index must be an integer")

    session = session_store.get(session_id)
    if not session:
        return _bad_request("Session not found", status=404)
    if index < 0:
        return _bad_request("index must be >= 0")

    if index < len(session.questions):
        session.questions = session.questions[: index + 1]
        target = session.questions[index]
        target.is_satisfactory = False
        target.satisfaction_reason = None
    session.summary = None
    session.background_image = None
    session_store.save(session)
    return JsonResponse(session.to_dict())


# ---------------------------------------------------------------------------
# Logo generation (async views)
# ---------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(["POST"])
async def generate_names(request: HttpRequest) -> JsonResponse:
    try:
        payload = _json_body(request)
        business_description = str(payload.get("business_description", "")).strip()
        if not business_description:
            return _bad_request("business_description is required")

        names = await logo_generation_service.generate_brand_names(business_description)
        return JsonResponse({"success": True, "names": names})
    except Exception as exc:
        logger.exception("Unexpected error in generate_names")
        return JsonResponse({"success": False, "error": str(exc)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
async def logo_palettes(request: HttpRequest) -> JsonResponse:
    try:
        payload = _json_body(request)
        business_description = str(payload.get("business_description", "")).strip()
        if not business_description:
            return _bad_request("business_description is required")

        palettes = await logo_generation_service.generate_logo_palettes(
            business_description
        )
        return JsonResponse({"success": True, "palettes": {"palettes": palettes}})
    except Exception as exc:
        logger.exception("Unexpected error in logo_palettes")
        return JsonResponse({"success": False, "error": str(exc)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
async def logo_suggestions(request: HttpRequest) -> JsonResponse:
    try:
        payload = _json_body(request)
        business_description = str(payload.get("business_description", "")).strip()
        if not business_description:
            return _bad_request("business_description is required")

        suggestions = await logo_generation_service.generate_logo_suggestions(
            business_description
        )
        return JsonResponse({"success": True, "suggestions": suggestions})
    except Exception as exc:
        logger.exception("Unexpected error in logo_suggestions")
        return JsonResponse({"success": False, "error": str(exc)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
async def logo_generate(request: HttpRequest) -> JsonResponse:
    try:
        payload = _json_body(request)
        business_description = str(payload.get("business_description", "")).strip()
        logo_description = str(payload.get("logo_description", "")).strip()
        color_palette = payload.get("color_palette", [])
        style = str(payload.get("style", "Modern")).strip()

        if not business_description or not logo_description:
            return _bad_request(
                "business_description and logo_description are required"
            )
        if not isinstance(color_palette, list):
            return _bad_request("color_palette must be a list")

        result = await logo_generation_service.generate_logo(
            business_description=business_description,
            logo_description=logo_description,
            color_palette=color_palette,
            style=style,
        )
        return JsonResponse(result)
    except Exception as exc:
        logger.exception("Unexpected error in logo_generate")
        return JsonResponse({"success": False, "error": str(exc)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
async def logo_generate_3d(request: HttpRequest) -> JsonResponse:
    try:
        payload = _json_body(request)
        business_description = str(payload.get("business_description", "")).strip()
        logo_description = str(payload.get("logo_description", "")).strip()
        color_palette = payload.get("color_palette", [])

        if not business_description or not logo_description:
            return _bad_request(
                "business_description and logo_description are required"
            )
        if not isinstance(color_palette, list):
            return _bad_request("color_palette must be a list")

        result = await logo_generation_service.generate_3d_logo(
            business_description=business_description,
            logo_description=logo_description,
            color_palette=color_palette,
        )
        return JsonResponse(result)
    except Exception as exc:
        logger.exception("Unexpected error in logo_generate_3d")
        return JsonResponse({"success": False, "error": str(exc)}, status=500)
