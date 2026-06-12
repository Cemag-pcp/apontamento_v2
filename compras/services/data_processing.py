import re
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / 'data'


def _tratar_valor_numerico(valor, default=0):
    if isinstance(valor, str):
        valor = valor.strip()
        if valor in ('', '#REF!', '#DIV/0!', 'N/A', 'nan', 'None'):
            return default
        try:
            return float(valor.replace('.', '').replace(',', '.'))
        except ValueError:
            return default
    try:
        return float(valor)
    except (ValueError, TypeError):
        return default


def _valor_escalar(valor, default=None):
    if isinstance(valor, pd.Series):
        serie = valor.dropna()
        return serie.iloc[0] if not serie.empty else default
    return default if valor is None else valor


def _repair_text(text):
    if not isinstance(text, str):
        return '' if text is None else str(text)
    repaired = text
    for _ in range(2):
        try:
            candidate = repaired.encode('latin1').decode('utf-8')
        except (UnicodeEncodeError, UnicodeDecodeError):
            break
        if candidate == repaired:
            break
        repaired = candidate
    return repaired


def _normalize_header(text):
    repaired = _repair_text(text)
    lowered = repaired.lower().replace('\n', ' ').strip()
    lowered = re.sub(r'\s+', ' ', lowered)
    lowered = (
        lowered.replace('ã§', 'c')
        .replace('ç', 'c')
        .replace('ã£', 'a')
        .replace('ã¡', 'a')
        .replace('ã©', 'e')
        .replace('é', 'e')
        .replace('ê', 'e')
        .replace('í', 'i')
        .replace('ã³', 'o')
        .replace('ó', 'o')
        .replace('õ', 'o')
        .replace('ú', 'u')
        .replace('â', '')
        .replace('ª', '')
        .replace('º', '')
    )
    lowered = re.sub(r'[^a-z0-9 ]+', '', lowered)
    return lowered.strip()


def _rename_columns_by_aliases(df, aliases_map):
    rename_map = {}
    normalized_columns = {col: _normalize_header(col) for col in df.columns}
    for target, aliases in aliases_map.items():
        normalized_aliases = {_normalize_header(alias) for alias in aliases}
        for original, normalized in normalized_columns.items():
            if normalized in normalized_aliases and original not in rename_map:
                rename_map[original] = target
                break
    return df.rename(columns=rename_map)


def _adicionar_dias_uteis(data_inicial, num_dias):
    if pd.isna(num_dias) or num_dias == 0:
        return data_inicial
    try:
        num_dias = int(num_dias)
    except (ValueError, TypeError):
        return data_inicial
    if abs(num_dias) > 20000:
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


def _ajustar_estoque(row, df_pedidos):
    data_limite = _valor_escalar(row.get('data_estoque_minimo'))
    if data_limite is None or pd.isna(data_limite):
        return row['estoque_almox']

    if isinstance(data_limite, datetime):
        data_limite = data_limite.date()

    try:
        data_limite_ts = pd.to_datetime(data_limite)
    except Exception:
        return row['estoque_almox']

    if 'qde_ped_corrigido' not in df_pedidos.columns:
        return row['estoque_almox']

    hoje_ts = pd.Timestamp(datetime.now().date())
    pedidos = df_pedidos[
        (df_pedidos['codigo'] == row['codigo']) &
        pd.notna(df_pedidos['data_entrega']) &
        (df_pedidos['data_entrega'] >= hoje_ts) &
        (df_pedidos['data_entrega'] <= data_limite_ts)
    ]
    if not pedidos.empty:
        return row['estoque_almox'] + pedidos['qde_ped_corrigido'].sum()
    return row['estoque_almox']


