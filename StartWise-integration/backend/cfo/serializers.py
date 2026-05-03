"""
api/serializers.py
==================
JSON serialisation helpers.
Convert internal Python objects (dataclasses, Pydantic models, enums)
into plain dicts safe for JsonResponse.
"""
from __future__ import annotations
import math
from typing import Any

from django.http import JsonResponse


# ── Core converter ────────────────────────────────────────────────────────────

def to_dict(obj: Any) -> Any:
    """Recursively convert any object to a JSON-serialisable dict.
    Replaces NaN / Infinity floats with None so browsers don't choke."""
    if obj is None:
        return None
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_dict(i) for i in obj]
    if hasattr(obj, "__dataclass_fields__"):
        from dataclasses import asdict
        return {k: to_dict(v) for k, v in asdict(obj).items()}
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "value"):
        return obj.value
    if isinstance(obj, (str, int, bool)):
        return obj
    return str(obj)


def safe_json(data: dict) -> JsonResponse:
    """Return a JsonResponse after sanitising all floats."""
    return JsonResponse(to_dict(data))


# ── Domain-specific serialisers ───────────────────────────────────────────────

def ser_analysis(analysis: dict) -> dict:
    if not analysis:
        return {}
    out: dict = {}
    for key in ("kpis", "monte_carlo", "scenarios", "seasonality", "comparator"):
        val = analysis.get(key)
        if val is not None:
            out[key] = to_dict(val)
    phase = analysis.get("phase")
    if phase:
        out["phase"] = phase.name if hasattr(phase, "name") else str(phase)
    confidence = analysis.get("confidence")
    if confidence is not None:
        out["confidence"] = to_dict(confidence)
    return out


def ser_validation(v: Any) -> dict | None:
    if v is None:
        return None
    return {
        "is_valid":            getattr(v, "is_valid", False),
        "data_quality_score":  getattr(v, "data_quality_score", 0),
        "missing_critical":    list(getattr(v, "missing_critical", []) or []),
        "incoherences":        list(getattr(v, "incoherences", []) or []),
        "questions_to_ask":    list(getattr(v, "questions_to_ask", []) or []),
    }


def ser_ctx(ctx: Any) -> dict | None:
    if ctx is None:
        return None
    try:
        from dataclasses import asdict
        d = asdict(ctx)
        for k, v in d.items():
            if hasattr(v, "name"):   d[k] = v.name
            elif hasattr(v, "value"): d[k] = v.value
        return d
    except Exception:
        return None


def ser_bench(bench: Any) -> dict | None:
    if bench is None:
        return None

    # Parse extra metrics from raw Chroma documents
    extra_metrics: dict = {}
    for doc in getattr(bench, "documents_raw", []) or []:
        meta = doc.get("metadata", {}) if isinstance(doc, dict) else {}
        for key in ("ltv_cac_ratio", "cac_payback_months", "nrr", "growth_rate_yoy",
                    "cac_median", "ltv_median", "arpu", "logo_churn", "revenue_per_employee"):
            if key in meta and extra_metrics.get(key) is None:
                try:
                    extra_metrics[key] = float(meta[key])
                except (TypeError, ValueError):
                    pass

    return {
        "source":               getattr(bench, "source", ""),
        "similarity_score":     getattr(bench, "similarity_score", 0),
        "churn_median":         getattr(bench, "churn_median", None),
        "gross_margin_median":  getattr(bench, "gross_margin_median", None),
        "valorisation_multiple":getattr(bench, "valorisation_multiple", None),
        "cac_median":           getattr(bench, "cac_median", None),
        "ltv_median":           getattr(bench, "ltv_median", None),
        **extra_metrics,
    }


def ser_task(task: Any) -> dict | None:
    if task is None:
        return None
    try:
        return task.to_dict() if hasattr(task, "to_dict") else None
    except Exception:
        return None
