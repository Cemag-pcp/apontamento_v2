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


def _formatar_data(valor):
    if not valor:
        return '-'
    for formato in ('%Y-%m-%d', '%d/%m/%Y'):
        try:
            return datetime.strptime(valor, formato).strftime('%d/%m/%Y')
        except ValueError:
            continue
    return valor


def _gerar_sugestoes_enriquecidas(projecao: dict) -> list:
    estoque_fisico = float(projecao.get('estoque_fisico', 0) or 0)
    estoque_projetado = float(projecao.get('estoque_projetado', estoque_fisico) or 0)
    estoque_minimo = float(projecao.get('estoque_minimo', 0) or 0)
    consumo_diario = float(projecao.get('consumo_diario', 0) or 0)
    ped_compras = float(projecao.get('ped_compras', 0) or 0)
    pedidos_atrasados = int(projecao.get('pedidos_atrasados_count', 0) or 0)
    pedidos_previstos = int(projecao.get('pedidos_previstos_count', 0) or 0)
    pedidos_sem_data = int(projecao.get('pedidos_sem_data_count', 0) or 0)
    ped_sem_data = float(projecao.get('ped_compras_sem_data', 0) or 0)
    pedidos_pendentes_detalhes = projecao.get('pedidos_pendentes_detalhes') or []
    dias_ate_compra = projecao.get('dias_ate_data_compra')
    dias_ressupr = float(projecao.get('dias_ressupr', 0) or 0)
    data_compra = _formatar_data(projecao.get('data_compra'))
    data_minimo = _formatar_data(projecao.get('data_estoque_minimo'))
    data_zero = _formatar_data(projecao.get('data_estoque_zero'))
    cobertura = (
        estoque_projetado / consumo_diario
        if consumo_diario > 0
        else None
    )

    resumo = {
        'tipo': 'resumo',
        'titulo': 'Resumo da projeção',
        'mensagem': (
            'O estoque projetado considera pedidos pendentes não atrasados '
            'como disponíveis e exclui pedidos atrasados.'
        ),
        'qtd_sugerida': None,
        'indicadores': [
            {'rotulo': 'Estoque físico', 'valor': f'{estoque_fisico:.2f}'},
            {'rotulo': 'Pedido pendente', 'valor': f'{ped_compras:.2f}'},
            {'rotulo': 'Estoque projetado', 'valor': f'{estoque_projetado:.2f}'},
            {'rotulo': 'Consumo diário', 'valor': f'{consumo_diario:.3f}'},
            {'rotulo': 'Estoque mínimo', 'valor': f'{estoque_minimo:.2f}'},
            {
                'rotulo': 'Cobertura projetada',
                'valor': f'{cobertura:.1f} dias' if cobertura is not None else '-',
            },
        ],
    }

    alertas = []
    data_minimo_usada = False

    if pedidos_atrasados:
        partes_atr = [f'**{pedidos_atrasados} pedido(s) atrasado(s)** não entram no estoque projetado.']
        for p in [p for p in pedidos_pendentes_detalhes if p.get('status') == 'ATRASADO']:
            data_raw = p.get('data', '')
            try:
                data_fmt = datetime.strptime(data_raw, '%Y-%m-%d').strftime('%d/%m/%Y') if data_raw else '-'
            except ValueError:
                data_fmt = data_raw or '-'
            partes_atr.append(f'• **{data_fmt}** — {float(p.get("quantidade", 0) or 0):.2f} unidades')
        alertas.append('\n'.join(partes_atr))
    if pedidos_sem_data:
        msg_sem_data = f'**Entrega pendente sem data de entrega:** {ped_sem_data:.2f} unidades.'
        if data_minimo != '-':
            msg_sem_data += (
                f' Essa entrega deveria ter chegado até **{data_minimo}**,'
                f' data em que o estoque mínimo é atingido.'
            )
            data_minimo_usada = True
        alertas.append(msg_sem_data)
    if pedidos_previstos:
        partes_prev = [f'**{pedidos_previstos} entrega(s) futura(s)** prevista(s):']
        for p in [p for p in pedidos_pendentes_detalhes if p.get('status') == 'A_RECEBER']:
            data_raw = p.get('data', '')
            try:
                data_fmt = datetime.strptime(data_raw, '%Y-%m-%d').strftime('%d/%m/%Y') if data_raw else '-'
            except ValueError:
                data_fmt = data_raw or '-'
            partes_prev.append(f'• **{data_fmt}** — {float(p.get("quantidade", 0) or 0):.2f} unidades')
        alertas.append('\n'.join(partes_prev))
    if data_minimo != '-' and not data_minimo_usada:
        alertas.append(f'Estoque mínimo projetado para **{data_minimo}**.')
    if data_zero != '-':
        alertas.append(f'Ruptura de estoque projetada para **{data_zero}**.')

    tipo_alerta = 'critico' if pedidos_atrasados or (
        dias_ate_compra is not None and dias_ate_compra <= 0
    ) else 'alerta'
    if not alertas:
        tipo_alerta = 'ok'
        alertas.append('Nenhum alerta crítico identificado na projeção atual.')

    card_alertas = {
        'tipo': tipo_alerta,
        'titulo': 'Alertas',
        'mensagem': '\n'.join(alertas),
        'qtd_sugerida': None,
    }

    qtd_ressuprimento = round(dias_ressupr * consumo_diario, 2)
    if pedidos_atrasados:
        tipo_acao = 'acao'
        titulo_acao = 'Acompanhar entrega atrasada'
        partes_acao = [
            'Contate o fornecedor e confirme uma nova previsão. '
            'O pedido atrasado não foi considerado no estoque projetado.'
        ]
        atrasados = [p for p in pedidos_pendentes_detalhes if p.get('status') == 'ATRASADO']
        if atrasados:
            partes_acao.append('Entregas atrasadas:')
            for p in atrasados:
                data_raw = p.get('data', '')
                try:
                    data_fmt = datetime.strptime(data_raw, '%Y-%m-%d').strftime('%d/%m/%Y') if data_raw else '-'
                except ValueError:
                    data_fmt = data_raw or '-'
                qtd_p = float(p.get('quantidade', 0) or 0)
                partes_acao.append(f'• **{data_fmt}** — {qtd_p:.2f} unidades')
        mensagem_acao = '\n'.join(partes_acao)
        qtd_sugerida = None
    elif ped_compras > 0:
        tipo_acao = 'acao'
        titulo_acao = 'Acompanhar pedidos pendentes'
        partes_acao = [
            f'Confirme as entregas pendentes. A próxima compra está prevista para '
            f'**{data_compra}**. Pedidos sem data devem receber uma previsão formal.'
        ]
        a_receber = [p for p in pedidos_pendentes_detalhes if p.get('status') == 'A_RECEBER']
        if a_receber:
            partes_acao.append('Entregas previstas:')
            for p in a_receber:
                data_raw = p.get('data', '')
                try:
                    data_fmt = datetime.strptime(data_raw, '%Y-%m-%d').strftime('%d/%m/%Y') if data_raw else '-'
                except ValueError:
                    data_fmt = data_raw or '-'
                qtd_p = float(p.get('quantidade', 0) or 0)
                partes_acao.append(f'• **{data_fmt}** — {qtd_p:.2f} unidades')
        mensagem_acao = '\n'.join(partes_acao)
        qtd_sugerida = None
    elif dias_ate_compra is not None and dias_ate_compra <= 3:
        tipo_acao = 'urgente'
        titulo_acao = 'Preparar nova compra'
        mensagem_acao = (
            f'Emita ou prepare o pedido até **{data_compra}** para evitar atingir '
            f'o estoque mínimo em **{data_minimo}**.'
        )
        qtd_sugerida = qtd_ressuprimento
    else:
        tipo_acao = 'ok'
        titulo_acao = 'Nenhuma ação imediata'
        mensagem_acao = (
            f'Monitore o consumo. A próxima compra está prevista para **{data_compra}**.'
        )
        qtd_sugerida = qtd_ressuprimento

    acao = {
        'tipo': tipo_acao,
        'titulo': titulo_acao,
        'mensagem': mensagem_acao,
        'qtd_sugerida': qtd_sugerida,
    }
    return [resumo, card_alertas, acao]


