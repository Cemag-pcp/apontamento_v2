import gspread
import pandas as pd
from google.oauth2 import service_account
from django.core.cache import cache
from django.conf import settings

CACHE_TTL = 60 * 60  # 1 hora

_KEY_SIMULACAO = 'compras_simulacao_df'
_KEY_PEDIDOS = 'compras_pedidos_df'

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive',
]


def _get_client():
    creds_info = settings.GSHEETS_SERVICE_ACCOUNT_INFO
    credentials = service_account.Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    return gspread.authorize(credentials)


def _open_sheet():
    client = _get_client()
    nome = settings.GSHEETS_COMPRAS_SPREADSHEET_NAME
    return client.open(nome)


def get_simulacao_df() -> pd.DataFrame:
    """Retorna df da aba 'Simulação Pend. Vendas', com cache de 1h."""
    cached = cache.get(_KEY_SIMULACAO)
    if cached is not None:
        return cached

    sh = _open_sheet()
    wks = sh.worksheet('Simulação Pend. Vendas')
    cabecalho = wks.row_values(2)
    dados = wks.get()
    df = pd.DataFrame(dados)
    n_cols = len(df.columns)
    header = (cabecalho + [''] * n_cols)[:n_cols]
    df = df.set_axis(header, axis=1)
    df = df.iloc[2:].reset_index(drop=True)

    cache.set(_KEY_SIMULACAO, df, CACHE_TTL)
    return df


def get_pedidos_df() -> pd.DataFrame:
    """Retorna df da aba 'Dados Pedidos', com cache de 1h."""
    cached = cache.get(_KEY_PEDIDOS)
    if cached is not None:
        return cached

    sh = _open_sheet()
    wks = sh.worksheet('Dados Pedidos')
    cabecalho = wks.row_values(1)  # sem truncar — alinhamos depois
    dados = wks.get()
    df = pd.DataFrame(dados)

    n_cols = len(df.columns)
    # Garante que o header tenha exatamente n_cols itens (pad ou trunca)
    header = (cabecalho + [''] * n_cols)[:n_cols]
    df = df.set_axis(header, axis=1)
    df = df.iloc[1:].reset_index(drop=True)

    # Remove colunas completamente vazias (sem nome e sem dados)
    df = df.loc[:, ~((df.columns == '') & df.isnull().all())]

    cache.set(_KEY_PEDIDOS, df, CACHE_TTL)
    return df


def invalidate_cache():
    cache.delete(_KEY_SIMULACAO)
    cache.delete(_KEY_PEDIDOS)


_KEY_MAT_INDIRETO_SIMULACAO = 'compras_mat_indireto_simulacao_df'
_KEY_MAT_INDIRETO_PEDIDOS = 'compras_mat_indireto_pedidos_df'


def _open_sheet_by_id(sheet_id):
    client = _get_client()
    return client.open_by_key(sheet_id)


def get_mat_indireto_simulacao_df() -> pd.DataFrame:
    """Retorna df da aba 'Dados Simulação' da planilha de material indireto, com cache de 1h."""
    cached = cache.get(_KEY_MAT_INDIRETO_SIMULACAO)
    if cached is not None:
        return cached

    sh = _open_sheet_by_id(settings.GSHEETS_MAT_INDIRETO_SPREADSHEET_ID)
    wks = sh.worksheet('Dados Simulação')
    cabecalho = wks.row_values(1)
    dados = wks.get()
    df = pd.DataFrame(dados)
    n_cols = len(df.columns)
    header = (cabecalho + [''] * n_cols)[:n_cols]
    df = df.set_axis(header, axis=1)
    df = df.iloc[1:].reset_index(drop=True)

    cache.set(_KEY_MAT_INDIRETO_SIMULACAO, df, CACHE_TTL)
    return df


def get_mat_indireto_pedidos_df() -> pd.DataFrame:
    """Retorna df da aba 'Dados Pedidos' da planilha de material indireto, com cache de 1h."""
    cached = cache.get(_KEY_MAT_INDIRETO_PEDIDOS)
    if cached is not None:
        return cached

    sh = _open_sheet_by_id(settings.GSHEETS_MAT_INDIRETO_SPREADSHEET_ID)
    wks = sh.worksheet('Dados Pedidos')
    cabecalho = wks.row_values(1)
    dados = wks.get()
    df = pd.DataFrame(dados)

    n_cols = len(df.columns)
    header = (cabecalho + [''] * n_cols)[:n_cols]
    df = df.set_axis(header, axis=1)
    df = df.iloc[1:].reset_index(drop=True)

    df = df.loc[:, ~((df.columns == '') & df.isnull().all())]

    cache.set(_KEY_MAT_INDIRETO_PEDIDOS, df, CACHE_TTL)
    return df


def invalidate_mat_indireto_cache():
    cache.delete(_KEY_MAT_INDIRETO_SIMULACAO)
    cache.delete(_KEY_MAT_INDIRETO_PEDIDOS)
