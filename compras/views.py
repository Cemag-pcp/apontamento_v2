import logging

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from compras.services.analise_ia import check_cache, get_or_create_analise
from compras.services.data_processing import get_projecao_para_material, processar_material_direto
from compras.services.dolar import get_cotacao_dolar_atual
from compras.services.google_sheets import (
    get_pedidos_df, get_simulacao_df, invalidate_cache,
    get_mat_indireto_simulacao_df, get_mat_indireto_pedidos_df, invalidate_mat_indireto_cache,
)
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
        resultado = processar_material_direto(
            simulacao_df,
            pedidos_df,
            considerar_pedido_pendente_como_recebido=True,
        )

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
        resultado = processar_material_direto(
            simulacao_df,
            pedidos_df,
            considerar_pedido_pendente_como_recebido=True,
        )

        projecao = get_projecao_para_material(
            codigo,
            resultado['df'],
            resultado['df_pedidos'],
            considerar_pedido_pendente_como_recebido=True,
        )

        if 'error' in projecao:
            return JsonResponse(projecao, status=404)

        projecao['sugestoes'] = gerar_sugestoes(projecao, formato_enriquecido=True)
        return JsonResponse(projecao)
    except Exception as e:
        logger.exception('Erro na projecao de estoque para %s: %s', codigo, e)
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_GET
def api_analise_ia(request):
    codigo = request.GET.get('codigo', '').strip()
    if not codigo:
        return JsonResponse({'error': 'codigo obrigatorio'}, status=400)

    check_only = request.GET.get('check_only') == '1'
    force = request.GET.get('force') == '1'

    try:
        simulacao_df = get_simulacao_df()
        pedidos_df = get_pedidos_df()
        resultado = processar_material_direto(
            simulacao_df,
            pedidos_df,
            considerar_pedido_pendente_como_recebido=True,
        )
        projecao = get_projecao_para_material(
            codigo,
            resultado['df'],
            resultado['df_pedidos'],
            considerar_pedido_pendente_como_recebido=True,
        )
        if 'error' in projecao:
            return JsonResponse(projecao, status=404)

        material = next((m for m in resultado['materiais'] if m['codigo'] == codigo), {})
        projecao['media_3m'] = material.get('media_3m')
        projecao['cons_mes_anterior'] = material.get('cons_mes_anterior')
        projecao['simulado_pend_vendas'] = material.get('simulado_pend_vendas')
        projecao['dee_dias_em_est'] = material.get('dee_dias_em_est')
        projecao['estoque_total'] = material.get('estoque_total')
        projecao['grupo'] = material.get('grupo')

        import pandas as pd
        df_ped = resultado['df_pedidos']
        if 'codigo' in df_ped.columns and 'recurso' in df_ped.columns:
            pedidos_mat = df_ped[df_ped['codigo'] == codigo][['recurso', 'data_entrega', 'qde_ped_corrigido']].copy()
            fornecedores = []
            for _, row in pedidos_mat.iterrows():
                recurso = str(row.get('recurso', '') or '')
                partes = recurso.split(' - ', 1)
                nome_fornecedor = partes[1].strip() if len(partes) > 1 else recurso.strip()
                data = row.get('data_entrega')
                data_fmt = data.strftime('%d/%m/%Y') if pd.notna(data) else '-'
                qtd = float(row.get('qde_ped_corrigido', 0) or 0)
                if nome_fornecedor:
                    fornecedores.append({
                        'fornecedor': nome_fornecedor,
                        'data_entrega': data_fmt,
                        'quantidade': round(qtd, 2),
                    })
            projecao['fornecedores_pedidos'] = fornecedores
        else:
            projecao['fornecedores_pedidos'] = []

        if check_only:
            cached = check_cache(codigo, projecao)
            if cached:
                return JsonResponse(cached)
            return JsonResponse({'analise': None, 'from_cache': False})

        return JsonResponse(get_or_create_analise(codigo, projecao, force=force))
    except Exception as e:
        logger.exception('Erro na analise IA para %s: %s', codigo, e)
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
def mat_indireto(request):
    return render(request, 'compras/mat_indireto.html')


