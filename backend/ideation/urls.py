from django.urls import path

from . import views


urlpatterns = [
    path("health", views.health_check),
    path("init", views.init_session),
    path("respond", views.respond),
    path("keywords/<str:session_id>/<int:question_index>", views.keywords),
    path("suggest", views.suggest),
    path("session/<str:session_id>", views.session_detail),
    path("summary/<str:session_id>", views.summary),
    path("summary-with-image/<str:session_id>", views.summary_with_image),
    path("reset", views.reset_session),
]
