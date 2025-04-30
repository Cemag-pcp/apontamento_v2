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

from apontamento_corte.models import PecasOrdem
from cadastro.models import Operador, Setor

df = pd.read_excel("Listagem de Empregados estamparia.xls")

df = df.iloc[5:34]
df=df[['Listagem de Empregados','Unnamed: 1']]
df.columns = ['codigo','nome']
df['codigo'] = df['codigo'].apply(lambda x: x[2:])
df['nome'] = df['nome'].apply(lambda x: x[:20])

# Itera pelas linhas do DataFrame
for _, row in df.iterrows():
    matricula = row['codigo'].strip()
    nome = row['nome'].strip()

    try:
    # Cria ou atualiza a Carreta
        operador_obj, _ = Operador.objects.update_or_create(
            matricula=matricula,
            nome=nome,
            setor=Setor.objects.get(nome="estamparia"),
        )
    except IntegrityError as e:
        continue
    