def _calcular_datas_projecao(
    row,
    df_pedidos,
    horizonte_dias_uteis=365,
    considerar_pedido_pendente_como_recebido=False,
):
    consumo_diario = float(_valor_escalar(row.get('consumo_diario'), 0) or 0)
    estoque_minimo = float(_valor_escalar(row.get('estoque_minimo'), 0) or 0)
    dias_ressupr = float(_valor_escalar(row.get('dias_ressupr'), 0) or 0)
    estoque_base = float(
        _valor_escalar(row.get('estoque_almox_central'), _valor_escalar(row.get('estoque_almox'), 0)) or 0
    )

    hoje = datetime.now().date()
    if consumo_diario <= 0:
        return {
            'data_estoque_minimo': None,
            'data_estoque_zero': None,
            'data_compra': None,
            'dias_ate_data_compra': None,
        }

    pedidos = df_pedidos[
        (df_pedidos['codigo'] == row['codigo']) &
        pd.notna(df_pedidos.get('data_entrega')) &
        (df_pedidos.get('qde_ped_corrigido', 0) > 0)
    ].copy()
    hoje_ts = pd.Timestamp(hoje)
    possui_pedido_atrasado = bool(
        not pedidos.empty
        and (pedidos['data_entrega'] < hoje_ts).any()
    )
    pedido_pendente = float(
        _valor_escalar(row.get('ped_compras_pendente'), 0) or 0
    )

    if (
        considerar_pedido_pendente_como_recebido
        and pedido_pendente > 0
        and not possui_pedido_atrasado
    ):
        estoque_base += pedido_pendente
        pedidos = pedidos.iloc[0:0]
    else:
        pedidos = pedidos[pedidos['data_entrega'] >= hoje_ts]

    chegadas_por_data = {}
    ultima_chegada = pd.Timestamp(hoje)
    if not pedidos.empty:
        chegadas_agrupadas = pedidos.groupby('data_entrega')['qde_ped_corrigido'].sum()
        chegadas_por_data = {
            pd.Timestamp(data): float(qtd)
            for data, qtd in chegadas_agrupadas.items()
            if pd.notna(data)
        }
        if chegadas_por_data:
            ultima_chegada = max(chegadas_por_data)

    data_estoque_minimo = None
    data_estoque_zero = None
    estoque = estoque_base
    datas = pd.date_range(start=hoje, periods=horizonte_dias_uteis, freq='B')

    for data in datas:
        estoque -= consumo_diario
        estoque += chegadas_por_data.get(data, 0)

        if data_estoque_zero is None and estoque <= 0:
            data_estoque_zero = data.date()

        if data_estoque_minimo is None and data >= ultima_chegada and estoque <= estoque_minimo:
            data_estoque_minimo = data.date()

        if data_estoque_minimo is not None and data_estoque_zero is not None:
            break

    data_compra = None
    dias_ate_data_compra = None
    if data_estoque_minimo is not None:
        data_compra = _adicionar_dias_uteis(data_estoque_minimo, -(dias_ressupr + 1))
        dias_ate_data_compra = int(np.busday_count(hoje, data_compra)) if pd.notna(data_compra) else None

    return {
        'data_estoque_minimo': data_estoque_minimo,
        'data_estoque_zero': data_estoque_zero,
        'data_compra': data_compra,
        'dias_ate_data_compra': dias_ate_data_compra,
    }


