import pandas as pd
import os
import django

from django.utils.timezone import now  # Para trabalhar com data e hora
from django.shortcuts import get_object_or_404  # Para buscar objetos no banco de dados
from django.db import connection

# Configurações do Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "apontamento_v2.settings")  
django.setup()

from apontamento_pintura.models import PecasOrdem, CambaoPecas

df = pd.read_csv("apagar_jaja.csv", sep=",")
df['peca_ordem_id'] = (df['peca_ordem_id'].astype(float) * 1000).astype(int)


for _, row in df.iterrows():
    novo_peca_ordem = row['peca_ordem_id']
    id_cambao_peca = row['id']

    try:
        nova_peca = PecasOrdem.objects.get(id=novo_peca_ordem)
        CambaoPecas.objects.filter(id=id_cambao_peca).update(peca_ordem_id=nova_peca.id)
    except PecasOrdem.DoesNotExist:
        print(f"❌ PecaOrdem {novo_peca_ordem} não existe")