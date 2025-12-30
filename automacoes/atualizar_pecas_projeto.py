"""
Automacao para sincronizar pecas/setores entre a planilha Google e o banco.

Fluxo resumido:
- Le a planilha "Lista Mestra" do arquivo "RQ EP-017-000 (Diretorio de Desenhos)".
- Normaliza codigo/descricao/setor e compara com a base local (cadastro_pecas_setor).
- Identifica combinacoes codigo+setor inexistentes e cria setor/peca/relacao faltante.
- Retorna a quantidade de registros adicionados quando ha diferenca.
"""

import pandas as pd
import os
import gspread
from google.oauth2 import service_account
from dotenv import load_dotenv
from pathlib import Path
import environ
import psycopg2
# import win32print

import warnings
warnings.filterwarnings("ignore")

# Carregar variáveis do arquivo .env
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

def _load_pecas_setor_from_db() -> pd.DataFrame:
    # Busca o cadastro atual de pecas/setor diretamente no banco.
    query = """
        select
            cp.codigo,
            cp.descricao,
            cs.nome as setor
        from apontamento_v2_testes.cadastro_pecas_setor cps
        left join apontamento_v2_testes.cadastro_pecas cp on cps.pecas_id = cp.id
        left join apontamento_v2_testes.cadastro_setor cs on cs.id = cps.setor_id
    """
    conn = psycopg2.connect(
        dbname=env("DB_NAME"),
        user=env("DB_USER"),
        password=env("DB_PASSWORD"),
        host=env("DB_HOST"),
        port=env("DB_PORT"),
    )
    try:
        return pd.read_sql_query(query, conn)
    finally:
        conn.close()

def get_data_from_sheets():
    """Carrega os dados da planilha e devolve codigo/descricao/setor."""

    google_credentials_json={
                "type":os.environ.get('type'),
                "project_id":os.environ.get('project_id'),
                "private_key":os.environ.get('private_key'),
                "private_key_id":os.environ.get('private_key_id'),
                "client_x509_cert_url":os.environ.get('client_x509_cert_url'),
                "client_email":os.environ.get('client_email'),
                "auth_uri":os.environ.get('auth_uri'),
                "auth_provider_x509_cert_url":os.environ.get('auth_provider_x509_cert_url'),
                "universe_domain":os.environ.get('universe_domain'),
                "client_id":os.environ.get('client_id'),
                "token_uri":os.environ.get('token_uri'),
            }

    if "\\n" in google_credentials_json["private_key"]:
        google_credentials_json["private_key"] = google_credentials_json["private_key"].replace("\\n", "\n")

    scope = ['https://www.googleapis.com/auth/spreadsheets',
            "https://www.googleapis.com/auth/drive"]

    credentials = service_account.Credentials.from_service_account_info(google_credentials_json, scopes=scope)

    sa = gspread.authorize(credentials)

    name_sheet = 'RQ EP-017-000 (Diretório de Desenhos)'

    worksheet1 = 'Lista Mestra'

    sh = sa.open(name_sheet)

    wks1 = sh.worksheet(worksheet1)

    list1 = wks1.get_all_values()

    # Transformando em dataframes
    base_pecas = pd.DataFrame(list1)
    base_pecas = base_pecas.iloc[6:]
    base_pecas = base_pecas[[0,1,6]]
    
    headers = ['codigo','descricao','setor']
    
    base_pecas.columns = headers
    base_pecas = base_pecas[base_pecas['codigo'] != '']
    base_pecas = base_pecas[base_pecas['setor'] != '']

    base_pecas['setor'] = base_pecas['setor'].str.lower()

    base_pecas = base_pecas.reset_index(drop=True)

    return base_pecas

def comparar_planilha_x_base():
    # Compara a planilha com a base e retorna apenas o que nao existe no banco.

    base_pecas = get_data_from_sheets()
    base_pecas = base_pecas[["codigo", "descricao", "setor"]].copy()
    base_pecas = base_pecas.fillna("").astype(str)
    for col in ["codigo", "descricao", "setor"]:
        base_pecas[col] = base_pecas[col].str.strip()

    pecas_db = _load_pecas_setor_from_db()
    pecas_db = pecas_db[["codigo", "setor"]].copy()
    pecas_db = pecas_db.fillna("").astype(str)
    for col in ["codigo", "setor"]:
        pecas_db[col] = pecas_db[col].str.strip()

    diff = base_pecas.merge(
        pecas_db,
        on=["codigo", "setor"],
        how="left",
        indicator=True,
    )

    return diff[diff["_merge"] == "left_only"][["codigo", "descricao", "setor"]]

def criar_registros_faltantes():
    # Cria setores, pecas e vinculos ausentes com base na diferenca encontrada.
    faltantes = comparar_planilha_x_base()
    if faltantes.empty:
        return 0

    conn = psycopg2.connect(
        dbname=env("DB_NAME"),
        user=env("DB_USER"),
        password=env("DB_PASSWORD"),
        host=env("DB_HOST"),
        port=env("DB_PORT"),
    )
    try:
        with conn:
            with conn.cursor() as cur:
                for _, row in faltantes.iterrows():
                    codigo = str(row["codigo"]).strip()
                    descricao = str(row["descricao"]).strip()
                    setor = str(row["setor"]).strip()

                    cur.execute(
                        "select id from apontamento_v2_testes.cadastro_setor where nome = %s",
                        (setor,),
                    )
                    setor_row = cur.fetchone()
                    if setor_row:
                        setor_id = setor_row[0]
                    else:
                        cur.execute(
                            "insert into apontamento_v2_testes.cadastro_setor (nome) values (%s) returning id",
                            (setor,),
                        )
                        setor_id = cur.fetchone()[0]

                    cur.execute(
                        "select id from apontamento_v2_testes.cadastro_pecas where codigo = %s",
                        (codigo,),
                    )
                    peca_row = cur.fetchone()
                    if peca_row:
                        peca_id = peca_row[0]
                    else:
                        cur.execute(
                            "insert into apontamento_v2_testes.cadastro_pecas (codigo, descricao) values (%s, %s) returning id",
                            (codigo, descricao),
                        )
                        peca_id = cur.fetchone()[0]

                    cur.execute(
                        """
                        select 1
                        from apontamento_v2_testes.cadastro_pecas_setor
                        where pecas_id = %s and setor_id = %s
                        """,
                        (peca_id, setor_id),
                    )
                    if not cur.fetchone():
                        cur.execute(
                            """
                            insert into apontamento_v2_testes.cadastro_pecas_setor (pecas_id, setor_id)
                            values (%s, %s)
                            """,
                            (peca_id, setor_id),
                        )
        return len(faltantes)
    finally:
        conn.close()
