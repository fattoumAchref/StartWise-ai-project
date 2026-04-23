from django.urls import path
from api import views

urlpatterns = [
    path("chat", views.chat_view),
    path("state", views.state_view),
    path("a2a/state", views.a2a_state_view),
    path("a2a/clarification", views.a2a_clarification_view),
    path("a2a/toggle-whatif", views.toggle_whatif_view),
    path("toggle-section", views.toggle_section_view),
    path("whatif", views.whatif_view),
    path("pdf", views.pdf_view),
    path("upload", views.upload_view),
    path("reset", views.reset_view),
    path("new-conversation", views.new_conversation_view),
    path("conversations", views.conversations_view),
    path("restore-conversation", views.restore_conversation_view),
    path("conversations/<str:conv_id>/delete", views.delete_conversation_view),
]
