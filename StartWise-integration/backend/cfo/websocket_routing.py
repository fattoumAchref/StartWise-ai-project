from django.urls import re_path
from cfo import websocket_consumer

websocket_urlpatterns = [
    re_path(r"ws/a2a/$", websocket_consumer.A2AConsumer.as_asgi()),
]
