from django.urls import path

from . import views


urlpatterns = [
    path("health", views.health_check),
    path("analyze", views.analyze_product),
    path("session/<str:session_id>", views.session_detail),
]
