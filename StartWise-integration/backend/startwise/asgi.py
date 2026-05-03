import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'startwise.settings')
# On récupère l'application HTTP d'abord
django_asgi_app = get_asgi_application()

import agents.routing
from cfo.websocket_routing import websocket_urlpatterns as cfo_ws

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": URLRouter(
        agents.routing.websocket_urlpatterns + cfo_ws
    ),
})
