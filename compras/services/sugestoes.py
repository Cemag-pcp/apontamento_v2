import numpy as np
from datetime import datetime, timedelta
import pandas as pd


def _adicionar_dias_uteis(data_inicial, num_dias):
    if pd.isna(num_dias) or num_dias == 0:
        return data_inicial
    try:
        num_dias = int(num_dias)
    except (ValueError, TypeError):
        return data_inicial
    if isinstance(data_inicial, datetime):
        data_inicial = data_inicial.date()
    incremento = 1 if num_dias > 0 else -1
    dias_abs = abs(num_dias)
    semanas, resto = divmod(dias_abs, 5)
    data_final = data_inicial + timedelta(days=semanas * 7 * incremento)
    while resto > 0:
        data_final += timedelta(days=incremento)
        if data_final.weekday() < 5:
            resto -= 1
    return data_final


def gerar_sugestoes(projecao: dict) -> list:
    """
    Porta de sugestoes.py. Recebe o dict retornado por get_projecao_para_material
    e retorna lista de sugestões em formato serializável JSON.
    """
    dias_ressupr = float(projecao.get('dias_ressupr', 0) or 0)
    consumo_diario = float(projecao.get('consumo_diario', 0) or 0)
    estoque_atual = float(projecao.get('estoque_atual', 0) or 0)
    estoque_minimo = float(projecao.get('estoque_minimo', 0) or 0)
    dias_ate_compra = projecao.get('dias_ate_data_compra')
    ped_compras = float(projecao.get('ped_compras', 0) or 0)

    if dias_ressupr == 0 or consumo_diario == 0:
        return [{
            'tipo': 'erro',
            'titulo': 'Dados insuficientes',
            'mensagem': 'Produto sem dias de ressuprimento ou consumo configurados. Verifique o cadastro.',
            'qtd_sugerida': None,
        }]

    hoje = datetime.now().date()
    data_chegada = _adicionar_dias_uteis(hoje, int(dias_ressupr))

    try:
        dias_uteis_ate_chegada = int(np.busday_count(hoje, data_chegada + timedelta(days=1)))
    except Exception:
        dias_uteis_ate_chegada = int(dias_ressupr)

    consumo_ate_chegada = dias_uteis_ate_chegada * consumo_diario
    estoque_no_dia_chegada = estoque_atual - consumo_ate_chegada
    gap_estoque = max(estoque_minimo - estoque_no_dia_chegada, 0)
    qtd_ressuprimento = dias_ressupr * consumo_diario

    sugestoes = []

    # CENÁRIO 1: Pedido pendente
    if ped_compras > 0:
        sugestoes.append({
            'tipo': 'info',
            'titulo': 'Pedido de compra pendente',
            'mensagem': f'Existe pedido de compra pendente de {ped_compras:.2f} unidades. '
                        f'Verifique se a entrega chegará antes do estoque mínimo.',
            'qtd_sugerida': None,
        })
        return sugestoes

    # CENÁRIO 2: Estoque crítico (abaixo do mínimo)
    if estoque_atual <= estoque_minimo:
        qtd_total = gap_estoque + qtd_ressuprimento
        dias_atraso = abs(dias_ate_compra) if dias_ate_compra is not None else 0
        sugestoes.append({
            'tipo': 'critico',
            'titulo': f'URGENTE — Prazo venceu há {dias_atraso} dias',
            'mensagem': (
                f'Estoque crítico abaixo do mínimo! Solicitar compra HOJE.\n'
                f'Chegada prevista: {data_chegada.strftime("%d/%m/%Y")} ({dias_uteis_ate_chegada} dias úteis)\n'
                f'Estoque projetado na chegada: {estoque_no_dia_chegada:.2f} unidades\n'
                f'Gap: {gap_estoque:.2f} | Ressuprimento: {qtd_ressuprimento:.2f}'
            ),
            'qtd_sugerida': round(qtd_total, 2),
        })
        return sugestoes

    # CENÁRIO 3: Prazo de compra vencido (mas estoque ainda acima do mínimo)
    if dias_ate_compra is not None and dias_ate_compra <= 0:
        dias_atraso = abs(dias_ate_compra)
        qtd_total = gap_estoque + qtd_ressuprimento
        sugestoes.append({
            'tipo': 'urgente',
            'titulo': f'Prazo venceu há {dias_atraso} dias',
            'mensagem': (
                f'Solicitar compra HOJE.\n'
                f'Chegada prevista: {data_chegada.strftime("%d/%m/%Y")}\n'
                f'Estoque projetado na chegada: {estoque_no_dia_chegada:.2f} unidades\n'
                f'Gap na chegada: {gap_estoque:.2f} | Ressuprimento: {qtd_ressuprimento:.2f}'
            ),
            'qtd_sugerida': round(qtd_total, 2),
        })
        return sugestoes

    # CENÁRIO 4: Alerta preventivo (≤3 dias para o prazo)
    if dias_ate_compra is not None and dias_ate_compra <= 3:
        if estoque_atual < estoque_minimo:
            gap = estoque_minimo - estoque_atual
            qtd = qtd_ressuprimento + gap
        else:
            qtd = qtd_ressuprimento
        sugestoes.append({
            'tipo': 'alerta',
            'titulo': f'Alerta preventivo — {dias_ate_compra} dias para o prazo',
            'mensagem': (
                f'Iniciar planejamento do pedido de compra nos próximos dias.\n'
                f'Quantidade padrão de ressuprimento: {qtd_ressuprimento:.2f} unidades ({int(dias_ressupr)} dias)'
            ),
            'qtd_sugerida': round(qtd, 2),
        })
        return sugestoes

    # CENÁRIO 5: Tudo OK
    sugestoes.append({
        'tipo': 'ok',
        'titulo': f'Situação controlada — próxima compra em {dias_ate_compra} dias',
        'mensagem': (
            f'Consumo diário: {consumo_diario:.3f} unidades\n'
            f'Dias de ressuprimento: {int(dias_ressupr)}\n'
            f'Quantidade padrão de compra: {qtd_ressuprimento:.2f} unidades'
        ),
        'qtd_sugerida': round(qtd_ressuprimento, 2),
    })
    return sugestoes
