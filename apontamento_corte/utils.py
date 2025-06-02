import pandas as pd
from datetime import date
import re
import numpy as np

def padronizar_medida_plasma(s):
    padroes = [1200, 1500, 2550]
    tolerancia = 100

    try:
        comprimento_str, largura_str = s.replace("mm", "").split("x")
        comprimento = comprimento_str.strip()#.replace(",", ".")
        largura = float(largura_str.strip().replace(",", "."))
    except Exception as e:
        print("Formato inválido:", e)
        return s
    
    # Verifica se a largura está dentro de ±100mm de algum padrão
    largura_padrao = largura
    for p in padroes:
        if abs(largura - p) <= tolerancia:
            largura_padrao = p
            break

    # Monta a string final (mantendo a ordem comprimento x largura)
    largura_str_ajustada = f"{largura_padrao:.2f}".replace(".", ",")
    resultado = f"{comprimento} x {largura_str_ajustada} mm"
    return resultado

def padronizar_medida_laser_2(s):
    padroes = [1200, 1500, 2550]
    tolerancia = 100

    try:
        largura_str, comprimento_str = s.replace("mm", "").split("×")
        comprimento = comprimento_str.strip()#.replace(",", ".")
        largura = float(largura_str.strip().replace(",", "."))
    except Exception as e:
        print("Formato inválido:", e)
        return s
    
    # Verifica se a largura está dentro de ±100mm de algum padrão
    largura_padrao = largura
    for p in padroes:
        if abs(largura - p) <= tolerancia:
            largura_padrao = p
            break

    # Monta a string final (mantendo a ordem comprimento x largura)
    largura_str_ajustada = f"{largura_padrao:.2f}".replace(".", ",")
    resultado = f"{comprimento} x {largura_str_ajustada} mm"
    return resultado

def tratamento_planilha_plasma(df):

    df = df.dropna(how='all')

    tamanho_chapa = df[df.columns[24:25]][9:10].values.tolist()[0][0].replace('×', 'x')
    qt_chapa = df[df.columns[2:3]][9:10]

    tamanho_chapa = padronizar_medida_plasma(tamanho_chapa)

    nome_coluna_1 = df[df.columns[0]].name
    aproveitamento_df = df['Unnamed: 22'][4:5]
    
    df = df[17:df.shape[0]-2]

    df = df[[nome_coluna_1, 'Unnamed: 19', 'Unnamed: 20',
             'Unnamed: 27', 'Unnamed: 32', 'Unnamed: 35']]
    df = df.dropna(how='all')

    espessura_df = df[df.columns[2:3]][2:3]

    df = df[[nome_coluna_1, 'Unnamed: 19',
             'Unnamed: 27', 'Unnamed: 32', 'Unnamed: 35']]

    df = df[2:]

    # quantidade de chapa

    qt_chapa_list = qt_chapa.values.tolist()

    # tamanho da chapa

    # tamanho_chapa_list = tamanho_chapa.values.tolist()

    # aproveitamento

    aproveitamento_list = aproveitamento_df.values.tolist()

    # espessura
    espessura_list = espessura_df.values.tolist()
    espessura_original = espessura_list[0][0]

    # limpa deixando so até até "mm"
    espessura = re.sub(r'(mm).*', r'\1', espessura_original, flags=re.IGNORECASE).strip()

    # cabeçalho da tabela

    cabecalho_df = pd.DataFrame({'Peças': ['Peças'], 'Quantidade': ['Quantidade'],
                                 'Tamanho chapa': ['Tamanho chapa'],
                                 'Peso': ['Peso'], 'Tempo': ['Tempo']})
    cabecalho_list = cabecalho_df.values.tolist()

    lista = df.values.tolist()

    # Criando colunas na tabela para guardar no bando de dados

    try:
        df = df.loc[:df[df['Unnamed: 19'].isnull()].index[0]-1]
    except:
        pass

    df['Unnamed: 19'] = df['Unnamed: 19'].astype(int)
    df['espessura'] = espessura
    df['aproveitamento'] = aproveitamento_list[0]
    df['tamanho da chapa'] = tamanho_chapa
    df['qt. chapas'] = int(qt_chapa_list[0][0])
    df['op'] = 1

    # reordenar colunas

    cols = df.columns.tolist()
    cols = cols[-1:] + cols[:-1]
    df = df[cols]

    df['data criada'] = date.today().strftime('%d/%m/%Y')
    df['Máquina'] = 'Plasma'
    df['op_espelho'] = ''
    # df['opp'] = 'opp'

    df = df.rename(columns={
        'Máquina': 'maquina',
        'ProNest 2021': 'peca',
        'Unnamed: 19': 'qtd_planejada',
        'Unnamed: 27': 'tamanho_peca',
        'Unnamed: 32': 'peso_peca',
        'Unnamed: 35': 'tempo_estimado_peca',
        'data criada': 'data_criada',
        'tamanho da chapa':'tamanho_da_chapa',
        'qt. chapas':"qt_chapa",

    })

    propriedades = [{
        'descricao_mp':espessura + " - " +tamanho_chapa,
        'tamanho':tamanho_chapa,
        'espessura':espessura,
        'quantidade':qt_chapa_list[0][0],
        'aproveitamento':aproveitamento_list[0],
    }]

    return df, propriedades

