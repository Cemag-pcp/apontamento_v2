# utils/sync_carretas.py
from django.db import transaction
from cadastro.models import CarretasExplodidas  

from itertools import islice
import pandas as pd

# Ajuste aqui se quiser outra chave natural:
KEY_FIELDS = ('codigo_peca', 'carreta', 'segundo_processo')

ALL_FIELDS = (
    'codigo_peca',
    'descricao_peca',
    'mp_peca',
    'total_peca',
    'conjunto_peca',
    'primeiro_processo',
    'segundo_processo',
    'carreta',
    'grupo'
)

def _chunked(iterable, size=1000):
    it = iter(iterable)
    while True:
        chunk = list(islice(it, size))
        if not chunk:
            return
        yield chunk

def _clean_cell(v):
    # Converte NaN/None/"" para None; strings são stripadas
    if v is None:
        return None
    s = str(v)
    if s.lower() == 'nan' or s.strip() == '':
        return None
    return s.strip()

def tratamento_carretas():
    
    """
    Precisa baixar a ultima versão da planilha: https://docs.google.com/spreadsheets/d/1A67y-gk0P5qW_jDaxL4B9I-wP9wDM6mjJ91BMrzGWHw/edit?gid=733473611#gid=733473611
    formato CSV e renomear para BASE_GERAL.

    """
    
    df = pd.read_csv("cadastro/BASE_GERAL.csv")

    df = df[['CODIGO', 'DESCRIÇÃO', 'MATÉRIA PRIMA', 'TOTAL', 'PRIMEIRO PROCESSO', '2 PROCESSO', 'CONJUNTO', 'CARRETA','CELULA 3']] 
    columns=['codigo_peca','descricao_peca','mp_peca','total_peca','primeiro_processo','segundo_processo','conjunto_peca','carreta','grupo']

    # codigos que deverã ser tratados manualmente (criar um processo apenas para eles) - COMPONENTE EXTRA
    codigo_processo = [
        '214104',
        '214105',
        '214108',
        '262729',
        '200391',
        '240471',
        '222416',
        '268150',
        '218455'
    ]

    df.columns = columns
    
    df['codigo_peca'] = df['codigo_peca'].astype(str).str.strip()

    mascara = df['codigo_peca'].isin(codigo_processo)
    df.loc[mascara, 'primeiro_processo'] = 'COMPONENTE EXTRA'

    return df

@transaction.atomic
def sync_carretas_from_df(update_existing=False, chunk_size=1000):
    
    """
    Garante que todas as linhas do DataFrame estejam na tabela CarretasExplodidas.
    - Insere as ausentes (comparando pela KEY_FIELDS).
    - Se update_existing=True, atualiza também as já existentes para refletir o DF.
    Retorna dict com contagens.
    """
    
    df = tratamento_carretas()

    # Garante colunas esperadas
    missing_cols = [c for c in ALL_FIELDS if c not in df.columns]
    if missing_cols:
        raise ValueError(f"DataFrame faltando colunas: {missing_cols}")

    # Normalização básica
    df_norm = df.loc[:, list(ALL_FIELDS)].copy()
    for col in ALL_FIELDS:
        df_norm[col] = df_norm[col].map(_clean_cell)

    # Conjunto de chaves já existentes no banco
    existing_keys = set(
        CarretasExplodidas.objects.values_list(*KEY_FIELDS)
    )

    to_create = []
    to_update = []

    # Se vamos atualizar existentes, crie um índice em memória dos objetos atuais por chave
    existing_map = None
    if update_existing:
        existing_map = {
            tuple(vals): obj_id
            for *vals, obj_id in CarretasExplodidas.objects.values_list(*KEY_FIELDS, 'id')
        }

    # Monta payloads
    for row in df_norm.to_dict(orient='records'):
        key = tuple(row[k] for k in KEY_FIELDS)
        if key not in existing_keys:
            to_create.append(CarretasExplodidas(**row))
        elif update_existing:
            obj_id = existing_map.get(key)
            if obj_id:
                obj = CarretasExplodidas(id=obj_id, **row)
                to_update.append(obj)

    created = 0
    updated = 0

    # bulk_create em chunks
    for chunk in _chunked(to_create, chunk_size):
        CarretasExplodidas.objects.bulk_create(chunk, batch_size=chunk_size)
        created += len(chunk)

    # bulk_update (se habilitado)
    if update_existing and to_update:
        # Campos que podem ser atualizados (todos menos a PK)
        update_fields = [f for f in ALL_FIELDS]
        for chunk in _chunked(to_update, chunk_size):
            CarretasExplodidas.objects.bulk_update(chunk, update_fields, batch_size=chunk_size)
            updated += len(chunk)

    return {"created": created, "updated": updated, "existing_kept": len(existing_keys)}



