import json
from django.utils.timezone import localtime
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async


class OrdemIniciadaConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.channel_layer.group_add("ordens_iniciadas", self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("ordens_iniciadas", self.channel_name)

    async def enviar_ordem(self, event):
        await self.send(text_data=json.dumps(event["data"]))


class NotificacaoConsumer(AsyncWebsocketConsumer):

    @database_sync_to_async
    def get_notificacoes(self, user):

        from .models import Notificacao

        user_profile = user.profile
        ultimas_notificacoes = Notificacao.objects.filter(profile=user_profile).order_by("-criado_em")[:3]
        
        notificacoes_data = [
            {
                "id": n.id,
                "titulo": n.titulo if len(n.titulo) < 45 else f"{n.titulo[0:44]}...",
                "mensagem": n.mensagem if len(n.mensagem) < 45 else f"{n.mensagem[0:44]}...",
                "tempo": localtime(n.criado_em).strftime("%d/%m %H:%M"),
                "tipo": n.tipo,  # <-- ADICIONADO
                "lido": n.lido, # <-- ADICIONADO
            }
            for n in ultimas_notificacoes
        ]
        
        quantidade_nao_lida = Notificacao.objects.filter(profile=user_profile, lido=False).count()
        
        # Estrutura para a carga inicial
        return {
            "type": "carga_inicial", # <-- ADICIONADO
            "payload": {
                "quantidade": quantidade_nao_lida,
                "notificacoes": notificacoes_data,
            }
        }

    async def connect(self):
        user = self.scope["user"]
        if user.is_anonymous:
            await self.close()
        else:
            self.group_name = f"notificacoes_{user.id}"
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()

            data = await self.get_notificacoes(user)
            await self.send(text_data=json.dumps(data))

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receber_notificacao(self, event):
        """
        Handler que recebe notificações do group_send via sinal.
        O 'event' contém a chave 'data' que definimos no sinal.
        """
        # Extrai o payload de dados enviado pelo sinal
        dados_para_enviar = event["data"]
        
        # Envia os dados para o cliente WebSocket conectado
        await self.send(text_data=json.dumps(dados_para_enviar))
