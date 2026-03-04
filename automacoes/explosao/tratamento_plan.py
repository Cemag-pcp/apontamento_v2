import pandas as pd
import re
# from conectar_planilha import conectar_planilha_apontamento


def contar_pontos_inicio(valor):
    if pd.isnull(valor):
        return 0
    # Remove espaços à esquerda
    texto = valor.lstrip()
    # Conta pontos seguidos no início (permitindo espaços entre os pontos)
    match = re.match(r"^((\.\s*)+)", texto)
    if match:
        return match.group(0).count(".")
    return 0

def limpar_espacos_unicode(texto):
    if pd.isnull(texto):
        return texto
    numero_pontos = contar_pontos_inicio(texto)
    # Remove apenas os pontos do início
    texto = texto.replace(".", "",numero_pontos)
    # Remove todos os espaços unicode no começo e fim
    return re.sub(r"^\s+|\s+$", "", texto)

def definir_primeiro_processo(texto):

    primeiro_processo_values = [
        ('S Mont Prod Especiais', 'MONTAR'),
        ('S Mont Conjuntos Carretas', 'MONTAR'),
        ('S Pintura', 'PINTAR'),
        ('S Expedição', 'EXPEDIR'),
        ('S C Serras', 'SERRAR'),
        ('S C Plasma', 'CORTAR'),
        ('S C Guilhotina', 'CORTAR'),
        ('S Corte Manual', 'CORTAR'),
        ('S C Prensas', 'CORTAR'),
        ('S C Laser', 'CORTAR'),
        ('S Usinagem', 'C USINAR'),
        ('S Mont Sistemas Carretas', 'MONTAR'),
        ('S Cx Acessórios - P Setor Cx Acessórios', 'CX'),
    ]

    if pd.isnull(texto):
        return None
    for chave, valor in primeiro_processo_values:
        if chave in texto:
            return valor
    return ''  # ou algum valor padrão, ex: ''

def classificar_codigo(codigo, valor_atual):
    codigo_str = str(codigo)
    if codigo_str.startswith('2'):
        return 'COMPONENTES'
    elif codigo_str.startswith('3'):
        return 'SECUNDÁRIOS'
    elif codigo_str.startswith('116'):
        return 'COMP. NAVAL'
    else:
        return valor_atual
    
def observacao_diferente(row):
    obs = row['observacao_proximo']
    descricao_2_depois = row['descricao_2_depois']
    observacoes = ['PINTAR','MONTAR','PINTURA','EXPEDIR']

    if obs not in observacoes:
        return descricao_2_depois
    else:
        return ''

def buscar_conjuntos(df):
    ultimos_por_ponto = {}  # dict para guardar a última linha vista com cada valor de 'NUMERO DE PONTOS' 
    resultados = []

    for idx, row in df.iterrows():
        pontos = row['NUMERO DE PONTOS']
        chave_alvo = pontos - 2

        # Busca no dicionário a última descrição que bate com pontos - 2
        if chave_alvo in ultimos_por_ponto:
            resultados.append(ultimos_por_ponto[chave_alvo])
        else:
            resultados.append("")

        # Atualiza o dicionário com a descrição atual
        ultimos_por_ponto[pontos] = row['DESCRIÇÃO'].strip() if isinstance(row['DESCRIÇÃO'], str) else ""

    # Retorna uma Series para adicionar ao DataFrame
    return pd.Series(resultados, index=df.index)

def verifica_descricao_3_depois(row, df):
    idx_atual = row.name  # pega o índice da linha atual
    
    # Tenta acessar a linha 3 abaixo
    idx_3_depois = idx_atual + 3
    
    if idx_3_depois < len(df):
        descricao_3 = df.loc[idx_3_depois, 'DESCRIÇÃO']
        
        if descricao_3 in [
            "S Estamparia - P Estamparia",
            "S Usinagem - P Setor Usinagem"
        ]:
            return descricao_3.strip()
    
    return ""

def definir_produto(row, df):
    idx = row.name  # índice da linha atual
    if row['NUMERO DE PONTOS'] == 0:
        return row['DESCRIÇÃO']
    else:
        if idx > 0:
            return df.loc[idx - 1, 'PRODUTO']
        else:
            return ""  # se for a primeira linha e pontos != 0

