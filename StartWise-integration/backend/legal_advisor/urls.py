from django.urls import path
from . import views

urlpatterns = [
    path(".well-known/agent.json", views.agent_card, name="legal_agent_card"),
    path("",               views.index,         name="index"),
    path("stats",          views.stats,          name="stats"),
    path("favicon.ico",    views.favicon,        name="favicon"),
    path("session/clear",  views.session_clear,  name="session_clear"),
    path("ask",            views.ask,            name="ask"),
    path("domains",        views.domains,        name="domains"),
]
