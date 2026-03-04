# utils/sync_carretas.py
from itertools import islice

import pandas as pd
from django.db import transaction

from cadastro.models import CarretasExplodidas

# Ajuste aqui se quiser outra chave natural:
KEY_FIELDS = ('codigo_peca', 'carreta', 'segundo_processo', 'grupo', 'grupo1', 'grupo2')

ALL_FIELDS = (
    'codigo_peca',
    'descricao_peca',
    'mp_peca',
    'total_peca',
    'conjunto_peca',
    'primeiro_processo',
    'segundo_processo',
    'carreta',
    'grupo',
    'grupo1',
    'grupo2',
    'peso',
)

SOURCE_FIELDS = (
    'CODIGO',
    'DESCRIÇÃO',
    'MATÉRIA PRIMA',
    'TOTAL',
    'PRIMEIRO PROCESSO',
    '2 PROCESSO',
    'CONJUNTO',
    'CARRETA',
    'CELULA 3',
    'CELULA 1',
    'CELULA 2',
    'PESO',
)

SOURCE_TO_MODEL = {
    'CODIGO': 'codigo_peca',
    'DESCRIÇÃO': 'descricao_peca',
    'MATÉRIA PRIMA': 'mp_peca',
    'TOTAL': 'total_peca',
    'PRIMEIRO PROCESSO': 'primeiro_processo',
    '2 PROCESSO': 'segundo_processo',
    'CONJUNTO': 'conjunto_peca',
    'CARRETA': 'carreta',
    'CELULA 3': 'grupo',
    'CELULA 1': 'grupo1',
    'CELULA 2': 'grupo2',
    'PESO': 'peso',
}

MANUAL_COMPONENTE_EXTRA = {
    '214104',
    '214105',
    '214108',
    '262729',
    '200391',
    '240471',
    '222416',
    '268150',
    '218455',
}


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


def _normalize_source_columns(df):
    """
    Permite receber colunas com acento normal ou mojibake
    (ex.: DESCRIÇÃO / MATÉRIA PRIMA).
    """
    aliases = {
        'DESCRIÇÃO': 'DESCRIÇÃO',
        'MATÉRIA PRIMA': 'MATÉRIA PRIMA',
    }
    rename_map = {k: v for k, v in aliases.items() if k in df.columns and v not in df.columns}
    if rename_map:
        df = df.rename(columns=rename_map)
    return df


def tratamento_carretas(source_df=None):
    """
    Tratamento padrão para dados de carretas.
    - Sem source_df: lê cadastro/BASE_GERAL.csv.
    - Com source_df: usa o DataFrame fornecido.
    """
    if source_df is None:
        df = pd.read_csv('cadastro/BASE_GERAL.csv')
    else:
        df = source_df.copy()

    df = _normalize_source_columns(df)

    if all(col in df.columns for col in SOURCE_FIELDS):
        df = df.loc[:, list(SOURCE_FIELDS)].rename(columns=SOURCE_TO_MODEL)
    elif all(col in df.columns for col in ALL_FIELDS):
        df = df.loc[:, list(ALL_FIELDS)].copy()
    else:
        missing_source = [c for c in SOURCE_FIELDS if c not in df.columns]
        missing_normalized = [c for c in ALL_FIELDS if c not in df.columns]
        raise ValueError(
            'DataFrame em formato invalido para sync de carretas. '
            f'Faltando colunas fonte: {missing_source}. '
            f'Faltando colunas normalizadas: {missing_normalized}.'
        )

    df['codigo_peca'] = df['codigo_peca'].astype(str).str.strip()
    mascara = df['codigo_peca'].isin(MANUAL_COMPONENTE_EXTRA)
    df.loc[mascara, 'primeiro_processo'] = 'COMPONENTE EXTRA'

    return df


@transaction.atomic
def sync_carretas_from_df(source_df=None, update_existing=False, chunk_size=1000):
    """
    Garante que todas as linhas do DataFrame estejam na tabela CarretasExplodidas.
    - Insere as ausentes (comparando pela KEY_FIELDS).
    - Se update_existing=True, atualiza também as já existentes para refletir o DF.
    """
    df = tratamento_carretas(source_df=source_df)

    missing_cols = [c for c in ALL_FIELDS if c not in df.columns]
    if missing_cols:
        raise ValueError(f'DataFrame faltando colunas: {missing_cols}')

    df_norm = df.loc[:, list(ALL_FIELDS)].copy()
    for col in ALL_FIELDS:
        df_norm[col] = df_norm[col].map(_clean_cell)

    existing_keys = set(CarretasExplodidas.objects.values_list(*KEY_FIELDS))

    to_create = []
    to_update = []

    existing_map = None
    if update_existing:
        existing_map = {
            tuple(vals): obj_id
            for *vals, obj_id in CarretasExplodidas.objects.values_list(*KEY_FIELDS, 'id')
        }

    for row in df_norm.to_dict(orient='records'):
        key = tuple(row[k] for k in KEY_FIELDS)
        if key not in existing_keys:
            to_create.append(CarretasExplodidas(**row))
        elif update_existing:
            obj_id = existing_map.get(key)
            if obj_id:
                to_update.append(CarretasExplodidas(id=obj_id, **row))

    created = 0
    updated = 0

    for chunk in _chunked(to_create, chunk_size):
        CarretasExplodidas.objects.bulk_create(chunk, batch_size=chunk_size)
        created += len(chunk)

    if update_existing and to_update:
        update_fields = [f for f in ALL_FIELDS]
        for chunk in _chunked(to_update, chunk_size):
            CarretasExplodidas.objects.bulk_update(chunk, update_fields, batch_size=chunk_size)
            updated += len(chunk)

    return {'created': created, 'updated': updated, 'existing_kept': len(existing_keys)}