def definir_peso(row):
    obs = str(row['observacao_proximo']).strip().upper()
    observacoes = ['PINTAR','MONTAR','PINTURA','EXPEDIR']

    if obs not in observacoes and obs != '':
        return row['TOTAL_PROXIMO_2']
    
    return ""

def classificar_produto(row):
    processo = row['PRIMEIRO PROCESSO']
    b = str(row['CELULA 2']) if pd.notnull(row['CELULA 2']) else ''
    conjunto = str(row['CONJUNTO']) if pd.notnull(row['CONJUNTO']) else ''

    if processo in ('MONTAR', 'PINTAR'):
        return ''
    
    if b == 'LATERAL':
        if 'LATE' in conjunto:
            return 'LATERAL'
        if 'DIANT' in conjunto:
            return 'DIANTEIRA'
        if 'TRASE' in conjunto:
            return 'TRASEIRA'
    
    if b == 'IÇAMENTO' and '029989' in conjunto:
        return '5ª RODA'

    if b in ('IÇAMENTO', 'EIXO') and '025840' in conjunto:
        return '5ª RODA'
    
    if b in ('CILINDRO', 'CILINDRO 2'):
        return 'CILINDRO'
    
    if b == 'EIXO' and any(cod in conjunto for cod in ['031737', '031755', '031291', '031776']):
        return 'SUPORTE'
    
    if b != '':
        return b

    return ''

def extrair_carreta(produto):
    if pd.isna(produto) or produto.strip() == "":
        return ""
    
    try:
        # Pega o trecho antes do primeiro " - "
        prefixo = produto.split(" - ")[0].strip()

        # Remove sufixos como LC, LH, VM, etc. se estiverem no final
        resultado = re.sub(r"(LC|LH|VM|VJ|AN|AV)$", "", prefixo).strip()
        return resultado
    except:
        return ""

def concatenar_colunas(df, colunas, nome_nova_coluna, separador=' - ', ignorar_nulos=True):
    """
    Concatena colunas de um DataFrame e cria uma nova coluna com o resultado.

    Parâmetros:
    - df: DataFrame onde estão as colunas
    - colunas: lista com os nomes das colunas a serem concatenadas
    - nome_nova_coluna: nome da nova coluna que será criada
    - separador: string usada para separar os valores concatenados (padrão: ' - ')
    - ignorar_nulos: se True, trata NaN como string vazia (padrão: True)

    Retorna:
    - DataFrame com a nova coluna criada
    """
    if ignorar_nulos:
        df[nome_nova_coluna] = df[colunas].fillna('').astype(str).agg(separador.join, axis=1)
    else:
        df[nome_nova_coluna] = df[colunas].astype(str).agg(separador.join, axis=1)
    
    return df

