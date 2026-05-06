import gspread
import pandas as pd
from google.oauth2 import service_account
from django.core.cache import cache
from django.conf import settings

CACHE_TTL = 60 * 30  # 30 minutos
_KEY_ESTOQUE = 'compras_estoque_saldo_recurso_df'

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive',
]

ABA_SALDO_RECURSO = 'saldo de recurso'


def _get_client():
    creds_info = settings.GSHEETS_SERVICE_ACCOUNT_INFO
    credentials = service_account.Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    return gspread.authorize(credentials)


def _open_sheet():
    client = _get_client()
    spreadsheet_id = settings.GSHEETS_ESTOQUE_SPREADSHEET_ID
    return client.open_by_key(spreadsheet_id)


def get_saldo_recurso_df() -> pd.DataFrame:
    """Retorna df da aba 'saldo de recurso', com cache de 30min."""
    cached = cache.get(_KEY_ESTOQUE)
    if cached is not None:
        return cached

    sh = _open_sheet()
    wks = sh.worksheet(ABA_SALDO_RECURSO)
    dados = wks.get_all_values()

    if not dados:
        return pd.DataFrame()

    cabecalho = dados[0]
    linhas = dados[1:]
    df = pd.DataFrame(linhas, columns=cabecalho)

    # Remove colunas totalmente vazias
    df = df.loc[:, df.columns != '']
    df = df[df.columns[df.columns != '']]

    # Remove linhas onde todas as colunas são vazias
    df = df[~df.apply(lambda row: all(v == '' for v in row), axis=1)].reset_index(drop=True)

    cache.set(_KEY_ESTOQUE, df, CACHE_TTL)
    return df


def invalidate_cache():
    cache.delete(_KEY_ESTOQUE)


def get_estoque_data(busca: str = '', grupo: str = '') -> dict:
    """Retorna os dados de estoque processados para a API."""
    df = get_saldo_recurso_df()

    if df.empty:
        return {'itens': [], 'colunas': [], 'grupos': [], 'total': 0}

    colunas = list(df.columns)

    # Detecta coluna de grupo (primeira coluna de texto que agrupe os itens)
    col_grupo = None
    for candidato in ['Grupo', 'grupo', 'GRUPO', 'Tipo', 'tipo', 'TIPO', 'Categoria', 'categoria']:
        if candidato in colunas:
            col_grupo = candidato
            break

    # Detecta coluna de busca (código ou descrição)
    col_busca_candidatos = ['Código', 'codigo', 'CÓDIGO', 'Código do Item', 'Descrição', 'descricao', 'DESCRIÇÃO', 'Item']
    col_busca = [c for c in colunas if any(cb.lower() in c.lower() for cb in ['cod', 'descri', 'item', 'recurso', 'material'])]

    grupos = []
    if col_grupo:
        grupos = sorted(df[col_grupo].dropna().unique().tolist())
        grupos = [g for g in grupos if g]

    # Filtra por grupo
    if grupo and col_grupo and col_grupo in df.columns:
        df = df[df[col_grupo] == grupo]

    # Filtra por busca (procura em todas as colunas de texto)
    if busca:
        busca_lower = busca.lower()
        mask = df.apply(
            lambda row: any(busca_lower in str(v).lower() for v in row),
            axis=1
        )
        df = df[mask]

    itens = df.to_dict(orient='records')

    return {
        'itens': itens,
        'colunas': colunas,
        'grupos': grupos,
        'total': len(itens),
    }
