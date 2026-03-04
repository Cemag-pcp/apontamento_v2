import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
import time
import os
import sys
from pathlib import Path
import django
import pandas as pd
from bs4 import BeautifulSoup
from tratamento_plan import tratar_df_final
from collections import defaultdict
import random
import re
from verificar_chrome import *
import logging

BASE_DIR = Path(__file__).resolve().parents[2]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "apontamento_v2.settings")  
django.setup()
logger = logging.getLogger(__name__)

def puxando_carretas():
    link = "https://cemag.innovaro.com.br/api/publica/v1/tabelas/listarProdutos"

    response = requests.get(link)

    if response.status_code == 200:
        dados = response.json()
    else:
        print('erro')

    # carretas_totais = []
    carretas_base_completo = []
    codigo_carretas = []
    carretas_com_cores = []
    codigo_cores = ['VJ', 'VM', 'AN', 'LC', 'LJ', 'AM','AV','CO']
    #adicionar tudo em uma lista menos os fora de linha
    #aplicar regex para achar codigo de cor e removê-lo


    for produto in dados['produtos']:
        # carretas_totais.append(str(produto.get('codigo')).strip())
        # if (produto.get('cor') == 'Laranja' or produto.get('cor') == '') and "fora de linha" not in produto.get('nome').lower():
        if "fora de linha" not in produto.get('nome').lower() and "fora de linha" not in produto.get('codigo').lower() and "+" not in produto.get('codigo'):
            cor_codigo_numerico = str(produto.get('codigo'))[-2:]

            try:
                cor_t1 = str(produto.get('codigo')).split(' ')[-1] # Cor no final do codigo
                cor_t2 = str(produto.get('codigo')).split(' ')[-2] # Cor na penultima posicao do codigo
                cor_t3 = str(produto.get('codigo')).split(' ')[-3] # Cor na antepenultima posicao do codigo
            except IndexError as e:
                cor_t2 = 'Não tem cor nessa posicao'
                cor_t3 = 'Não tem cor nessa posicao'

            if any(cor in codigo_cores for cor in [cor_t1, cor_t2, cor_t3, cor_codigo_numerico]):
                carretas_com_cores.append(str(produto.get('codigo')).strip())
            else:
                codigo_carretas.append(str(produto.get('codigo')).strip())
            carreta = {
                'chave':str(produto.get('chave')).strip(),
                'codigo': str(produto.get('codigo')).strip()
            }
            #adicionando em uma lista so de chaves
            
            #adicionando em uma lista de dicionario que contem chave e codigo
            carretas_base_completo.append(carreta)
            

    
    # print(len(carretas_base))
    print("codigos sem cor: ", len(codigo_carretas))
    print("codigos com cor: ",len(carretas_com_cores))
    return codigo_carretas,carretas_com_cores, carretas_base_completo

