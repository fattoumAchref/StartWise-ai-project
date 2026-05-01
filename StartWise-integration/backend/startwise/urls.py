"""
URL configuration for startwise project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),

    # ── FinAgent CFO — Financial viability analysis ───────────────────────
    path('api/', include('cfo.urls')),

    # ── StartWise agents REST (upload-document, etc.) ─────────────────────
    path('api/', include('agents.urls')),

    # ── Ideation module — ADK Q&A flow ────────────────────────────────────
    # Routes: /health, /init, /respond, /keywords/…, /suggest, /summary/…
    path('ideation/', include('ideation.urls')),

    # ── Product Audit module — Gemini + Qdrant ────────────────────────────
    path('product-audit/', include('product_audit.urls')),

    # ── Legal Advisor — RAG juridique tunisien ────────────────────────────
    path('legal/', include('legal_advisor.urls')),
]
