# ASGI/Daphne desabilitado (ver core/routing.py). O servico roda como WSGI
# puro via gunicorn (apontamento_v2.wsgi:application). Arquivo mantido
# comentado para reversao facil caso o WebSocket precise voltar.

# import os
# from channels.routing import ProtocolTypeRouter, URLRouter
# from django.core.asgi import get_asgi_application
# from channels.auth import AuthMiddlewareStack
# from core.routing import websocket_urlpatterns
#
# os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'apontamento_v2.settings')
#
# application = ProtocolTypeRouter({
#     "http": get_asgi_application(),
#     "websocket": AuthMiddlewareStack(
#         URLRouter(
#             websocket_urlpatterns
#         )
#     ),
# })
