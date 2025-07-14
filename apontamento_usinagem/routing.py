from django.urls import re_path
from .consumers import OrdemIniciadaConsumer

websocket_urlpatterns = [
    re_path(r'ws/ordens/iniciadas/$', OrdemIniciadaConsumer.as_asgi()),
]
