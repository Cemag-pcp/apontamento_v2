"""Regras comuns do apontamento de produção no ERP (Innovaro), usadas por
corte, estamparia, montagem e usinagem.

O ERP às vezes demora para responder. Quando a resposta não chega a tempo,
o ERP pode ter gravado o apontamento mesmo assim. Reenviar nesse caso
duplica o apontamento no ERP. Por isso:

- erro de CONEXÃO (o pedido nem chegou ao ERP): nada foi gravado lá, pode
  tentar de novo normalmente;
- erro DEPOIS de enviar (timeout de leitura, conexão caída no meio da
  resposta): o item fica "aguardando confirmação no ERP" e o apontamento
  fica bloqueado até alguém conferir no ERP e escolher "Confirmar que entrou
  no ERP" ou "Liberar para reenviar".
"""
import json

import requests
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils.timezone import now

# (conexão, leitura) em segundos. O gunicorn de produção usa --timeout 60.
TIMEOUT_ERP_APONTAMENTO = (5, 45)

MENSAGEM_AGUARDANDO_ERP = (
    'O ERP demorou a responder e o apontamento pode ter sido registrado. '
    'Confira no ERP antes de tentar de novo.'
)
MENSAGEM_ITEM_BLOQUEADO = (
    'Este item está aguardando confirmação no ERP: numa tentativa anterior o ERP '
    'demorou a responder e o apontamento pode ter sido registrado. Confira no ERP '
    'e use "Confirmar que entrou no ERP" ou "Liberar para reenviar".'
)


def resposta_incerta(exc):
    """True quando o pedido pode ter chegado ao ERP e sido processado (não dá
    para saber se gravou). False quando com certeza nem chegou lá."""
    if isinstance(exc, requests.exceptions.ConnectTimeout):
        return False  # não conectou: o ERP não recebeu nada
    if isinstance(exc, (requests.exceptions.ReadTimeout, requests.exceptions.ChunkedEncodingError)):
        return True
    if isinstance(exc, requests.exceptions.ConnectionError):
        # "Connection aborted" / "RemoteDisconnected": o pedido já tinha sido
        # enviado e a conexão caiu antes da resposta.
        texto = str(exc)
        return 'Connection aborted' in texto or 'RemoteDisconnected' in texto
    return False


def marcar_aguardando_confirmacao_erp(item, user, exc=None):
    """Marca o item como aguardando confirmação (não marca como apontado)."""
    detalhe = f' Detalhe técnico: {exc}' if exc else ''
    item.aguardando_confirmacao_erp = True
    item.erro_apontamento = (MENSAGEM_AGUARDANDO_ERP + detalhe)[:2000]
    item.tipo_apontamento = 'api'
    item.resp_apontamento = user if getattr(user, 'is_authenticated', False) else None
    item.save(update_fields=[
        'aguardando_confirmacao_erp', 'erro_apontamento', 'tipo_apontamento', 'resp_apontamento',
    ])


def resposta_aguardando_erp(payload_enviado=None):
    """Resposta da API quando o ERP não respondeu a tempo."""
    return JsonResponse(
        {
            'status': 'error',
            'aguardando_confirmacao_erp': True,
            'message': MENSAGEM_AGUARDANDO_ERP,
            'description': MENSAGEM_AGUARDANDO_ERP,
            'payload_enviado': payload_enviado,
        },
        status=504,
    )


def resposta_item_bloqueado():
    """Resposta da API ao tentar apontar um item que aguarda confirmação."""
    return JsonResponse(
        {
            'status': 'error',
            'aguardando_confirmacao_erp': True,
            'message': MENSAGEM_ITEM_BLOQUEADO,
            'description': MENSAGEM_ITEM_BLOQUEADO,
        },
        status=409,
    )


def resolver_aguardando_erp(request, queryset, pk):
    """Resolve um item que aguarda confirmação no ERP.

    POST {"acao": "confirmar"}  -> o apontamento entrou no ERP: marca como apontado.
                                    Aceita "chave_apontamento" opcional.
    POST {"acao": "liberar"}    -> não entrou no ERP: libera para reenviar.
    """
    try:
        dados = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        dados = {}
    acao = str(dados.get('acao') or '').strip().lower()
    if acao not in ('confirmar', 'liberar'):
        return JsonResponse({'status': 'error', 'message': 'Ação inválida.'}, status=400)

    with transaction.atomic():
        item = get_object_or_404(queryset.select_for_update(of=('self',)), pk=pk)
        if not item.aguardando_confirmacao_erp:
            return JsonResponse(
                {'status': 'error', 'message': 'Este item não está aguardando confirmação no ERP.'},
                status=409,
            )

        quem = (request.user.get_full_name() or request.user.username) if request.user.is_authenticated else ''
        item.aguardando_confirmacao_erp = False
        if acao == 'confirmar':
            chave = str(dados.get('chave_apontamento') or '').strip()[:200]
            item.apontado = True
            item.data_apontamento = now()
            item.tipo_apontamento = 'api'
            item.resp_apontamento = request.user
            if chave:
                item.chave_apontamento = chave
            item.erro_apontamento = (
                f'Confirmado por {quem} que o apontamento entrou no ERP '
                '(o ERP tinha demorado a responder).'
            )
            item.save(update_fields=[
                'aguardando_confirmacao_erp', 'apontado', 'data_apontamento', 'tipo_apontamento',
                'resp_apontamento', 'chave_apontamento', 'erro_apontamento',
            ])
        else:
            item.erro_apontamento = (
                f'Liberado para reenviar por {quem}: o apontamento não estava no ERP.'
            )
            item.save(update_fields=['aguardando_confirmacao_erp', 'erro_apontamento'])

    return JsonResponse({'status': 'success', 'acao': acao})
