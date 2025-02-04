import pandas as pd
import os
import django

from django.utils.timezone import now  # Para trabalhar com data e hora

# Configurações do Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "apontamento_v2.settings")  
django.setup()

from core.models import Ordem, Operador, PropriedadesOrdem
from apontamento_corte.models import PecasOrdem

df = pd.read_csv(r'C:\Users\pcp2\apontamento_usinagem\apontamento_corte\file_temp\criadas.csv')
df['status_atual'] = 'finalizada'
df['data_programacao'] = df['data abertura de op']
df['grupo_maquina'] = df['maquina'].apply(
    lambda x: 'plasma' if 'Plasma' in x 
    else 'laser_2' if 'Laser JYF' in x 
    else 'laser_1' if 'Laser' in x 
    else 'outro'
)
df['maquina'] = df['maquina'].apply(
    lambda x: 'plasma_1' if 'Plasma' in x 
    else 'laser_2' if 'Laser JYF' in x 
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

df['ordem'] = df['ordem'].astype(int)

df_carga_ordem = df[['ordem','data_criacao','grupo_maquina','maquina','status_atual','operador_final_matricula','data_programacao']]
df_carga_propriedade = df[['ordem','grupo_maquina', 'descricao_mp', 'tamanho', 'espessura', 'quantidade','aproveitamento','tipo_chapa',]]
df_carga_pecas = df[['ordem','Peças','Quantidade','grupo_maquina']] 

df_carga_ordem.drop_duplicates(subset=['ordem'], keep='first', inplace=True)
df_carga_propriedade.drop_duplicates(subset=['ordem'], keep='first', inplace=True)

def importar_ordens(df_carga_ordem):
    for _, row in df_carga_ordem.iterrows():
        try:
            # Buscar operador_final pelo campo operador_final_matricula
            operador = None
            if pd.notna(row.get('operador_final_matricula')):  # Usa .get() para evitar KeyError
                operador = Operador.objects.filter(matricula=row['operador_final_matricula']).first()

            # Criar a ordem no banco de dados
            Ordem.objects.create(
                ordem=row.get('ordem'),
                data_criacao=row['data_criacao'] if pd.notna(row.get('data_criacao')) else now(),
                grupo_maquina=row['grupo_maquina'],
                maquina=row['grupo_maquina'],
                status_atual=row.get('status_atual', ''),
                operador_final=operador,
                data_programacao=row['data_programacao'] if pd.notna(row.get('data_programacao')) else None
            )

            print(f"✅ Ordem {row.get('ordem', 'N/A')} importada com sucesso.")

        except Exception as e:
            print(f"❌ Erro ao importar ordem {row.get('ordem', 'N/A')}: {e}")

def importar_propriedades(df_carga_propriedade):
    for _, row in df_carga_propriedade.iterrows():
        try:
            ordem = Ordem.objects.get(ordem=row['ordem'], grupo_maquina=row['grupo_maquina'])

            # Criando e salvando cada instância separadamente
            PropriedadesOrdem.objects.create(
                ordem=ordem,
                descricao_mp=row['descricao_mp'],
                tamanho=row['tamanho'],
                espessura=row['espessura'],
                quantidade=float(row['quantidade'].replace(",",'.')),
                aproveitamento=str(row['aproveitamento'])[:6],
                tipo_chapa=row['tipo_chapa']
            )

        except Ordem.DoesNotExist:
            print(f"Erro: Ordem {row['ordem']} não encontrada. Linha ignorada.")
        except Exception as e:
            print(f"Erro ao inserir a linha {row.to_dict()}: {e}")

def importar_pecas(df_carga_pecas):
    for _, row in df_carga_pecas.iterrows():
        try:
            ordem = Ordem.objects.get(ordem=row['ordem'], grupo_maquina=row['grupo_maquina'])

            # Criando e salvando cada instância separadamente
            PecasOrdem.objects.create(
                ordem=ordem,
                peca=row['Peças'],
                qtd_planejada=int(row['Quantidade']),
                qtd_morta=0,
                qtd_boa=int(row['Quantidade']),
            )

        except Ordem.DoesNotExist:
            print(f"Erro: Ordem {row['ordem']} não encontrada. Linha ignorada.")
        except Exception as e:
            print(f"Erro ao inserir a linha {row.to_dict()}: {e}")

# Chamada da função com o DataFrame
importar_ordens(df_carga_ordem)
importar_propriedades(df_carga_propriedade)
importar_pecas(df_carga_pecas)

