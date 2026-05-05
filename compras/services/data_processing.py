import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path

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
    """Adiciona pedidos de compra que chegam antes do estoque mínimo."""
    data_limite = row.get('data_estoque_minimo')
    if data_limite is None or pd.isna(data_limite):
        return row['Est.Almox Central']

    if isinstance(data_limite, datetime):
        data_limite = data_limite.date()

    try:
        data_limite_ts = pd.to_datetime(data_limite)
    except Exception:
        return row['Est.Almox Central']

    # Coluna de quantidade pode ter dois nomes
    try:
        qde_col = df_pedidos.loc[:, ~df_pedidos.columns.duplicated()]['Qde Ped']
    except KeyError:
        try:
            qde_col = df_pedidos.loc[:, ~df_pedidos.columns.duplicated()]['Qdade Pedido']
        except KeyError:
            return row['Est.Almox Central']

    qde_col = qde_col.apply(
        lambda x: float(str(x).replace('.', '').replace(',', '.'))
        if not pd.isna(x) and str(x).strip() != '' else 0
    )
    df_pedidos = df_pedidos.copy()
    df_pedidos['Qde Ped Corrigido'] = qde_col
    df_pedidos['Data Entrega'] = pd.to_datetime(df_pedidos['Data Entrega'], format='%d/%m/%Y', errors='coerce')

    pedidos = df_pedidos[
        (df_pedidos['Código'] == row['Código']) &
        (df_pedidos['Data Entrega'] <= data_limite_ts)
    ]
    if not pedidos.empty:
        return row['Est.Almox Central'] + pedidos['Qde Ped Corrigido'].sum()
    return row['Est.Almox Central']


