from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),

    # ── FinAgent (finance / investment / PDF / A2A) ───────────────────────────
    path('api/', include('cfo.urls')),

    # ── Colleague agents REST (upload-document, send-email, etc.) ────────────
    path('api/', include('agents.urls')),

    # ── Ideation module — ADK Q&A flow ────────────────────────────────────────
    path('ideation/', include('ideation.urls')),

    # ── Product Audit module — Gemini + Qdrant ────────────────────────────────
    path('product-audit/', include('product_audit.urls')),
]
