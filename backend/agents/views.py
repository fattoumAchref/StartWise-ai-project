import json
from django.http import StreamingHttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .graph import compiled_graph

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