@login_required
@require_GET
def api_debug_colunas_indireto(request):
    try:
        from compras.services.google_sheets import _open_sheet_by_id
        from django.conf import settings
        invalidate_mat_indireto_cache()
        sh = _open_sheet_by_id(settings.GSHEETS_MAT_INDIRETO_SPREADSHEET_ID)
        wks_sim = sh.worksheet('Dados Simulação')
        primeiras_linhas = wks_sim.get_all_values()[:4]
        pedidos_df = get_mat_indireto_pedidos_df()
        return JsonResponse({
            'simulacao_linhas_1_a_4': [
                {'linha': i + 1, 'valores': row}
                for i, row in enumerate(primeiras_linhas)
            ],
            'pedidos_colunas': list(pedidos_df.columns),
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_GET
def api_material_indireto(request):
    if request.GET.get('refresh') == '1':
        invalidate_mat_indireto_cache()

    try:
        simulacao_df = get_mat_indireto_simulacao_df()
        pedidos_df = get_mat_indireto_pedidos_df()
        resultado = processar_material_direto(simulacao_df, pedidos_df, skip_first_row=False)

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
        logger.exception('Erro ao processar material indireto: %s', e)
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_GET
def api_projecao_indireto(request):
    codigo = request.GET.get('codigo', '').strip()
    if not codigo:
        return JsonResponse({'error': 'Parametro codigo obrigatorio'}, status=400)

    try:
        simulacao_df = get_mat_indireto_simulacao_df()
        pedidos_df = get_mat_indireto_pedidos_df()
        resultado = processar_material_direto(simulacao_df, pedidos_df, skip_first_row=False)

        projecao = get_projecao_para_material(codigo, resultado['df'], resultado['df_pedidos'])

        if 'error' in projecao:
            return JsonResponse(projecao, status=404)

        projecao['sugestoes'] = gerar_sugestoes(projecao)
        return JsonResponse(projecao)
    except Exception as e:
        logger.exception('Erro na projecao de estoque (indireto) para %s: %s', codigo, e)
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_GET
def api_analise_ia_indireto(request):
    codigo = request.GET.get('codigo', '').strip()
    if not codigo:
        return JsonResponse({'error': 'codigo obrigatorio'}, status=400)

    check_only = request.GET.get('check_only') == '1'
    force = request.GET.get('force') == '1'

    try:
        simulacao_df = get_mat_indireto_simulacao_df()
        pedidos_df = get_mat_indireto_pedidos_df()
        resultado = processar_material_direto(simulacao_df, pedidos_df, skip_first_row=False)
        projecao = get_projecao_para_material(codigo, resultado['df'], resultado['df_pedidos'])
        if 'error' in projecao:
            return JsonResponse(projecao, status=404)

        material = next((m for m in resultado['materiais'] if m['codigo'] == codigo), {})
        projecao['media_3m'] = material.get('media_3m')
        projecao['cons_mes_anterior'] = material.get('cons_mes_anterior')
        projecao['simulado_pend_vendas'] = material.get('simulado_pend_vendas')
        projecao['dee_dias_em_est'] = material.get('dee_dias_em_est')
        projecao['estoque_total'] = material.get('estoque_total')
        projecao['grupo'] = material.get('grupo')

        import pandas as pd
        df_ped = resultado['df_pedidos']
        if 'codigo' in df_ped.columns and 'recurso' in df_ped.columns:
            pedidos_mat = df_ped[df_ped['codigo'] == codigo][['recurso', 'data_entrega', 'qde_ped_corrigido']].copy()
            fornecedores = []
            for _, row in pedidos_mat.iterrows():
                recurso = str(row.get('recurso', '') or '')
                partes = recurso.split(' - ', 1)
                nome_fornecedor = partes[1].strip() if len(partes) > 1 else recurso.strip()
                data = row.get('data_entrega')
                data_fmt = data.strftime('%d/%m/%Y') if pd.notna(data) else '-'
                qtd = float(row.get('qde_ped_corrigido', 0) or 0)
                if nome_fornecedor:
                    fornecedores.append({
                        'fornecedor': nome_fornecedor,
                        'data_entrega': data_fmt,
                        'quantidade': round(qtd, 2),
                    })
            projecao['fornecedores_pedidos'] = fornecedores
        else:
            projecao['fornecedores_pedidos'] = []

        if check_only:
            cached = check_cache(codigo, projecao)
            if cached:
                return JsonResponse(cached)
            return JsonResponse({'analise': None, 'from_cache': False})

        return JsonResponse(get_or_create_analise(codigo, projecao, force=force))
    except Exception as e:
        logger.exception('Erro na analise IA (indireto) para %s: %s', codigo, e)
        return JsonResponse({'error': str(e)}, status=500)