def tratamento_planilha_laser2(df,df2,df3):

    tamanho_chapa = df['Unnamed: 2'][6].replace(".",",").replace("*","×") + " mm"
    qt_chapa = df['Unnamed: 3'][6:len(df)-1].sum()
    aproveitamento_df = df['Unnamed: 5'][6:len(df)-1].mean()
    espessura_df = str(df['Unnamed: 2'][2]).replace(".",",") + " mm"

    # Encontrar a linha que contém "SlabSize(mm*mm):"
    index_tamanho_chapa_real = np.where(df3 == 'SlabSize(mm*mm):')[0][0]
    tamanho_chapa_real = df3['Unnamed: 4'][index_tamanho_chapa_real + 1]
    tamanho_chapa_real = tamanho_chapa_real.replace(".",",").replace("*","×") + " mm"
    tamanho_chapa_real = padronizar_medida_laser_2(tamanho_chapa_real)

    df2.columns = df2.iloc[0]
    df2 = df2[1:].reset_index(drop=True)
    
    # Define as possíveis variações
    colunas_ingles = ['Part name', 'Amount:', 'Part size (mm*mm)']
    colunas_portugues = ['Nome da peça', 'Quantia:', 'Tamanho da peça (mm*mm)']

    # Verifica quais colunas estão presentes no DataFrame
    if all(col in df2.columns for col in colunas_ingles):
        df2 = df2[colunas_ingles]
        df2.columns = ['peca', 'qtd_planejada', 'tamanho_peça']  # renomeia para padrão comum
    elif all(col in df2.columns for col in colunas_portugues):
        df2 = df2[colunas_portugues]
        df2.columns = ['peca', 'qtd_planejada', 'tamanho_peça']  # renomeia para padrão comum
    else:
        raise ValueError("Nenhuma das combinações de colunas esperadas (inglês ou português) foi encontrada.")

    # adiciona as colunas extras
    df2['espessura'] = espessura_df
    df2['aproveitamento'] = aproveitamento_df
    df2['tamanho da chapa'] = tamanho_chapa_real
    df2['qt. chapas'] = qt_chapa
    df2['Peso'] = ''
    df2['Tempo'] = ''

    # reordenar colunas com base nos nomes padronizados
    df2 = df2[['peca', 'qtd_planejada', 'espessura', 'aproveitamento', 'tamanho da chapa', 'qt. chapas']]

    # renomear final, se quiser nomes mais "seguros" para código
    df2.columns = ['peca', 'qtd_planejada', 'espessura', 'aproveitamento', 'tamanho_da_chapa', 'qt_chapas']

    df2['data criada'] = date.today().strftime('%d/%m/%Y')
    df2['Máquina'] = 'Laser JYF'
    df2['op_espelho'] = ''
    df2['opp'] = 'opp'

    propriedades = [{
        'descricao_mp':espessura_df + " - " + tamanho_chapa_real,
        'tamanho':tamanho_chapa_real,
        'espessura':espessura_df,
        'quantidade':qt_chapa,
        'aproveitamento':aproveitamento_df,
    }]

    return df2, propriedades

def tratamento_planilha_laser1(df,df2,comprimento,largura,espessura):

    df = df.dropna(how='all')            
    df2 = df2.dropna(how='all')            

    qt_chapas = df2[df2.columns[2:3]][3:4]
    qt_chapas_list = qt_chapas.values.tolist()[0][0]

    try:
        aprov1 = df2[df2.columns[4:5]][7:8] 
        aprov2 = df2[df2.columns[4:5]][9:10]
        aprov_list = str(1 - ( float(aprov2.values.tolist()[0][0]) / float(aprov1.values.tolist()[0][0]) ) )
    except:
        aprov1 = df2[df2.columns[2:3]][7:8] 
        aprov2 = df2[df2.columns[2:3]][9:10]
        aprov_list = str(1 - ( float(aprov2.values.tolist()[0][0]) / float(aprov1.values.tolist()[0][0]) ) ) 

    df = df[['Unnamed: 1','Unnamed: 4']]
    df = df.rename(columns={'Unnamed: 1':'Descrição',
                            'Unnamed: 4': 'Quantidade'})
    df = df.dropna(how='all')
    
    df = df[10:len(df)-1]
    
    df = df.reset_index(drop=True)
    
    # df['op'] = n_op

    cols = df.columns.tolist()
    cols = cols[-1:] + cols[:-1]
    df = df[cols]

    # df['tamanho da peça'] = ''
    # df['peso'] = ''
    # df['tempo'] = ''
    #espessura = '14'
    df['espessura'] = espessura
    df['aproveitamento'] = aprov_list
    #tamanho_chapa = '2800,00 x 1500,00 mm'
    df['tamanho_da_chapa'] = f"{comprimento} x {largura} mm "
    df['qt_chapas'] = qt_chapas_list
    # df['data criada'] = date.today().strftime('%d/%m/%Y')
    # df['Máquina'] = 'Laser'
    # df['op_espelho'] = ''
    # df['opp'] = 'opp'

    df.columns = ['qtd_planejada','peca','espessura','aproveitamento','tamanho_da_chapa','qt_chapas']

    propriedades = [{
        'descricao_mp': espessura + " - " + f"{comprimento} x {largura} mm ",
        'tamanho':f"{comprimento} x {largura} mm ",
        'espessura':espessura,
        'quantidade':qt_chapas_list,
        'aproveitamento':aprov_list,
    }]

    return df, propriedades