def gerar_sugestoes(projecao: dict, formato_enriquecido: bool = False) -> list:
    """
    Porta de sugestoes.py. Recebe o dict retornado por get_projecao_para_material
    e retorna lista de sugestoes em formato serializavel JSON.
    """
    if formato_enriquecido:
        return _gerar_sugestoes_enriquecidas(projecao)

    dias_ressupr = float(projecao.get('dias_ressupr', 0) or 0)
    consumo_diario = float(projecao.get('consumo_diario', 0) or 0)
    estoque_atual = float(projecao.get('estoque_atual', 0) or 0)
    estoque_minimo = float(projecao.get('estoque_minimo', 0) or 0)
    dias_ate_compra = projecao.get('dias_ate_data_compra')
    ped_compras = float(projecao.get('ped_compras', 0) or 0)
    chegadas_previstas = projecao.get('chegadas_previstas') or []
    pedidos_pendentes_count = int(projecao.get('pedidos_pendentes_count', 0) or 0)
    pedidos_atrasados_count = int(projecao.get('pedidos_atrasados_count', 0) or 0)
    pedidos_previstos_count = int(projecao.get('pedidos_previstos_count', 0) or 0)
    pedidos_pendentes_detalhes = projecao.get('pedidos_pendentes_detalhes') or []
    datas_pedidos_pendentes = projecao.get('datas_pedidos_pendentes') or []
    chegada_planejada_compra = projecao.get('chegada_planejada_compra') or {}

    if dias_ressupr == 0 or consumo_diario == 0:
        return [{
            'tipo': 'erro',
            'titulo': 'Dados insuficientes',
            'mensagem': 'Produto sem dias de ressuprimento ou consumo configurados. Verifique o cadastro.',
            'qtd_sugerida': None,
        }]

    hoje = datetime.now().date()
    data_chegada = _adicionar_dias_uteis(hoje, int(dias_ressupr))
    data_chegada_planejada = chegada_planejada_compra.get('data')
    data_chegada_planejada_formatada = (
        datetime.strptime(data_chegada_planejada, '%Y-%m-%d').strftime('%d/%m/%Y')
        if data_chegada_planejada else None
    )

    try:
        dias_uteis_ate_chegada = int(np.busday_count(hoje, data_chegada + timedelta(days=1)))
    except Exception:
        dias_uteis_ate_chegada = int(dias_ressupr)

    consumo_ate_chegada = dias_uteis_ate_chegada * consumo_diario
    estoque_no_dia_chegada = estoque_atual - consumo_ate_chegada
    gap_estoque = max(estoque_minimo - estoque_no_dia_chegada, 0)
    qtd_ressuprimento = dias_ressupr * consumo_diario

    sugestoes = []

    if ped_compras > 0:
        data_estoque_minimo_str = projecao.get('data_estoque_minimo')
        data_estoque_zero_str   = projecao.get('data_estoque_zero')

        try:
            dt_minimo = datetime.strptime(data_estoque_minimo_str, '%Y-%m-%d').date() if data_estoque_minimo_str else None
        except ValueError:
            dt_minimo = None
        try:
            dt_zero = datetime.strptime(data_estoque_zero_str, '%d/%m/%Y').date() if data_estoque_zero_str else None
        except ValueError:
            dt_zero = None

        n = pedidos_pendentes_count or 1
        titulo = (
            f'{n} pedido{"s" if n > 1 else ""} de compra pendente{"s" if n > 1 else ""}'
        )

        partes = [
            f'Há **{n} pedido{"s" if n > 1 else ""}** de compra pendente{"s" if n > 1 else ""}'
            f' totalizando **{ped_compras:.2f} unidades**.'
        ]
        if pedidos_atrasados_count > 0:
            partes.append(
                f'**{pedidos_atrasados_count} pedido{"s" if pedidos_atrasados_count > 1 else ""}**'
                f' est{"ao" if pedidos_atrasados_count > 1 else "a"} **atrasado{"s" if pedidos_atrasados_count > 1 else ""}**'
                f' e nao entra{"m" if pedidos_atrasados_count > 1 else ""} no calculo de **Est. almox**.'
            )
        if pedidos_previstos_count > 0:
            partes.append(
                f'**{pedidos_previstos_count} pedido{"s" if pedidos_previstos_count > 1 else ""}**'
                f' ainda est{"ao" if pedidos_previstos_count > 1 else "a"} previsto{"s" if pedidos_previstos_count > 1 else ""} para chegada.'
            )

        if pedidos_pendentes_detalhes:
            partes.append('Pedidos pendentes:')
            for idx, pedido in enumerate(pedidos_pendentes_detalhes, start=1):
                data_str = pedido.get('data')
                try:
                    data_fmt = datetime.strptime(data_str, '%Y-%m-%d').strftime('%d/%m/%Y') if data_str else '-'
                except ValueError:
                    data_fmt = data_str or '-'
                quantidade = float(pedido.get('quantidade', 0) or 0)
                partes.append(f'{idx}. **{data_fmt}** — **{quantidade:.2f} unidades**')

        chegadas = projecao.get('chegadas_previstas') or []
        datas_analisadas = set()

        for chegada in chegadas:
            data_str = chegada.get('data')
            if not data_str or data_str in datas_analisadas:
                continue
            datas_analisadas.add(data_str)
            try:
                dt_chegada = datetime.strptime(data_str, '%Y-%m-%d').date()
            except ValueError:
                continue

            qtd = chegada.get('quantidade', 0)
            estoque_apos = chegada.get('estoque_apos_chegada', 0)
            dt_fmt = dt_chegada.strftime('%d/%m/%Y')

            partes.append(
                f'A entrega prevista é **{dt_fmt}** ({qtd:.0f} unidades),'
                f' com estoque projetado após chegada de **{estoque_apos:.2f} unidades**.'
            )

            if dt_minimo:
                dias_diff = int(np.busday_count(dt_chegada, dt_minimo))
                if dias_diff >= 0:
                    partes.append(
                        f'✅ O pedido chegará **{dias_diff} dia{"s" if dias_diff != 1 else ""}** antes'
                        f' do estoque mínimo (previsto para **{dt_minimo.strftime("%d/%m/%Y")}**).'
                    )
                else:
                    partes.append(
                        f'⚠️ O pedido chegará **{abs(dias_diff)} dia{"s" if abs(dias_diff) != 1 else ""}** APÓS'
                        f' o estoque mínimo (previsto para **{dt_minimo.strftime("%d/%m/%Y")}**) — risco de ruptura!'
                    )

            if dt_zero and dt_chegada > dt_zero:
                dias_atraso_zero = int(np.busday_count(dt_zero, dt_chegada))
                partes.append(
                    f'🚨 O estoque zerará **{dias_atraso_zero} dia{"s" if dias_atraso_zero != 1 else ""}**'
                    f' antes da entrega (estoque zero em **{dt_zero.strftime("%d/%m/%Y")}**)!'
                )

        if not chegadas and datas_pedidos_pendentes:
            for data_str in datas_pedidos_pendentes[:3]:
                try:
                    dt_chegada = datetime.strptime(data_str, '%Y-%m-%d').date()
                except ValueError:
                    continue
                dt_fmt = dt_chegada.strftime('%d/%m/%Y')
                if dt_minimo:
                    dias_diff = int(np.busday_count(dt_chegada, dt_minimo))
                    if dias_diff >= 0:
                        partes.append(
                            f'Entrega prevista para **{dt_fmt}**, chegando **{dias_diff} dia{"s" if dias_diff != 1 else ""}** antes do estoque mínimo (**{dt_minimo.strftime("%d/%m/%Y")}**). ✅'
                        )
                    else:
                        partes.append(
                            f'Entrega prevista para **{dt_fmt}**, porém **{abs(dias_diff)} dia{"s" if abs(dias_diff) != 1 else ""}** após o estoque mínimo (**{dt_minimo.strftime("%d/%m/%Y")}**) — risco de ruptura! ⚠️'
                        )
                else:
                    partes.append(f'Entrega prevista para **{dt_fmt}**.')

        sugestoes.append({
            'tipo': 'info',
            'titulo': titulo,
            'mensagem': '\n'.join(partes),
            'qtd_sugerida': None,
        })
        return sugestoes

    dt_chegada_fmt = data_chegada_planejada_formatada or data_chegada.strftime('%d/%m/%Y')

    if estoque_atual <= estoque_minimo:
        qtd_total = gap_estoque + qtd_ressuprimento
        dias_atraso = abs(dias_ate_compra) if dias_ate_compra is not None else 0
        sugestoes.append({
            'tipo': 'critico',
            'titulo': f'Estoque abaixo do mínimo — prazo vencido há {dias_atraso} dias',
            'mensagem': (
                f'O estoque atual está abaixo do mínimo e o prazo de compra venceu há **{dias_atraso} dias**.'
                f' Solicite a compra **hoje**. A chegada prevista do material é **{dt_chegada_fmt}**'
                f' ({dias_uteis_ate_chegada} dias úteis), com estoque projetado na chegada de'
                f' **{estoque_no_dia_chegada:.2f} unidades**.'
                f' Gap estimado: **{gap_estoque:.2f}** unidades; ressuprimento necessário: **{qtd_ressuprimento:.2f}** unidades.'
            ),
            'qtd_sugerida': round(qtd_total, 2),
        })
        return sugestoes

    if dias_ate_compra is not None and dias_ate_compra <= 0:
        dias_atraso = abs(dias_ate_compra)
        qtd_total = gap_estoque + qtd_ressuprimento
        sugestoes.append({
            'tipo': 'urgente',
            'titulo': f'Prazo de compra vencido há {dias_atraso} dias',
            'mensagem': (
                f'O prazo para solicitar a compra venceu há **{dias_atraso} dias** — solicite **hoje**.'
                f' A chegada prevista do material é **{dt_chegada_fmt}**, com estoque projetado na chegada de'
                f' **{estoque_no_dia_chegada:.2f} unidades**.'
                f' Gap estimado: **{gap_estoque:.2f}** unidades; ressuprimento necessário: **{qtd_ressuprimento:.2f}** unidades.'
            ),
            'qtd_sugerida': round(qtd_total, 2),
        })
        return sugestoes

    if dias_ate_compra is not None and dias_ate_compra <= 3:
        if estoque_atual < estoque_minimo:
            gap = estoque_minimo - estoque_atual
            qtd = qtd_ressuprimento + gap
        else:
            qtd = qtd_ressuprimento
        sugestoes.append({
            'tipo': 'alerta',
            'titulo': f'Prazo de compra em {dias_ate_compra} dia{"s" if dias_ate_compra != 1 else ""}',
            'mensagem': (
                f'Restam apenas **{dias_ate_compra} dia{"s" if dias_ate_compra != 1 else ""}** para solicitar a compra.'
                f' Inicie o planejamento do pedido agora. O ressuprimento padrão é de **{qtd_ressuprimento:.2f} unidades**'
                f' ({int(dias_ressupr)} dias de cobertura), com chegada prevista em **{dt_chegada_fmt}**.'
            ),
            'qtd_sugerida': round(qtd, 2),
        })
        return sugestoes

    sugestoes.append({
        'tipo': 'ok',
        'titulo': f'Situação controlada — próxima compra em {dias_ate_compra} dias',
        'mensagem': (
            f'O estoque está dentro do planejado. A próxima compra deve ser solicitada em **{dias_ate_compra} dias**,'
            f' com ressuprimento de **{qtd_ressuprimento:.2f} unidades** ({int(dias_ressupr)} dias de cobertura,'
            f' consumo diário de **{consumo_diario:.3f} unidades**).'
            f' Chegada prevista após a compra: **{dt_chegada_fmt}**.'
        ),
        'qtd_sugerida': round(qtd_ressuprimento, 2),
    })
    return sugestoes
