import gspread
from google.oauth2 import service_account
import pandas as pd
from gspread_dataframe import set_with_dataframe
import random
import time

def set_with_dataframe_safe(worksheet, df, max_retries=6):
    for attempt in range(1, max_retries + 1):
        try:
            set_with_dataframe(worksheet, df)
            return
        except gspread.exceptions.APIError as e:
            msg = str(e)

            # só retry se for 503
            if "503" not in msg and "UNAVAILABLE" not in msg:
                raise

            wait = min(30, 2 ** attempt) + random.random()
            print(f"[Retry {attempt}] Sheets indisponível (503). Aguardando {wait:.1f}s...")
            time.sleep(wait)

    raise RuntimeError("Falha ao enviar DataFrame após várias tentativas.")

def configuracoes_iniciais():
    #Configuração inicial
    # service_account_info = ["GOOGLE_SERVICE_ACCOUNT"]
    scope = ['https://www.googleapis.com/auth/spreadsheets',
            "https://www.googleapis.com/auth/drive"]
    

    credentials = service_account.Credentials.from_service_account_file(r'C:\Users\Engine\robo_atualizacao_carretas\automacao-atualizacao-carretas\credentials.json', scopes=scope)
    # credentials = service_account.Credentials.from_service_account_file(r'C:\Users\TIDEV\planilha_atualizacao_carretas\credentials.json', scopes=scope)
    client = gspread.authorize(credentials)
    
    return client

def conectar_planilha_apontamento():
    """
    Retorna as celulas e codigos atualizados
    """

    #Configurações iniciais
    client = configuracoes_iniciais()

    #ID planilha apontamento
    sheet_id_apontamento = '1x26yfwoF7peeb59yJuJuxCQNlqjCjh65NYS1RIrC0Zc'

    #Abrindo a planilha pelo ID
    
    sh_apontamento_montagem = client.open_by_key(sheet_id_apontamento)

    wks_apontamento = sh_apontamento_montagem.worksheet('RQ PCP 002-000 (APONTAMENTO MONTAGEM)')
    list_montagem = wks_apontamento.get_all_values()

    #Tratando o df para pegar as colunas necessárias
    itens_montagem = pd.DataFrame(list_montagem)
    itens_montagem.columns = itens_montagem.iloc[4]
    itens_montagem = itens_montagem.drop(index=[0,1,2,3,4])

    itens_montagem = itens_montagem[['Código','Célula']]
    itens_montagem = itens_montagem[
        itens_montagem['Célula'].notna() & (itens_montagem['Célula'] != '') &
        itens_montagem['Código'].notna() & (itens_montagem['Código'] != '')
    ]
    df_celuas_codigo_atualizados = itens_montagem.groupby(['Código'],as_index=False).last().reset_index()

    return df_celuas_codigo_atualizados

def armazenar_base_atualizada_planilha(df):

    # df = pd.read_excel(r"C:\Users\TIDEV\Documents\planilhas_auxiliares\carretas_final.xlsx")

    client = configuracoes_iniciais()

    sheet_id = "1A67y-gk0P5qW_jDaxL4B9I-wP9wDM6mjJ91BMrzGWHw"

    sh_base_conjuntos = client.open_by_key(sheet_id)

    # Selecionar a aba
    worksheet = sh_base_conjuntos.worksheet("BASE ATUALIZADA")

    # Limpa a planilha Inteira
    worksheet.clear()
    df.to_csv("carga_base.csv")
    # Substituir tudo com o DataFrame
    set_with_dataframe_safe(worksheet, df)  # df é seu DataFrame pandas

    print("BASE ATUALIZADA COM SUCESSO!")

def armazenar_carretas_pe(df):

    # df = pd.read_excel(r"C:\Users\TIDEV\Documents\planilhas_auxiliares\carretas_final.xlsx")

    df = df.fillna("")

    client = configuracoes_iniciais()

    sheet_id = "1A67y-gk0P5qW_jDaxL4B9I-wP9wDM6mjJ91BMrzGWHw"

    sh_base_conjuntos = client.open_by_key(sheet_id)

    # Selecionar a aba
    worksheet = sh_base_conjuntos.worksheet("BASE ATUALIZADA")

    # Limpa a planilha Inteira
    # worksheet.clear()
    # Substituir tudo com o DataFrame
    # set_with_dataframe(worksheet, df)  # df é seu DataFrame pandas

    # 4. Encontrar a última linha preenchida
    ultima_linha = len(worksheet.get_all_values())

    # 5. Inserir DataFrame a partir da próxima linha
    worksheet.insert_rows(df.values.tolist(), row=ultima_linha+1)

    print("BASE ATUALIZADA COM SUCESSO!")

def puxar_pecas_aba():
    """Puxa a aba de BASE PEÇAS da planilha final e cola na aba BASE ATUALIZADA"""
    
    print("iniciando")

    client = configuracoes_iniciais()

    sheet_id = "1A67y-gk0P5qW_jDaxL4B9I-wP9wDM6mjJ91BMrzGWHw"

    sh_base_conjuntos = client.open_by_key(sheet_id)

    # ABA BASE ATUALIZADA
    worksheet_base_final = sh_base_conjuntos.worksheet("BASE ATUALIZADA")

    # 4. Encontrar a última linha preenchida
    ultima_linha_base_final = len(worksheet_base_final.col_values(4)) # pegando a coluna codigo

    # Selecionar a aba peças
    worksheet_pecas = sh_base_conjuntos.worksheet("BASE PEÇAS")

    df_pecas = pd.DataFrame(worksheet_pecas.get_all_values())

    df_pecas.columns = df_pecas.iloc[0]
    df_pecas = df_pecas.drop(index=0)
    df_pecas = df_pecas.fillna("")

    print(df_pecas)

    # Inserir DataFrame a partir da próxima linha
    worksheet_base_final.insert_rows(df_pecas.values.tolist(), row=ultima_linha_base_final+1)

    print("PEÇAS INSERIDAS COM SUCESSO!")

def base_felipe():
    """
        Compara o retorno da API com a base_felipe para ver oq ta faltando ser explodido
    """
    client = configuracoes_iniciais()

    #ID planilha
    sheet_id = '1n2J6n_VxOsVxY5ikjJeDGva7oHTUJOlzadFfUbJnaSE'

    sh = client.open_by_key(sheet_id)
    #worksheet_name
    wks = sh.worksheet('BASE')
    list1 = wks.get_all_values()

    itens = pd.DataFrame(list1)
    itens.columns = itens.iloc[0]
    itens = itens.drop(index=0) 

    itens['carreta'] = itens['carreta'].str.strip()
    itens = itens['carreta'].drop_duplicates()
    # print(itens)

    carretas = itens.to_list()

    print(len(carretas))

    return carretas
