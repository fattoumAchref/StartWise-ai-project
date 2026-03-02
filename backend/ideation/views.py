import json

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .services.orchestrator import orchestrator
from .services.schemas import QuestionState
from .services.session_store import session_store


def _json_body(request: HttpRequest) -> dict:
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid JSON body") from exc


def _bad_request(message: str, status: int = 400) -> JsonResponse:
    return JsonResponse({"detail": message}, status=status)


@require_http_methods(["GET"])
def health_check(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "healthy", "service": "startwise-ideation-django"})


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
    question, keywords = orchestrator.generate_next_question(session)
    session.questions.append(
        QuestionState(
            question=question,
            keywords=keywords,
        )
    )
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
    is_ok, reason = orchestrator.evaluate_answer(session, question_index, response_text)
    question.is_satisfactory = is_ok
    question.satisfaction_reason = reason

    has_more_questions = False
    next_question: str | None = None
    if is_ok and len(session.questions) < orchestrator.max_questions:
        next_question, next_keywords = orchestrator.generate_next_question(session)
        session.questions.append(
            QuestionState(
                question=next_question,
                keywords=next_keywords,
            )
        )
        has_more_questions = True

    session_store.save(session)
    return JsonResponse(
        {
            "question": next_question,
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
        question.keywords = orchestrator.generate_keywords(question.question, session)
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

    answer = orchestrator.suggest_answer(
        session=session,
        question_index=question_index,
        selected_keywords=[str(k).strip() for k in selected_keywords if str(k).strip()],
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


@require_http_methods(["GET"])
def summary(request: HttpRequest, session_id: str) -> JsonResponse:
    return _build_summary_response(session_id)


def _build_summary_response(session_id: str) -> JsonResponse:
    session = session_store.get(session_id)
    if not session:
        return _bad_request("Session not found", status=404)

    if not session.summary:
        session.summary = orchestrator.generate_summary(session)
        session_store.save(session)
    return JsonResponse({"summary": session.summary})


@csrf_exempt
@require_http_methods(["POST"])
def summary_with_image(request: HttpRequest, session_id: str) -> JsonResponse:
    # For now this returns the same summary contract expected by frontend.
    # Image generation metadata can be appended later.
    return _build_summary_response(session_id)


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
    session_store.save(session)
    return JsonResponse(session.to_dict())
