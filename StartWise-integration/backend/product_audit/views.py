from __future__ import annotations

import json
import logging

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .services.orchestrator import product_audit_orchestrator
from .services.schemas import AuditAttachment, AuditSessionState
from .services.session_store import product_audit_session_store


logger = logging.getLogger(__name__)


def _json_body(request: HttpRequest) -> dict:
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid JSON body") from exc


def _bad_request(message: str, status: int = 400) -> JsonResponse:
    return JsonResponse({"detail": message}, status=status)


def _parse_attachments(raw_items: object) -> list[AuditAttachment]:
    if raw_items is None:
        return []
    if not isinstance(raw_items, list):
        raise ValueError("attachments must be a list")

    items: list[AuditAttachment] = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        items.append(AuditAttachment.from_dict(raw))
    return items


def _coerce_bool(value: object, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    cleaned = str(value).strip().lower()
    if cleaned in {"1", "true", "yes", "on"}:
        return True
    if cleaned in {"0", "false", "no", "off"}:
        return False
    return default


@require_http_methods(["GET"])
def health_check(request: HttpRequest) -> JsonResponse:
    return JsonResponse(
        {
            "status": "healthy",
            "service": "startwise-product-audit",
            "providers": product_audit_orchestrator.capabilities(),
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
def analyze_product(request: HttpRequest) -> JsonResponse:
    try:
        payload = _json_body(request)
        attachments = _parse_attachments(payload.get("attachments"))
    except ValueError as exc:
        return _bad_request(str(exc))

    session_id = str(payload.get("session_id", "")).strip()
    startup_name = str(payload.get("startup_name", "")).strip()
    product_description = str(payload.get("product_description", "")).strip()
    website_url = str(payload.get("website_url", "")).strip() or None
    audit_goal = str(payload.get("audit_goal", "")).strip()
    include_search = _coerce_bool(payload.get("include_search"), default=True)

    if not session_id:
        return _bad_request("session_id is required")
    if not startup_name and not product_description and not website_url and not attachments:
        return _bad_request(
            "Provide at least one of startup_name, product_description, website_url, or attachments"
        )

    session = AuditSessionState(
        session_id=session_id,
        startup_name=startup_name,
        product_description=product_description,
        website_url=website_url,
        audit_goal=audit_goal,
        attachments=attachments,
    )
    product_audit_session_store.save(session)

    try:
        product_audit_orchestrator.run(session, include_search=include_search)
    except Exception as exc:
        logger.exception("Product audit failed for session %s", session_id)
        session.status = "error"
        session.error = str(exc)
        product_audit_session_store.save(session)
        return JsonResponse({"detail": "Product audit failed", "error": str(exc)}, status=500)

    product_audit_session_store.save(session)
    return JsonResponse(session.to_dict())


@require_http_methods(["GET", "DELETE"])
@csrf_exempt
def session_detail(request: HttpRequest, session_id: str) -> JsonResponse:
    session = product_audit_session_store.get(session_id)
    if not session:
        return _bad_request("Session not found", status=404)

    if request.method == "DELETE":
        product_audit_session_store.delete(session_id)
        return JsonResponse({"message": "Session deleted"})

    return JsonResponse(session.to_dict())
