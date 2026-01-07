import redis, json, uuid
from datetime import datetime
from google.oauth2 import service_account
from dotenv import load_dotenv
import gspread
import os
import pandas as pd
import re

# ip 226

def chamar_impressora(cliente, data_carga, nome_pacote, obs):

    # data_formatada = datetime.strptime(data_carga, "%Y-%m-%d").strftime("%d/%m/%Y")

    # Monta o ZPL final
    zpl = f"""
^XA
^CI28
^PW799
^LL420
^LT0
^LH0,0

^FX ===================== CABEÇALHO =====================
^FO50,30
^A0N,40,40
^FB700,1,0,C,0
^FD{cliente}^FS

^FO50,80
^A0N,30,30
^FB700,1,0,C,0
^FDData da Carga: {data_carga}^FS

^FX Linha separadora
^FO40,120
^GB720,3,3^FS

^FX ===================== PACOTE =====================
^FO50,160
^AE,40,30
^FB700,1,0,C,0
^FD{nome_pacote}^FS

^FX ===================== OBSERVAÇÕES =====================
^FO50,220
^A0N,28,28
^FDObservações:^FS

^FO50,260
^A0N,24,24
^FB700,4,10,L,0
^FD{obs}^FS

^XZ

    """

    r = redis.from_url("redis://default:AWbmAbD4G2CfZPb3RxwuWQ4RfY7JOmxS@redis-19210.c262.us-east-1-3.ec2.redns.redis-cloud.com:19210")

    job_id = str(uuid.uuid4())
    payload = {"job_id": job_id, "zpl": zpl}
    r.rpush("print-zebra", json.dumps(payload))
    print(job_id)

def chamar_impressora_qrcode():

    # Monta o ZPL final
    zpl = f"""


^XA
^MMT
^PW799
^LL0400
^LS0
^PR1,1,1
~SD14
^FT40,350^BQN,2,7
^FDLA,https://apontamento-v2-testes.onrender.com/montagem/apontamento-qrcode/?ordem_id=36680&selecao_setor=pendente^FS
^PQ1,0,1,Y
^XZ
    """

    r = redis.from_url("redis://default:AWbmAbD4G2CfZPb3RxwuWQ4RfY7JOmxS@redis-19210.c262.us-east-1-3.ec2.redns.redis-cloud.com:19210")

    job_id = str(uuid.uuid4())
    payload = {"job_id": job_id, "zpl": zpl}
    r.rpush("print-zebra", json.dumps(payload))
    print(job_id)

def buscar_conjuntos_carreta(carretas):

    """
    Consulta a lista de carretas no google sheets a planilha:
    https://docs.google.com/spreadsheets/d/1A67y-gk0P5qW_jDaxL4B9I-wP9wDM6mjJ91BMrzGWHw/edit?gid=733473611#gid=733473611
    na aba de "BASE ATUALIZADA" e retorna todos os seus conjuntos que são expedidos.
    Formato de dataframe contendo colunas: CODIGO_BASE | DESCRICAO_LIMPA | TOTAL

    CARRETA | CODIGO_BASE | DESCRICAO_LIMPA       | TOTAL
    CBH5..  |  030383     | MACACO COMPLETO CINZA | 1.0

    :param: carretas -> List
    :return: df -> DataFrame
    """
    
    ### Configurações de acesso a api do google sheets ###

    load_dotenv()

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

    name_sheet = 'BASE GERAL'

    worksheet1 = 'BASE ATUALIZADA'

    sh = sa.open(name_sheet)

    """Carrega os dados das planilhas e retorna como DataFrames."""
    wks1 = sh.worksheet(worksheet1)

    list1 = wks1.get_all_records()

    ### TRATAMENTO DAS PLANILHAS ###
    base_conjuntos = pd.DataFrame(list1)

    # Filtrar apenas pelo PRIMEIRO PROCESSO que interessa
    base_conjuntos = base_conjuntos[base_conjuntos['PRIMEIRO PROCESSO'] == 'PINTAR']

    # mask = (
    #     base_conjuntos['CARRETA']
    #     .astype('string')
    #     .str.contains(str(carretas), case=False, regex=False, na=False)
    # )
    # base_conjuntos = base_conjuntos[mask]

    base_conjuntos = base_conjuntos[ base_conjuntos['CARRETA'].isin(carretas) ]

    # escolhendo colunas
    base_conjuntos = base_conjuntos[['CARRETA','CODIGO','DESCRIÇÃO','TOTAL']]
    base_conjuntos['TOTAL'] = base_conjuntos['TOTAL'] / 1000

    # tratando codigo (retirando cor do código)

    # Código base sem a sigla
    base_conjuntos['CODIGO_BASE'] = base_conjuntos['CODIGO'].str.replace(
        r'(?<=\d)[A-Z]{2}$', '', regex=True
    )

    base_conjuntos['DESCRICAO_LIMPA'] = (
    base_conjuntos['DESCRIÇÃO']
      .astype('string')
      # remove "QUALQUER_COISA - " do começo (geralmente o código + hífen)
      .str.replace(r'^\s*[^-]+-\s*', '', regex=True)
      # normaliza espaços
      .str.replace(r'\s+', ' ', regex=True)
      .str.strip()
    )
    
    base_conjuntos = base_conjuntos[['CARRETA','CODIGO_BASE','DESCRICAO_LIMPA','TOTAL']]

    return base_conjuntos

