import pandas as pd
import os
import django

from django.utils.timezone import now  # Para trabalhar com data e hora
from django.shortcuts import get_object_or_404  # Para buscar objetos no banco de dados
from django.db import connection
from django.db import transaction, models, IntegrityError

# Configurações do Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "apontamento_v2.settings")  
django.setup()

from core.models import Ordem

df = pd.read_csv("plasma_vazios_preenchidos.csv", sep=',')

df1 = df[['op_limpa','tempo_estimado']]
df1.dropna(inplace=True)
df1['op_limpa'] = df1['op_limpa'].astype(int)

# Atualiza o tempo_estimado de cada ordem conforme o CSV
print('Inserção de tempos estimados para PLASMA iniciada!')
for _, row in df1.iterrows():
    ordem_num = row['op_limpa']
    tempo_estimado = row['tempo_estimado']

    try:
        ordem_obj = Ordem.objects.filter(
            grupo_maquina='plasma',
            ordem=ordem_num
        ).first()
        if ordem_obj:
            ordem_obj.tempo_estimado = tempo_estimado
            ordem_obj.save()
    except Exception as e:
        continue

print('Inserção de tempos estimados para PLASMA concluída!')

# print('Inserção de tempos estimados para LASER 2 iniciada!')
# for _, row in df1.iterrows():
#     ordem_num = row['op_limpa']
#     tempo_estimado = row['tempo_estimado']

#     try:
#         ordem_obj = Ordem.objects.filter(
#             grupo_maquina='laser_1',
#             ordem=ordem_num
#         ).first()
#         if ordem_obj:
#             ordem_obj.tempo_estimado = tempo_estimado
#             ordem_obj.save()
#     except Exception as e:
#         continue

    