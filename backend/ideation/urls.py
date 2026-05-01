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
    path("generate-image", views.generate_image),
    path("image-output", views.image_output),
    path("images/<str:filename>", views.serve_image),
    path("reset", views.reset_session),
    
    # Logo Generation Routes
    path("logo/generate-names", views.generate_names),
    path("logo/generate-palettes", views.logo_palettes),
    path("logo/suggestions", views.logo_suggestions),
    path("logo/generate", views.logo_generate),
    path("logo/generate-3d", views.logo_generate_3d),
]