def tratar_df_final(df):
    
    # df = pd.read_excel(r"C:\Users\TIDEV\planilha_atualizacao_carretas\resultado_innovaro.xlsx")
    # df = pd.read_excel(r"C:\Users\TIDEV\Documents\planilhas_auxiliares\resultado_innovaro_explosao.xlsx")
    # df = pd.read_csv(r"C:\Users\TIDEV\Desktop\teste-carreta.txt",sep='\t')

    # print(df.columns)
    

    df.columns = ['Recurso','Qtd.','TOTAL','Und.','Observação','Depósito Origem','Depósito Destino','Custo']

    print(df.columns)
    print(df.head())

    # input('teste')
    df['DESCRIÇÃO'] = df['Recurso'].apply(limpar_espacos_unicode)
    print("1")
    df['CODIGO'] = df['DESCRIÇÃO'].apply(lambda x: str(x).split(' ')[0] if pd.notnull(x) else '')
    print("2")
    df['NUMERO DE PONTOS'] = df['Recurso'].apply(contar_pontos_inicio)
    print("3")


    # verificando o valor de 'DESCRIÇÃO' da linha seguinte
    df['descricao_proxima'] = df['DESCRIÇÃO'].shift(-1)
    print("4")

    print("5")
    df['PRIMEIRO PROCESSO'] = df['descricao_proxima'].apply(definir_primeiro_processo)

    df['PRIMEIRO PROCESSO'] = [
        classificar_codigo(cod, atual)
        for cod, atual in zip(df['CODIGO'], df['PRIMEIRO PROCESSO'])
    ]
    print("6")

    # Verificando a coluna 'Observação' para definir
    df['observacao_proximo'] = df['Observação'].shift(-1)
    df['descricao_2_depois'] = df['DESCRIÇÃO'].shift(-2) 
    print("7")

    df['MATÉRIA PRIMA'] = df.apply(observacao_diferente,axis=1)
    print("8")
    df['CONJUNTO'] = buscar_conjuntos(df)
    print("9")

    df['descricao_3_depois'] = df['DESCRIÇÃO'].shift(-3)

    print("10")
    
    df['2 PROCESSO'] = df.apply(lambda row: verifica_descricao_3_depois(row, df), axis=1)

    print("11")

    df['PRODUTO'] = ""
    df['PRODUTO'] = df['DESCRIÇÃO'].where(df['NUMERO DE PONTOS'] == 0)
    df['PRODUTO'] = df['PRODUTO'].ffill()

    print("12")

    df['TOTAL_PROXIMO_2'] = df['TOTAL'].shift(-2)

    print("13")

    df['PESO'] = df.apply(definir_peso, axis=1)

    print("14")


    # Colocando valores NaN e None como string vazia
    df = df.fillna("")

    # Filtros de "PRIMEIRO PROCESSO" (coluna I)
    filtro_processo = (
        df['CODIGO'].str.startswith('116', na=False) |
        df['PRIMEIRO PROCESSO'].str.startswith(
            ('CORTAR', 'SERRAR', 'MONTAR', 'PINTAR', 'C USINAR', 'SECUNDÁRIOS', 'COMPONENTES', 'CX'),
            na=False
        )
    )

    # Filtros para excluir "CODIGO" (coluna L)
    filtro_excluir_codigo = ~(
        df['CODIGO'].str.startswith(('11', '13', '120', '126', 'S'), na=False)
        & ~df['CODIGO'].str.startswith('116', na=False)
    )

    # Aplicando os dois filtros
    df_filtrado = df[filtro_processo & filtro_excluir_codigo]

    df_filtrado['CODIGO_SPLIT_CONJUNTO'] = (
        df_filtrado['CONJUNTO']
        .astype(str)            # garante que é string
        .str.split('-', n=1)    # divide no primeiro hífen
        .str[0]                 # pega a parte antes do hífen
        .str.strip()            # remove espaços antes/depois
    )
    
    celulas_codigos_atualizados = merge_base_final_celulas

    # celulas_codigos_atualizados = conectar_planilha_apontamento()

    # merge_base_final_celulas = pd.merge(df_filtrado,celulas_codigos_atualizados,left_on='CODIGO_SPLIT_CONJUNTO',right_on='Código',how='left')

    merge_base_final_celulas['CELULA 1'] = merge_base_final_celulas['Célula']
    merge_base_final_celulas['CELULA 2'] = merge_base_final_celulas['CELULA 1']

    merge_base_final_celulas['CELULA 3'] = ''

    merge_base_final_celulas['CARRETA'] = merge_base_final_celulas['PRODUTO'].apply(extrair_carreta)

    merge_base_final_celulas['CELULA 3'] = merge_base_final_celulas.apply(classificar_produto, axis=1)

    merge_base_final_celulas = concatenar_colunas(merge_base_final_celulas, ['CODIGO', 'CARRETA'], 'peça + carreta')

    merge_base_final_celulas['CARRETA TRATADA'] = ""

    print("15")



    merge_base_final_celulas = merge_base_final_celulas[['CELULA 1','CELULA 2','CELULA 3','CODIGO','DESCRIÇÃO','MATÉRIA PRIMA','TOTAL','CONJUNTO','PRIMEIRO PROCESSO','2 PROCESSO','PESO','PRODUTO','CARRETA','CARRETA TRATADA','peça + carreta']]
    # merge_base_final_celulas = merge_base_final_celulas.astype(str)

    merge_base_final_celulas.to_excel(r"C:\Users\Engine\planilhas_auxiliares\carretas_final.xlsx", index=False)
    # merge_base_final_celulas.to_excel(r"C:\Users\TIDEV\Documents\planilhas_auxiliares\carretas_teste.xlsx", index=False)
    print(merge_base_final_celulas)

    return merge_base_final_celulas

if __name__ == "__main__":
    tratar_df_final()

#[213813 rows x 9 columns]