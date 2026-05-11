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

    pedidos = df_pedidos[
        (df_pedidos['codigo'] == row['codigo']) &
        (df_pedidos['data_entrega'] <= data_limite_ts)
    ]
    if not pedidos.empty:
        return row['estoque_almox'] + pedidos['qde_ped_corrigido'].sum()
    return row['estoque_almox']


def processar_material_direto(simulacao_df_raw: pd.DataFrame, pedidos_df_raw: pd.DataFrame) -> dict:
    grupo_df = pd.read_csv(DATA_DIR / 'agrupamento_chapas.csv', sep=';')
    grupos_df = pd.read_csv(DATA_DIR / 'grupos_atualizados.csv', sep=',')
    grupos_df = grupos_df.rename(columns={'CÃ³digo': 'codigo'} if 'CÃ³digo' in grupos_df.columns else {})
    if 'codigo' not in grupos_df.columns:
        grupos_df = _rename_columns_by_aliases(grupos_df, {'codigo': ['Código', 'CÃ³digo', 'codigo']})
    grupos_df = grupos_df[['codigo', 'grupo']]

    simulacao_aliases = {
        'codigo': ['Código', 'CÃ³digo', 'codigo'],
        'descricao': ['Descrição', 'Descrição', 'DescriÃ§Ã£o', 'descricao'],
        'media_3m': ['Média 3M', 'MÃ©dia 3M', 'media 3m'],
        'cons_mes_anterior': ['Cons Mes Anterior', 'Cons Mes\nAnterior'],
        'simulado_pend_vendas': ['Simulado Pend Vendas', 'Simulado \nPend Vendas'],
        'estoque_almox': ['Est.Almox Central'],
        'est_producao': ['Est. Produção', 'Est. ProduÃ§Ã£o'],
        'estoque_total': ['Estoque Total'],
        'ped_compras_pendente': ['Ped.Compras Pendente', 'Ped.Compras\n Pendente'],
        'prev_consumo': ['Prev Con Mov Est(CMM)'],
        'simulacao': ['SIMULAÇÃO / (F.Pend/Fat.MM)', 'SIMULAÃ‡ÃƒO / (F.Pend/Fat.MM)', 'SIMULACAO / (F.Pend/Fat.MM)'],
        'dee_dias_em_est': ['DEE - Dias Em Est.'],
        'dias_ressupr': ['Dias Ressupr', 'Dias\nRessupr'],
        'dias_seg': ['Dias de seg.'],
        'estoque_minimo': ['Estoque Mínimo', 'Estoque MÃ­nimo', 'Estoque Minimo'],
    }
    pedidos_aliases = {
        'recurso': ['Recurso'],
        'data_entrega': ['Data Entrega'],
        'qde_ped': ['Qde Ped', 'Qdade Pedido'],
        'codigo': ['Código', 'CÃ³digo', 'codigo'],
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

    hoje = datetime.now().date()
    df['dias_ate_estoque_minimo'] = df.apply(
        lambda row: (row['estoque_almox'] - row['estoque_minimo']) / row['consumo_diario']
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
    df['dias_ate_estoque_minimo'] = df.apply(
        lambda row: (row['estoque_almox'] - row['estoque_minimo']) / row['consumo_diario']
        if row['consumo_diario'] > 0 else None,
        axis=1,
    )
    df['data_estoque_minimo'] = df['dias_ate_estoque_minimo'].apply(lambda dias: _adicionar_dias_uteis(hoje, dias))
    df['dias_ate_estoque_zero'] = df.apply(
        lambda row: row['estoque_almox'] / row['consumo_diario'] if row['consumo_diario'] > 0 else None,
        axis=1,
    )
    df['data_estoque_zero'] = df['dias_ate_estoque_zero'].apply(lambda dias: _adicionar_dias_uteis(hoje, dias))
    df['data_compra'] = df.apply(
        lambda row: _adicionar_dias_uteis(row['data_estoque_minimo'], (_valor_escalar(row.get('dias_ressupr'), 0) + 1) * -1)
        if pd.notna(_valor_escalar(row.get('data_estoque_minimo'))) and pd.notna(_valor_escalar(row.get('dias_ressupr'))) else None,
        axis=1,
    )
    df['dias_ate_data_compra'] = df.apply(
        lambda row: int(np.busday_count(hoje, row['data_compra'])) if pd.notna(_valor_escalar(row.get('data_compra'))) else None,
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

    if len(df) > 1:
        df = df.iloc[1:].reset_index(drop=True)

    materiais = []
    for _, row in df.iterrows():
        materiais.append({
            'codigo': str(_valor_escalar(row.get('codigo'), '')),
            'descricao': str(_valor_escalar(row.get('descricao'), '')),
            'grupo': str(_valor_escalar(row.get('grupo'), '')),
            'media_3m': round(float(_valor_escalar(row.get('media_3m'), 0) or 0), 2),
            'cons_mes_anterior': round(float(_valor_escalar(row.get('cons_mes_anterior'), 0) or 0), 2),
            'simulado_pend_vendas': round(float(_valor_escalar(row.get('simulado_pend_vendas'), 0) or 0), 2),
            'dee_dias_em_est': round(float(_valor_escalar(row.get('dee_dias_em_est'), 0) or 0), 1),
            'estoque_almox': round(float(_valor_escalar(row.get('estoque_almox'), 0) or 0), 2),
            'estoque_total': round(float(_valor_escalar(row.get('estoque_total'), 0) or 0), 2),
            'ped_compras': round(float(_valor_escalar(row.get('ped_compras_pendente'), 0) or 0), 2),
            'consumo_diario': round(float(_valor_escalar(row.get('consumo_diario'), 0) or 0), 3),
            'dias_ate_zero': round(float(row['dias_ate_estoque_zero']), 1)
            if pd.notna(_valor_escalar(row.get('dias_ate_estoque_zero'))) else 9999,
            'dias_ate_data_compra': int(row['dias_ate_data_compra'])
            if pd.notna(_valor_escalar(row.get('dias_ate_data_compra'))) else None,
            'data_compra': row['data_compra'].strftime('%d/%m/%Y')
            if pd.notna(_valor_escalar(row.get('data_compra'))) else None,
            'data_estoque_minimo': row['data_estoque_minimo'].strftime('%d/%m/%Y')
            if pd.notna(_valor_escalar(row.get('data_estoque_minimo'))) else None,
            'data_estoque_zero': row['data_estoque_zero'].strftime('%d/%m/%Y')
            if pd.notna(_valor_escalar(row.get('data_estoque_zero'))) else None,
            'dias_ressupr': round(float(_valor_escalar(row.get('dias_ressupr'), 0) or 0), 0),
            'estoque_minimo': round(float(_valor_escalar(row.get('estoque_minimo'), 0) or 0), 2),
            'flag_urgencia': _valor_escalar(row.get('flag_urgencia'), 'SEM_DADOS'),
            'tem_pedido': 'SIM' if float(_valor_escalar(row.get('ped_compras_pendente'), 0) or 0) > 0 else 'NÃO',
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


def get_projecao_para_material(codigo: str, df: pd.DataFrame, df_ped: pd.DataFrame) -> dict:
    linha = df[df['codigo'] == codigo]
    if linha.empty:
        return {'error': 'Material não encontrado'}

    row = linha.iloc[0]
    estoque_atual = float(_valor_escalar(row.get('estoque_almox'), 0) or 0)
    estoque_minimo = float(_valor_escalar(row.get('estoque_minimo'), 0) or 0)
    consumo_diario = float(_valor_escalar(row.get('consumo_diario'), 0) or 0)
    dias_ressupr = float(_valor_escalar(row.get('dias_ressupr'), 0) or 0)
    data_compra = _valor_escalar(row.get('data_compra'))

    datas = pd.date_range(start=datetime.now().date(), periods=121, freq='B')
    estoque_atual_dia = estoque_atual
    datas_grafico = []
    estoque_diario = []
    chegadas_previstas = []
    pedidos_pendentes_qs = df_ped[df_ped['codigo'] == codigo].copy()
    pedidos_pendentes_qs = pedidos_pendentes_qs[
        pd.notna(pedidos_pendentes_qs.get('data_entrega')) &
        (pedidos_pendentes_qs.get('qde_ped_corrigido', 0) > 0)
    ]

    for data in datas:
        estoque_atual_dia -= consumo_diario
        datas_grafico.append(data.strftime('%Y-%m-%d'))
        estoque_diario.append(round(estoque_atual_dia, 2))

        pedidos_do_dia = df_ped[(df_ped['codigo'] == codigo) & (df_ped['data_entrega'] == data)]
        if not pedidos_do_dia.empty and 'qde_ped_corrigido' in pedidos_do_dia.columns:
            quantidade_chegada = float(pedidos_do_dia['qde_ped_corrigido'].sum())
            estoque_atual_dia += quantidade_chegada
            datas_grafico.append(data.strftime('%Y-%m-%d'))
            estoque_diario.append(round(estoque_atual_dia, 2))
            chegadas_previstas.append({
                'data': data.strftime('%Y-%m-%d'),
                'quantidade': round(quantidade_chegada, 2),
                'estoque_apos_chegada': round(estoque_atual_dia, 2),
            })

    estoque_ideal = estoque_atual
    valor_ideal_compra = dias_ressupr * consumo_diario
    datas_ideal = []
    estoque_ideal_diario = []

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
        'chegadas_previstas': chegadas_previstas,
        'pedidos_pendentes_count': int(len(pedidos_pendentes_qs)),
        'datas_pedidos_pendentes': sorted({
            data.strftime('%Y-%m-%d')
            for data in pedidos_pendentes_qs['data_entrega'].tolist()
            if pd.notna(data)
        }),
        'chegada_planejada_compra': chegada_planejada_compra,
        'estoque_atual': round(estoque_atual, 2),
        'ped_compras': round(float(_valor_escalar(row.get('ped_compras_pendente'), 0) or 0), 2),
        'data_estoque_minimo': row['data_estoque_minimo'].strftime('%Y-%m-%d')
            if pd.notna(_valor_escalar(row.get('data_estoque_minimo'))) else None,
    }
