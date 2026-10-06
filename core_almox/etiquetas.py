"""Etiqueta Zebra de prateleira do almoxarifado.

O código de barras (Code 128) é o próprio código do item - é o que o app
lê na hora da entrega pra conferir se pegou o item certo.
"""
import json
import os
import uuid

import redis

from apontamento_exped.utils import ZEBRA_REDIS_URL

# Fila lida pelo worker da Zebra do almoxarifado (separada da expedição)
FILA_ZEBRA_ALMOX = os.getenv("ZEBRA_QUEUE_ALMOX", "print-zebra-almox")
MAX_COPIAS = 50


def _limpar_zpl(texto):
    """^ e ~ são comandos no ZPL - fora deles o texto vai como está (^CI28 = UTF-8)."""
    return str(texto or "").replace("^", " ").replace("~", " ").strip()


LARGURA_ETIQUETA = 799  # dots (203 dpi)
MARGEM = 40


def _modulos_code128(codigo):
    """Largura do Code 128 em módulos (modo automático: dígitos em pares viram subset C)."""
    if codigo.isdigit() and len(codigo) % 2 == 0:
        simbolos = len(codigo) // 2
    else:
        simbolos = len(codigo)
    # start + dados + checksum (11 módulos cada) + stop (13)
    return 11 * (simbolos + 2) + 13


def _barras_centralizadas(codigo):
    """(largura do módulo, x inicial) pra o código caber e ficar no centro da etiqueta."""
    modulos = _modulos_code128(codigo)
    for largura_modulo in (4, 3, 2, 1):
        largura = modulos * largura_modulo
        if largura <= LARGURA_ETIQUETA - 2 * MARGEM:
            return largura_modulo, (LARGURA_ETIQUETA - largura) // 2
    return 1, MARGEM


def zpl_etiqueta_prateleira(codigo, nome, unidade=None, copias=1):
    codigo = _limpar_zpl(codigo)
    nome = _limpar_zpl(nome)
    unidade = _limpar_zpl(unidade)
    linha_unidade = f"Unidade: {unidade}" if unidade else ""
    largura_modulo, x_barras = _barras_centralizadas(codigo)
    return f"""
^XA
^CI28
^PW799
^LL420
^LT0
^LH0,0
^PQ{int(copias)},0,1,Y

^FX ===================== CODIGO DO ITEM =====================
^FO40,20
^A0N,50,50
^FB720,1,0,C,0
^FD{codigo}^FS

^FX ===================== DESCRICAO =====================
^FO40,78
^A0N,28,28
^FB720,2,4,C,0
^FD{nome}^FS

^FO40,145
^A0N,24,24
^FB720,1,0,C,0
^FD{linha_unidade}^FS

^FX ===================== CODIGO DE BARRAS (bipagem na entrega) =====================
^FO{x_barras},180
^BY{largura_modulo},3,110
^BCN,110,N,N,N,A
^FD{codigo}^FS

^XZ
"""


def imprimir_etiqueta_prateleira(item, copias=1):
    """Coloca a etiqueta na fila da Zebra do almox. Retorna o job_id."""
    copias = max(1, min(int(copias), MAX_COPIAS))
    zpl = zpl_etiqueta_prateleira(item.codigo, item.nome, item.unidade, copias)
    job_id = str(uuid.uuid4())
    r = redis.from_url(ZEBRA_REDIS_URL)
    r.rpush(FILA_ZEBRA_ALMOX, json.dumps({"job_id": job_id, "zpl": zpl}))
    return job_id
