import json
from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from comercial.models import ConferenciaPedido
from comercial.services.ploomes import (
    PloomesAPIError,
    PloomesConfigError,
    consultar_conf_pedido,
)


def _serialize_conferencia(conferencia: ConferenciaPedido) -> dict:
    return {
        'chave_pedido': conferencia.chave_pedido,
        'deal_id': conferencia.deal_id,
        'data_criacao': conferencia.data_criacao,
        'quote_id': conferencia.quote_id,
        'contato': conferencia.contato,
        'observacao': conferencia.observacao,
        'itens': conferencia.itens or [],
        'conferencia': {
            'conferido_por': conferencia.conferido_por.get_full_name() or conferencia.conferido_por.username,
            'conferido_em': conferencia.conferido_em.isoformat(),
        },
    }


@login_required
def conf_pedido(request):
    return render(request, 'comercial/conf_pedido.html')


@login_required
@require_GET
def api_conf_pedido(request):
    start_raw = (request.GET.get('data_inicio') or '').strip()
    end_raw = (request.GET.get('data_fim') or '').strip()

    if not start_raw or not end_raw:
        return JsonResponse({'error': 'Informe data inicial e data final.'}, status=400)

    try:
        start_date = datetime.strptime(start_raw, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_raw, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'error': 'Datas inválidas. Use o formato YYYY-MM-DD.'}, status=400)

    if start_date > end_date:
        return JsonResponse({'error': 'A data inicial não pode ser maior que a data final.'}, status=400)

    try:
        resultados = consultar_conf_pedido(start_date, end_date)
    except PloomesConfigError as exc:
        return JsonResponse({'error': str(exc)}, status=500)
    except PloomesAPIError as exc:
        return JsonResponse({'error': str(exc)}, status=502)
    except Exception as exc:
        return JsonResponse({'error': f'Erro interno ao consultar pedidos: {exc}'}, status=500)

    return JsonResponse({
        'results': resultados,
        'total': len(resultados),
        'columns': [
            {'key': 'chave_pedido', 'label': 'Chave do Pedido'},
            {'key': 'deal_id', 'label': 'Deal ID'},
            {'key': 'data_criacao', 'label': 'Data Criação'},
            {'key': 'quote_id', 'label': 'Quote ID'},
            {'key': 'contato', 'label': 'Contato'},
            {'key': 'codigo_produto', 'label': 'Código do Produto'},
            {'key': 'cor', 'label': 'Cor'},
            {'key': 'observacao', 'label': 'Observação'},
        ],
    })


@login_required
@require_GET
def api_conferidos(request):
    queryset = ConferenciaPedido.objects.select_related('conferido_por').all()

    conferido_por = (request.GET.get('conferido_por') or '').strip()
    data_inicio_raw = (request.GET.get('data_conferencia_inicio') or '').strip()
    data_fim_raw = (request.GET.get('data_conferencia_fim') or '').strip()

    if conferido_por:
        queryset = queryset.filter(
            Q(conferido_por__username__icontains=conferido_por) |
            Q(conferido_por__first_name__icontains=conferido_por) |
            Q(conferido_por__last_name__icontains=conferido_por)
        )

    try:
        if data_inicio_raw:
            data_inicio = datetime.strptime(data_inicio_raw, '%Y-%m-%d').date()
            queryset = queryset.filter(conferido_em__date__gte=data_inicio)
        if data_fim_raw:
            data_fim = datetime.strptime(data_fim_raw, '%Y-%m-%d').date()
            queryset = queryset.filter(conferido_em__date__lte=data_fim)
    except ValueError:
        return JsonResponse({'error': 'Datas de conferência inválidas. Use o formato YYYY-MM-DD.'}, status=400)

    resultados = [_serialize_conferencia(item) for item in queryset]
    return JsonResponse({'results': resultados, 'total': len(resultados)})


@login_required
@require_POST
def api_marcar_conferido(request):
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido.'}, status=400)

    required_fields = ['chave_pedido', 'deal_id', 'quote_id']
    if any(not str(payload.get(field, '')).strip() for field in required_fields):
        return JsonResponse({'error': 'Pedido inválido para conferência.'}, status=400)

    conferencia, _ = ConferenciaPedido.objects.update_or_create(
        chave_pedido=str(payload.get('chave_pedido')).strip(),
        deal_id=str(payload.get('deal_id')).strip(),
        quote_id=str(payload.get('quote_id')).strip(),
        defaults={
            'data_criacao': str(payload.get('data_criacao') or ''),
            'contato': str(payload.get('contato') or ''),
            'observacao': str(payload.get('observacao') or ''),
            'itens': payload.get('itens') or [],
            'conferido_por': request.user,
        },
    )

    return JsonResponse({
        'message': 'Pedido conferido com sucesso.',
        'result': _serialize_conferencia(conferencia),
    })


@login_required
@require_POST
def api_desfazer_conferido(request):
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido.'}, status=400)

    required_fields = ['chave_pedido', 'deal_id', 'quote_id']
    if any(not str(payload.get(field, '')).strip() for field in required_fields):
        return JsonResponse({'error': 'Pedido inválido para desfazer conferência.'}, status=400)

    deleted_count, _ = ConferenciaPedido.objects.filter(
        chave_pedido=str(payload.get('chave_pedido')).strip(),
        deal_id=str(payload.get('deal_id')).strip(),
        quote_id=str(payload.get('quote_id')).strip(),
    ).delete()

    if deleted_count == 0:
        return JsonResponse({'error': 'Conferência não encontrada.'}, status=404)

    return JsonResponse({'message': 'Conferência desfeita com sucesso.'})