def processar_material_direto(simulacao_df_raw: pd.DataFrame, pedidos_df_raw: pd.DataFrame) -> dict:
    """
    Porta fiel de main_suporte.py::tratamento_geral().
    Retorna dict com materiais processados, codigos e grupos para filtros.
    """
    grupo_df = pd.read_csv(DATA_DIR / 'agrupamento_chapas.csv', sep=';')
    grupos_df = pd.read_csv(DATA_DIR / 'grupos_atualizados.csv', sep=',')
    grupos_df = grupos_df[['Código', 'grupo']]

    # --- Processamento do df de simulação ---
    df = simulacao_df_raw.copy()

    # Criar linhas agrupadas de chapas
    duplicated = df[df['Código'].isin(grupo_df['codigo'])].copy()
    duplicated = duplicated.merge(grupo_df, left_on='Código', right_on='codigo')
    duplicated['Descrição'] = duplicated['grupo']
    duplicated['Código'] = duplicated['grupo']
    df = pd.concat([df, duplicated.drop(columns=['grupo', 'codigo'])]).reset_index(drop=True)

    # Tratar colunas numéricas
    colunas_numericas = [
        'Média 3M', 'Cons Mes\nAnterior', 'Simulado \nPend Vendas',
        'Est.Almox Central', 'Est. Produção', 'Estoque Total',
        'Ped.Compras\n Pendente', 'Prev Con Mov Est(CMM)',
        'SIMULAÇÃO / (F.Pend/Fat.MM)', 'DEE - Dias Em Est.',
        'Dias\nRessupr', 'Dias de seg.', 'Estoque Mínimo'
    ]
    for col in colunas_numericas:
        if col in df.columns:
            default = 10 if col == 'Dias de seg.' else 0
            df[col] = df[col].apply(lambda x: _tratar_valor_numerico(x, default))

    # Agrupar
    agg = {
        'Média 3M': 'mean', 'Cons Mes\nAnterior': 'mean',
        'Dias\nRessupr': 'max', 'Dias de seg.': 'max',
        'Estoque Mínimo': 'mean', 'Prev Con Mov Est(CMM)': 'mean',
        'SIMULAÇÃO / (F.Pend/Fat.MM)': 'max',
        'Simulado \nPend Vendas': 'sum', 'Est.Almox Central': 'sum',
        'Est. Produção': 'sum', 'Estoque Total': 'sum',
        'Ped.Compras\n Pendente': 'sum', 'DEE - Dias Em Est.': 'sum',
    }
    agg_valido = {k: v for k, v in agg.items() if k in df.columns}
    df = df.groupby(['Descrição', 'Código']).agg(agg_valido).reset_index()

    # Merge com grupos para filtro
    df = df.merge(grupos_df, on='Código', how='left').fillna({'grupo': 'Sem Grupo'})

    # --- Processamento de pedidos ---
    df_ped = pedidos_df_raw.copy()
    renomear_col = list(df_ped.columns)
    if len(renomear_col) > 12:
        renomear_col[12] = 'Recurso_1'
        df_ped.columns = renomear_col

    if 'Recurso' in df_ped.columns:
        df_ped['Código'] = df_ped['Recurso'].str.split(' - ').str[0]

    df_ped['Data Entrega'] = pd.to_datetime(df_ped['Data Entrega'], format='%d/%m/%Y', errors='coerce')
    df_ped['Data Entrega'] = df_ped['Data Entrega'].apply(
        lambda x: x - timedelta(days=1) if pd.notna(x) and x.weekday() == 5
        else (x + timedelta(days=1) if pd.notna(x) and x.weekday() == 6 else x)
    )

    # Duplicar pedidos de chapas agrupadas
    if 'Código' in df_ped.columns:
        dup_ped = df_ped[df_ped['Código'].isin(grupo_df['codigo'])].copy()
        dup_ped = dup_ped.merge(grupo_df, left_on='Código', right_on='codigo')
        if not dup_ped.empty:
            dup_ped['Recurso'] = dup_ped['grupo']
            dup_ped['Código'] = dup_ped['grupo']
            if 'Recurso' in dup_ped.columns:
                dup_ped['Recurso'] = dup_ped['Recurso'].apply(lambda x: f"{x} - {x}")
            df_ped = pd.concat([df_ped, dup_ped.drop(columns=['grupo', 'codigo'])]).reset_index(drop=True)
        if 'Recurso' in df_ped.columns:
            df_ped = df_ped[df_ped['Recurso'] != '']

    # --- Cálculos principais ---
    df['consumo_diario'] = df.apply(
        lambda row: max(
            row.get('SIMULAÇÃO / (F.Pend/Fat.MM)', 0) or 0,
            row.get('Prev Con Mov Est(CMM)', 0) or 0
        ) / 20,
        axis=1
    )

    hoje = datetime.now().date()

    df['dias_ate_estoque_minimo'] = df.apply(
        lambda row: (row['Est.Almox Central'] - row['Estoque Mínimo']) / row['consumo_diario']
        if row['consumo_diario'] > 0 else None,
        axis=1
    )
    df['data_estoque_minimo'] = df['dias_ate_estoque_minimo'].apply(
        lambda dias: _adicionar_dias_uteis(hoje, dias)
    )
    df['data_compra'] = df.apply(
        lambda row: _adicionar_dias_uteis(row['data_estoque_minimo'], (row['Dias\nRessupr']) * -1)
        if pd.notna(row.get('data_estoque_minimo')) and pd.notna(row.get('Dias\nRessupr')) else None,
        axis=1
    )

    # Ajusta estoque com pedidos pendentes antes do mínimo
    df['Est.Almox Central'] = df.apply(lambda row: _ajustar_estoque(row, df_ped), axis=1)

    # Recalcula com estoque ajustado
    df['dias_ate_estoque_minimo'] = df.apply(
        lambda row: (row['Est.Almox Central'] - row['Estoque Mínimo']) / row['consumo_diario']
        if row['consumo_diario'] > 0 else None,
        axis=1
    )
    df['data_estoque_minimo'] = df['dias_ate_estoque_minimo'].apply(
        lambda dias: _adicionar_dias_uteis(hoje, dias)
    )
    df['dias_ate_estoque_zero'] = df.apply(
        lambda row: row['Est.Almox Central'] / row['consumo_diario']
        if row['consumo_diario'] > 0 else None,
        axis=1
    )
    df['data_estoque_zero'] = df['dias_ate_estoque_zero'].apply(
        lambda dias: _adicionar_dias_uteis(hoje, dias)
    )
    df['data_compra'] = df.apply(
        lambda row: _adicionar_dias_uteis(row['data_estoque_minimo'], (row['Dias\nRessupr'] + 1) * -1)
        if pd.notna(row.get('data_estoque_minimo')) and pd.notna(row.get('Dias\nRessupr')) else None,
        axis=1
    )
    df['dias_ate_data_compra'] = df.apply(
        lambda row: int(np.busday_count(hoje, row['data_compra']))
        if pd.notna(row.get('data_compra')) else None,
        axis=1
    )

    # Flag urgência
    def _flag(dias):
        if dias is None or pd.isna(dias):
            return 'SEM_DADOS'
        if dias <= 0:
            return 'URGENTE'
        if dias <= 5:
            return 'PRAZO_CURTO'
        return 'PRAZO_OK'

    df['flag_urgencia'] = df['dias_ate_data_compra'].apply(_flag)

    # Remover primeira linha (cabeçalho duplicado da planilha)
    df = df.iloc[1:].reset_index(drop=True)

    # Montar lista de materiais para serialização JSON
    materiais = []
    for _, row in df.iterrows():
        materiais.append({
            'codigo': str(row.get('Código', '')),
            'descricao': str(row.get('Descrição', '')),
            'grupo': str(row.get('grupo', '')),
            'media_3m': round(float(row.get('Média 3M', 0) or 0), 2),
            'estoque_almox': round(float(row.get('Est.Almox Central', 0) or 0), 2),
            'estoque_total': round(float(row.get('Estoque Total', 0) or 0), 2),
            'ped_compras': round(float(row.get('Ped.Compras\n Pendente', 0) or 0), 2),
            'consumo_diario': round(float(row.get('consumo_diario', 0) or 0), 3),
            'dias_ate_zero': round(float(row['dias_ate_estoque_zero']), 1)
                if pd.notna(row.get('dias_ate_estoque_zero')) else 9999,
            'dias_ate_data_compra': int(row['dias_ate_data_compra'])
                if pd.notna(row.get('dias_ate_data_compra')) else None,
            'data_compra': row['data_compra'].strftime('%d/%m/%Y')
                if pd.notna(row.get('data_compra')) else None,
            'data_estoque_minimo': row['data_estoque_minimo'].strftime('%d/%m/%Y')
                if pd.notna(row.get('data_estoque_minimo')) else None,
            'data_estoque_zero': row['data_estoque_zero'].strftime('%d/%m/%Y')
                if pd.notna(row.get('data_estoque_zero')) else None,
            'dias_ressupr': round(float(row.get('Dias\nRessupr', 0) or 0), 0),
            'estoque_minimo': round(float(row.get('Estoque Mínimo', 0) or 0), 2),
            'flag_urgencia': row['flag_urgencia'],
            'tem_pedido': 'SIM' if float(row.get('Ped.Compras\n Pendente', 0) or 0) > 0 else 'NÃO',
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
    """
    Retorna dados para o gráfico de projeção de estoque de um material.
    df e df_ped já devem ser os DataFrames processados por processar_material_direto.
    """
    linha = df[df['Código'] == codigo]
    if linha.empty:
        return {'error': 'Material não encontrado'}

    row = linha.iloc[0]
    estoque_atual = float(row['Est.Almox Central'])
    estoque_minimo = float(row.get('Estoque Mínimo', 0) or 0)
    consumo_diario = float(row.get('consumo_diario', 0) or 0)
    dias_ressupr = float(row.get('Dias\nRessupr', 0) or 0)

    datas = pd.date_range(start=datetime.now().date(), periods=61, freq='B')

    # Série de consumo real (com pedidos)
    estoque_atual_dia = estoque_atual
    datas_grafico = []
    estoque_diario = []

    for data in datas:
        estoque_atual_dia -= consumo_diario
        datas_grafico.append(data.strftime('%Y-%m-%d'))
        estoque_diario.append(round(estoque_atual_dia, 2))

        pedidos_do_dia = df_ped[
            (df_ped['Código'] == codigo) &
            (df_ped['Data Entrega'] == data)
        ]
        if not pedidos_do_dia.empty and 'Qde Ped Corrigido' in pedidos_do_dia.columns:
            estoque_atual_dia += pedidos_do_dia['Qde Ped Corrigido'].sum()
            datas_grafico.append(data.strftime('%Y-%m-%d'))
            estoque_diario.append(round(estoque_atual_dia, 2))

    # Série ideal (serrote)
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

    return {
        'codigo': codigo,
        'descricao': str(row.get('Descrição', '')),
        'estoque_minimo': estoque_minimo,
        'consumo_diario': round(consumo_diario, 3),
        'dias_ressupr': dias_ressupr,
        'dias_ate_data_compra': int(row['dias_ate_data_compra'])
            if pd.notna(row.get('dias_ate_data_compra')) else None,
        'data_compra': row['data_compra'].strftime('%d/%m/%Y')
            if pd.notna(row.get('data_compra')) else None,
        'data_estoque_zero': row['data_estoque_zero'].strftime('%d/%m/%Y')
            if pd.notna(row.get('data_estoque_zero')) else None,
        'flag_urgencia': str(row.get('flag_urgencia', '')),
        'serie_real': {'datas': datas_grafico, 'estoques': estoque_diario},
        'serie_ideal': {'datas': datas_ideal, 'estoques': estoque_ideal_diario},
        'estoque_atual': round(estoque_atual, 2),
        'ped_compras': round(float(row.get('Ped.Compras\n Pendente', 0) or 0), 2),
    }