def processar_material_direto(
    simulacao_df_raw: pd.DataFrame,
    pedidos_df_raw: pd.DataFrame,
    skip_first_row: bool = True,
    considerar_pedido_pendente_como_recebido: bool = False,
) -> dict:
    grupo_df = pd.read_csv(DATA_DIR / 'agrupamento_chapas.csv', sep=';')
    grupos_df = pd.read_csv(DATA_DIR / 'grupos_atualizados.csv', sep=',')
    grupos_df = grupos_df.rename(columns={'Código': 'codigo'} if 'Código' in grupos_df.columns else {})
    if 'codigo' not in grupos_df.columns:
        grupos_df = _rename_columns_by_aliases(grupos_df, {'codigo': ['Código', 'Código', 'codigo']})
    grupos_df = grupos_df[['codigo', 'grupo']]

    simulacao_aliases = {
        'codigo': ['Código', 'Código', 'codigo'],
        'descricao': ['Descrição', 'Descrição', 'DescriÃ§Ã£o', 'descricao'],
        'media_3m': ['Média 3M', 'MÃ©dia 3M', 'media 3m', 'Média'],
        'cons_mes_anterior': ['Cons Mes Anterior', 'Cons Mes\nAnterior', 'CMA'],
        'simulado_pend_vendas': ['Simulado Pend Vendas', 'Simulado \nPend Vendas', 'Simulado'],
        'estoque_almox': ['Est.Almox Central', 'Qtd.Est.'],
        'est_producao': ['Est. Produção', 'Est. ProduÃ§Ã£o'],
        'estoque_total': ['Estoque Total', 'Est Total'],
        'ped_compras_pendente': ['Ped.Compras Pendente', 'Ped.Compras\n Pendente', 'Pedidos Pend.'],
        'prev_consumo': ['Prev Con Mov Est(CMM)'],
        'simulacao': ['SIMULAÇÃO / (F.Pend/Fat.MM)', 'SIMULAÃ‡ÃƒO / (F.Pend/Fat.MM)', 'SIMULACAO / (F.Pend/Fat.MM)'],
        'dee_dias_em_est': ['DEE - Dias Em Est.', 'DEE'],
        'dias_ressupr': ['Dias Ressupr', 'Dias\nRessupr', 'TRP'],
        'dias_seg': ['Dias de seg.'],
        'estoque_minimo': ['Estoque Mínimo', 'Estoque MÃ­nimo', 'Estoque Minimo'],
    }
    pedidos_aliases = {
        'recurso': ['Recurso'],
        'data_entrega': ['Data Entrega'],
        'qde_ped': ['Qde Ped', 'Qdade Pedido'],
        'codigo': ['Código', 'Código', 'codigo'],
    }

    df = _rename_columns_by_aliases(simulacao_df_raw.copy(), simulacao_aliases)
    df_ped = _rename_columns_by_aliases(pedidos_df_raw.copy(), pedidos_aliases)

    duplicated = df[df['codigo'].isin(grupo_df['codigo'])].copy()
    duplicated = duplicated.merge(grupo_df, left_on='codigo', right_on='codigo')
    duplicated['descricao'] = duplicated['grupo']
    duplicated['codigo'] = duplicated['grupo']
    df = pd.concat([df, duplicated.drop(columns=['grupo'])]).reset_index(drop=True)

    colunas_numericas = [
        'media_3m', 'cons_mes_anterior', 'simulado_pend_vendas', 'estoque_almox',
        'est_producao', 'estoque_total', 'ped_compras_pendente', 'prev_consumo',
        'simulacao', 'dee_dias_em_est', 'dias_ressupr', 'dias_seg', 'estoque_minimo',
    ]
    for col in colunas_numericas:
        if col in df.columns:
            default = 10 if col == 'dias_seg' else 0
            df[col] = df[col].apply(lambda x: _tratar_valor_numerico(x, default))

    agg = {
        'media_3m': 'mean',
        'cons_mes_anterior': 'mean',
        'dias_ressupr': 'max',
        'dias_seg': 'max',
        'estoque_minimo': 'mean',
        'prev_consumo': 'mean',
        'simulacao': 'max',
        'simulado_pend_vendas': 'sum',
        'estoque_almox': 'sum',
        'est_producao': 'sum',
        'estoque_total': 'sum',
        'ped_compras_pendente': 'sum',
        'dee_dias_em_est': 'sum',
    }
    agg_valido = {k: v for k, v in agg.items() if k in df.columns}
    df = df.groupby(['descricao', 'codigo']).agg(agg_valido).reset_index()
    df = df.loc[:, ~df.columns.duplicated()]
    df = df.merge(grupos_df, on='codigo', how='left').fillna({'grupo': 'Sem Grupo'})

    renomear_col = list(df_ped.columns)
    if len(renomear_col) > 12:
        renomear_col[12] = 'recurso_1'
        df_ped.columns = renomear_col

    if 'recurso' in df_ped.columns:
        df_ped['codigo'] = df_ped['recurso'].astype(str).str.split(' - ').str[0]

    if 'qde_ped' in df_ped.columns:
        qde_raw = df_ped.loc[:, df_ped.columns == 'qde_ped']
        qde_serie = qde_raw.iloc[:, 0] if isinstance(qde_raw, pd.DataFrame) else qde_raw
        df_ped['qde_ped_corrigido'] = qde_serie.apply(
            lambda x: float(str(x).replace('.', '').replace(',', '.'))
            if not pd.isna(x) and str(x).strip() != '' else 0
        )
    else:
        df_ped['qde_ped_corrigido'] = 0

    if 'data_entrega' in df_ped.columns:
        df_ped['data_entrega'] = pd.to_datetime(df_ped['data_entrega'], format='%d/%m/%Y', errors='coerce')
        df_ped['data_entrega'] = df_ped['data_entrega'].apply(
            lambda x: x - timedelta(days=1) if pd.notna(x) and x.weekday() == 5
            else (x + timedelta(days=1) if pd.notna(x) and x.weekday() == 6 else x)
        )

    hoje_ts = pd.Timestamp(datetime.now().date())

    if 'codigo' in df_ped.columns:
        dup_ped = df_ped[df_ped['codigo'].isin(grupo_df['codigo'])].copy()
        dup_ped = dup_ped.merge(grupo_df, on='codigo')
        if not dup_ped.empty:
            dup_ped['recurso'] = dup_ped['grupo']
            dup_ped['codigo'] = dup_ped['grupo']
            if 'recurso' in dup_ped.columns:
                dup_ped['recurso'] = dup_ped['recurso'].apply(lambda x: f"{x} - {x}")
            df_ped = pd.concat([df_ped, dup_ped.drop(columns=['grupo'])]).reset_index(drop=True)
        if 'recurso' in df_ped.columns:
            df_ped = df_ped[df_ped['recurso'] != '']

    df['consumo_diario'] = df.apply(
        lambda row: max(
            _valor_escalar(row.get('simulacao'), 0) or 0,
            _valor_escalar(row.get('prev_consumo'), 0) or 0,
        ) / 20,
        axis=1,
    )
    df['estoque_almox_central'] = df['estoque_almox']

    hoje = datetime.now().date()
    df['dias_ate_estoque_minimo'] = df.apply(
        lambda row: (row['estoque_almox'] - row.get('estoque_minimo', 0)) / row['consumo_diario']
        if row['consumo_diario'] > 0 else None,
        axis=1,
    )
    df['data_estoque_minimo'] = df['dias_ate_estoque_minimo'].apply(lambda dias: _adicionar_dias_uteis(hoje, dias))
    df['data_compra'] = df.apply(
        lambda row: _adicionar_dias_uteis(row['data_estoque_minimo'], _valor_escalar(row.get('dias_ressupr'), 0) * -1)
        if pd.notna(_valor_escalar(row.get('data_estoque_minimo'))) and pd.notna(_valor_escalar(row.get('dias_ressupr'))) else None,
        axis=1,
    )

    df['estoque_almox'] = df.apply(lambda row: _ajustar_estoque(row, df_ped), axis=1)
    projecoes_datas = df.apply(
        lambda row: _calcular_datas_projecao(
            row,
            df_ped,
            considerar_pedido_pendente_como_recebido=(
                considerar_pedido_pendente_como_recebido
            ),
        ),
        axis=1,
    )
    df['data_estoque_minimo'] = projecoes_datas.apply(lambda item: item.get('data_estoque_minimo'))
    df['data_estoque_zero'] = projecoes_datas.apply(lambda item: item.get('data_estoque_zero'))
    df['data_compra'] = projecoes_datas.apply(lambda item: item.get('data_compra'))
    df['dias_ate_data_compra'] = projecoes_datas.apply(lambda item: item.get('dias_ate_data_compra'))
    df['dias_ate_estoque_minimo'] = df.apply(
        lambda row: int(np.busday_count(hoje, row['data_estoque_minimo']))
        if pd.notna(_valor_escalar(row.get('data_estoque_minimo'))) else None,
        axis=1,
    )
    df['dias_ate_estoque_zero'] = df.apply(
        lambda row: int(np.busday_count(hoje, row['data_estoque_zero']))
        if pd.notna(_valor_escalar(row.get('data_estoque_zero'))) else None,
        axis=1,
    )

    def _flag(dias):
        if dias is None or pd.isna(dias):
            return 'SEM_DADOS'
        if dias <= 0:
            return 'URGENTE'
        if dias <= 5:
            return 'PRAZO_CURTO'
        return 'PRAZO_OK'

    df['flag_urgencia'] = df['dias_ate_data_compra'].apply(_flag)

    mask_pedido = (df['flag_urgencia'] == 'URGENTE') & (df['ped_compras_pendente'] > 0)
    df.loc[mask_pedido, 'flag_urgencia'] = 'URGENTE_COM_PEDIDO'

    if skip_first_row and len(df) > 1:
        df = df.iloc[1:].reset_index(drop=True)

    materiais = []
    for _, row in df.iterrows():
        pedidos_material = df_ped[
            (df_ped['codigo'] == row['codigo']) &
            pd.notna(df_ped.get('data_entrega')) &
            (df_ped.get('qde_ped_corrigido', 0) > 0)
        ].copy()
        pedidos_atrasados = pedidos_material[pedidos_material['data_entrega'] < hoje_ts]
        pedidos_previstos = pedidos_material[pedidos_material['data_entrega'] >= hoje_ts]
        exibir_data_compra = _valor_escalar(row.get('data_compra'))

        flag_status = 'PEDIDO_ATRASADO' if len(pedidos_atrasados) > 0 else _valor_escalar(row.get('flag_urgencia'), 'SEM_DADOS')

        materiais.append({
            'codigo': str(_valor_escalar(row.get('codigo'), '')),
            'descricao': str(_valor_escalar(row.get('descricao'), '')),
            'grupo': str(_valor_escalar(row.get('grupo'), '')),
            'media_3m': round(float(_valor_escalar(row.get('media_3m'), 0) or 0), 2),
            'cons_mes_anterior': round(float(_valor_escalar(row.get('cons_mes_anterior'), 0) or 0), 2),
            'simulado_pend_vendas': round(float(_valor_escalar(row.get('simulado_pend_vendas'), 0) or 0), 2),
            'dee_dias_em_est': round(float(_valor_escalar(row.get('dee_dias_em_est'), 0) or 0), 1),
            'estoque_almox_central': round(float(_valor_escalar(row.get('estoque_almox_central'), 0) or 0), 2),
            'estoque_almox': round(float(_valor_escalar(row.get('estoque_almox'), 0) or 0), 2),
            'estoque_total': round(float(_valor_escalar(row.get('estoque_total'), 0) or 0), 2),
            'ped_compras': round(float(_valor_escalar(row.get('ped_compras_pendente'), 0) or 0), 2),
            'ped_compras_atrasado': round(float(pedidos_atrasados['qde_ped_corrigido'].sum()), 2),
            'ped_compras_previsto': round(float(pedidos_previstos['qde_ped_corrigido'].sum()), 2),
            'consumo_diario': round(float(_valor_escalar(row.get('consumo_diario'), 0) or 0), 3),
            'dias_ate_zero': round(float(row['dias_ate_estoque_zero']), 1)
            if pd.notna(_valor_escalar(row.get('dias_ate_estoque_zero'))) else 9999,
            'dias_ate_data_compra': int(row['dias_ate_data_compra'])
            if pd.notna(_valor_escalar(row.get('dias_ate_data_compra'))) else None,
            'data_compra': exibir_data_compra.strftime('%d/%m/%Y')
            if pd.notna(exibir_data_compra) else None,
            'data_estoque_minimo': row['data_estoque_minimo'].strftime('%d/%m/%Y')
            if pd.notna(_valor_escalar(row.get('data_estoque_minimo'))) else None,
            'data_estoque_zero': row['data_estoque_zero'].strftime('%d/%m/%Y')
            if pd.notna(_valor_escalar(row.get('data_estoque_zero'))) else None,
            'dias_ressupr': round(float(_valor_escalar(row.get('dias_ressupr'), 0) or 0), 0),
            'estoque_minimo': round(float(_valor_escalar(row.get('estoque_minimo'), 0) or 0), 2),
            'flag_urgencia': flag_status,
            'tem_pedido': 'SIM' if float(_valor_escalar(row.get('ped_compras_pendente'), 0) or 0) > 0 else 'NÃO',
            'pedidos_atrasados_count': int(len(pedidos_atrasados)),
            'pedidos_previstos_count': int(len(pedidos_previstos)),
        })

    codigos = sorted(set(m['codigo'] for m in materiais if m['codigo']))
    grupos = sorted(set(m['grupo'] for m in materiais if m['grupo'] and m['grupo'] != 'Sem Grupo'))

    return {
        'materiais': materiais,
        'codigos': codigos,
        'grupos': grupos,
        'df': df,
        'df_pedidos': df_ped,
    }


