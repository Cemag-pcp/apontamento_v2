# WebSocket desabilitado por completo (ver notificar_ordem em core/utils.py e
# o commit e34d816b). O projeto agora roda como WSGI puro (gunicorn), sem
# Daphne/Channels. Infra mantida comentada para reversao facil.

# from django.urls import re_path
# from . import consumers
#
# websocket_urlpatterns = [
#     re_path(r'ws/ordens/iniciadas/$', consumers.OrdemIniciadaConsumer.as_asgi()),
#     re_path(r'ws/almox/solicitacoes/$', consumers.AlmoxSolicitacoesConsumer.as_asgi()),
# ]

websocket_urlpatterns = []