def rodar_automacao(carretas):
    # Inicializa o navegador
    lista_df = []
    total_itens = len(carretas)
    lote_atual = 0
    while len(carretas) > 0:
        lote_atual += 1
        print(f"[LOTE {lote_atual}] Itens restantes antes: {len(carretas)} de {total_itens}")
        try:
            driver = webdriver.Chrome()
        except:
            chrome_driver_path = verificar_chrome_driver()
            driver = webdriver.Chrome(chrome_driver_path)

        # Acessa o sistema
        driver.get("http://192.168.3.141/sistema")
        # driver.get("https://hcemag.innovaro.com.br/sistema")
        # driver.maximize_window() # Maximiza a tela
        time.sleep(2)

        # Faz login
        driver.find_element(By.ID, "username").send_keys("Luan Araujo")
        driver.find_element(By.ID, "password").send_keys("luanaraujo7")
        # driver.find_element(By.ID, "username").send_keys("ti.prod")
        # driver.find_element(By.ID, "password").send_keys("cem@1610")
        driver.find_element(By.ID, "submit-login").click()
        time.sleep(5)

        # fechar_todas_abas(driver)
        
        busca_carretas = carretas[:100]

        resultado = ";".join(busca_carretas)
        resultado += ";"
        
        # Navega nos menus
        driver.find_element(By.ID, "bt_1892603865").click()
        time.sleep(2)
        driver.find_element(By.XPATH, "//span[text()='Produção']").click()
        time.sleep(1)
        driver.find_element(By.XPATH, "//span[text()='Consultas gerenciais']").click()
        time.sleep(1)
        driver.find_element(By.XPATH, "//span[text()='Processos e composição de recursos com custos (BOM) CEMAG']").click()
        time.sleep(3)

        # input('tete')
        # Fechar menus
        driver.find_element(By.ID, "bt_1892603865").click()
        time.sleep(2)
        driver.find_element(By.XPATH, "//span[text()='Consultas gerenciais']").click()
        time.sleep(1)
        driver.find_element(By.XPATH, "//span[text()='Produção']").click()
        time.sleep(1)
        driver.find_element(By.ID, "bt_1892603865").click()
        time.sleep(2)


        # Acessa o iframe onde está o campo de pesquisa
        driver.switch_to.frame("inlineFrameTabId1")

        # Cola o valor no campo de recursos
        input_recurso = driver.find_element(By.NAME, 'recursos')
        input_recurso.clear()
        time.sleep(1)
        # input_recurso.send_keys("CBHM5000 GR SS RD P750(I) M17;CBHM5000 CA SC RD MM M17")
        input_recurso.send_keys(resultado)
        print("✅ Valor colado no campo de recursos.")
        time.sleep(3)

        # Sai do iframe para clicar no botão "Executar"
        driver.switch_to.default_content()

        # 🔁 Loop até a mensagem "Realizando a consulta..." aparecer
        print("⏳ Esperando a mensagem de execução aparecer...")

        cont_vezes_sem_aparecer_msg = 0
        max_tentativas_status = 5
        cont_msg_waitbox = 0
        while True:
            try:
                # Primeiro clique no botão "Executar"
                botao_executar = driver.find_element(By.XPATH, "//span[contains(., 'Executar')]")
                ActionChains(driver).move_to_element(botao_executar).click().perform()
                print("🔄 Primeiro clique no botão 'Executar'")
                time.sleep(10)

                while True:
                    # Verifica se a mensagem apareceu
                    mensagem = driver.find_elements(By.ID, "waitMessageBox")
                    if mensagem:
                        # print("✅ Mensagem detectada:", mensagem[0].text)
                        if cont_msg_waitbox == 0:
                            print(f"⚠️ Mensagem ainda está aparecendo: {mensagem[0].text}")
                        cont_msg_waitbox+=1
                    else:
                        print("✅ Mensagem desapareceu")
                        break
                    
                    time.sleep(2)

                # Acessa o iframe para clicar no botão "Todos"
                driver.switch_to.frame("inlineFrameTabId1")
                botao_todos = driver.find_element(By.XPATH, "//span[contains(., 'Todos')]")
                ActionChains(driver).move_to_element(botao_todos).click().perform()
                print("🟢 Botão 'Todos' clicado")
                time.sleep(1)
                driver.switch_to.default_content()

                # Segundo clique no botão "Executar"
                print('2 clique')
                botao_executar = driver.find_element(By.XPATH, "//span[contains(., 'Executar')]")
                ActionChains(driver).move_to_element(botao_executar).click().perform()
                print("✅ Segundo clique no botão 'Executar' enviado")

            except Exception as e:
                print(f"❌ Erro ao clicar: {e}")

            time.sleep(2)

            # Verifica se a mensagem apareceu
            if cont_vezes_sem_aparecer_msg < max_tentativas_status:
                cont_vezes_sem_aparecer_msg += 1
                mensagem = driver.find_elements(By.ID, "content_statusMessageBox")
                if mensagem:
                    print("✅ Mensagem detectada:", mensagem[0].text)
                    break

                print("⚠️ Mensagem ainda não apareceu. Tentando novamente...\n")
                time.sleep(2)
            else:
                driver.quit()
                raise RuntimeError(
                    "Mensagem 'content_statusMessageBox' nao apareceu apos "
                    f"{max_tentativas_status} tentativas."
                )

        cont = 0
        while True:
            # Verifica se a mensagem apareceu
            mensagem = driver.find_elements(By.ID, "content_statusMessageBox")
            if mensagem:
                # print("✅ Mensagem detectada:", mensagem[0].text)
                if cont == 0:
                    print(f"⚠️ Mensagem ainda está aparecendo: {mensagem[0].text}")
                cont+=1
            else:
                print("✅ Mensagem desapareceu")
                break
            
            time.sleep(2)

        cont_msg_progresso = 0
        while True:
            # Verifica se a mensagem apareceu
            mensagem = driver.find_elements(By.ID, "progressMessageBox")
            if mensagem:
                # print("✅ Mensagem detectada:", mensagem[0].text)
                if cont_msg_progresso == 0:
                    print(f"⚠️ Mensagem progresso: {mensagem[0].text}")
                cont_msg_progresso+=1
            else:
                print("✅ Mensagem desapareceu")
                break
            
            time.sleep(2)

        # # 🟢 Aguarda a tabela ser carregada após a mensagem
        # time.sleep(60)

        # Volta para o iframe para acessar a tabela
        driver.switch_to.frame("inlineFrameTabId1")

        # Extrai as linhas da tabela localizada em //*[@id="lid-0"]/tbody
        # linhas = driver.find_elements(By.XPATH, '//*[@id="lid-0"]/tbody/tr')

        

        # 1. Extrai o HTML da tabela de uma vez
        html_tabela = driver.find_element(By.XPATH, '//*[@id="lid-0"]/tbody').get_attribute("outerHTML")

        # 2. Processa com BeautifulSoup (muito mais rápido)
        soup = BeautifulSoup(html_tabela, 'html.parser')
        linhas = soup.find_all('tr')

        dados = []
        for linha in linhas:
            colunas = linha.find_all('td')
            if colunas:
                dados.append([coluna.get_text(strip=True) for coluna in colunas])

        print('Linhas extraídas:', len(dados))


        # Exibe os dados coletados
        print("📋 Dados extraídos")
        # for linha in dados:
        #     print(linha)

        #Retira os elementos já buscado
        carretas = carretas[100:]
        # Salva os dados em Excel
        df = pd.DataFrame(dados)
        lista_df.append(df)
        
        print("✅ Dados adicionados em uma lista de dataframes")
        print(f"[LOTE {lote_atual}] Itens restantes depois: {len(carretas)}")

        time.sleep(2)

        driver.quit()


        
    print('Finalização das explosões')
    # Concatena todos em um único DataFrame
    df_final = pd.concat(lista_df, ignore_index=True)
    df_final.columns = ['Recurso','Qtd.','TOTAL','Und.','Observação','Depósito Origem','Depósito Destino','Custo']
    
    # df_final.to_excel("resultado_innovaro.xlsx", index=False)

    print(f'Tamanho da lista de df: {len(lista_df)}')
    # print("✅ Dados salvos no arquivo 'resultado_innovaro.xlsx'")

    return df_final