def get_projecao_para_material(
    codigo: str,
    df: pd.DataFrame,
    df_ped: pd.DataFrame,
    considerar_pedido_pendente_como_recebido: bool = False,
) -> dict:
    linha = df[df['codigo'] == codigo]
    if linha.empty:
        return {'error': 'Material não encontrado'}

    row = linha.iloc[0]
    estoque_fisico = float(
        _valor_escalar(row.get('estoque_almox_central'), _valor_escalar(row.get('estoque_almox'), 0)) or 0
    )
    estoque_minimo = float(_valor_escalar(row.get('estoque_minimo'), 0) or 0)
    consumo_diario = float(_valor_escalar(row.get('consumo_diario'), 0) or 0)
    dias_ressupr = float(_valor_escalar(row.get('dias_ressupr'), 0) or 0)
    data_compra = _valor_escalar(row.get('data_compra'))

    hoje_ts = pd.Timestamp(datetime.now().date())
    ped_compras = float(_valor_escalar(row.get('ped_compras_pendente'), 0) or 0)
    pedidos_codigo = df_ped[df_ped['codigo'] == codigo].copy()
    pedidos_pendentes_qs = pedidos_codigo[
        pd.notna(pedidos_codigo.get('data_entrega')) &
        (pedidos_codigo.get('qde_ped_corrigido', 0) > 0)
    ].copy()
    pedidos_pendentes_qs = pedidos_pendentes_qs.sort_values(by='data_entrega', ascending=True)
    pedidos_atrasados_qs = pedidos_pendentes_qs[pedidos_pendentes_qs['data_entrega'] < hoje_ts].copy()
    pedidos_previstos_qs = pedidos_pendentes_qs[pedidos_pendentes_qs['data_entrega'] >= hoje_ts].copy()

    ped_compras_atrasado = float(pedidos_atrasados_qs.get('qde_ped_corrigido', 0).sum())
    ped_compras_previsto = float(pedidos_previstos_qs.get('qde_ped_corrigido', 0).sum())
    ped_compras_sem_data = max(
        ped_compras - ped_compras_atrasado - ped_compras_previsto,
        0,
    )
    pedido_elegivel_projecao = max(ped_compras - ped_compras_atrasado, 0)
    estoque_projetado = (
        estoque_fisico + pedido_elegivel_projecao
        if considerar_pedido_pendente_como_recebido
        else estoque_fisico
    )

    datas = pd.date_range(start=datetime.now().date(), periods=121, freq='B')
    estoque_atual_dia = estoque_projetado
    datas_grafico = []
    estoque_diario = []
    chegadas_previstas = []

    if len(datas):
        datas_grafico.append(datas[0].strftime('%Y-%m-%d'))
        estoque_diario.append(round(estoque_atual_dia, 2))

    for data in datas:
        estoque_atual_dia -= consumo_diario
        datas_grafico.append(data.strftime('%Y-%m-%d'))
        estoque_diario.append(round(estoque_atual_dia, 2))

        pedidos_do_dia = pedidos_previstos_qs[pedidos_previstos_qs['data_entrega'] == data]
        if not pedidos_do_dia.empty and 'qde_ped_corrigido' in pedidos_do_dia.columns:
            quantidade_chegada = float(pedidos_do_dia['qde_ped_corrigido'].sum())
            if not considerar_pedido_pendente_como_recebido:
                estoque_atual_dia += quantidade_chegada
            datas_grafico.append(data.strftime('%Y-%m-%d'))
            estoque_diario.append(round(estoque_atual_dia, 2))
            chegadas_previstas.append({
                'data': data.strftime('%Y-%m-%d'),
                'quantidade': round(quantidade_chegada, 2),
                'estoque_apos_chegada': round(estoque_atual_dia, 2),
            })

    estoque_ideal = estoque_projetado
    valor_ideal_compra = dias_ressupr * consumo_diario
    datas_ideal = []
    estoque_ideal_diario = []

    if len(datas):
        datas_ideal.append(datas[0].strftime('%Y-%m-%d'))
        estoque_ideal_diario.append(round(estoque_ideal, 2))

    for data in datas:
        estoque_ideal -= consumo_diario
        datas_ideal.append(data.strftime('%Y-%m-%d'))
        estoque_ideal_diario.append(round(estoque_ideal, 2))
        if estoque_ideal <= estoque_minimo:
            estoque_ideal += valor_ideal_compra
            datas_ideal.append(data.strftime('%Y-%m-%d'))
            estoque_ideal_diario.append(round(estoque_ideal, 2))

    chegada_planejada_compra = None
    if pd.notna(data_compra):
        chegada_planejada_data = _adicionar_dias_uteis(data_compra, dias_ressupr)
        if pd.notna(chegada_planejada_data):
            chegada_planejada_compra = {
                'data': pd.to_datetime(chegada_planejada_data).strftime('%Y-%m-%d'),
                'estoque_referencia': round(estoque_minimo, 2),
            }

    def _iso_data(valor):
        if valor is None or pd.isna(valor):
            return None
        return pd.to_datetime(valor).strftime('%Y-%m-%d')

    def _estoque_na_data(data_iso):
        if not data_iso:
            return None
        indices = [
            index
            for index, data in enumerate(datas_grafico)
            if data <= data_iso
        ]
        if not indices:
            return round(estoque_projetado, 2)
        return round(float(estoque_diario[indices[-1]]), 2)

    data_compra_iso = _iso_data(data_compra)
    data_minimo_iso = _iso_data(_valor_escalar(row.get('data_estoque_minimo')))
    data_zero_iso = _iso_data(_valor_escalar(row.get('data_estoque_zero')))
    eventos_grafico = [
        {
            'tipo': 'hoje',
            'data': hoje_ts.strftime('%Y-%m-%d'),
            'titulo': 'Hoje',
            'descricao': (
                f'Estoque físico: {estoque_fisico:.2f}. '
                f'Estoque projetado: {estoque_projetado:.2f}.'
            ),
            'quantidade': round(estoque_projetado, 2),
            'estoque': round(estoque_projetado, 2),
        }
    ]

    for _, pedido in pedidos_atrasados_qs.iterrows():
        data_iso = _iso_data(pedido.get('data_entrega'))
        quantidade = float(pedido.get('qde_ped_corrigido', 0) or 0)
        eventos_grafico.append({
            'tipo': 'entrega_atrasada',
            'data': data_iso,
            'titulo': 'Entrega atrasada',
            'descricao': f'Pedido de {quantidade:.2f} unidades ainda não recebido.',
            'quantidade': round(quantidade, 2),
            'estoque': _estoque_na_data(data_iso),
        })

    for _, pedido in pedidos_previstos_qs.iterrows():
        data_iso = _iso_data(pedido.get('data_entrega'))
        quantidade = float(pedido.get('qde_ped_corrigido', 0) or 0)
        eventos_grafico.append({
            'tipo': 'entrega_prevista',
            'data': data_iso,
            'titulo': 'Entrega prevista',
            'descricao': f'Pedido de {quantidade:.2f} unidades com entrega programada.',
            'quantidade': round(quantidade, 2),
            'estoque': _estoque_na_data(data_iso),
        })

    marcos = [
        (
            'proxima_compra',
            data_compra_iso,
            'Próxima compra',
            'Data recomendada para emitir o próximo pedido.',
        ),
        (
            'estoque_minimo',
            data_minimo_iso,
            'Estoque mínimo',
            f'Estoque projetado atinge o mínimo de {estoque_minimo:.2f} unidades.',
        ),
        (
            'estoque_zero',
            data_zero_iso,
            'Estoque zero',
            'Data projetada para ruptura do estoque.',
        ),
    ]
    for tipo, data_iso, titulo, descricao in marcos:
        if data_iso:
            eventos_grafico.append({
                'tipo': tipo,
                'data': data_iso,
                'titulo': titulo,
                'descricao': descricao,
                'quantidade': None,
                'estoque': _estoque_na_data(data_iso),
            })

    return {
        'codigo': codigo,
        'descricao': str(_valor_escalar(row.get('descricao'), '')),
        'estoque_minimo': estoque_minimo,
        'consumo_diario': round(consumo_diario, 3),
        'dias_ressupr': dias_ressupr,
        'dias_ate_data_compra': int(row['dias_ate_data_compra']) if pd.notna(_valor_escalar(row.get('dias_ate_data_compra'))) else None,
        'data_compra': row['data_compra'].strftime('%d/%m/%Y') if pd.notna(_valor_escalar(row.get('data_compra'))) else None,
        'data_estoque_zero': row['data_estoque_zero'].strftime('%d/%m/%Y') if pd.notna(_valor_escalar(row.get('data_estoque_zero'))) else None,
        'flag_urgencia': str(_valor_escalar(row.get('flag_urgencia'), '')),
        'serie_real': {'datas': datas_grafico, 'estoques': estoque_diario},
        'serie_ideal': {'datas': datas_ideal, 'estoques': estoque_ideal_diario},
        'eventos_grafico': eventos_grafico,
        'chegadas_previstas': chegadas_previstas,
        'pedidos_pendentes_count': int(len(pedidos_pendentes_qs)),
        'pedidos_atrasados_count': int(len(pedidos_atrasados_qs)),
        'pedidos_previstos_count': int(len(pedidos_previstos_qs)),
        'ped_compras_atrasado': round(ped_compras_atrasado, 2),
        'ped_compras_previsto': round(ped_compras_previsto, 2),
        'pedidos_sem_data_count': 1 if ped_compras_sem_data > 0 else 0,
        'ped_compras_sem_data': round(ped_compras_sem_data, 2),
        'pedidos_pendentes_detalhes': [
            {
                'data': data.strftime('%Y-%m-%d'),
                'quantidade': round(float(qtd), 2),
                'status': 'ATRASADO' if data < hoje_ts else 'A_RECEBER',
            }
            for data, qtd in zip(
                pedidos_pendentes_qs['data_entrega'].tolist(),
                pedidos_pendentes_qs['qde_ped_corrigido'].tolist(),
            )
            if pd.notna(data)
        ],
        'datas_pedidos_pendentes': sorted({
            data.strftime('%Y-%m-%d')
            for data in pedidos_pendentes_qs['data_entrega'].tolist()
            if pd.notna(data)
        }),
        'chegada_planejada_compra': chegada_planejada_compra,
        'estoque_atual': round(estoque_projetado, 2),
        'estoque_fisico': round(estoque_fisico, 2),
        'estoque_projetado': round(estoque_projetado, 2),
        'ped_compras': round(ped_compras, 2),
        'data_estoque_minimo': row['data_estoque_minimo'].strftime('%Y-%m-%d')
            if pd.notna(_valor_escalar(row.get('data_estoque_minimo'))) else None,
    }
