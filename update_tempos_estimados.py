import pandas as pd
import os
import django

from django.utils.timezone import now  # Para trabalhar com data e hora
from django.shortcuts import get_object_or_404  # Para buscar objetos no banco de dados
from django.db import connection
from django.db import transaction, models, IntegrityError

from apontamento_corte.utils import normalizar_tempo

# Configurações do Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "apontamento_v2.settings")  
django.setup()

from core.models import Ordem


# ordens_laser1 = Ordem.objects.filter(
#             grupo_maquina='laser_1',
#             tempo_estimado__contains='.'
#             ).values()

# for ordem in ordens_laser1:
#     print(ordem['tempo_estimado'].split('.')[0])

# ordens_laser2 = Ordem.objects.filter(
#             grupo_maquina='laser_2',
#             tempo_estimado__contains='s'
#             ).values()

# for ordem in ordens_laser2:
#     print(normalizar_tempo(ordem['tempo_estimado']))
    # print(ordem.tempo_estimado)


ordens_plasma = Ordem.objects.filter(
            grupo_maquina='plasma'
            ).values()

cont = 0
for ordem in ordens_plasma:
    if len(str(ordem['tempo_estimado'])) == 7:
        cont+=1
        print(str('0'+ordem['tempo_estimado']))

print(cont)