import logging

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from compras.services.google_sheets import get_simulacao_df, get_pedidos_df, invalidate_cache
from compras.services.data_processing import processar_material_direto, get_projecao_para_material
from compras.services.sugestoes import gerar_sugestoes

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

        materiais = resultado['materiais']

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
        return JsonResponse({'error': 'Parâmetro codigo obrigatório'}, status=400)

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
        logger.exception('Erro na projeção de estoque para %s: %s', codigo, e)
        return JsonResponse({'error': str(e)}, status=500)
