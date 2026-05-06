import logging

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from compras.services.data_processing import get_projecao_para_material, processar_material_direto
from compras.services.dolar import get_cotacao_dolar_atual
from compras.services.google_sheets import get_pedidos_df, get_simulacao_df, invalidate_cache
from compras.services.sugestoes import gerar_sugestoes
from compras.services import estoque as estoque_service

logger = logging.getLogger(__name__)


@login_required
def analise(request):
    return render(request, 'compras/analise.html')


@login_required
@require_GET
def api_material_direto(request):
    if request.GET.get('refresh') == '1':
        invalidate_cache()

    try:
        simulacao_df = get_simulacao_df()
        pedidos_df = get_pedidos_df()
        resultado = processar_material_direto(simulacao_df, pedidos_df)

        materiais_base = resultado['materiais']
        materiais = materiais_base

        produtos = []
        vistos = set()
        for item in materiais_base:
            codigo_item = item.get('codigo')
            if not codigo_item or codigo_item in vistos:
                continue
            vistos.add(codigo_item)
            produtos.append({
                'codigo': codigo_item,
                'descricao': item.get('descricao') or '',
                'rotulo': f"{codigo_item} - {item.get('descricao') or ''}".strip(' -'),
            })

        urgencia = request.GET.get('urgencia', '').strip()
        codigo = request.GET.get('codigo', '').strip()
        grupo = request.GET.get('grupo', '').strip()
        busca = request.GET.get('busca', '').strip().lower()

        if urgencia:
            materiais = [m for m in materiais if m['flag_urgencia'] == urgencia]
        if codigo:
            materiais = [m for m in materiais if m['codigo'] == codigo]
        if grupo:
            materiais = [m for m in materiais if m.get('grupo') == grupo]
        if busca:
            materiais = [
                m for m in materiais
                if busca in m['codigo'].lower() or busca in m['descricao'].lower()
            ]

        return JsonResponse({
            'materiais': materiais,
            'codigos': resultado['codigos'],
            'grupos': resultado['grupos'],
            'produtos': produtos,
            'total': len(materiais),
        })
    except Exception as e:
        logger.exception('Erro ao processar material direto: %s', e)
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_GET
def api_projecao(request):
    codigo = request.GET.get('codigo', '').strip()
    if not codigo:
        return JsonResponse({'error': 'Parametro codigo obrigatorio'}, status=400)

    try:
        simulacao_df = get_simulacao_df()
        pedidos_df = get_pedidos_df()
        resultado = processar_material_direto(simulacao_df, pedidos_df)

        projecao = get_projecao_para_material(codigo, resultado['df'], resultado['df_pedidos'])

        if 'error' in projecao:
            return JsonResponse(projecao, status=404)

        projecao['sugestoes'] = gerar_sugestoes(projecao)
        return JsonResponse(projecao)
    except Exception as e:
        logger.exception('Erro na projecao de estoque para %s: %s', codigo, e)
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_GET
def api_dolar(request):
    force_refresh = request.GET.get('refresh') == '1'

    try:
        return JsonResponse(get_cotacao_dolar_atual(force_refresh=force_refresh))
    except Exception as e:
        logger.exception('Erro ao consultar cotacao do dolar: %s', e)
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def estoque(request):
    return render(request, 'compras/estoque.html')


@login_required
@require_GET
def api_estoque(request):
    if request.GET.get('refresh') == '1':
        estoque_service.invalidate_cache()

    busca = request.GET.get('busca', '').strip()
    grupo = request.GET.get('grupo', '').strip()

    try:
        dados = estoque_service.get_estoque_data(busca=busca, grupo=grupo)
        return JsonResponse(dados)
    except Exception as e:
        logger.exception('Erro ao carregar estoque: %s', e)
        return JsonResponse({'error': str(e)}, status=500)