def salvar_explosao_no_banco(df):
    """
    Aplica os tratamentos e sincroniza no banco via cadastro/utils/sync_carretas.py.
    """
    df_tratado = tratar_df_final(df)

    from cadastro.utils.sync_carretas import sync_carretas_from_df

    resultado_sync = sync_carretas_from_df(source_df=df_tratado, update_existing=False)
    print(f"Sincronizacao no banco concluida: {resultado_sync}")
    return resultado_sync


def carregar_itens_explodidos():

    from cadastro.models import ItensExplodidos

    itens = (
        ItensExplodidos.objects
        .values_list('produto', flat=True)
    )

    itens_limpos = [str(item).strip() for item in itens if str(item).strip()]
    print(f"ItensExplodidos carregados: {len(itens_limpos)}")
    return itens_limpos

def main():

    inicio = time.time()

    #Pegando as carretas atualizadas da api
    codigo_carretas, carretas_com_cores, carretas_base_completo = puxando_carretas()


    # Valores que já existem nos codigos sem cor
    resultado = {}
    for item in codigo_carretas:
        correspondentes = [c for c in carretas_com_cores if c.startswith(item)]
        if correspondentes:
            resultado[item] = correspondentes

    # Removendo os valores que já existem sem cor na lista de codigo_carretas
    
    for items in resultado.values():
        for i in items:
            try:
                carretas_com_cores.remove(i)
            except ValueError as e:
                print(f'Codigo {i} já removido')

    print(len(carretas_com_cores))
    # print(carretas_com_cores)

    codigo_cores = ['VJ', 'VM', 'AN', 'LC', 'LJ', 'AM','AV','CO']

    grupos = defaultdict(list)

    # Criando grupos com codigos com prefixo repetido
    # CBHM6000 CA SC T MM P700(R) M21: ['CBHM6000 CA SC T MM P700(R) M21 AV']
    # CBHM3500 SS RS BE MM M17: ['CBHM3500 SS RS BE MM M17 VM']
    # 623064: ['623064AV', '623064AN', '623064CO', '623064LC', '623064VJ', '623064VM']
    # 623063: ['623063AN', '623063AV', '623063CO', '623063LC', '623063VJ', '623063VM']
    # 623016: ['623016AV', '623016AN', '623016VJ']
    # 623019: ['623019AN', '623019LC', '623019VJ', '623019VM']
    # CBHM6000 CA SC RD P650(R) M21: ['CBHM6000 CA SC RD P650(R) M21 VJ']
    # CBHM6000 CA SC RD P750(R) M21: ['CBHM6000 CA SC RD P750(R) M21 AV']
    # CBH7 FO SC RD MM P700(R) M21: ['CBH7 FO SC RD MM P700(R) M21 VM', 'CBH7 FO SC RD MM P700(R) M21 AV']

    for item in carretas_com_cores:
        cor_encontrada = None
        for cor in codigo_cores:
            if f" {cor} " in f" {item} " or item.endswith(cor):
                cor_encontrada = cor
                # remover a cor do item para criar a base
                base = item.replace(cor, "").strip()
                grupos[base].append(item)
                break

        if not cor_encontrada:
            grupos["OUTROS"].append(item)

    # Sorteando valores por cada grupo(chave)
    sorteados = []
    for chave, itens in grupos.items():
        item_sorteado = random.choice(itens)
        sorteados.append(item_sorteado)

    lista_completa_produtos = codigo_carretas + sorteados

    lista_set = set(lista_completa_produtos)

    print(len(lista_set))

    #Elemento com PE
    lista_elementos_diferentes_pe = []

    for elemento in lista_set:
        if 'PE' in elemento:
            lista_elementos_diferentes_pe.append(elemento)

    
    lista_set_sem_pe = [x for x in lista_set if x not in lista_elementos_diferentes_pe]


    lista_pesquisa_bom_chaves = []
    lista_pesquisa_bom_chaves_pe = []
    # lista de codigos e chaves para adicionar ao dataframe
    lista_completa_chaves_codigos = []


    for item in carretas_base_completo:
        if item['codigo'] in lista_set_sem_pe:
            lista_pesquisa_bom_chaves.append(item['chave'])
        if item['codigo'] in lista_elementos_diferentes_pe:
            lista_pesquisa_bom_chaves_pe.append(item['chave'])
        if item['codigo'] in lista_set_sem_pe or item['codigo'] in lista_elementos_diferentes_pe:
            lista_completa_chaves_codigos.append({
                    'codigo': re.sub(r"(LC|LH|VM|VJ|AN|AV)$", "", item['codigo']).strip(), 
                    'chave': item['chave']
                })

    print(lista_completa_chaves_codigos)

    print(len(lista_pesquisa_bom_chaves))
    print(len(list(set(lista_pesquisa_bom_chaves))))

    itens_model = carregar_itens_explodidos()

    lista_sem_duplicadas_chaves_bom = list(
        set(lista_pesquisa_bom_chaves) | set(itens_model)
    )
    if not lista_sem_duplicadas_chaves_bom:
        print("Nenhum item encontrado na API nem em ItensExplodidos. Encerrando sem executar explosao.")
        return

    #verificar tudo oq em carretas_com_cores que tenha o mesmo sufixo de codigo_carretas

    #Explodindo as carretas de 100 em 100 e concatenando-as
    df_final = rodar_automacao(lista_sem_duplicadas_chaves_bom)

    fim = time.time()

    duracao_segundos = fim - inicio
    duracao_minutos = duracao_segundos / 60

    # Em vez de gerar arquivo auxiliar, aplica tratamento e salva direto no banco.
    salvar_explosao_no_banco(df_final)


    print(f"Tempo de execução da aplicação completa: {duracao_minutos:.2f} minutos")


if __name__ == "__main__":
    main()
