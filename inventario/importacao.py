"""Leitura da planilha da lista de contagem: Setor | Célula | Código | Descrição.

Aceita .xlsx, .xls e .csv (separado por ";" ou ","). O cabeçalho pode estar em
qualquer uma das primeiras linhas e as colunas podem vir em qualquer ordem; os
nomes são comparados sem acento e sem diferenciar maiúsculas.
"""
import io
import re
import unicodedata

import pandas as pd

COLUNAS = {
    'setor': ('Setor', {'setor'}, 100),
    'celula': ('Célula', {'celula'}, 100),
    'codigo': ('Código', {'codigo', 'cod', 'codigodapeca', 'codigodoitem', 'item'}, 60),
    'descricao': ('Descrição', {'descricao', 'desc', 'descricaodapeca', 'descricaodoitem'}, 255),
}
OBRIGATORIAS = ('setor', 'celula', 'codigo')
LINHAS_PROCURA_CABECALHO = 10
MAXIMO_ERROS = 30


class ErroImportacao(Exception):
    def __init__(self, mensagem, detalhes=None):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.detalhes = detalhes or []


def _chave_coluna(valor):
    texto = unicodedata.normalize('NFKD', str(valor or '')).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]', '', texto.lower())


def _texto(valor):
    texto = ' '.join(str(valor if valor is not None else '').split())
    return '' if texto.lower() == 'nan' else texto


def _codigo(valor):
    texto = _texto(valor)
    # código numérico que o Excel guardou como número decimal (1234.0)
    return texto[:-2] if re.fullmatch(r'\d+\.0', texto) else texto


def _ler_tabela(arquivo):
    nome = (arquivo.name or '').lower()
    conteudo = arquivo.read()
    try:
        if nome.endswith('.csv'):
            for codificacao in ('utf-8-sig', 'cp1252', 'latin-1'):  # latin-1 nunca falha
                try:
                    texto = conteudo.decode(codificacao)
                    break
                except UnicodeDecodeError:
                    continue
            return pd.read_csv(
                io.StringIO(texto), header=None, dtype=str, sep=None, engine='python',
                keep_default_na=False, skip_blank_lines=False,
            )
        if nome.endswith('.xlsx') or nome.endswith('.xlsm'):
            return pd.read_excel(io.BytesIO(conteudo), header=None, dtype=str, engine='openpyxl')
        if nome.endswith('.xls'):
            return pd.read_excel(io.BytesIO(conteudo), header=None, dtype=str, engine='xlrd')
    except Exception as erro:  # arquivo corrompido, senha, formato trocado...
        raise ErroImportacao(f'Não foi possível ler a planilha ({erro.__class__.__name__}).')
    raise ErroImportacao('Formato não aceito. Envie um arquivo .xlsx, .xls ou .csv.')


def _achar_cabecalho(tabela):
    """Devolve (índice da linha do cabeçalho, {campo: índice da coluna})."""
    for indice in range(min(LINHAS_PROCURA_CABECALHO, len(tabela))):
        colunas = {}
        for posicao, valor in enumerate(tabela.iloc[indice].tolist()):
            chave = _chave_coluna(valor)
            for campo, (_, apelidos, _) in COLUNAS.items():
                if chave in apelidos and campo not in colunas:
                    colunas[campo] = posicao
        if all(campo in colunas for campo in OBRIGATORIAS):
            return indice, colunas
    raise ErroImportacao(
        'Cabeçalho não encontrado. A planilha precisa das colunas Setor, Célula, Código e Descrição.'
    )


def ler_planilha_contagem(arquivo):
    """Lê e valida a planilha. Devolve uma lista de dicts com setor, celula,
    codigo e descricao, ou levanta ErroImportacao com os problemas
    encontrados (nada é importado se houver erro)."""
    tabela = _ler_tabela(arquivo)
    if tabela.empty:
        raise ErroImportacao('A planilha está vazia.')
    linha_cabecalho, colunas = _achar_cabecalho(tabela)

    linhas, erros, vistos = [], [], {}
    for indice in range(linha_cabecalho + 1, len(tabela)):
        bruta = tabela.iloc[indice].tolist()
        numero = indice + 1  # número da linha como aparece no Excel
        valores = {
            campo: (_codigo if campo == 'codigo' else _texto)(bruta[colunas[campo]]) if campo in colunas else ''
            for campo in COLUNAS
        }
        if not any(valores.values()):
            continue

        faltando = [COLUNAS[c][0] for c in OBRIGATORIAS if not valores[c]]
        if faltando:
            erros.append(f'Linha {numero}: falta {", ".join(faltando)}.')
            continue
        grandes = [f'{COLUNAS[c][0]} (máx. {COLUNAS[c][2]})' for c in COLUNAS if len(valores[c]) > COLUNAS[c][2]]
        if grandes:
            erros.append(f'Linha {numero}: texto grande demais em {", ".join(grandes)}.')
            continue

        chave = (valores['setor'].lower(), valores['celula'].lower(), valores['codigo'].lower())
        if chave in vistos:
            erros.append(
                f'Linha {numero}: código {valores["codigo"]} repetido em '
                f'{valores["setor"]} / {valores["celula"]} (já está na linha {vistos[chave]}).'
            )
            continue
        vistos[chave] = numero
        linhas.append(valores)

    if erros:
        total = len(erros)
        detalhes = erros[:MAXIMO_ERROS]
        if total > MAXIMO_ERROS:
            detalhes.append(f'... e mais {total - MAXIMO_ERROS} erro(s).')
        raise ErroImportacao(
            f'A planilha tem {total} linha(s) com problema. Corrija e envie de novo; nada foi importado.',
            detalhes,
        )
    if not linhas:
        raise ErroImportacao('Nenhum item encontrado abaixo do cabeçalho.')
    return linhas
