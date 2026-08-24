# WebSocket desabilitado (ver core/routing.py). Nao referenciado por nada -
# mantido comentado para reversao facil.

# import json
# from channels.generic.websocket import AsyncWebsocketConsumer
#
# class OrdemIniciadaConsumer(AsyncWebsocketConsumer):
#     async def connect(self):
#         await self.channel_layer.group_add("ordens_iniciadas", self.channel_name)
#         await self.accept()
#
#     async def disconnect(self, close_code):
#         await self.channel_layer.group_discard("ordens_iniciadas", self.channel_name)
#
#     async def enviar_ordem(self, event):
#         await self.send(text_data=json.dumps(event["data"]))
#
#
# class AlmoxSolicitacoesConsumer(AsyncWebsocketConsumer):
#     async def connect(self):
#         await self.channel_layer.group_add("almox_solicitacoes", self.channel_name)
#         await self.accept()
#
#     async def disconnect(self, close_code):
#         await self.channel_layer.group_discard("almox_solicitacoes", self.channel_name)
#
#     async def enviar_acao_almox(self, event):
#         await self.send(text_data=json.dumps(event["data"]))
