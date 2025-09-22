from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from datetime import timedelta as dt_timedelta
from django.db import transaction
from django.utils import timezone as dj_timezone
from .models import Profile, Notificacao, RegistroNotificacao
from solicitacao_almox.models import SolicitacaoRequisicao, SolicitacaoTransferencia

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

def notificacao_almoxarifado(
    titulo: str,
    mensagem: str,
    rota_acesso: str,
    tipo: str = "info",
    chave: str = None,
    frequencia: dt_timedelta = None,
):
    # 1) Controle de frequência
    if chave and frequencia:
        agora = dj_timezone.now()
        try:
            registro = RegistroNotificacao.objects.get(chave=chave)
            if agora - registro.ultimo_envio < frequencia:
                print(f"🔕 Notificação para a chave '{chave}' pulada.")
                return
        except RegistroNotificacao.DoesNotExist:
            pass
    elif chave or frequencia:
        raise ValueError("Para notificações periódicas, 'chave' e 'frequencia' devem ser fornecidos.")

    profiles_to_notify = Profile.objects.filter(tipo_acesso="almoxarifado")
    if not profiles_to_notify.exists():
        print("AVISO: Nenhum usuário com perfil de destino foi encontrado.")
        return

    # 2) Escritas em transação
    try:
        with transaction.atomic():
            notificacoes_criadas = 0
            for profile in profiles_to_notify:
                Notificacao.objects.create(
                    profile=profile,
                    rota_acesso=rota_acesso,
                    titulo=titulo,
                    mensagem=mensagem,
                    tipo=tipo,
                )
                notificacoes_criadas += 1

            if chave:
                RegistroNotificacao.objects.update_or_create(
                    chave=chave,
                    defaults={"ultimo_envio": dj_timezone.now()},
                )

            if notificacoes_criadas > 0:
                print(f"✅ Transação concluída: {notificacoes_criadas} notificações criadas com sucesso.")
    except Exception as e:
        print(f"❌ ERRO na transação ao criar notificações: {e}. Rollback executado.")

def verificar_e_notificar_requisicoes_pendentes():
    """
    Verifica o número total de requisições pendentes e envia uma notificação
    se o limite de 30 for atingido.
    Usa um controle de frequência para não enviar múltiplos alertas seguidos.
    """
    requisicoes_pendentes = SolicitacaoRequisicao.objects.filter(
        entregue_por__isnull=True, data_entrega__isnull=True
    ).count()

    if requisicoes_pendentes >= 30:
        print(f"⚠️ Limite atingido! {requisicoes_pendentes} requisições pendentes. Tentando notificar...")

        notificacao_almoxarifado(
            titulo="Alerta: Alto Volume de Requisições",
            mensagem=f"Existem {requisicoes_pendentes} requisições pendentes de atendimento. Por favor, verifique.",
            rota_acesso="/almox/solicitacoes-page/",
            tipo="aviso",
            chave="alerta_requisicoes_pendentes_almox",
            frequencia=dt_timedelta(days=2),  # ajuste aqui
        )


def verificar_e_notificar_transferencias_pendentes():
    """
    Verifica o número total de transferências pendentes e envia uma notificação
    se o limite de 30 for atingido.
    Usa um controle de frequência para não enviar múltiplos alertas seguidos.
    """
    transferencias_pendentes = SolicitacaoTransferencia.objects.filter(
        entregue_por__isnull=True, data_entrega__isnull=True
    ).count()

    if transferencias_pendentes >= 30:
        print(f"⚠️ Limite atingido! {transferencias_pendentes} transferências pendentes. Tentando notificar...")

        notificacao_almoxarifado(
            titulo="Alerta: Alto Volume de Transferências",
            mensagem=f"Existem {transferencias_pendentes} requisições pendentes de atendimento. Por favor, verifique.",
            rota_acesso="/almox/solicitacoes-page/",
            tipo="alerta",
            chave="alerta_transferencias_pendentes_almox",
            frequencia=dt_timedelta(days=2),  # ajuste aqui
        )