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

# Démarrage des singletons agents au boot de Django
try:
    from cfo.session_manager import startup_singletons
    startup_singletons()
except Exception as _e:
    import logging
    logging.getLogger(__name__).warning("[asgi] startup_singletons failed: %s", _e)