def limpar_cor(nome_carreta: str) -> str:
    """
    Remove a sigla de cor do final do nome da carreta SOMENTE se ela estiver
    em SIGLA_POR_COR (ex.: 'AV', 'LC', ...). Aceita com/sem espaço antes.
    """
    SIGLA_POR_COR = {
        'amarelo': 'AV',
        'laranja': 'LC',
        'cinza': 'CO',
        'azul': 'AZ',
        'verde': 'VD',
        'preto': 'PR',
        'branco': 'BC',
        'vermelho': 'VM',
        'cinza escuro': 'CE',
        # adicione outras se precisar...
    }

    if not nome_carreta:
        return nome_carreta

    siglas = {v for v in SIGLA_POR_COR.values() if v}
    if not siglas:
        return nome_carreta.strip()

    # monta regex: (espaços?) (uma das siglas) no final
    pattern = r'(?:\s+)?(?:' + '|'.join(re.escape(s) for s in siglas) + r')$'

    # remove uma vez se casar; case-insensitive
    return re.sub(pattern, '', nome_carreta.strip(), flags=re.IGNORECASE)

def chamar_impressora_qrcode():

    # Monta o ZPL final
    zpl = f"""


^XA
^MMT
^PW799
^LL0400
^LS0
^PR1,1,1
~SD14
^FT40,350^BQN,2,7
^FDLA,https://apontamento-v2-testes.onrender.com/montagem/apontamento-qrcode/?ordem_id=36680&selecao_setor=pendente^FS
^PQ1,0,1,Y
^XZ
    """

    r = redis.from_url("redis://default:AWbmAbD4G2CfZPb3RxwuWQ4RfY7JOmxS@redis-19210.c262.us-east-1-3.ec2.redns.redis-cloud.com:19210")

    job_id = str(uuid.uuid4())
    payload = {"job_id": job_id, "zpl": zpl}
    r.rpush("print-zebra", json.dumps(payload))
    print(job_id)

