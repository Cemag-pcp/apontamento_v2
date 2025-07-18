from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

def notificar_ordem(ordem):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "ordens_iniciadas",
        {
            "type": "enviar_ordem",
            "data": {
                "ordem": ordem.ordem,
                "ultima_atualizacao": ordem.ultima_atualizacao.isoformat()
            }
        }
    )
