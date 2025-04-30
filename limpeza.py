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
from cadastro.models import Carretas, Conjuntos, ConjuntoCarreta  # ajuste o nome do seu app aqui

df = pd.read_csv("apagar_jaja.csv", sep=",")


df1 = df[df['PRIMEIRO PROCESSO'] == 'MONTAR']
df1['PRODUTO'] = df1['PRODUTO'].apply(lambda x: str(x).split(' - ', 1)[1] if ' - ' in str(x) else '')
df1 = df1[['CONJUNTO','TOTAL','carreta','PRODUTO']]
df1['codigo'] = df1['CONJUNTO'].apply(lambda x: str(x).split(' ')[0])
df1['descricao'] = df1['CONJUNTO'].apply(lambda x: str(x).split(' - ', 1)[1] if ' - ' in str(x) else '')
df1.drop_duplicates(inplace=True)
df1 = df1[['carreta','codigo','descricao','TOTAL','PRODUTO']]
df1.columns = ['carreta','cod_conj','desc_conj','qt_por_carreta','desc_carreta']


# Carrega o CSV
df = df1

# Remove espaços e garante tipos corretos
df = df.fillna('').astype(str)
df['qt_por_carreta'] = df['qt_por_carreta'].astype(int)

# Itera pelas linhas do DataFrame
for _, row in df.iterrows():
    codigo_carreta = row['carreta'].strip()
    desc_carreta = row['desc_carreta'].strip()

    cod_conj = row['cod_conj'].strip()
    desc_conj = row['desc_conj'].strip()
    qtd = int(row['qt_por_carreta'])

    # Cria ou atualiza a Carreta
    carreta_obj, _ = Carretas.objects.update_or_create(
        codigo=codigo_carreta,
        defaults={"descricao": desc_carreta}
    )

    # Cria ou atualiza o Conjunto
    conjunto_obj, _ = Conjuntos.objects.update_or_create(
        codigo=cod_conj,
        defaults={"descricao": desc_conj, "quantidade": qtd}
    )

    # Cria a relação ConjuntoCarreta (se não existir)
    ConjuntoCarreta.objects.get_or_create(
        conjunto=conjunto_obj,
        carreta=carreta_obj
    )
