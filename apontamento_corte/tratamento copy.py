import pandas as pd
import os
import django

from django.utils.timezone import now  # Para trabalhar com data e hora
from django.shortcuts import get_object_or_404  # Para buscar objetos no banco de dados
from django.db import connection

# Configurações do Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "apontamento_v2.settings")  
django.setup()

from core.models import Ordem, Operador, PropriedadesOrdem
from apontamento_corte.models import PecasOrdem
from cadastro.models import Maquina

df1 = pd.read_csv(r'C:\Users\pcp2\apontamento_usinagem\apontamento_corte\file_temp\criadas.csv') # todas as ordens dos sistema estão aqui dentro
df2 = pd.read_csv(r'C:\Users\pcp2\apontamento_usinagem\apontamento_corte\file_temp\ordens_sistema.csv') # nem todas as ordems criadas estão aqui dentro

df1['grupo_maquina'] = df1['maquina'].apply(
    lambda x: 'plasma' if 'Plasma' in x 
    else 'laser_2' if 'Laser JYF' in x 
    else 'laser_1' if 'Laser' in x 
    else 'outro'
)
df1['maquina'] = df1['maquina'].apply(
    lambda x: 'Plasma 1' if 'Plasma' in x 
    else 'Laser 2 (JFY)' if 'Laser JYF' in x 
    else 'Laser 1'
)

df1['coluna_comum'] = df1['op'].astype(str) + df1['grupo_maquina']
df2['coluna_comum'] = df2['ordem'].astype(str) + df2['grupo_maquina']

# Preciso saber quais ordens faltam ser criadas
df3 = pd.merge(df1, df2, on='coluna_comum', how='left', indicator=True)
df3 = df3[df3['_merge'] == 'left_only']
df3 = df3.drop(columns=['_merge'])
df3 = df3.iloc[:,0:17].reset_index(drop=True)
df3.to_csv("criadas_continuacao.csv", index=False)















