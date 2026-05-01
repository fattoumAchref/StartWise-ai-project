from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # Utilise .as_asgi() qui est la méthode standard de Channels
    re_path(r'^ws/agents/?$', consumers.AgentConsumer.as_asgi()),
]