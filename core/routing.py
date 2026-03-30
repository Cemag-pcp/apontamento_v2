from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/ordens/iniciadas/$', consumers.OrdemIniciadaConsumer.as_asgi()),
    re_path(r'ws/almox/solicitacoes/$', consumers.AlmoxSolicitacoesConsumer.as_asgi()),
]
