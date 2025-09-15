import gspread
from google.oauth2 import service_account
import pandas as pd
import os
from cachetools import LRUCache

cache = LRUCache(maxsize=100)

def format_private_key(key: str) -> str:
    # Render já passa com quebras de linha reais, então só faz replace se necessário
    if '\\n' in key:
        return key.replace('\\n', '\n')
    return key

def busca_saldo_recurso_central(codigos):
    #Recebe codigo do item nos parametros e retorna saldo de recurso ao vivo do almox central e a data de último saldo puxada da planilha

    #Transformação em tupla para verificar o cache
    codigos_tupla = tuple(codigos)
    if codigos_tupla in cache:
        print('Ta no cache')
        return cache[codigos_tupla]
    
    print('Não ta no cache')
    #Configuração inicial
    service_account_info = ["GOOGLE_SERVICE_ACCOUNT"]
    scope = ['https://www.googleapis.com/auth/spreadsheets',
            "https://www.googleapis.com/auth/drive"]
    
    # credentials_path = os.getenv('GOOGLE_SHEETS_CREDENTIALS_PATH')
    
    credentials_google = {
        "type": os.environ.get('type'),
        "project_id": os.environ.get('project_id'),
        "private_key": format_private_key(os.environ.get('private_key')),
        "client_email": os.environ.get('client_email'),
        "client_id": os.environ.get('client_id'),
        "auth_uri": os.environ.get('auth_uri'),
        "token_uri": os.environ.get('token_uri'),
        "auth_provider_x509_cert_url": os.environ.get('auth_provider_x509_cert_url'),
        "client_x509_cert_url": os.environ.get('client_x509_cert_url'),
        "universe_domain": os.environ.get('universe_domain')
    }
    
    credentials = service_account.Credentials.from_service_account_info(credentials_google, scopes=scope)

    #ID planilha
    sheet_id = '1u2Iza-ocp6ROUBXG9GpfHvEJwLHuW7F2uiO583qqLIE'

    #Abrindo a planilha pelo ID
    client = gspread.authorize(credentials)

    sh = client.open_by_key(sheet_id)
    #worksheet_name
    wks = sh.worksheet('saldo central')
    list1 = wks.get_all_values()
    
    itens = pd.DataFrame(list1)
    itens.columns = itens.iloc[0]
    itens = itens.drop(index=0)
    data_ultimo_saldo = itens.loc[itens.index[0],'data ultimo saldo']

    #filtrando pelo codigo
    itens = itens[itens['codigo'].isin(codigos)]
    if itens.empty:
        cache[codigos_tupla] = dict(),data_ultimo_saldo
        return dict(),data_ultimo_saldo
    else:
        saldo_dict = dict(zip(itens['codigo'], itens['Saldo']))
        # data_ultimo_saldo = itens.loc[itens.index[0],'data ultimo saldo']
        cache[codigos_tupla] = saldo_dict,data_ultimo_saldo
        return saldo_dict,data_ultimo_saldo
 

# lista = []
# print(busca_saldo_recurso_central(lista))
