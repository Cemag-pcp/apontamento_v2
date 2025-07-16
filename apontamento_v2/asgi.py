import os
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from channels.auth import AuthMiddlewareStack
from apontamento_usinagem.routing import websocket_urlpatterns  # crie esse arquivo

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'apontamento_v2.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            websocket_urlpatterns
        )
    ),
})
