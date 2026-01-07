import json
from channels.generic.websocket import AsyncWebsocketConsumer

class OrdemIniciadaConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.channel_layer.group_add("ordens_iniciadas", self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("ordens_iniciadas", self.channel_name)

    async def enviar_ordem(self, event):
        await self.send(text_data=json.dumps(event["data"]))