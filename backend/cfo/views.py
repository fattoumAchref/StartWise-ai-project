"""
api/views.py
============
HTTP view layer — thin REST handlers only.
All business logic lives in the modules below:
  - cfo_engine.py  : LLM, pipeline, what-if, context merging
  - formatters.py  : Markdown text formatting
  - serializers.py : JSON serialisation
  - session_utils.py : Redis session + agent singletons
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
import uuid
from pathlib import Path

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from cfo.serializers import (
    safe_json, ser_analysis, ser_validation, ser_ctx, ser_bench, ser_task,
)
from cfo.formatters import parse_docs_extra
from cfo.cfo_engine import (
    MODULES_OK,
    has_financial_data, is_ideation_message, extract_ideation_sector,
    answer_general, run_whatif, process_ctx, build_ideation_preanalysis,
)
from cfo.session_manager import (
    delete_state, get_a2a_classes, get_comm_agent,
    get_finance_agent, get_state, save_state,
)

logger = logging.getLogger(__name__)


# ── Session ID ────────────────────────────────────────────────────────────────

def _sid(request) -> str:
    """Resolve session ID: prefer X-Session-ID header, fall back to Django cookie."""
    sid = request.headers.get("X-Session-ID", "").strip()
    if sid:
        return sid
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key


# ── /api/chat ─────────────────────────────────────────────────────────────────

@csrf_exempt
@require_http_methods(["POST"])
def chat_view(request):
    if not MODULES_OK:
        return JsonResponse({"error": "Modules non chargés"}, status=500)

    session_id = _sid(request)
    body   = json.loads(request.body)
    prompt = body.get("message", "").strip()
    silent = body.get("silent", False)  # block answers set this to skip chat history
    if not prompt:
        return JsonResponse({"error": "Message vide"}, status=400)

    state    = get_state(session_id)
    messages = state.get("messages", [])
    if not silent:
        messages.append({"role": "user", "content": prompt})

    # Parse prompt → FinancialContext
    new_ctx = None
    try:
        from finagents.finance.tools.parser import parse_founder_input
        new_ctx = parse_founder_input(prompt)
    except Exception as exc:
        logger.warning("parse_founder_input: %s", exc)

    # What-if mode
    if state.get("whatif_mode") and state.get("financial_context") is not None:
        reply = run_whatif(prompt, state["financial_context"])
        state["whatif_mode"] = False
        messages.append({"role": "assistant", "content": reply})
        state["messages"] = messages
        save_state(session_id, state)
        return JsonResponse({"type": "whatif", "reply": reply, "messages": messages})

    # Financial data detected → full pipeline
    if has_financial_data(new_ctx):
        data_text, questions, bench = process_ctx(state, new_ctx, raw_text=prompt)
        bench_text = state.get("last_bench_text", "")
        reply = data_text
        if bench_text:
            reply += "\n\n" + bench_text
        if not silent and questions:
            reply += "\n\n---\n**Questions pour compléter l'analyse :**\n" + "\n".join(f"- {q}" for q in questions)
        if not silent:
            messages.append({"role": "assistant", "content": reply})
        state["messages"] = messages
        save_state(session_id, state)
        return safe_json({
            "type":             "analysis",
            "reply":            reply,
            "data_text":        data_text,
            "bench_text":       bench_text,
            "questions":        questions,
            "analysis":         ser_analysis(state.get("analysis", {})),
            "financial_context":ser_ctx(state.get("financial_context")),
            "validation":       ser_validation(state.get("validation_result")),
            "bench":            ser_bench(bench),
            "bench_extra":      state.get("last_bench_extra", {}),
            "agent_task":       ser_task(state.get("agent_task")),
            "a2a_publish_time": state.get("a2a_publish_time"),
            "messages":         messages,
        })

    # Ideation message (no real financial data yet)
    if is_ideation_message(prompt):
        reply = build_ideation_preanalysis(prompt)
        # Do not append this bootstrap answer to chat history to avoid polluting
        # the free-chat panel with auto-triggered ideation context messages.
        state["preanalysis_text"] = reply
        state["messages"] = messages
        save_state(session_id, state)
        return JsonResponse({"type": "ideation_preanalysis", "reply": reply, "messages": messages})

    # General question
    reply = answer_general(prompt, state.get("financial_context"))
    if not silent:
        messages.append({"role": "assistant", "content": reply})
    state["messages"] = messages
    save_state(session_id, state)
    return JsonResponse({"type": "general", "reply": reply, "messages": messages})


# ── /api/state ────────────────────────────────────────────────────────────────

@csrf_exempt
@require_http_methods(["GET"])
def state_view(request):
    session_id = _sid(request)
    state      = get_state(session_id)
    task       = state.get("agent_task")
    task_state = getattr(getattr(task, "status", None), "state", "")
    return safe_json({
        "messages":              state.get("messages", []),
        "preanalysis_text":      state.get("preanalysis_text", ""),
        "financial_context":     ser_ctx(state.get("financial_context")),
        "validation":            ser_validation(state.get("validation_result")),
        "analysis":              ser_analysis(state.get("analysis", {})),
        "bench":                 ser_bench(state.get("last_bench")),
        "bench_extra":           state.get("last_bench_extra", {}),
        "bench_text":            state.get("last_bench_text", ""),
        "shown_sections":        list(state.get("shown_sections", set())),
        "whatif_mode":           state.get("whatif_mode", False),
        "awaiting_clarification":state.get("awaiting_clarification", False),
        "a2a_publish_time":      state.get("a2a_publish_time"),
        "agent_task_state":      task_state,
        "agent_task":            ser_task(task),
        "conversations":         [{"id": c["id"], "title": c["title"]}
                                  for c in state.get("conversations", [])],
    })


# ── /api/a2a-state ────────────────────────────────────────────────────────────

@csrf_exempt
@require_http_methods(["GET"])
def a2a_state_view(request):
    comm = get_comm_agent()
    if comm is None or not os.getenv("A2A_BUS_URL"):
        return JsonResponse({"available": False})
    try:
        return safe_json({"available": True, **comm.get_state()})
    except Exception as exc:
        return JsonResponse({"available": False, "error": str(exc)})


# ── /api/a2a-clarification ────────────────────────────────────────────────────

@csrf_exempt
@require_http_methods(["POST"])
def a2a_clarification_view(request):
    import time
    session_id = _sid(request)
    comm       = get_comm_agent()
    if comm is None:
        return JsonResponse({"error": "CommAgent non disponible"}, status=503)
    body   = json.loads(request.body)
    answer = body.get("answer", "")
    comm.answer_clarification(answer)
    state = get_state(session_id)
    state["awaiting_clarification"] = False
    state["a2a_publish_time"]       = time.time()
    msgs = state.get("messages", [])
    msgs.append({"role": "user",      "content": answer})
    msgs.append({"role": "assistant", "content": "Réponse transmise à l'investment_agent. Analyse en cours..."})
    state["messages"] = msgs
    save_state(session_id, state)
    return JsonResponse({"ok": True})


# ── /api/toggle-section ───────────────────────────────────────────────────────

@csrf_exempt
@require_http_methods(["POST"])
def toggle_section_view(request):
    session_id = _sid(request)
    body       = json.loads(request.body)
    section    = body.get("section", "")
    state      = get_state(session_id)
    sections   = state.get("shown_sections", set())
    if isinstance(sections, list):
        sections = set(sections)
    sections.discard(section) if section in sections else sections.add(section)
    state["shown_sections"] = sections
    save_state(session_id, state)
    return JsonResponse({"shown_sections": list(sections)})


# ── /api/toggle-whatif ────────────────────────────────────────────────────────

@csrf_exempt
@require_http_methods(["POST"])
def toggle_whatif_view(request):
    session_id = _sid(request)
    state      = get_state(session_id)
    state["whatif_mode"] = not state.get("whatif_mode", False)
    save_state(session_id, state)
    return JsonResponse({"whatif_mode": state["whatif_mode"]})


# ── /api/whatif ───────────────────────────────────────────────────────────────

@csrf_exempt
@require_http_methods(["POST"])
def whatif_view(request):
    session_id = _sid(request)
    body       = json.loads(request.body)
    prompt     = body.get("prompt", "")
    state      = get_state(session_id)
    reply      = run_whatif(prompt, state.get("financial_context"))
    msgs       = state.get("messages", [])
    msgs.append({"role": "user",      "content": prompt})
    msgs.append({"role": "assistant", "content": reply})
    state["messages"]    = msgs
    state["whatif_mode"] = False
    save_state(session_id, state)
    return JsonResponse({"reply": reply, "messages": msgs})


# ── /api/pdf ──────────────────────────────────────────────────────────────────

@csrf_exempt
@require_http_methods(["POST"])
def pdf_view(request):
    import traceback
    from datetime import datetime
    session_id = _sid(request)
    state      = get_state(session_id)
    ctx        = state.get("financial_context")
    if ctx is None:
        return JsonResponse({"error": "Aucune donnée disponible"}, status=400)
    try:
        from finagents.finance.tools.pdf_report import generate_pdf_report
        pdf_bytes = generate_pdf_report(
            ctx,
            state.get("validation_result"),
            state.get("analysis", {}),
            state.get("last_bench"),
            state.get("last_bench_extra", {}),
        )
        if not isinstance(pdf_bytes, (bytes, bytearray)):
            pdf_bytes = bytes(pdf_bytes)
        date_str  = datetime.now().strftime("%Y%m%d")
        response  = HttpResponse(bytes(pdf_bytes), content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="startwise_rapport_{date_str}.pdf"'
        response["Content-Length"]      = len(pdf_bytes)
        response["Cache-Control"]       = "no-cache"
        return response
    except Exception:
        return JsonResponse({"error": traceback.format_exc()}, status=500)


# ── /api/upload ───────────────────────────────────────────────────────────────

@csrf_exempt
@require_http_methods(["POST"])
def upload_view(request):
    if not MODULES_OK:
        return JsonResponse({"error": "Modules non chargés"}, status=500)
    session_id = _sid(request)
    uploaded   = request.FILES.get("file")
    if not uploaded:
        return JsonResponse({"error": "Aucun fichier reçu"}, status=400)
    suffix = Path(uploaded.name).suffix
    try:
        from finagents.finance.tools.parser import parse_founder_input
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            for chunk in uploaded.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name
        new_ctx = parse_founder_input(tmp_path)
        os.unlink(tmp_path)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)

    state = get_state(session_id)
    if has_financial_data(new_ctx):
        data_text, questions, bench = process_ctx(state, new_ctx, raw_text="")
        save_state(session_id, state)
        return JsonResponse({
            "type":             "analysis",
            "data_text":        data_text,
            "questions":        questions,
            "analysis":         ser_analysis(state.get("analysis", {})),
            "financial_context":ser_ctx(state.get("financial_context")),
            "validation":       ser_validation(state.get("validation_result")),
            "bench":            ser_bench(bench),
        })
    return JsonResponse({"type": "no_data",
                         "message": "Aucune donnée financière détectée dans le fichier"})


# ── /api/prefetch-benchmarks ──────────────────────────────────────────────────

@csrf_exempt
@require_http_methods(["POST"])
def prefetch_benchmarks_view(request):
    """Fetch sector benchmarks early (before full financial data) using ideation context."""
    if not MODULES_OK:
        return JsonResponse({"error": "Modules non chargés"}, status=500)
    session_id = _sid(request)
    body = json.loads(request.body)
    secteur = body.get("secteur", "SaaS")
    pays = body.get("pays", "TN")
    state = get_state(session_id)
    # Don't re-fetch if we already have a valid bench in state
    existing_bench = state.get("last_bench")
    if existing_bench is not None and getattr(existing_bench, "source", "unavailable") != "unavailable":
        return safe_json({"bench": ser_bench(existing_bench), "bench_extra": state.get("last_bench_extra", {}), "cached": True})
    try:
        from finagents.models.data_models import FinancialContext, DataQuality, Phase
        from finagents.finance.tools.benchmark_fetcher import fetch_benchmarks
        from cfo.formatters import parse_docs_extra, format_benchmark_result
        ctx = FinancialContext(
            burn_rate=None, cash_balance=None, monthly_revenue=None,
            n_clients=None, prix_client=None, churn_rate=None,
            marketing_budget=None, new_clients_month=None, cogs=None,
            months_data=None, secteur=secteur, pays=pays,
            phase_hint=Phase.SEED, intent_fundraising=False,
            burn_quality=DataQuality.MISSING, cash_quality=DataQuality.MISSING,
            revenue_quality=DataQuality.MISSING, hypotheses=[], revenue_history=[],
        )
        bench = fetch_benchmarks(ctx)
        if bench is not None and getattr(bench, "source", "unavailable") != "unavailable":
            state["last_bench"] = bench
            state["last_bench_extra"] = parse_docs_extra(list(getattr(bench, "documents_raw", []) or []))
            bench_text = format_benchmark_result(bench, ctx)
            if bench_text:
                state["last_bench_text"] = bench_text
            save_state(session_id, state)
            return safe_json({"bench": ser_bench(bench), "bench_extra": state["last_bench_extra"], "bench_text": bench_text, "cached": False})
        return JsonResponse({"bench": None, "reason": "no_data"})
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)


# ── /api/reset ────────────────────────────────────────────────────────────────

@csrf_exempt
@require_http_methods(["DELETE", "POST"])
def reset_view(request):
    delete_state(_sid(request))
    return JsonResponse({"ok": True})


# ── /api/conversations ────────────────────────────────────────────────────────

@csrf_exempt
@require_http_methods(["POST"])
def new_conversation_view(request):
    session_id = _sid(request)
    state      = get_state(session_id)
    msgs       = state.get("messages", [])
    if msgs and any(m["role"] == "user" for m in msgs):
        first = next((m["content"] for m in msgs if m["role"] == "user"), "Conv")
        title = first[:40] + ("..." if len(first) > 40 else "")
        conv  = {"id": str(uuid.uuid4()), "title": title, "messages": msgs}
        convs = state.get("conversations", [])
        convs.insert(0, conv)
        state["conversations"] = convs[:20]
    from cfo.session_manager import _default_state
    new_state = _default_state()
    new_state["conversations"] = state.get("conversations", [])
    save_state(session_id, new_state)
    return JsonResponse({"ok": True})


@csrf_exempt
@require_http_methods(["GET"])
def conversations_view(request):
    state = get_state(_sid(request))
    return JsonResponse({"conversations": [{"id": c["id"], "title": c["title"]}
                                           for c in state.get("conversations", [])]})


@csrf_exempt
@require_http_methods(["POST"])
def restore_conversation_view(request):
    session_id = _sid(request)
    body       = json.loads(request.body)
    conv_id    = body.get("conversation_id", "")
    state      = get_state(session_id)
    conv       = next((c for c in state.get("conversations", []) if c["id"] == conv_id), None)
    if conv is None:
        return JsonResponse({"error": "Conversation non trouvée"}, status=404)
    state["messages"] = conv.get("messages", [])
    save_state(session_id, state)
    return JsonResponse({"ok": True, "messages": conv.get("messages", [])})


@csrf_exempt
@require_http_methods(["DELETE"])
def delete_conversation_view(request, conv_id: str):
    session_id = _sid(request)
    state      = get_state(session_id)
    state["conversations"] = [c for c in state.get("conversations", []) if c["id"] != conv_id]
    save_state(session_id, state)
    return JsonResponse({"ok": True})