def buscar_conjuntos_carreta(carretas):

    """
    Consulta a lista de carretas no google sheets a planilha:
    https://docs.google.com/spreadsheets/d/1A67y-gk0P5qW_jDaxL4B9I-wP9wDM6mjJ91BMrzGWHw/edit?gid=733473611#gid=733473611
    na aba de "BASE ATUALIZADA" e retorna todos os seus conjuntos que são expedidos.
    Formato de dataframe contendo colunas: CODIGO_BASE | DESCRICAO_LIMPA | TOTAL

    CARRETA | CODIGO_BASE | DESCRICAO_LIMPA       | TOTAL
    CBH5..  |  030383     | MACACO COMPLETO CINZA | 1.0

    :param: carretas -> List
    :return: df -> DataFrame
    """
    
    ### Configurações de acesso a api do google sheets ###

    load_dotenv()

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

    name_sheet = 'BASE GERAL'

    worksheet1 = 'BASE ATUALIZADA'

    sh = sa.open(name_sheet)

    """Carrega os dados das planilhas e retorna como DataFrames."""
    wks1 = sh.worksheet(worksheet1)

    list1 = wks1.get_all_records()

    ### TRATAMENTO DAS PLANILHAS ###
    base_conjuntos = pd.DataFrame(list1)

    # Filtrar apenas pelo PRIMEIRO PROCESSO que interessa
    base_conjuntos = base_conjuntos[base_conjuntos['PRIMEIRO PROCESSO'] == 'PINTAR']

    # mask = (
    #     base_conjuntos['CARRETA']
    #     .astype('string')
    #     .str.contains(str(carretas), case=False, regex=False, na=False)
    # )
    # base_conjuntos = base_conjuntos[mask]

    base_conjuntos = base_conjuntos[ base_conjuntos['CARRETA'].isin(carretas) ]

    # escolhendo colunas
    base_conjuntos = base_conjuntos[['CARRETA','CODIGO','DESCRIÇÃO','TOTAL']]
    base_conjuntos['TOTAL'] = base_conjuntos['TOTAL'] / 1000

    # tratando codigo (retirando cor do código)

    # Código base sem a sigla
    base_conjuntos['CODIGO_BASE'] = base_conjuntos['CODIGO'].str.replace(
        r'(?<=\d)[A-Z]{2}$', '', regex=True
    )

    base_conjuntos['DESCRICAO_LIMPA'] = (
    base_conjuntos['DESCRIÇÃO']
      .astype('string')
      # remove "QUALQUER_COISA - " do começo (geralmente o código + hífen)
      .str.replace(r'^\s*[^-]+-\s*', '', regex=True)
      # normaliza espaços
      .str.replace(r'\s+', ' ', regex=True)
      .str.strip()
    )
    
    base_conjuntos = base_conjuntos[['CARRETA','CODIGO_BASE','DESCRICAO_LIMPA','TOTAL']]

    return base_conjuntos

def limpar_cor(nome_carreta: str) -> str:
    """
    Remove a sigla de cor do final do nome da carreta SOMENTE se ela estiver
    em SIGLA_POR_COR (ex.: 'AV', 'LC', ...). Aceita com/sem espaço antes.
    """
    SIGLA_POR_COR = {
        'amarelo': 'AV',
        'laranja': 'LC',
        'cinza': 'CO',
        'azul': 'AZ',
        'verde': 'VD',
        'preto': 'PR',
        'branco': 'BC',
        'vermelho': 'VM',
        'cinza escuro': 'CE',
        # adicione outras se precisar...
    }

    if not nome_carreta:
        return nome_carreta

    siglas = {v for v in SIGLA_POR_COR.values() if v}
    if not siglas:
        return nome_carreta.strip()

    # monta regex: (espaços?) (uma das siglas) no final
    pattern = r'(?:\s+)?(?:' + '|'.join(re.escape(s) for s in siglas) + r')$'

    # remove uma vez se casar; case-insensitive
    return re.sub(pattern, '', nome_carreta.strip(), flags=re.IGNORECASE)

import json, uuid, time, redis


def chamar_impressora_pecas_montagem(zpl):
    
    r = redis.from_url("redis://default:AWbmAbD4G2CfZPb3RxwuWQ4RfY7JOmxS@redis-19210.c262.us-east-1-3.ec2.redns.redis-cloud.com:19210")
    job_id = str(uuid.uuid4())
    payload = {"job_id": job_id, "zpl": zpl}
    r.rpush("print-zebra", json.dumps(payload))

    
    print(job_id)

def chamar_impressora_pecas_montagem_2(zpl, itens_agrupados):
    
    r = redis.from_url("redis://default:AWbmAbD4G2CfZPb3RxwuWQ4RfY7JOmxS@redis-19210.c262.us-east-1-3.ec2.redns.redis-cloud.com:19210")
    job_id = str(uuid.uuid4())
    
    payload = {"job_id": job_id, "zpl": zpl}
    
    r.rpush("print-zebra", json.dumps(payload))

    
    print(job_id)