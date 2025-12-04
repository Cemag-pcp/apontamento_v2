from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.timezone import localtime
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.contrib.auth.models import User
from .models import Profile, Notificacao


# @receiver(post_save, sender=User)
# def create_user_profile(sender, instance, created, **kwargs):
#     if created:
#         Profile.objects.create(user=instance)


# @receiver(post_save, sender=User)
# def save_user_profile(sender, instance, **kwargs):
#     if hasattr(instance, "profile"):
#         instance.profile.save()


# @receiver(post_save, sender=Notificacao)
# def enviar_notificacao_em_tempo_real(sender, instance, created, **kwargs):
#     """
#     Este sinal envia a notificação completa tanto na criação quanto na atualização.
#     """
#     channel_layer = get_channel_layer()
#     if not channel_layer:
#         return

#     user_id = instance.profile.user.id
#     group_name = f"notificacoes_{user_id}"

#     # Recalcula a contagem de não lidas
#     contagem_nao_lida = Notificacao.objects.filter(
#         profile=instance.profile, lido=False
#     ).count()

#     # Formata o objeto de notificação completo. Este formato será usado em ambos os casos.
#     notificacao_data = {
#         "id": instance.id,
#         "titulo": instance.titulo if len(instance.titulo) < 45 else f"{instance.titulo[0:44]}...",
#         "mensagem": instance.mensagem if len(instance.mensagem) < 45 else f"{instance.mensagem[0:44]}...",
#         "tempo": localtime(instance.criado_em).strftime("%d/%m %H:%M"),
#         "tipo": instance.tipo,
#         "rota": "#",  # Substitua se tiver uma lógica de rota
#         "lido": instance.lido,
#     }

#     if created:
#         print(f"✅ SINAL (Criação): Enviando nova notificação '{instance.titulo}'.")
#         evento = {
#             "type": "nova_notificacao",  # Evento para ADICIONAR
#             "payload": {
#                 "quantidade": contagem_nao_lida,
#                 "notificacao": notificacao_data,
#             },
#         }
#     else:
#         print(f"✅ SINAL (Atualização): Enviando atualização para a notificação ID {instance.id}.")
#         evento = {
#             "type": "atualizacao_notificacao",  # Evento para SUBSTITUIR
#             "payload": {
#                 "quantidade": contagem_nao_lida,
#                 "notificacao": notificacao_data, # Agora enviando o objeto completo
#             },
#         }

#     # Envia o evento para o grupo do usuário
#     async_to_sync(channel_layer.group_send)(
#         group_name, {"type": "receber.notificacao", "data": evento}
#     )
