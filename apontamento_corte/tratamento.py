import pandas as pd

df = pd.read_csv(r'C:\Users\pcp2\apontamento_usinagem\apontamento_corte\file_temp\criadas.csv')
df['status_atual'] = 'finalizada'
df['data_programacao'] = df['data abertura de op']
df['grupo_maquina'] = df['maquina'].apply(
    lambda x: 'plasma' if 'Plasma' in x 
    else 'laser_2' if 'Laser JFY' in x 
    else 'laser_1' if 'Laser' in x 
    else 'outro'
)
df['maquina'] = df['maquina'].apply(
    lambda x: 'plasma_1' if 'Plasma' in x 
    else 'laser_2' if 'Laser JFY' in x 
    else 'laser_1' if 'Laser' in x 
    else 'outro'
)

df['descricao_mp'] = df['Espessura'] + " - " + df['Tamanho da chapa']
df['Aproveitamento']=df['Aproveitamento'].astype(str)
df['Aproveitamento']=df['Aproveitamento'].apply(lambda x: str(x.replace('%','').replace(',',".")))
df['Aproveitamento']=df['Aproveitamento'].astype(float)/100

df['tipo_chapa'] = df['Espessura'].apply(
    lambda x: 'alta_resistencia' if 'A.R' in str(x) 
    else 'inox' if 'Inox' in str(x) 
    else 'anti_derrapante' if 'A.D' in str(x)
    else 'aco_carbono'
)

df = df[df['op_espelho'].isnull()]

df.rename(columns={"op":"ordem","data abertura de op":"data_criacao","Tamanho da chapa":"tamanho","Espessura":"espessura","qt. chapa":"quantidade","Aproveitamento":"aproveitamento"},inplace=True)

df['data_criacao'] = pd.to_datetime(df['data_criacao'], format='%d/%m/%Y', errors='coerce')
df['data_programacao'] = pd.to_datetime(df['data_programacao'], format='%d/%m/%Y', errors='coerce')
df['ordem'] = df['ordem'].apply(lambda x: str(x).replace(' JFY','').replace('L','').replace('.',''))
df = df.drop(df[df.ordem == '09l1'].index)
df = df.drop(df[df.ordem == '1577 7'].index)
df = df.drop(df[df.ordem == ' 1577 8'].index)
df = df.drop(df[df.ordem == '543 1'].index)
df = df.drop(df[df.ordem == '536 1'].index)
df = df.drop(df[df.ordem == '1229-'].index)
df = df.drop(df[df.ordem == '93l1'].index)
df = df.drop(df[df.ordem == 'None'].index)
df = df.drop(df[df.ordem == '53l1'].index)
df.drop_duplicates(subset='ordem', keep='first', inplace=True)

df['ordem'] = df['ordem'].astype(int)


df_carga_ordem = df[['ordem','data_criacao','grupo_maquina','maquina','status_atual','operador_final_matricula','data_programacao']]
df_carga_propriedade = df[['ordem', 'descricao_mp', 'tamanho', 'espessura', 'quantidade','aproveitamento','tipo_chapa',]]


import os
import django

# Configurações do Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "apontamento_v2.settings")  
django.setup()

# Agora já pode importar os modelos sem erro
from core.models import Ordem, Operador

# Exemplo: Listar ordens
print(Ordem.objects.all())


from core.models import Ordem, Operador  # Importe os modelos necessários
from django.utils.timezone import now  # Para trabalhar com data e hora

def importar_ordens(df_carga_ordem):
    for index, row in df_carga_ordem.iterrows():
        # Buscar operador_final pelo campo operador_final_matricula
        operador = None
        if pd.notna(row['operador_final_matricula']):
            operador = Operador.objects.filter(matricula=row['operador_final_matricula']).first()

        # Criando a instância do modelo
        ordem = Ordem(
            ordem=row['ordem'],
            data_criacao=row['data_criacao'] if pd.notna(row['data_criacao']) else now(),
            grupo_maquina=row['grupo_maquina'],
            maquina=row['maquina'],
            status_atual=row['status_atual'],
            operador_final=operador,
            data_programacao=row['data_programacao'] if pd.notna(row['data_programacao']) else None
        )

        # Salva a instância individualmente
        ordem.save()

        # Exibe no console a ordem inserida
        print(f"✅ Ordem Inserida: {ordem.ordem} | Máquina: {ordem.maquina} | Status: {ordem.status_atual}")

# Chamada da função com o DataFrame
importar_ordens(df_carga_ordem)