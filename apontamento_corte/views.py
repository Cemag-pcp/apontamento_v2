from django.http import JsonResponse
from django.views import View
from django.conf import settings
from django.db import transaction, connection
from django.shortcuts import get_object_or_404, render
from django.core.paginator import Paginator, EmptyPage
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.utils.timezone import now,localtime
from django.utils.dateparse import parse_date
from django.db.models import Q, Count, Sum, F, Max, Value, IntegerField, Prefetch
from django.db.models.functions import Coalesce
from django.forms.models import model_to_dict
from django.contrib.auth.decorators import login_required

from .models import Ordem, PecasOrdem, TransferenciaChapaCorte
from core.models import OrdemProcesso,PropriedadesOrdem,MaquinaParada, Profile
from cadastro.models import Maquina, MotivoInterrupcao, Operador, Espessura, MotivoMaquinaParada, MotivoExclusao, EspessuraChapa, CarretasExplodidas
from .utils import *
from .utils_dashboard import *
from apontamento_serra.utils import formatar_timedelta
from core.utils import notificar_ordem

import pandas as pd
import os
import tempfile
import re
import json
import math
import requests
import xml.etree.ElementTree as ET
from copy import deepcopy
from urllib.parse import unquote
from datetime import datetime, time, timedelta
from functools import reduce
from collections import defaultdict
from decimal import Decimal, InvalidOperation

from datetime import date
from functools import reduce
from urllib.parse import unquote
import re, json

# Caminho para a pasta temporária dentro do projeto
TEMP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'temp')

# Certifique-se de que a pasta existe
os.makedirs(TEMP_DIR, exist_ok=True)

PROCESSOS_APONTAMENTO_DEPOSITODEST_FALLBACK_CORTE = [
    "S Mont Prod Especiais",
    "S Mont Conjuntos Carretas",
    "S Pintura",
    "S Expedição",
    "S C Serras",
    "S C Plasma",
    "S C Guilhotina",
    "S Corte Manual",
    "S C Prensas",
    "S C Laser",
    "S Usinagem",
]

def _url_apontamento_erp_corte():
    return (
        "https://hcemag.innovaro.com.br/api/integracao/v1/producao/apontar"
        if os.getenv("DJANGO_ENV") == "dev"
        else "https://cemag.innovaro.com.br/api/integracao/v1/producao/apontar"
    )

def _post_apontamento_erp_corte(payload):
    return requests.post(
        _url_apontamento_erp_corte(),
        json=payload,
        auth=("luan araujo", "luanaraujo7"),
        timeout=(10, 60),
    )

def _erro_depositodest_indefinido_corte(descricao):
    texto = str(descricao or '').lower()
    return 'depositodest' in texto and 'undefined' in texto

def _processos_fallback_depositodest_corte(processo_atual):
    processo_atual = str(processo_atual or '').strip()
    return [
        processo
        for processo in PROCESSOS_APONTAMENTO_DEPOSITODEST_FALLBACK_CORTE
        if processo != processo_atual
    ]

def _tentar_apontamento_depositodest_processos_alternativos_corte(payload_integracao):
    tentativas = []

    for processo in _processos_fallback_depositodest_corte(payload_integracao.get('processo')):
        payload_tentativa = deepcopy(payload_integracao)
        payload_tentativa['processo'] = processo

        try:
            response_integracao = _post_apontamento_erp_corte(payload_tentativa)
        except requests.RequestException as exc:
            tentativas.append({'processo': processo, 'erro': f'Falha de comunicacao com API ERP: {exc}'})
            continue

        try:
            resposta_api_json = response_integracao.json()
        except ValueError:
            resposta_api_json = None

        if not response_integracao.ok:
            retorno_texto = response_integracao.text[:500] if response_integracao.text else 'Sem detalhes'
            tentativas.append({
                'processo': processo,
                'erro': retorno_texto,
                'status_code': response_integracao.status_code,
                'retorno_api': resposta_api_json or retorno_texto,
            })
            continue

        if isinstance(resposta_api_json, dict):
            status_erp = str(resposta_api_json.get('status') or '').strip().lower()
            if status_erp == 'success':
                return payload_tentativa, resposta_api_json, tentativas

            descricao_erro = str(resposta_api_json.get('description') or 'Erro retornado pela API ERP.')
            tentativas.append({'processo': processo, 'erro': descricao_erro, 'retorno_api': resposta_api_json})
            continue

        tentativas.append({
            'processo': processo,
            'erro': 'API ERP nao retornou JSON valido.',
            'retorno_api': (response_integracao.text or '')[:500],
        })

    return None, None, tentativas

def _mensagem_processo_alternativo_depositodest(payload_original, payload_final):
    processo_original = payload_original.get('processo')
    processo_final = payload_final.get('processo')
    if processo_original == processo_final:
        return ''
    return (
        'Apontamento reenviado automaticamente por erro DEPOSITODEST '
        f'alterando processo de {processo_original} para {processo_final}.'
    )

def _transferencia_chapa_corte_confirmada(transferencia_chapa):
    if not isinstance(transferencia_chapa, dict):
        return False
    return (
        str(transferencia_chapa.get('status') or '').lower() == 'sucesso'
        or bool(transferencia_chapa.get('ja_transferida'))
    )

def _ordem_precisa_transferencia_chapa_corte(itens, dados_chapa):
    return bool(
        itens
        and dados_chapa
        and dados_chapa.get('encontrou_chapa')
        and dados_chapa.get('codigo')
    )

def _parse_decimal_br(valor):
    if valor in (None, ''):
        return None
    try:
        return float(str(valor).strip().replace(',', '.'))
    except (TypeError, ValueError):
        return None

def _extrair_chave_retorno_erp(retorno):
    if not isinstance(retorno, dict):
        return ''

    for campo in ('chaveTransferencia', 'chaveProducao', 'chave', 'productionKey'):
        valor = retorno.get(campo)
        if valor not in (None, ''):
            return str(valor).strip()

    for valor in retorno.values():
        if isinstance(valor, dict):
            chave = _extrair_chave_retorno_erp(valor)
            if chave:
                return chave

    return ''

def _normalizar_chave_apontamento_erp(retorno_api, payload_integracao):
    chave = _extrair_chave_retorno_erp(retorno_api)
    if chave:
        return chave, None

    retorno_serializado = json.dumps(retorno_api, ensure_ascii=False, default=str)[:1200]
    chave_fallback = f"sem-chave:{payload_integracao.get('id')}"
    aviso = (
        'ERP confirmou o apontamento, mas nao retornou chave explicita. '
        f'Retorno bruto: {retorno_serializado}'
    )
    return chave_fallback, aviso

def _extrair_codigo_peca_corte(peca):
    texto = str(peca or '').strip()
    if not texto:
        return ''
    match = re.match(r'^\s*([A-Za-z0-9]+)', texto)
    codigo = match.group(1).strip() if match else texto
    if codigo.isdigit() and len(codigo) == 5:
        return f"0{codigo}"
    return codigo

def _normalizar_texto_validacao_chapa(valor):
    texto = str(valor or '').strip().lower()
    texto = re.sub(r'\s+', ' ', texto)
    texto = texto.replace('×', 'x')
    texto = texto.replace(',', '.')
    return texto

def _parse_decimal_texto_corte(valor):
    texto = str(valor or '').strip()
    if not texto:
        return None
    match = re.search(r'-?[\d.,]+', texto)
    if not match:
        return None
    numero = match.group(0)
    if ',' in numero and '.' in numero:
        numero = numero.replace('.', '').replace(',', '.')
    elif ',' in numero:
        numero = numero.replace(',', '.')
    return _to_decimal_or_none(numero)

def _dados_carreta_explodida_peca_corte(codigo_peca):
    codigo_peca = str(codigo_peca or '').strip()
    if not codigo_peca:
        return None

    queryset = (
        CarretasExplodidas.objects
        .filter(codigo_peca__iexact=codigo_peca)
        .exclude(mp_peca__isnull=True)
        .exclude(mp_peca='')
        .order_by('id')
    )
    primeiro_registro = None
    for dados_carreta in queryset:
        if primeiro_registro is None:
            primeiro_registro = dados_carreta
        if _parse_decimal_texto_corte(getattr(dados_carreta, 'peso', None)) is not None:
            return dados_carreta
    return primeiro_registro

def _espessura_chapa_por_codigo(codigo_chapa):
    codigo_chapa = str(codigo_chapa or '').strip()
    if not codigo_chapa:
        return None
    chapa = (
        EspessuraChapa.objects
        .filter(codigo=codigo_chapa, ativo=True)
        .order_by('id')
        .first()
    )
    if not chapa:
        return None
    return _to_decimal_or_none(chapa.espessura)

def _espessura_chapa_por_materia_prima(materia_prima):
    dados_chapa = _extrair_dados_chapa(materia_prima)
    if dados_chapa:
        chapa = _selecionar_espessura_chapa(dados_chapa, None)
        if chapa:
            return _to_decimal_or_none(chapa.espessura)

    codigo_chapa = _extrair_codigo_peca_corte(materia_prima)
    return _espessura_chapa_por_codigo(codigo_chapa)

def _normalizar_codigo_chapa_corte(codigo):
    codigo = _extrair_codigo_peca_corte(codigo)
    return str(codigo or '').strip().upper()

def _parece_codigo_chapa_corte(codigo):
    codigo = _normalizar_codigo_chapa_corte(codigo)
    return bool(codigo and re.search(r'\d', codigo))

def _codigos_chapa_diferentes_corte(codigo_chapa_ordem, materia_peca):
    codigo_ordem = _normalizar_codigo_chapa_corte(codigo_chapa_ordem)
    codigo_peca = _normalizar_codigo_chapa_corte(materia_peca)
    if (
        not codigo_ordem
        or not codigo_peca
        or not _parece_codigo_chapa_corte(codigo_ordem)
        or not _parece_codigo_chapa_corte(codigo_peca)
    ):
        return False
    return codigo_ordem != codigo_peca

def _item_precisa_transferencia_chapa_corte(item, codigo_chapa_ordem):
    codigo_peca = _extrair_codigo_peca_corte(item.peca)
    dados_carreta = _dados_carreta_explodida_peca_corte(codigo_peca)
    materia_peca = str(getattr(dados_carreta, 'mp_peca', '') or '').strip() if dados_carreta else ''
    descricao_chapa = getattr(getattr(item.ordem, 'propriedade', None), 'descricao_mp', None)

    chapa_norm = _normalizar_texto_validacao_chapa(descricao_chapa)
    materia_norm = _normalizar_texto_validacao_chapa(materia_peca)
    if materia_norm and chapa_norm and (
        materia_norm == chapa_norm or materia_norm in chapa_norm or chapa_norm in materia_norm
    ):
        return False

    return _codigos_chapa_diferentes_corte(codigo_chapa_ordem, materia_peca)

def _calcular_quantidade_ficha_tecnica_chapa(peso_total, espessura_antiga, espessura_nova):
    peso_total = _to_decimal_or_none(peso_total)
    espessura_antiga = _to_decimal_or_none(espessura_antiga)
    espessura_nova = _to_decimal_or_none(espessura_nova)
    if peso_total is None or espessura_antiga is None or espessura_nova is None:
        return None
    if espessura_antiga == 0:
        return None
    quantidade = (peso_total / espessura_antiga) * espessura_nova
    return float((quantidade * Decimal('-1')).quantize(Decimal('0.0001')))

def _resolver_ficha_tecnica_chapa_corte(item, transferencia=None, codigo_chapa_ordem=None):
    propriedade = getattr(item.ordem, 'propriedade', None)
    descricao_chapa = getattr(propriedade, 'descricao_mp', None)
    codigo_peca = _extrair_codigo_peca_corte(item.peca)
    dados_carreta = _dados_carreta_explodida_peca_corte(codigo_peca)
    materia_peca = str(getattr(dados_carreta, 'mp_peca', '') or '').strip() if dados_carreta else ''
    peso_peca = _parse_decimal_texto_corte(getattr(dados_carreta, 'peso', None)) if dados_carreta else None

    if not descricao_chapa:
        return False, 'Nao foi possivel identificar a chapa da ordem.', None
    if not codigo_peca:
        return False, 'Nao foi possivel identificar o codigo da peca.', None
    if not materia_peca:
        return False, f'Peca {codigo_peca} nao possui materia-prima cadastrada em CarretasExplodidas.', None
    if peso_peca is None:
        return False, f'Peca {codigo_peca} nao possui peso cadastrado em CarretasExplodidas.', None

    chapa_norm = _normalizar_texto_validacao_chapa(descricao_chapa)
    materia_norm = _normalizar_texto_validacao_chapa(materia_peca)
    if materia_norm and (materia_norm == chapa_norm or materia_norm in chapa_norm or chapa_norm in materia_norm):
        return True, '', None

    codigo_chapa_novo = str(
        codigo_chapa_ordem or getattr(transferencia, 'codigo_chapa', '') or ''
    ).strip()
    if not codigo_chapa_novo:
        return False, 'Nao foi possivel identificar o codigo da chapa transferida para montar a ficha tecnica.', None

    codigo_chapa_antigo = _extrair_codigo_peca_corte(materia_peca)
    if not codigo_chapa_antigo:
        return False, f'Nao foi possivel identificar o codigo antigo da materia-prima da peca {codigo_peca}.', None
    if (
        not _parece_codigo_chapa_corte(codigo_chapa_novo)
        or not _parece_codigo_chapa_corte(codigo_chapa_antigo)
    ):
        return True, '', None
    if not _codigos_chapa_diferentes_corte(codigo_chapa_novo, materia_peca):
        return True, '', None
    if not transferencia:
        return False, 'Transfira a chapa antes de apontar este item, pois os codigos da chapa e da materia-prima da peca sao diferentes.', None

    espessura_antiga = _espessura_chapa_por_materia_prima(materia_peca)
    if espessura_antiga is None:
        return False, f'Nao foi possivel identificar a espessura do codigo antigo {codigo_chapa_antigo}.', None

    espessura_nova = _espessura_chapa_por_codigo(codigo_chapa_novo)
    if espessura_nova is None:
        return False, f'Nao foi possivel identificar a espessura do codigo novo {codigo_chapa_novo}.', None

    quantidade_pecas = _to_decimal_or_none(getattr(item, 'qtd_boa', None))
    if quantidade_pecas is None:
        return False, f'Nao foi possivel identificar a quantidade de pecas boas do item {item.id}.', None

    peso_total_pecas = peso_peca * quantidade_pecas
    quantidade_ficha = _calcular_quantidade_ficha_tecnica_chapa(peso_total_pecas, espessura_antiga, espessura_nova)
    if quantidade_ficha is None:
        return False, 'Nao foi possivel calcular a quantidade da ficha tecnica.', None

    return True, (
        f'Peca {codigo_peca} usa materia-prima diferente da chapa da ordem; '
        'fichaTecnica de substituicao sera enviada ao ERP.'
    ), [
        {
            "insumo": codigo_chapa_novo,
            "quantidade": quantidade_ficha,
            "insumoSubstituido": codigo_chapa_antigo,
        }
    ]

def _payload_apontamento_item_corte(item, ficha_tecnica=None):
    data_producao = localtime(item.data) if item.data else localtime(now())
    payload = {
        "id": f"corte-item-{item.id}",
        "data": data_producao.strftime('%d/%m/%Y'),
        "pessoa": "4357",
        "recurso": _extrair_codigo_peca_corte(item.peca),
        "processo": "S C Plasma",
        "produzido": item.qtd_boa,
        "observacao": str(item.ordem_id),
    }
    if ficha_tecnica:
        payload["fichaTecnica"] = ficha_tecnica
    return payload

def _registrar_erro_apontamento_api_corte(item, erro, user):
    item.erro_apontamento = erro
    item.tipo_apontamento = 'api'
    item.resp_apontamento = user
    item.save(update_fields=['erro_apontamento', 'tipo_apontamento', 'resp_apontamento'])

def _mensagem_ficha_tecnica_apontamento(ficha_tecnica):
    if not ficha_tecnica:
        return ''
    itens = [
        f"{item.get('insumoSubstituido')} -> {item.get('insumo')}"
        for item in ficha_tecnica
    ]
    return (
        'Ficha tecnica enviada para substituir insumo: '
        + ', '.join(itens)
    )

def _normalizar_tipo_chapa_display(tipo_chapa_display):
    if not tipo_chapa_display:
        return ''
    if str(tipo_chapa_display).strip().lower() == 'inox':
        return 'Aço inox'
    return str(tipo_chapa_display).strip()

def _normalizar_tipo_chapa_cadastro(tipo_chapa):
    tipo = str(tipo_chapa or '').strip()
    if tipo == 'inox':
        return 'aco_inox'
    return tipo

def _to_decimal_or_none(valor):
    if valor in (None, ''):
        return None
    try:
        return Decimal(str(valor).strip().replace(',', '.'))
    except (InvalidOperation, ValueError):
        return None

def _mesma_largura_chapa(largura_cadastro, largura_descricao):
    largura_cadastro = _to_decimal_or_none(largura_cadastro)
    largura_descricao = _to_decimal_or_none(largura_descricao)
    if largura_cadastro is None or largura_descricao is None:
        return False
    return abs(largura_cadastro - largura_descricao) <= Decimal('0.001')

def _intervalo_largura_chapa(chapa):
    return _to_decimal_or_none(chapa.largura), _to_decimal_or_none(getattr(chapa, 'largura_maxima', None))

def _largura_dentro_intervalo_chapa(chapa, largura_descricao):
    largura_descricao = _to_decimal_or_none(largura_descricao)
    if largura_descricao is None:
        return False

    largura_minima, largura_maxima = _intervalo_largura_chapa(chapa)
    if largura_minima is not None and largura_descricao < largura_minima:
        return False
    if largura_maxima is not None and largura_descricao > largura_maxima:
        return False
    return True

def _score_intervalo_largura_chapa(chapa, largura_descricao):
    largura_descricao = _to_decimal_or_none(largura_descricao)
    if largura_descricao is None:
        return 0

    largura_minima, largura_maxima = _intervalo_largura_chapa(chapa)
    if largura_minima is None and largura_maxima is None:
        return 0
    if (
        largura_minima is not None
        and largura_maxima is not None
        and _mesma_largura_chapa(largura_minima, largura_descricao)
        and _mesma_largura_chapa(largura_maxima, largura_descricao)
    ):
        return 5
    if largura_minima is not None and largura_maxima is not None:
        intervalo = largura_maxima - largura_minima
        if intervalo <= Decimal('100'):
            return 4
        if intervalo <= Decimal('500'):
            return 3
        return 2
    return 1

def _selecionar_espessura_chapa(dados_chapa, propriedade):
    candidatos = list(EspessuraChapa.objects.filter(
        como_aparece_planilha__iexact=dados_chapa['espessura_planilha'],
        ativo=True,
    ))
    if not candidatos:
        return None

    tipo_ordem = _normalizar_tipo_chapa_cadastro(getattr(propriedade, 'tipo_chapa', None))
    largura_ordem = dados_chapa.get('largura')
    candidatos_validos = []

    for chapa in candidatos:
        tipos_chapa = chapa.tipos_chapa or []
        if not tipos_chapa and chapa.tipo_chapa:
            tipos_chapa = [chapa.tipo_chapa]

        if tipos_chapa and tipo_ordem and tipo_ordem not in tipos_chapa:
            continue
        if not _largura_dentro_intervalo_chapa(chapa, largura_ordem):
            continue

        score = 0
        if tipos_chapa and tipo_ordem and tipo_ordem in tipos_chapa:
            score += 2
        score += _score_intervalo_largura_chapa(chapa, largura_ordem)
        candidatos_validos.append((score, chapa.id, chapa))

    if not candidatos_validos:
        return None

    candidatos_validos.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return candidatos_validos[0][2]

def _extrair_dados_chapa(descricao_mp):
    """
    Extrai dados de textos como "11 - 1200 x 2000 mm".
    Retorna a espessura como aparece na planilha, menor dimensao como largura,
    e maior dimensao como comprimento.
    """
    texto = str(descricao_mp or '').strip()
    match = re.search(
        r'^\s*(?P<espessura>.+?)\s*-\s*(?P<largura>\d+(?:[,.]\d+)?)\s*[x×]\s*(?P<comprimento>\d+(?:[,.]\d+)?)',
        texto,
        flags=re.IGNORECASE,
    )
    if not match:
        return None

    dimensao_a = _parse_decimal_br(match.group('largura'))
    dimensao_b = _parse_decimal_br(match.group('comprimento'))
    if dimensao_a is None or dimensao_b is None:
        return None

    largura = min(dimensao_a, dimensao_b)
    comprimento = max(dimensao_a, dimensao_b)

    return {
        'espessura_planilha': match.group('espessura').strip(),
        'largura': largura,
        'comprimento': comprimento,
    }

def _calcular_peso_chapas_corte(propriedade, qtd_chapas):
    dados_chapa = _extrair_dados_chapa(propriedade.descricao_mp if propriedade else None)
    if not dados_chapa:
        return None

    espessura_chapa = _selecionar_espessura_chapa(dados_chapa, propriedade)
    if not espessura_chapa:
        return {
            'encontrou_chapa': False,
            'espessura_planilha': dados_chapa['espessura_planilha'],
            'largura': dados_chapa.get('largura'),
            'tipo_chapa': _normalizar_tipo_chapa_cadastro(getattr(propriedade, 'tipo_chapa', None)),
            'descricao_mp': propriedade.descricao_mp if propriedade else None,
        }

    quantidade = _parse_decimal_br(qtd_chapas)
    if quantidade is None:
        quantidade = _parse_decimal_br(propriedade.quantidade if propriedade else None) or 0

    espessura = float(espessura_chapa.espessura)
    peso_total = (
        dados_chapa['largura']
        * dados_chapa['comprimento']
        * espessura
        * 7.85
        * 10 ** -6
        * quantidade
    )

    tipos_chapa = espessura_chapa.tipos_chapa or []
    tipo_chapa = tipos_chapa[0] if tipos_chapa else (espessura_chapa.tipo_chapa or '')

    return {
        'encontrou_chapa': True,
        'espessura_planilha': dados_chapa['espessura_planilha'],
        'espessura_mm': str(espessura_chapa.espessura).replace('.', ',').rstrip('0').rstrip(','),
        'codigo': espessura_chapa.codigo,
        'tipo_chapa': tipo_chapa,
        'tipo_chapa_display': espessura_chapa.get_tipo_chapa_display() if tipo_chapa and tipo_chapa == espessura_chapa.tipo_chapa else '',
        'largura': dados_chapa['largura'],
        'comprimento': dados_chapa['comprimento'],
        'quantidade_chapas': quantidade,
        'peso_total': round(peso_total, 3),
    }

def _chamar_innovaro_transferir_chapa_corte(ordem, dados_chapa):
    registro_existente = TransferenciaChapaCorte.objects.filter(ordem=ordem, status='sucesso').first()
    if registro_existente:
        return {
            'enviado': False,
            'ja_transferida': True,
            'registro_id': registro_existente.id,
            'status': registro_existente.status,
            'transferido_em': localtime(registro_existente.transferido_em).strftime('%d/%m/%Y %H:%M') if registro_existente.transferido_em else '',
            'chave_transferencia': registro_existente.chave_transferencia,
        }

    propriedade = getattr(ordem, 'propriedade', None)
    pessoa = "luan araujo soares"
    deposito_origem = "Almox Central"
    deposito_destino = "Almox Corte e Estamparia"

    if not dados_chapa or not dados_chapa.get('encontrou_chapa'):
        registro, _ = TransferenciaChapaCorte.objects.update_or_create(
            ordem=ordem,
            defaults={
                'descricao_chapa': propriedade.descricao_mp if propriedade else None,
                'espessura_planilha': dados_chapa.get('espessura_planilha') if dados_chapa else None,
                'codigo_chapa': None,
                'quantidade_chapas': 0,
                'peso_total': 0,
                'deposito_origem': deposito_origem,
                'deposito_destino': deposito_destino,
                'pessoa': pessoa,
                'payload': None,
                'resposta_api': None,
                'chave_transferencia': None,
                'status': 'ignorada',
                'erro': 'Chapa nao encontrada no cadastro.',
                'transferido_em': None,
            },
        )
        return {
            'enviado': False,
            'registro_id': registro.id,
            'status': registro.status,
            'erro': 'Chapa nao encontrada no cadastro.',
        }
    if not dados_chapa.get('codigo'):
        registro, _ = TransferenciaChapaCorte.objects.update_or_create(
            ordem=ordem,
            defaults={
                'descricao_chapa': propriedade.descricao_mp if propriedade else None,
                'espessura_planilha': dados_chapa.get('espessura_planilha'),
                'espessura_mm': dados_chapa.get('espessura_mm'),
                'codigo_chapa': None,
                'quantidade_chapas': dados_chapa.get('quantidade_chapas') or 0,
                'peso_total': dados_chapa.get('peso_total') or 0,
                'deposito_origem': deposito_origem,
                'deposito_destino': deposito_destino,
                'pessoa': pessoa,
                'payload': None,
                'resposta_api': None,
                'chave_transferencia': None,
                'status': 'ignorada',
                'erro': 'Chapa cadastrada sem codigo.',
                'transferido_em': None,
            },
        )
        return {
            'enviado': False,
            'registro_id': registro.id,
            'status': registro.status,
            'erro': 'Chapa cadastrada sem codigo.',
        }

    identificacao_ordem = ordem.ordem or ordem.ordem_duplicada or ordem.id
    payload = [
        {
            "id": f"corte-chapa-{ordem.id}",
            "pessoa": pessoa,
            "recurso": str(dados_chapa['codigo']),
            "quantidade": dados_chapa['peso_total'],
            "depositoOrigem": deposito_origem,
            "depositoDestino": deposito_destino,
        }
    ]

    registro, _ = TransferenciaChapaCorte.objects.update_or_create(
        ordem=ordem,
        defaults={
            'descricao_chapa': propriedade.descricao_mp if propriedade else None,
            'espessura_planilha': dados_chapa.get('espessura_planilha'),
            'espessura_mm': dados_chapa.get('espessura_mm'),
            'codigo_chapa': str(dados_chapa['codigo']),
            'quantidade_chapas': dados_chapa.get('quantidade_chapas') or 0,
            'peso_total': dados_chapa.get('peso_total') or 0,
            'deposito_origem': deposito_origem,
            'deposito_destino': deposito_destino,
            'pessoa': pessoa,
            'payload': payload,
            'resposta_api': None,
            'chave_transferencia': None,
            'status': 'pendente',
            'erro': None,
            'transferido_em': None,
        },
    )

    if os.getenv("DJANGO_ENV") == "dev":
        url = "https://hcemag.innovaro.com.br/api/integracao/v1/producao/transferir"
    else:
        url = "https://cemag.innovaro.com.br/api/integracao/v1/producao/transferir"

    print(f"[CHAPAS_CORTE][INNOVARO] ordem={identificacao_ordem} payload={payload}")
    print(f"[CHAPAS_CORTE][INNOVARO] URL: {url}")

    try:
        response = requests.post(
            url,
            json=payload,
            auth=("luan araujo", "luanaraujo7"),
            timeout=(10, 60),
        )
    except requests.RequestException as exc:
        erro = f"Erro de conexao com o Innovaro: {exc}"
        print(f"[CHAPAS_CORTE][INNOVARO] {erro}")
        registro.status = 'erro'
        registro.erro = erro
        registro.payload = payload
        registro.save(update_fields=['status', 'erro', 'payload', 'atualizado_em'])
        return {
            'enviado': False,
            'registro_id': registro.id,
            'status': registro.status,
            'erro': erro,
            'payload': payload,
        }

    print(f"[CHAPAS_CORTE][INNOVARO] status: {response.status_code}")
    print(f"[CHAPAS_CORTE][INNOVARO] resposta: {response.text}")

    try:
        resp_json = response.json()
    except ValueError:
        resp_json = {}

    resp_item = resp_json[0] if isinstance(resp_json, list) and resp_json else resp_json
    resp_status = resp_item.get("status") if isinstance(resp_item, dict) else None
    if not response.ok or resp_status == "Error":
        erro = resp_item.get("description") if isinstance(resp_item, dict) else None
        erro = erro or response.text or "Erro desconhecido no Innovaro."
        registro.status = 'erro'
        registro.erro = erro
        registro.resposta_api = resp_json or response.text
        registro.save(update_fields=['status', 'erro', 'resposta_api', 'atualizado_em'])
        return {
            'enviado': False,
            'registro_id': registro.id,
            'status': registro.status,
            'erro': erro,
            'payload': payload,
            'status_code': response.status_code,
        }

    chave_transferencia = _extrair_chave_retorno_erp(resp_item if isinstance(resp_item, dict) else {})
    registro.status = 'sucesso'
    registro.erro = None
    registro.resposta_api = resp_json
    registro.chave_transferencia = chave_transferencia
    registro.transferido_em = now()
    registro.save(update_fields=[
        'status',
        'erro',
        'resposta_api',
        'chave_transferencia',
        'transferido_em',
        'atualizado_em',
    ])

    return {
        'enviado': True,
        'registro_id': registro.id,
        'status': registro.status,
        'payload': payload,
        'status_code': response.status_code,
        'resposta': resp_json,
        'chave_transferencia': chave_transferencia,
        'transferido_em': localtime(registro.transferido_em).strftime('%d/%m/%Y %H:%M') if registro.transferido_em else '',
    }

def _registrar_transferencia_chapa_corte_manual(ordem, dados_chapa, user):
    registro_existente = TransferenciaChapaCorte.objects.filter(ordem=ordem, status='sucesso').first()
    if registro_existente:
        return {
            'enviado': False,
            'manual': True,
            'ja_transferida': True,
            'registro_id': registro_existente.id,
            'status': registro_existente.status,
            'transferido_em': localtime(registro_existente.transferido_em).strftime('%d/%m/%Y %H:%M') if registro_existente.transferido_em else '',
            'chave_transferencia': registro_existente.chave_transferencia,
        }

    propriedade = getattr(ordem, 'propriedade', None)
    pessoa = "luan araujo soares"
    deposito_origem = "Almox Central"
    deposito_destino = "Almox Corte e Estamparia"

    if not dados_chapa or not dados_chapa.get('encontrou_chapa') or not dados_chapa.get('codigo'):
        return {
            'enviado': False,
            'manual': True,
            'erro': 'Nao foi possivel registrar manualmente: chapa nao encontrada ou sem codigo.',
        }

    payload = [
        {
            "id": f"corte-chapa-{ordem.id}",
            "pessoa": pessoa,
            "recurso": str(dados_chapa['codigo']),
            "quantidade": dados_chapa['peso_total'],
            "depositoOrigem": deposito_origem,
            "depositoDestino": deposito_destino,
            "tipo": "manual",
            "usuario": getattr(user, 'username', '') or '',
        }
    ]

    registro, _ = TransferenciaChapaCorte.objects.update_or_create(
        ordem=ordem,
        defaults={
            'descricao_chapa': propriedade.descricao_mp if propriedade else None,
            'espessura_planilha': dados_chapa.get('espessura_planilha'),
            'espessura_mm': dados_chapa.get('espessura_mm'),
            'codigo_chapa': str(dados_chapa['codigo']),
            'quantidade_chapas': dados_chapa.get('quantidade_chapas') or 0,
            'peso_total': dados_chapa.get('peso_total') or 0,
            'deposito_origem': deposito_origem,
            'deposito_destino': deposito_destino,
            'pessoa': pessoa,
            'payload': payload,
            'resposta_api': {'tipo': 'manual', 'usuario': getattr(user, 'username', '') or ''},
            'chave_transferencia': 'MANUAL',
            'status': 'sucesso',
            'erro': None,
            'transferido_em': now(),
        },
    )

    return {
        'enviado': False,
        'manual': True,
        'registro_id': registro.id,
        'status': registro.status,
        'payload': payload,
        'chave_transferencia': registro.chave_transferencia,
        'transferido_em': localtime(registro.transferido_em).strftime('%d/%m/%Y %H:%M') if registro.transferido_em else '',
    }

def _apontar_itens_corte_via_api_bloco(itens, user):
    itens_validos = []
    erros = []
    fichas_tecnicas = {}
    dados_chapa_por_ordem = {}

    for item in itens:
        if item.apontado:
            continue

        if item.ordem_id not in dados_chapa_por_ordem:
            propriedade = getattr(item.ordem, 'propriedade', None)
            dados_chapa_por_ordem[item.ordem_id] = _calcular_peso_chapas_corte(
                propriedade,
                propriedade.quantidade if propriedade else None,
            )
        dados_chapa = dados_chapa_por_ordem.get(item.ordem_id) or {}
        codigo_chapa_ordem = dados_chapa.get('codigo')

        transferencia = (
            TransferenciaChapaCorte.objects
            .filter(ordem_id=item.ordem_id, status='sucesso')
            .order_by('-transferido_em', '-id')
            .first()
        )
        if not transferencia and _item_precisa_transferencia_chapa_corte(item, codigo_chapa_ordem):
            erros.append({'id': item.id, 'erro': 'Transfira a chapa antes de apontar este item.'})
            continue

        peca_valida, aviso_peca, ficha_tecnica = _resolver_ficha_tecnica_chapa_corte(
            item,
            transferencia,
            codigo_chapa_ordem,
        )
        if not peca_valida:
            _registrar_erro_apontamento_api_corte(item, aviso_peca, user)
            erros.append({'id': item.id, 'erro': aviso_peca})
            continue
        if ficha_tecnica:
            fichas_tecnicas[item.id] = ficha_tecnica

        if (item.qtd_morta or 0) > 0:
            msg_qtd_morta = (
                'Apontamento via API bloqueado automaticamente: item com qtd_morta > 0. '
                'A funcionalidade de desvio precisa ser ajustada na API.'
            )
            item.erro_apontamento = msg_qtd_morta
            item.tipo_apontamento = 'api'
            item.resp_apontamento = user
            item.save(update_fields=['erro_apontamento', 'tipo_apontamento', 'resp_apontamento'])
            erros.append({'id': item.id, 'erro': msg_qtd_morta})
            continue

        itens_validos.append(item)

    if not itens_validos:
        return {
            'enviado': False,
            'sucessos': [],
            'erros': erros,
            'message': 'Nenhum item valido para apontar.',
        }

    payload_integracao = [
        _payload_apontamento_item_corte(item, fichas_tecnicas.get(item.id))
        for item in itens_validos
    ]
    print(
        "[CORTE][INNOVARO][APONTAMENTO_AUTO][BODY]",
        json.dumps(payload_integracao, ensure_ascii=False, indent=2),
    )

    try:
        response_integracao = _post_apontamento_erp_corte(payload_integracao)
    except requests.RequestException as exc:
        erro = f'Falha de comunicacao com API ERP: {exc}'
        for item in itens_validos:
            item.erro_apontamento = erro
            item.tipo_apontamento = 'api'
            item.resp_apontamento = user
            item.save(update_fields=['erro_apontamento', 'tipo_apontamento', 'resp_apontamento'])
        return {
            'enviado': False,
            'sucessos': [],
            'erros': erros + [{'erro': erro}],
            'payload_enviado': payload_integracao,
        }

    try:
        resposta_api_json = response_integracao.json()
    except ValueError:
        resposta_api_json = None

    if not response_integracao.ok:
        retorno_texto = response_integracao.text[:500] if response_integracao.text else 'Sem detalhes'
        for item in itens_validos:
            item.erro_apontamento = retorno_texto
            item.tipo_apontamento = 'api'
            item.resp_apontamento = user
            item.save(update_fields=['erro_apontamento', 'tipo_apontamento', 'resp_apontamento'])
        return {
            'enviado': False,
            'sucessos': [],
            'erros': erros + [{'erro': retorno_texto}],
            'payload_enviado': payload_integracao,
            'retorno_api': resposta_api_json or retorno_texto,
            'status_code': response_integracao.status_code,
        }

    respostas = resposta_api_json if isinstance(resposta_api_json, list) else [resposta_api_json]
    sucessos = []

    for index, item in enumerate(itens_validos):
        retorno_item = respostas[index] if index < len(respostas) else resposta_api_json
        if isinstance(retorno_item, dict) and str(retorno_item.get('status') or '').lower() == 'error':
            descricao_erro = str(retorno_item.get('description') or 'Erro retornado pela API ERP.')
            if _erro_depositodest_indefinido_corte(descricao_erro):
                payload_tentativa, retorno_tentativa, tentativas = (
                    _tentar_apontamento_depositodest_processos_alternativos_corte(payload_integracao[index])
                )
                if payload_tentativa and retorno_tentativa:
                    item.chave_apontamento, aviso_chave = _normalizar_chave_apontamento_erp(
                        retorno_tentativa,
                        payload_tentativa,
                    )
                    avisos = [
                        aviso_chave,
                        _mensagem_ficha_tecnica_apontamento(payload_tentativa.get('fichaTecnica')),
                        _mensagem_processo_alternativo_depositodest(
                            payload_integracao[index],
                            payload_tentativa,
                        ),
                    ]
                    item.erro_apontamento = ' '.join(aviso for aviso in avisos if aviso) or None
                    item.apontado = True
                    item.tipo_apontamento = 'api'
                    item.resp_apontamento = user
                    item.data_apontamento = now()
                    item.save(update_fields=[
                        'apontado',
                        'tipo_apontamento',
                        'resp_apontamento',
                        'data_apontamento',
                        'chave_apontamento',
                        'erro_apontamento',
                    ])
                    payload_integracao[index] = payload_tentativa
                    sucessos.append({
                        'id': item.id,
                        'chave_apontamento': item.chave_apontamento,
                        'processo': payload_tentativa.get('processo'),
                    })
                    continue
                retorno_item['tentativas_processos_alternativos'] = tentativas
            item.erro_apontamento = descricao_erro
            item.tipo_apontamento = 'api'
            item.resp_apontamento = user
            item.save(update_fields=['erro_apontamento', 'tipo_apontamento', 'resp_apontamento'])
            erros.append({'id': item.id, 'erro': descricao_erro, 'retorno_api': retorno_item})
            continue

        item.chave_apontamento, aviso_chave = _normalizar_chave_apontamento_erp(
            retorno_item if isinstance(retorno_item, dict) else {},
            payload_integracao[index],
        )
        aviso_ficha = _mensagem_ficha_tecnica_apontamento(payload_integracao[index].get('fichaTecnica'))
        item.erro_apontamento = aviso_chave or aviso_ficha
        item.apontado = True
        item.tipo_apontamento = 'api'
        item.resp_apontamento = user
        item.data_apontamento = now()
        item.save(update_fields=[
            'apontado',
            'tipo_apontamento',
            'resp_apontamento',
            'data_apontamento',
            'chave_apontamento',
            'erro_apontamento',
        ])
        sucessos.append({'id': item.id, 'chave_apontamento': item.chave_apontamento})

    return {
        'enviado': True,
        'sucessos': sucessos,
        'erros': erros,
        'payload_enviado': payload_integracao,
        'retorno_api': resposta_api_json,
        'status_code': response_integracao.status_code,
    }

def extrair_numeracao(nome_arquivo):
    match = re.search(r"(?i)OP\s*(\d+)", nome_arquivo)  # Permite espaços opcionais entre OP e o número
    if match:
        return match.group(1)
    return None

def planejamento(request):

    motivos = MotivoInterrupcao.objects.filter(setor__nome='corte', visivel=True)
    operadores = Operador.objects.filter(setor__nome='corte')
    espessuras = Espessura.objects.all()
    maquinas_plasma = Maquina.objects.filter(setor__nome='corte', nome__icontains='plasma').order_by('nome')
    motivos_maquina_parada = MotivoMaquinaParada.objects.filter(setor__nome='serra').exclude(nome='Finalizada parcial')
    motivos_exclusao = MotivoExclusao.objects.filter(setor__nome='corte')

    return render(request, 'apontamento_corte/planejamento.html', {
        'motivos': motivos,
        'operadores': operadores,
        'espessuras': espessuras,
        'maquinas_plasma': maquinas_plasma,
        'motivos_maquina_parada': motivos_maquina_parada,
        'motivos_exclusao': motivos_exclusao,
    })

def get_pecas_ordem(request, pk_ordem):
    try:
        # Busca a ordem com os relacionamentos necessários
        ordem = Ordem.objects.prefetch_related('ordem_pecas_corte', 'propriedade').get(pk=pk_ordem)

        # Propriedades da ordem
        propriedades = {
            'descricao_mp': ordem.propriedade.descricao_mp if ordem.propriedade else None,
            'espessura': ordem.propriedade.espessura if ordem.propriedade else None,
            'quantidade': ordem.propriedade.quantidade if ordem.propriedade else None,
            'tipo_chapa': ordem.propriedade.get_tipo_chapa_display() if ordem.propriedade else None,
            'aproveitamento': ordem.propriedade.aproveitamento if ordem.propriedade else None,
        }

        # Peças relacionadas à ordem
        pecas = [
            {'peca': peca.peca, 'quantidade': peca.qtd_planejada if peca.qtd_boa == 0 else  peca.qtd_boa}
            for peca in ordem.ordem_pecas_corte.all()
        ]

        return JsonResponse({'pecas': pecas, 'propriedades': propriedades})

    except Ordem.DoesNotExist:
        return JsonResponse({'error': 'Ordem não encontrada.'}, status=404)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)    

def get_ordens_criadas(request):

    # Captura os parâmetros de filtro
    filtro_ordem = request.GET.get('ordem', '')
    filtro_maquina = request.GET.get('maquina', '').strip()
    filtro_status = request.GET.get('status', '')
    filtro_peca = request.GET.get('peca', '').strip()
    filtro_turno = request.GET.get('turno', '')
    filtro_data_programada = request.GET.get('data-programada', '').strip()

    page = int(request.GET.get('page', 1))
    limit = int(request.GET.get('limit', 10))

    # Filtra as ordens com base nos parâmetros
    ordens_queryset = Ordem.objects.prefetch_related('ordem_pecas_corte').select_related('propriedade').filter(grupo_maquina__in=['plasma', 'laser_1', 'laser_2', 'laser_3']).order_by('-ultima_atualizacao', '-status_prioridade')

    if filtro_ordem:
        if '.' in filtro_ordem or 'dup' in filtro_ordem:
            ordens_queryset = ordens_queryset.filter(ordem_duplicada__contains=filtro_ordem)
        else:
            ordens_queryset = ordens_queryset.filter(ordem=int(filtro_ordem))

    if filtro_maquina:
        ordens_queryset = ordens_queryset.filter(grupo_maquina__icontains=filtro_maquina)
    if filtro_status:
        ordens_queryset = ordens_queryset.filter(status_atual=filtro_status)
    if filtro_peca:
        ordens_queryset = ordens_queryset.filter(ordem_pecas_corte__peca__icontains=filtro_peca)
    if filtro_turno:
        if filtro_turno == 'turnoA':
            # Filtra entre 07:00 e 18:00
            ordens_queryset = ordens_queryset.filter(
                ultima_atualizacao__time__gte=time(7, 0),
                ultima_atualizacao__time__lte=time(18, 0),
            )
        elif filtro_turno == 'turnoB':
            # Filtra entre 21:00 e 07:00 do dia seguinte
            ordens_queryset = ordens_queryset.filter(
                Q(ultima_atualizacao__time__gte=time(21, 0)) |
                Q(ultima_atualizacao__time__lte=time(7, 0))
            )
    if filtro_data_programada:
        ordens_queryset = ordens_queryset.filter(data_programacao=filtro_data_programada)

    # Paginação
    paginator = Paginator(ordens_queryset, limit)
    try:
        ordens_page = paginator.page(page)
    except EmptyPage:
        return JsonResponse({'ordens': []})

    # Monta os dados
    data = [{
        'id':ordem.pk,  
        'ordem': ordem.ordem if ordem.ordem else ordem.ordem_duplicada,
        'grupo_maquina': ordem.get_grupo_maquina_display(),
        'data_criacao': localtime(ordem.data_criacao).strftime('%d/%m/%Y %H:%M'),
        'data_programacao': ordem.data_programacao.strftime('%d/%m/%Y'),
        'obs': ordem.obs,
        'status_atual': ordem.status_atual,
        'maquina': ordem.maquina.nome if ordem.maquina else None,
        'maquina_id': ordem.maquina.id if ordem.maquina else None,
        'sequenciada': ordem.sequenciada,
        'propriedade': {
            'descricao_mp': ordem.propriedade.descricao_mp if ordem.propriedade.descricao_mp else None,
            'quantidade': ordem.propriedade.quantidade if ordem.propriedade.quantidade else None,
            'tipo_chapa': ordem.propriedade.get_tipo_chapa_display() if ordem.propriedade.tipo_chapa else None,
            'aproveitamento': ordem.propriedade.aproveitamento if ordem.propriedade.aproveitamento else None,
            'retalho': 'Sim' if ordem.propriedade.retalho else None,
        },
        'ultima_atualizacao': localtime(ordem.ultima_atualizacao).strftime('%d/%m/%Y %H:%M') if ordem.status_atual == 'finalizada' else None,
        'tempo_estimado': ordem.tempo_estimado if ordem.tempo_estimado else 'Não foi possivel calcular',
    } for ordem in ordens_page]

    return JsonResponse({'ordens': data})

def editar_informacoes_ordem(request):
    if request.method != 'PATCH':
        return JsonResponse({'error': 'Método não permitido.'}, status=405)

    try:
        with transaction.atomic():
            body = json.loads(request.body)

            ordem_id = body.get('ordem_id')
            obs = body.get('obs', '')
            qtd_chapas = body.get('qtdChapas')

            if not ordem_id:
                return JsonResponse({'error': 'Informe a ordem.'}, status=400)

            try:
                qtd_chapas = float(qtd_chapas)
            except (TypeError, ValueError):
                return JsonResponse({'error': 'Quantidade de chapas inválida.'}, status=400)

            if qtd_chapas <= 0:
                return JsonResponse({'error': 'Quantidade de chapas deve ser maior que zero.'}, status=400)

            ordem = get_object_or_404(
                Ordem,
                pk=ordem_id,
                grupo_maquina__in=['plasma', 'laser_1', 'laser_2', 'laser_3']
            )

            if ordem.status_atual == 'finalizada':
                return JsonResponse({'error': 'Não é possível editar ordens finalizadas.'}, status=400)

            propriedade = getattr(ordem, 'propriedade', None)
            if not propriedade:
                return JsonResponse({'error': 'Propriedades da ordem não encontradas.'}, status=404)

            qtd_chapas_atual = float(propriedade.quantidade or 0)
            if qtd_chapas_atual <= 0:
                return JsonResponse({'error': 'Quantidade atual de chapas inválida para recálculo.'}, status=400)

            fator = qtd_chapas / qtd_chapas_atual

            ordem.obs = obs
            ordem.save()

            propriedade.quantidade = qtd_chapas
            propriedade.save()

            pecas_ordem = list(PecasOrdem.objects.filter(ordem=ordem))
            for peca in pecas_ordem:
                nova_quantidade = math.floor(float(peca.qtd_planejada) * fator)
                peca.qtd_planejada = max(nova_quantidade, 0)

            if pecas_ordem:
                PecasOrdem.objects.bulk_update(pecas_ordem, ['qtd_planejada'])

            transaction.on_commit(lambda: notificar_ordem(ordem))

            return JsonResponse({
                'message': 'Informações atualizadas com sucesso.',
                'ordem_id': ordem.id,
                'qtd_chapas': propriedade.quantidade,
                'obs': ordem.obs,
            })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def atualizar_status_ordem(request):
    if request.method == 'PATCH':
        try:
            with transaction.atomic():
                # Parse do corpo da requisição
                body = json.loads(request.body)
                print(body)

                status = body['status']
                ordem_id = body['ordem_id']
                comentario_extra = body['comentario_extra'] if 'comentario_extra' in body else ''
                # grupo_maquina = body['grupo_maquina'].lower()
                pecas_geral = body.get('pecas_mortas', [])
                qtd_chapas = body.get('qtdChapas', None)
                maquina_request = body.get('maquina')
                tipo_chapa = body.get('tipoChapa')
                finalizar_parcial = bool(body.get('finalizar_parcial', False))

                if maquina_request:
                    maquina_nome = get_object_or_404(Maquina, pk=int(maquina_request))

                # Obtém a ordem
                ordem = Ordem.objects.get(pk=ordem_id)#, grupo_maquina=grupo_maquina)
                
                # Validações básicas
                if ordem.status_atual == status:
                    return JsonResponse({'error': f'Essa ordem ja está {status}. Atualize a página.'}, status=400)

                # Verifica se já existe uma ordem iniciada na mesma máquina
                if status == 'iniciada' and maquina_nome:
                    ordem_em_andamento = Ordem.objects.filter(
                        maquina=maquina_nome, status_atual='iniciada'
                    ).exclude(id=ordem.id).exists()

                    if ordem_em_andamento:
                        return JsonResponse({'error': f'Já existe uma ordem iniciada para essa máquina ({maquina_nome}). Finalize ou interrompa antes de iniciar outra.'}, status=400)

                # Finaliza o processo atual (se existir)
                processo_atual = ordem.processos.filter(data_fim__isnull=True).first()
                if processo_atual:
                    processo_atual.finalizar_atual()

                # Cria o novo processo
                novo_processo = OrdemProcesso.objects.create(
                    ordem=ordem,
                    status=status,
                    data_inicio=now(),
                    data_fim=now() if status == 'finalizada' else None
                )

                # Atualiza o status da ordem para o novo status
                ordem.status_atual = status
                
                if status == 'iniciada':
                    # Finaliza paradas da máquina se necessário
                    maquinas_paradas = MaquinaParada.objects.filter(maquina=maquina_nome, data_fim__isnull=True)
                    for parada in maquinas_paradas:
                        parada.data_fim = now()
                        parada.save()

                    ordem.maquina = maquina_nome
                    ordem.status_prioridade = 1
                elif status == 'finalizada':
                    propriedade_atual = ordem.propriedade
                    quantidade_chapas_original = propriedade_atual.quantidade if propriedade_atual else 0
                    tipo_chapa_original = propriedade_atual.tipo_chapa if propriedade_atual else None
                    peso_chapas = None
                    transferencia_chapa = None

                    # Verifica se a quantidade de chapas mudaram
                    if int(qtd_chapas) != ordem.propriedade.quantidade:
                        ordem.propriedade.quantidade = int(qtd_chapas)
                        ordem.propriedade.save()
                    if tipo_chapa is not None and tipo_chapa != ordem.propriedade.tipo_chapa:
                        ordem.propriedade.tipo_chapa = tipo_chapa
                        ordem.propriedade.save()

                    peso_chapas = _calcular_peso_chapas_corte(ordem.propriedade, qtd_chapas)

                    pecas_restantes = []
                    for peca in pecas_geral:
                        peca_id = peca.get('peca')
                        planejada = peca.get('planejadas')
                        mortas = peca.get('mortas', 0)

                        peca = PecasOrdem.objects.get(ordem=ordem, peca=peca_id)
                        qtd_planejada_original = peca.qtd_planejada
                        peca.qtd_boa = planejada - mortas
                        peca.qtd_morta = mortas

                        peca.save()

                        if finalizar_parcial:
                            restante = max(qtd_planejada_original - planejada, 0)
                            if restante > 0:
                                pecas_restantes.append({"peca": peca.peca, "quantidade": restante})

                    # Se existir peça iniciando com 9, marca a ordem como excluída
                    if PecasOrdem.objects.filter(ordem=ordem, peca__startswith='9').exists():
                        ordem.excluida = True

                    ordem.status_prioridade = 3
                    ordem.operador_final = get_object_or_404(Operador, pk=body.get('operadorFinal'))
                    ordem.obs_operador = body.get('obsFinal')

                    nova_ordem = None
                    if finalizar_parcial and pecas_restantes:
                        quantidade_chapas_usada = float(qtd_chapas) if qtd_chapas is not None else 0
                        quantidade_chapas_restante = max(quantidade_chapas_original - quantidade_chapas_usada, 0)

                        ordem_base = ordem.ordem or ordem.ordem_duplicada
                        if ordem_base:
                            ordem_base = re.sub(r'^continuacao#', '', str(ordem_base))
                            ordem_base = re.sub(r'\.\d+$', '', ordem_base)
                        continuacao_prefixo = f"continuacao#{ordem_base}"
                        continuacoes_existentes = Ordem.objects.filter(
                            ordem_duplicada__startswith=f"{continuacao_prefixo}."
                        ).count()
                        nova_ordem = Ordem.objects.create(
                            ordem=None,
                            ordem_duplicada=f"{continuacao_prefixo}.{continuacoes_existentes + 1}",
                            obs=f"Saldo da ordem #{ordem_base}",
                            grupo_maquina=ordem.grupo_maquina,
                            data_programacao=now().date(),
                            status_atual='aguardando_iniciar',
                            maquina=ordem.maquina,
                            tempo_estimado=ordem.tempo_estimado,
                        )

                        PropriedadesOrdem.objects.create(
                            ordem=nova_ordem,
                            descricao_mp=propriedade_atual.descricao_mp if propriedade_atual else None,
                            tamanho=propriedade_atual.tamanho if propriedade_atual else None,
                            espessura=propriedade_atual.espessura if propriedade_atual else None,
                            quantidade=quantidade_chapas_restante,
                            aproveitamento=propriedade_atual.aproveitamento if propriedade_atual else None,
                            tipo_chapa=tipo_chapa if tipo_chapa is not None else tipo_chapa_original,
                            retalho=propriedade_atual.retalho if propriedade_atual else False,
                        )

                        for peca_restante in pecas_restantes:
                            PecasOrdem.objects.create(
                                ordem=nova_ordem,
                                peca=peca_restante["peca"],
                                qtd_planejada=peca_restante["quantidade"],
                            )
                elif status == 'interrompida':
                    novo_processo.motivo_interrupcao = MotivoInterrupcao.objects.get(nome=body['motivo'])
                    novo_processo.comentario_extra = comentario_extra
                    novo_processo.save()
                    ordem.status_prioridade = 2

                ordem.save()
                if status == 'finalizada':
                    itens_para_apontamento_erp = list(
                        PecasOrdem.objects
                        .select_related('ordem', 'ordem__propriedade')
                        .filter(ordem=ordem, qtd_boa__gt=0)
                        .order_by('id')
                    )
                    precisa_transferencia_chapa = False
                    try:
                        precisa_transferencia_chapa = _ordem_precisa_transferencia_chapa_corte(
                            itens_para_apontamento_erp,
                            peso_chapas,
                        )

                        if precisa_transferencia_chapa:
                            transferencia_chapa = _chamar_innovaro_transferir_chapa_corte(ordem, peso_chapas)
                        else:
                            transferencia_chapa = {
                                'enviado': False,
                                'status': 'ignorada',
                                'erro': None if peso_chapas and peso_chapas.get('codigo') else 'Chapa nao encontrada ou sem codigo.',
                                'motivo': 'Alteracao de ficha tecnica nao necessaria: sem divergencia entre a chapa cadastrada e a chapa usada na ordem.',
                            }
                    except Exception as exc:
                        transferencia_chapa = {
                            'enviado': False,
                            'status': 'erro',
                            'erro': str(exc),
                        }

                    if (
                        precisa_transferencia_chapa
                        and not _transferencia_chapa_corte_confirmada(transferencia_chapa)
                    ):
                        apontamento_erp = {
                            'enviado': False,
                            'sucessos': [],
                            'erros': [{
                                'erro': (
                                    'Apontamento bloqueado: a transferencia de chapa era '
                                    'obrigatoria e nao foi confirmada no ERP.'
                                ),
                                'transferencia_chapa': transferencia_chapa,
                            }],
                            'message': 'Apontamento bloqueado aguardando transferencia de chapa.',
                        }
                    else:
                        try:
                            apontamento_erp = _apontar_itens_corte_via_api_bloco(
                                itens_para_apontamento_erp,
                                request.user,
                            )
                        except Exception as exc:
                            apontamento_erp = {
                                'enviado': False,
                                'erros': [{'erro': str(exc)}],
                            }

                notificar_ordem(ordem)

                response_payload = {
                    'message': 'Status atualizado com sucesso.',
                    'ordem_id': ordem.id,
                    'status': novo_processo.status,
                    'data_inicio': novo_processo.data_inicio,
                    'maquina_id': ordem.maquina.id if ordem.maquina else None,
                }
                if status == 'finalizada' and 'nova_ordem' in locals() and nova_ordem:
                    response_payload['nova_ordem_id'] = nova_ordem.id
                    response_payload['nova_ordem_numero'] = nova_ordem.ordem or nova_ordem.ordem_duplicada
                if status == 'finalizada' and 'peso_chapas' in locals() and peso_chapas:
                    response_payload['peso_chapas'] = peso_chapas
                if status == 'finalizada' and 'transferencia_chapa' in locals() and transferencia_chapa:
                    response_payload['transferencia_chapa'] = transferencia_chapa
                if status == 'finalizada' and 'apontamento_erp' in locals() and apontamento_erp:
                    response_payload['apontamento_erp'] = apontamento_erp

                return JsonResponse(response_payload)

        except Ordem.DoesNotExist:
            return JsonResponse({'error': 'Ordem não encontrada.'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Método não permitido.'}, status=405)

@require_GET
def get_ordens_iniciadas(request):
    usuario_tipo = Profile.objects.filter(user=request.user).values_list('tipo_acesso', flat=True).first()

    # Filtra as ordens com base no status 'iniciada'
    ordens_queryset = Ordem.objects.prefetch_related('ordem_pecas_corte').select_related('propriedade') \
        .filter(status_atual='iniciada', grupo_maquina__in=['plasma','laser_1','laser_2', 'laser_3'])

    # Paginação (opcional)
    page = request.GET.get('page', 1)  # Obtém o número da página
    limit = request.GET.get('limit', 10)  # Define o limite padrão por página
    paginator = Paginator(ordens_queryset, limit)  # Aplica a paginação
    ordens_page = paginator.get_page(page)  # Obtém a página atual

    # Monta os dados para retorno
    data = [{
        'id': ordem.id,
        'ordem': ordem.ordem if ordem.ordem else ordem.ordem_duplicada,
        'grupo_maquina': ordem.get_grupo_maquina_display(),
        'data_criacao': ordem.data_criacao.strftime('%d/%m/%Y %H:%M'),
        'obs': ordem.obs,
        'status_atual': ordem.status_atual,
        'maquina': ordem.maquina.nome if ordem.maquina else None,
        'maquina_id': ordem.maquina.id if ordem.maquina else None,
        'ultima_atualizacao': ordem.ultima_atualizacao,
        'propriedade': {
            'descricao_mp': ordem.propriedade.descricao_mp if ordem.propriedade else None,
            'espessura': ordem.propriedade.espessura if ordem.propriedade else None,
            'quantidade': ordem.propriedade.quantidade if ordem.propriedade else None,
            'tipo_chapa': ordem.propriedade.get_tipo_chapa_display() if ordem.propriedade else None,
            'aproveitamento': ordem.propriedade.aproveitamento if ordem.propriedade else None,
        }
    } for ordem in ordens_page]

    # Retorna os dados paginados como JSON
    return JsonResponse({
        'usuario_tipo_acesso':usuario_tipo,
        'ordens': data,
        'page': ordens_page.number,
        'total_pages': paginator.num_pages,
        'total_ordens': paginator.count
    })

@require_GET
def get_ordens_interrompidas(request):

    usuario_tipo = Profile.objects.filter(user=request.user).values_list('tipo_acesso', flat=True).first()

    # Filtra as ordens com base no status 'interrompida'
    processos_interrompidos = Prefetch(
        'processos',
        queryset=OrdemProcesso.objects.filter(status='interrompida').order_by('-data_inicio').select_related('motivo_interrupcao'),
        to_attr='processos_interrompidos_cache'
    )
    ordens_queryset = Ordem.objects.prefetch_related(processos_interrompidos, 'ordem_pecas_corte').select_related('propriedade', 'maquina') \
        .filter(status_atual='interrompida', grupo_maquina__in=['plasma','laser_1','laser_2','laser_3'])

    # Paginação (opcional)
    page = request.GET.get('page', 1)  # Obtém o número da página
    limit = request.GET.get('limit', 10)  # Define o limite padrão por página
    paginator = Paginator(ordens_queryset, limit)  # Aplica a paginação
    ordens_page = paginator.get_page(page)  # Obtém a página atual

    # Monta os dados para retorno
    data = []
    for ordem in ordens_page:
        # Obtém o último processo interrompido usando o prefetch já carregado
        processos_cache = getattr(ordem, 'processos_interrompidos_cache', [])
        ultimo_processo_interrompido = processos_cache[0] if processos_cache else None

        data.append({
            'id': ordem.id,
            'ordem': ordem.ordem if ordem.ordem else ordem.ordem_duplicada,
            'grupo_maquina': ordem.get_grupo_maquina_display(),
            'data_criacao': ordem.data_criacao.strftime('%d/%m/%Y %H:%M'),
            'obs': ordem.obs,
            'status_atual': ordem.status_atual,
            'maquina': ordem.maquina.nome if ordem.maquina else None,
            'maquina_id': ordem.maquina.id if ordem.maquina else None,
            'motivo_interrupcao': ultimo_processo_interrompido.motivo_interrupcao.nome if ultimo_processo_interrompido and ultimo_processo_interrompido.motivo_interrupcao else None,
            'comentario_extra': ultimo_processo_interrompido.comentario_extra if ultimo_processo_interrompido else None,
            'ultima_atualizacao': ordem.ultima_atualizacao,
            'propriedade': {
                'descricao_mp': ordem.propriedade.descricao_mp if ordem.propriedade else None,
                'espessura': ordem.propriedade.espessura if ordem.propriedade else None,
                'quantidade': ordem.propriedade.quantidade if ordem.propriedade else None,
                'tipo_chapa': ordem.propriedade.get_tipo_chapa_display() if ordem.propriedade else None,
                'aproveitamento': ordem.propriedade.aproveitamento if ordem.propriedade else None,
            }
        })

    # Retorna os dados paginados como JSON
    return JsonResponse({
        'usuario_tipo_acesso':usuario_tipo,
        'ordens': data,
        'page': ordens_page.number,
        'total_pages': paginator.num_pages,
        'total_ordens': paginator.count
    })

def get_pecas(request):

    """
    Retorna uma lista paginada de peças, com suporte a busca por código ou descrição.
    """
    
    # Obtém os parâmetros da requisição
    search = request.GET.get('search', '').strip()  # Termo de busca
    page = int(request.GET.get('page', 1))  # Página atual (padrão é 1)
    per_page = int(request.GET.get('per_page', 10))  # Itens por página (padrão é 10)

    # Filtra as peças com base no termo de busca (opcional)
    pecas_query = PecasOrdem.objects.values_list('peca', flat=True).distinct()  # Apenas o campo `peca`, eliminando duplicatas
    if search:
        pecas_query = pecas_query.filter(peca__icontains=search).order_by('peca')

    # Paginação
    paginator = Paginator(pecas_query, per_page)
    pecas_page = paginator.get_page(page)

    # Monta os resultados paginados no formato esperado pelo Select2
    data = {
        'results': [
            {'id': peca, 'text': peca} for peca in pecas_page  # Usa a string como `id` e `text`
        ],
        'pagination': {
            'more': pecas_page.has_next()  # Se há mais páginas
        },
    }

    return JsonResponse(data)

def filtrar_ordens(request):
    pecas_ids = request.GET.getlist("pecas")  # Lista de IDs das peças selecionadas
    maquina = request.GET.get("maquina", "")  # Máquina filtrada (se existir)

    # Filtra as ordens com base nas peças selecionadas
    ordens = PecasOrdem.objects.all()

    if maquina:
        ordens = ordens.filter(ordem__maquina=maquina)
    if pecas_ids:
        ordens = ordens.filter(peca__in=pecas_ids)

    # Monta os resultados com os dados relevantes
    resultados = [
        {
            "id": ordem.id,
            "mp": ordem.ordem.propriedade.descricao_mp if ordem.ordem.propriedade else "Sem MP",  # Acessa a propriedade corretamente
            "peca": ordem.peca.codigo,
            "quantidade": ordem.qtd_planejada,
        }
        for ordem in ordens
    ]

    return JsonResponse({"ordens": resultados})

def get_ordens_criadas_duplicar_ordem(request):
    #  Captura os parâmetros da requisição
    pecas = request.GET.get('pecas', '')
    pecas = [unquote(p) for p in pecas.split('|')] if pecas else []
    pecas = [re.match(r'\d+', p).group() for p in pecas if re.match(r'\d+', p)]

    maquina = unquote(request.GET.get('maquina', ''))
    ordem = unquote(request.GET.get('ordem', ''))
    filtro_excluida = request.GET.get('excluida', 'nao')

    codigos = [re.match(r'\d+', p).group() for p in pecas if re.match(r'\d+', p)]
    codigos_unicos = list(set(pecas))

    dataCriacao = request.GET.get('dataCriacao','')

    page = int(request.GET.get('page', 1))
    limit = int(request.GET.get('limit', 10))
    draw = int(request.GET.get('draw', 1))

    # NOVOS PARÂMETROS (acréscimo)
    modo = request.GET.get('modo', 'all')  # 'all' | 'prioritize' | 'qty'
    priorizar_raw = unquote(request.GET.get('priorizar', '')).strip()
    priorizar = re.match(r'\d+', priorizar_raw).group() if re.match(r'\d+', priorizar_raw) else ''

    qtymap_str = request.GET.get('qtymap', '')
    try:
        qtymap = json.loads(unquote(qtymap_str)) if qtymap_str else {}
    except Exception:
        qtymap = {}
    # normaliza chaves de qtymap para manter só dígitos
    qtymap = {
        (re.match(r'\d+', k).group() if re.match(r'\d+', k) else k): v
        for k, v in qtymap.items()
        if (isinstance(v, (int, float)) and v >= 0)
    }

    #  Define a Query Base
    ordens_queryset = (
        Ordem.objects.filter(grupo_maquina__in=['plasma', 'laser_1', 'laser_2','laser_3'], duplicada=False)
        .prefetch_related('ordem_pecas_corte')  # Evita queries repetidas para peças
        .select_related('propriedade')          # Carrega a propriedade diretamente
        .order_by('-propriedade__aproveitamento')
    )

    # otimização do Filtro de Peças (comportamento existente)
    if codigos_unicos:
        filtros = reduce(
            lambda acc, c: acc | Q(ordem_pecas_corte__peca__startswith=c),
            codigos_unicos[1:],
            Q(ordem_pecas_corte__peca__startswith=codigos_unicos[0])
        )

        ordens_queryset = ordens_queryset.filter(filtros).annotate(
            pecas_encontradas=Count(
                'ordem_pecas_corte__peca',
                filter=Q(ordem_pecas_corte__qtd_planejada__gt=0) & filtros,
                distinct=True
            )
        ).filter(
            pecas_encontradas=len(codigos_unicos)
        )

    # Filtra Máquina e Ordem se necessário (existente)
    if maquina:
        ordens_queryset = ordens_queryset.filter(grupo_maquina=maquina)
    if ordem:
        ordens_queryset = ordens_queryset.filter(ordem=ordem)
    if filtro_excluida == 'sim':
        ordens_queryset = ordens_queryset.filter(excluida=True)
    elif filtro_excluida == 'nao':
        ordens_queryset = ordens_queryset.filter(excluida=False)

    # Filtra Data Criação (existente)
    if dataCriacao:
        ordens_queryset = ordens_queryset.filter(data_criacao__date=date.fromisoformat(dataCriacao))

    # ========= ACRÉSCIMOS DE LÓGICA (sem desfazer o que existe) =========

    # Para priorização e qty precisamos de anotações de quantidade por peça
    # Monta o conjunto de "códigos de interesse" conforme o modo
    codigos_interesse = set(codigos_unicos)
    if modo == 'qty' and qtymap:
        codigos_interesse |= set(qtymap.keys())
    if modo == 'prioritize' and priorizar:
        codigos_interesse |= {priorizar}

    # Cria anotações dinâmicas por peça (Sum filtrado por prefixo do código da peça)
    # Ex.: q_12345 = SUM(qtd_planejada WHERE peca startswith '12345')
    if codigos_interesse:
        annotations = {}
        for c in codigos_interesse:
            key = f"q_{c}"
            annotations[key] = Sum(
                'ordem_pecas_corte__qtd_planejada',
                filter=Q(ordem_pecas_corte__peca__startswith=c)
            )
        ordens_queryset = ordens_queryset.annotate(**annotations)

    # (1) modo PRIORITIZE: priorizar peça -> a peça priorizada deve ter a MAIOR quantidade
    #    Estratégia: exigir q_priorizar >= q_outros para cada outro código relevante.
    if modo == 'prioritize' and priorizar:
        prio_key = f"q_{priorizar}"
        # Garante que existe a anotação da priorizada
        if codigos_interesse and prio_key in ordens_queryset.query.annotations:
            for c in codigos_interesse:
                if c == priorizar:
                    continue
                other_key = f"q_{c}"
                # só compara se a outra anotação também existe
                if other_key in ordens_queryset.query.annotations:
                    ordens_queryset = ordens_queryset.filter(
                        Q(**{f"{prio_key}__gte": F(other_key)}) | Q(**{other_key: None})
                    )
            # também assegura que a priorizada exista (>0) para fazer sentido
            ordens_queryset = ordens_queryset.filter(**{f"{prio_key}__gt": 0})

    # (2) modo QTY: qtymap = { 'CODPECA': quantidade_minima } -> exigir q_cod >= quantidade
    if modo == 'qty' and qtymap:
        for c, req in qtymap.items():
            key = f"q_{c}"
            # se a anotação não existir, ainda assim o filtro abaixo retornará vazio
            ordens_queryset = ordens_queryset.filter(**{f"{key}__gte": req})

    # =====================================================================

    # Contagem de Registros para Paginação (existente)
    records_filtered = ordens_queryset.count()

    # Paginação eficiente (existente)
    paginator = Paginator(ordens_queryset, limit)
    try:
        ordens_page = paginator.page(page)
    except EmptyPage:
        return JsonResponse({'draw': draw, 'recordsTotal': records_filtered, 'recordsFiltered': records_filtered, 'data': []})

    # Otimização da Serialização dos Dados (existente)
    data = [
        {
            'id': ordem.pk,
            'ordem': ordem.ordem,
            'grupo_maquina': ordem.get_grupo_maquina_display(),
            'data_criacao': localtime(ordem.data_criacao).strftime('%d/%m/%Y %H:%M'),
            'obs': ordem.obs,
            'status_atual': ordem.status_atual,
            'excluida': ordem.excluida,
            'aproveitamento': round(ordem.propriedade.aproveitamento, 5) if ordem.propriedade else None,
            'propriedade': {
                'descricao_mp': ordem.propriedade.descricao_mp if ordem.propriedade else None,
                'quantidade': ordem.propriedade.quantidade if ordem.propriedade else None,
                'tipo_chapa': ordem.propriedade.get_tipo_chapa_display() if ordem.propriedade else None,
                'aproveitamento': round(ordem.propriedade.aproveitamento, 5) if ordem.propriedade else None,
                'retalho': 'Sim' if ordem.propriedade and ordem.propriedade.retalho else None,
            }
        } for ordem in ordens_page
    ]

    #  Ordena os dados com base no aproveitamento corrigido (existente)
    data.sort(key=lambda x: x['aproveitamento'], reverse=True)

    return JsonResponse({
        'draw': draw,
        'recordsTotal': records_filtered,
        'recordsFiltered': records_filtered,
        'data': data
    })

def get_pecas_ordem_duplicar_ordem(request, pk_ordem):
    try:
        # Busca a ordem com os relacionamentos necessários
        ordem = Ordem.objects.prefetch_related('ordem_pecas_corte').select_related('propriedade').get(pk=pk_ordem)

        espessuras_distintas = PropriedadesOrdem.objects.exclude(
            espessura__isnull=True
        ).exclude(
            espessura__exact=''
        ).values_list(
            'espessura', flat=True
        ).distinct().order_by('espessura')
        
        valores_remover = {'nan', 'Selecione', ''}
        espessuras = [
            esp for esp in espessuras_distintas 
            if str(esp) not in valores_remover and esp is not None
        ]

        tipos_chapas = [tipo[1] for tipo in PropriedadesOrdem.TIPO_CHAPA_CHOICES]

        # Propriedades da ordem
        propriedades = {
            'descricao_mp': ordem.propriedade.descricao_mp if ordem.propriedade else None,
            'espessura': ordem.propriedade.espessura if ordem.propriedade else None,
            'quantidade': ordem.propriedade.quantidade if ordem.propriedade else None,
            'tipo_chapa': ordem.propriedade.get_tipo_chapa_display() if ordem.propriedade else None,
            'aproveitamento': ordem.propriedade.aproveitamento if ordem.propriedade else None,
            'maquina': ordem.grupo_maquina,
            'ordem': ordem.ordem,
        }

        # Peças relacionadas à ordem
        pecas = [
            {'peca': peca.peca, 'quantidade': peca.qtd_planejada}
            for peca in ordem.ordem_pecas_corte.all()
            if peca.qtd_planejada > 0
        ]

        return JsonResponse({'pecas': pecas, 'propriedades': propriedades, 
                             'espessuras': espessuras, 'tipos_chapas':tipos_chapas})

    except Ordem.DoesNotExist:
        return JsonResponse({'error': 'Ordem não encontrada.'}, status=404)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)    

def excluir_op_padrao(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)
    
    try:
        # Parse do JSON do corpo da requisição
        data = json.loads(request.body)
        ordem_id = data.get('ordem_id')
        
        if not ordem_id:
            return JsonResponse({'error': 'ordem_id não fornecido'}, status=400)
        
        # Busca a ordem no banco de dados
        try:
            ordem = Ordem.objects.get(pk=ordem_id)
        except Ordem.DoesNotExist:
            return JsonResponse({'error': 'Ordem não encontrada'}, status=404)
        
        # Marca como excluída e salva
        ordem.excluida = True

        ordem.save(update_fields=['excluida'])  # NÃO atualiza `ultima_atualizacao`
        
        return JsonResponse({'success': True, 'message': f'Ordem {ordem_id} marcada como excluída'})
    
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def excluir_op_lote(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)

    try:
        data = json.loads(request.body)
        ordem_ids = data.get('ordem_ids', [])

        if not isinstance(ordem_ids, list) or not ordem_ids:
            return JsonResponse({'error': 'ordem_ids deve ser uma lista não vazia'}, status=400)

        # Garante inteiros
        try:
            ordem_ids = [int(i) for i in ordem_ids]
        except Exception:
            return JsonResponse({'error': 'ordem_ids contém valores inválidos'}, status=400)

        updated = Ordem.objects.filter(pk__in=ordem_ids).update(excluida=True)
        return JsonResponse({'success': True, 'atualizadas': updated})
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def restaurar_op_padrao(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'MÃ©todo nÃ£o permitido'}, status=405)

    try:
        data = json.loads(request.body)
        ordem_id = data.get('ordem_id')

        if not ordem_id:
            return JsonResponse({'error': 'ordem_id nÃ£o fornecido'}, status=400)

        try:
            ordem = Ordem.objects.get(pk=ordem_id)
        except Ordem.DoesNotExist:
            return JsonResponse({'error': 'Ordem nÃ£o encontrada'}, status=404)

        ordem.excluida = False
        ordem.save(update_fields=['excluida'])

        return JsonResponse({'success': True, 'message': f'Ordem {ordem_id} restaurada'})
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON invÃ¡lido'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def gerar_op_duplicada(request, pk_ordem):

    """
    Duplicar uma ordem existente com suas propriedades e criar uma nova entrada na base.
    """
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)

    # Carrega os dados do JSON
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    # Valida os campos necessários
    obs_duplicar = data.get('obs_duplicar')
    data_programacao = data.get('dataProgramacao')
    qtd_chapa = data.get('qtdChapa')
    tipo_chapa = data.get('tipoChapa')
    espessura = data.get('espessura')
    maquina = data.get('maquina', None)
    pecas = data.get('pecas', [])

    if not qtd_chapa or not pecas:
        return JsonResponse({'error': 'Campos obrigatórios ausentes (qtdChapa ou pecas)'}, status=400)

    try:
        qtd_chapa = float(qtd_chapa)  # Converte qtdChapa para float
    except ValueError:
        return JsonResponse({'error': 'Quantidade de chapas inválida'}, status=400)

    try:
        # Busca a ordem original
        ordem_original = Ordem.objects.get(pk=pk_ordem)

        if maquina:
            maquina_ordem = get_object_or_404(Maquina, pk=maquina)
        else:
            maquina_ordem = ordem_original.maquina

        with transaction.atomic():
            # Cria a nova ordem como duplicada
            nova_ordem = Ordem.objects.create(
                ordem_pai=ordem_original,
                duplicada=True,
                grupo_maquina=ordem_original.grupo_maquina,
                maquina=maquina_ordem,
                obs=obs_duplicar,
                status_atual='aguardando_iniciar',
                data_programacao=data_programacao,
                tempo_estimado=ordem_original.tempo_estimado,
            )

            # Duplica as propriedades associadas
            if hasattr(ordem_original, 'propriedade'):
                propriedade_original = ordem_original.propriedade

                if espessura == None:
                    espessura = propriedade_original.espessura

                if tipo_chapa == None:
                    tipo_chapa = propriedade_original.tipo_chapa

                PropriedadesOrdem.objects.create(
                    ordem=nova_ordem,  # Associa a nova ordem
                    descricao_mp=propriedade_original.descricao_mp,
                    tamanho=propriedade_original.tamanho,
                    espessura=espessura,
                    quantidade=qtd_chapa,
                    aproveitamento=propriedade_original.aproveitamento,
                    tipo_chapa=tipo_chapa,
                    retalho=propriedade_original.retalho,
                )

            # Criar peças para ordem duplicada
            for peca in pecas:
                PecasOrdem.objects.create(
                    ordem=nova_ordem,
                    peca=peca['peca'],
                    qtd_planejada=peca['qtd_planejada']
                )

            transaction.on_commit(lambda: notificar_ordem(nova_ordem))

        return JsonResponse({'message': 'Ordem duplicada com sucesso', 'nova_ordem_id': nova_ordem.pk, 'nova_ordem': nova_ordem.ordem_duplicada}, status=201)

    except Ordem.DoesNotExist:
        return JsonResponse({'error': 'Ordem original não encontrada'}, status=404)
    except Exception as e:
        return JsonResponse({'error': f'Erro ao duplicar ordem: {str(e)}'}, status=500)

def duplicar_op(request):

    return render(request, 'apontamento_corte/duplicar-op.html')

def get_ordens_sequenciadas(request):
    """
    Função para buscar ordens já sequenciadas não finalizadas
    """

    # Máquina do laser ou plasma
    tipo_maquina = request.GET.get('maquina')
    ordem = request.GET.get('ordem', '')
    filtro_grupo_maquina = {
        'grupo_maquina': tipo_maquina
    }

    # if tipo_maquina == 'laser':
    #     filtro_grupo_maquina = {
    #         'grupo_maquina__in': ['laser_1', 'laser_2', 'Laser 2 (JFY)','laser_3']
    #     }
    # else:
    #     filtro_grupo_maquina = {
    #         'grupo_maquina': 'plasma'
    #     }

    filtros = {
        'sequenciada': True,
        **filtro_grupo_maquina
    }

    if ordem:
        # Verifica se é uma ordem duplicada; ajuste a condição para funcionar corretamente
        if '.' in ordem or 'dup' in ordem:
            filtros['ordem_duplicada__contains'] = ordem
        else:
            filtros['ordem'] = int(ordem)

    ordens_sequenciadas = (
        Ordem.objects
        .filter(~Q(status_atual='finalizada'), **filtros)
        .annotate(
            prioridade_ordenacao=Coalesce('ordem_prioridade', Value(999999), output_field=IntegerField())
        )
        .order_by('prioridade_ordenacao', 'data_programacao', 'id')
        .select_related('propriedade')
    )
    
    # Converte cada objeto para dicionário e adiciona o display do grupo_maquina
    data = []
    for ordem_obj in ordens_sequenciadas:
        ordem_dict = model_to_dict(ordem_obj, exclude=['qrcode'])  # << aqui
        ordem_dict['grupo_maquina_display'] = ordem_obj.get_grupo_maquina_display()

        propriedade = getattr(ordem_obj, 'propriedade', None)
        if propriedade:
            ordem_dict['descricao_mp'] = propriedade.descricao_mp if propriedade.descricao_mp else None
            ordem_dict['quantidade'] = propriedade.quantidade
            ordem_dict['tipo_chapa'] = propriedade.get_tipo_chapa_display() if hasattr(propriedade, 'tipo_chapa') else None
        else:
            ordem_dict['descricao_mp'] = None
            ordem_dict['quantidade'] = None
            ordem_dict['tipo_chapa'] = None

        data.append(ordem_dict)

    return JsonResponse({'ordens_sequenciadas': data})

def resequenciar_ordem(request):

    # Verifica se o usuário tem o tipo de acesso "pcp"
    if not hasattr(request.user, 'profile') or request.user.profile.tipo_acesso not in ['pcp','supervisor']:
        return JsonResponse({'error': 'Acesso negado: você não tem permissão para excluir ordens.'}, status=403)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            ordem_id = data['ordem_id']

            ordem = get_object_or_404(Ordem, pk=ordem_id)

            if ordem.sequenciada:
                return JsonResponse({'error':'Essa ordem já está sequenciada.'}, status=400)

            if ordem.status_atual != 'aguardando_iniciar':
                return JsonResponse({'error':'Essa ordem precisa está com status "Aguardando iniciar".'}, status=400)

            ordem.sequenciada = True
            ordem.save()
            transaction.on_commit(lambda: notificar_ordem(ordem))

            return JsonResponse({'message': 'Ordem sequenciada com sucesso.'}, status=201)

        except Exception as e:
            return JsonResponse({'error': 'Erro interno no servidor.'}, status=500)

    return JsonResponse({'error': 'Método não permitido.'}, status=405)

def api_ordens_finalizadas(request):

    hoje = localtime(now()).date()

    data_inicio_str = request.GET.get('data_inicio')
    data_fim_str = request.GET.get('data_fim')

    try:
        data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date() if data_inicio_str else hoje - timedelta(days=1)
        data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date() if data_fim_str else hoje
    except ValueError:
        return JsonResponse({'erro': 'Formato de data inválido. Use YYYY-MM-DD.'}, status=400)

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                COALESCE(o.ordem::TEXT, o.ordem_duplicada) AS ordem,
                poc.peca,
                poc.qtd_planejada,

                -- tamanho_chapa: prioridade para tamanho, senão extrai da descricao_mp
                CASE
                    WHEN p.tamanho IS NOT NULL THEN p.tamanho
                    WHEN p.descricao_mp IS NOT NULL THEN SPLIT_PART(p.descricao_mp, ' - ', 2)
                    ELSE NULL
                END AS tamanho_chapa,

                p.quantidade AS qt_chapa,
                p.aproveitamento,

                -- espessura_final = espessura + sigla tipo_chapa
                TRIM(
                    TRIM(COALESCE(p.espessura, '')) ||
                    CASE p.tipo_chapa
                        WHEN 'inox' THEN ' Inox'
                        WHEN 'anti_derrapante' THEN ' A.D'
                        WHEN 'alta_resistencia' THEN ' A.R'
                        ELSE ''
                    END
                ) AS espessura,

                poc.qtd_morta,
                CONCAT(op.matricula, ' - ', op.nome) AS operador,
                TO_CHAR(o.ultima_atualizacao - interval '3 hours', 'DD/MM/YYYY HH24:MI') AS data_finalizacao,
                poc.qtd_boa AS total_produzido,
                p.retalho
            FROM apontamento_v2.core_ordem o
            INNER JOIN apontamento_v2.apontamento_corte_pecasordem poc ON poc.ordem_id = o.id
            LEFT JOIN apontamento_v2.core_propriedadesordem p ON o.id = p.ordem_id
            LEFT JOIN apontamento_v2.cadastro_operador op ON op.id = o.operador_final_id
            WHERE
                o.status_atual = 'finalizada'
                AND (o.ultima_atualizacao - interval '3 hours')::date BETWEEN %s AND %s
                AND poc.qtd_boa > 0
            ORDER BY o.ultima_atualizacao, peca;
        """, [data_inicio, data_fim])
        columns = [col[0] for col in cursor.description]
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]

    return JsonResponse(results, safe=False)

def api_ordens_finalizadas_mp(request):
    with connection.cursor() as cursor:
        cursor.execute("""
        SELECT 
            COALESCE(o.ordem::TEXT, o.ordem_duplicada) AS ordem,
            TO_CHAR(o.ultima_atualizacao - interval '3 hours', 'DD/MM/YYYY HH24:MI') AS data_finalizacao,

            -- tamanho_chapa: usa 'tamanho', senão usa split da descricao_mp
            CASE 
                WHEN p.tamanho IS NOT NULL THEN p.tamanho
                WHEN p.descricao_mp IS NOT NULL THEN SPLIT_PART(p.descricao_mp, ' - ', 2)
                ELSE NULL
            END AS tamanho_chapa,

            p.quantidade AS qt_chapa,
            p.aproveitamento,
            p.descricao_mp AS descricao_chapa,
            TRIM(p.espessura) AS espessura,
            m.nome AS maquina,
            CASE p.tipo_chapa
                WHEN 'inox' THEN ' Inox'
                WHEN 'anti_derrapante' THEN ' A.D'
                WHEN 'alta_resistencia' THEN ' A.R'
                ELSE ''
            END
            AS tipo_chapa,
            CASE 
                WHEN p.retalho THEN 'Sim'
                ELSE 'Não'
                END AS retalho

            FROM apontamento_v2.core_ordem o
            LEFT JOIN apontamento_v2.core_propriedadesordem p ON o.id = p.ordem_id
            LEFT JOIN apontamento_v2.cadastro_maquina m ON o.maquina_id = m.id
        WHERE 
            o.status_atual = 'finalizada'
        AND o.grupo_maquina IN ('laser_1', 'laser_2', 'plasma','laser_3')
        AND (o.ultima_atualizacao AT TIME ZONE 'America/Sao_Paulo')::date >= (NOW() AT TIME ZONE 'America/Sao_Paulo')::date - INTERVAL '1 day'
        AND (o.ultima_atualizacao AT TIME ZONE 'America/Sao_Paulo')::date <= (NOW() AT TIME ZONE 'America/Sao_Paulo')::date
        ORDER BY o.ultima_atualizacao;
        """)

        columns = [col[0] for col in cursor.description]
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]

    return JsonResponse(results, safe=False)

def api_ordens_criadas(request):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT 
                TO_CHAR(o.data_criacao - interval '3 hours', 'DD/MM/YYYY HH24:MI') AS data_criacao,
                COALESCE(o.ordem::TEXT, o.ordem_duplicada) AS ordem,
                poc.peca,
                poc.qtd_planejada,
                o.status_atual,
                m.nome AS maquina,
                TO_CHAR(o.ultima_atualizacao - interval '3 hours', 'DD/MM/YYYY HH24:MI') AS ultima_atualizacao
            FROM apontamento_v2.core_ordem o
            INNER JOIN apontamento_v2.apontamento_corte_pecasordem poc ON poc.ordem_id = o.id
            LEFT JOIN apontamento_v2.cadastro_maquina m ON m.id = o.maquina_id
            WHERE (o.ultima_atualizacao AT TIME ZONE 'America/Sao_Paulo')::date >= (NOW() AT TIME ZONE 'America/Sao_Paulo')::date - INTERVAL '1 day'
            AND (o.ultima_atualizacao AT TIME ZONE 'America/Sao_Paulo')::date <= (NOW() AT TIME ZONE 'America/Sao_Paulo')::date
            ORDER BY o.ultima_atualizacao;
        """)
        columns = [col[0] for col in cursor.description]
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]

    return JsonResponse(results, safe=False)


@login_required
def erp_apontamentos_corte(request):
    return render(request, "apontamento_corte/erp_apontamentos_corte.html")


@login_required
@require_GET
def api_erp_apontamentos_corte(request):
    page = max(int(request.GET.get('page', 1) or 1), 1)
    limit = int(request.GET.get('limit', 50) or 50)
    limit = min(max(limit, 10), 200)

    filtros = {
        'ordem': request.GET.get('ordem', '').strip(),
        'peca': request.GET.get('peca', '').strip(),
        'chapa': request.GET.get('chapa', '').strip(),
        'data_producao_inicio': request.GET.get('data_producao_inicio', '').strip(),
        'data_producao_fim': request.GET.get('data_producao_fim', '').strip(),
        'apontado': request.GET.get('apontado', 'nao').strip().lower(),
    }

    queryset = (
        PecasOrdem.objects
        .filter(
            qtd_boa__gt=0,
            ordem__status_atual='finalizada',
            ordem__grupo_maquina__in=['plasma', 'laser_1', 'laser_2', 'laser_3'],
        )
        .select_related('ordem', 'ordem__maquina', 'ordem__operador_final', 'ordem__propriedade', 'resp_apontamento')
        .prefetch_related('ordem__transferencias_chapa_corte')
        .order_by('-ordem__ultima_atualizacao', '-id')
    )

    if filtros['ordem']:
        queryset = queryset.filter(
            Q(ordem__ordem__icontains=filtros['ordem']) |
            Q(ordem__ordem_duplicada__icontains=filtros['ordem'])
        )

    if filtros['peca']:
        queryset = queryset.filter(peca__icontains=filtros['peca'])

    if filtros['chapa']:
        queryset = queryset.filter(
            Q(ordem__propriedade__descricao_mp__icontains=filtros['chapa']) |
            Q(ordem__propriedade__espessura__icontains=filtros['chapa'])
        )

    data_producao_inicio = parse_date(filtros['data_producao_inicio']) if filtros['data_producao_inicio'] else None
    data_producao_fim = parse_date(filtros['data_producao_fim']) if filtros['data_producao_fim'] else None

    if data_producao_inicio:
        queryset = queryset.filter(ordem__ultima_atualizacao__date__gte=data_producao_inicio)
    if data_producao_fim:
        queryset = queryset.filter(ordem__ultima_atualizacao__date__lte=data_producao_fim)

    if filtros['apontado'] == 'sim':
        queryset = queryset.filter(
            Q(apontado=True) |
            Q(data_apontamento__isnull=False) |
            Q(chave_apontamento__isnull=False)
        ).exclude(chave_apontamento='')
    elif filtros['apontado'] == 'nao':
        queryset = queryset.filter(apontado=False, data_apontamento__isnull=True).filter(
            Q(chave_apontamento__isnull=True) | Q(chave_apontamento='')
        )

    paginator = Paginator(queryset, limit)
    pagina = paginator.get_page(page)

    itens = []
    for item in pagina.object_list:
        ordem = item.ordem
        propriedade = getattr(ordem, 'propriedade', None)
        dados_chapa = _calcular_peso_chapas_corte(propriedade, propriedade.quantidade if propriedade else None)
        operador = ordem.operador_final
        ordem_display = ordem.ordem or ordem.ordem_duplicada or ''
        transferencia = next(iter(ordem.transferencias_chapa_corte.all()), None)
        tipo_chapa_display = ''
        if propriedade and propriedade.tipo_chapa:
            tipo_chapa_display = _normalizar_tipo_chapa_display(propriedade.get_tipo_chapa_display())
        elif dados_chapa and dados_chapa.get('tipo_chapa_display'):
            tipo_chapa_display = _normalizar_tipo_chapa_display(dados_chapa.get('tipo_chapa_display'))

        itens.append({
            'id': item.id,
            'ordem_id': item.ordem_id,
            'ordem': ordem_display,
            'peca': item.peca,
            'qtd_boa': item.qtd_boa,
            'qtd_morta': item.qtd_morta,
            'qtd_planejada': item.qtd_planejada,
            'maquina': ordem.maquina.nome if ordem.maquina else '',
            'operador': f"{operador.matricula} - {operador.nome}" if operador else '',
            'obs_operador': ordem.obs_operador or '',
            'descricao_chapa': propriedade.descricao_mp if propriedade else '',
            'espessura_planilha': dados_chapa.get('espessura_planilha', '') if dados_chapa else '',
            'codigo_chapa': dados_chapa.get('codigo', '') if dados_chapa and dados_chapa.get('encontrou_chapa') else '',
            'tipo_chapa': propriedade.tipo_chapa if propriedade and propriedade.tipo_chapa else dados_chapa.get('tipo_chapa', '') if dados_chapa and dados_chapa.get('encontrou_chapa') else '',
            'tipo_chapa_display': tipo_chapa_display,
            'espessura_mm': dados_chapa.get('espessura_mm', '') if dados_chapa and dados_chapa.get('encontrou_chapa') else '',
            'quantidade_chapas': dados_chapa.get('quantidade_chapas', propriedade.quantidade if propriedade else '') if dados_chapa else '',
            'peso_total': dados_chapa.get('peso_total', '') if dados_chapa and dados_chapa.get('encontrou_chapa') else '',
            'chapa_encontrada': bool(dados_chapa and dados_chapa.get('encontrou_chapa')),
            'transferencia_status': transferencia.status if transferencia else '',
            'transferido_em': localtime(transferencia.transferido_em).strftime('%d/%m/%Y %H:%M') if transferencia and transferencia.transferido_em else '',
            'chave_transferencia': transferencia.chave_transferencia if transferencia else '',
            'transferencia_erro': transferencia.erro if transferencia else '',
            'transferencia_registro_id': transferencia.id if transferencia else None,
            'apontado': item.apontado,
            'tipo_apontamento': item.tipo_apontamento or '',
            'chave_apontamento': item.chave_apontamento or '',
            'erro_apontamento': item.erro_apontamento or '',
            'resp_apontamento': (item.resp_apontamento.get_full_name() or item.resp_apontamento.username) if item.resp_apontamento else '',
            'data_apontamento': localtime(item.data_apontamento).strftime('%d/%m/%Y %H:%M') if item.data_apontamento else '',
            'data_producao': localtime(ordem.ultima_atualizacao).strftime('%d/%m/%Y %H:%M') if ordem.ultima_atualizacao else '',
        })

    return JsonResponse({
        'results': itens,
        'pagination': {
            'page': pagina.number,
            'page_size': limit,
            'total_items': paginator.count,
            'total_pages': paginator.num_pages,
            'has_next': pagina.has_next(),
            'has_previous': pagina.has_previous(),
        }
    })


@login_required
@require_POST
def api_erp_transferir_chapa_corte(request, pk):
    try:
        body = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        body = {}

    tipo_apontamento = (body.get('tipo_apontamento') or 'api').strip().lower()
    if tipo_apontamento not in ('manual', 'api'):
        return JsonResponse({'status': 'error', 'message': 'tipo_apontamento invalido.'}, status=400)

    item = get_object_or_404(
        PecasOrdem.objects.select_related('ordem', 'ordem__propriedade'),
        pk=pk,
        ordem__status_atual='finalizada',
        ordem__grupo_maquina__in=['plasma', 'laser_1', 'laser_2', 'laser_3'],
    )
    ordem = item.ordem
    propriedade = getattr(ordem, 'propriedade', None)
    if not propriedade:
        return JsonResponse({'status': 'error', 'message': 'Propriedades da ordem nao encontradas.'}, status=404)

    dados_chapa = _calcular_peso_chapas_corte(propriedade, propriedade.quantidade)
    if not dados_chapa or not dados_chapa.get('encontrou_chapa') or not dados_chapa.get('codigo'):
        transferencia = _chamar_innovaro_transferir_chapa_corte(ordem, dados_chapa)
        return JsonResponse(
            {
                'status': 'error',
                'message': transferencia.get('erro') or 'Chapa nao encontrada ou sem codigo.',
                'transferencia': transferencia,
            },
            status=422,
        )

    if tipo_apontamento == 'manual':
        transferencia = _registrar_transferencia_chapa_corte_manual(ordem, dados_chapa, request.user)
    else:
        transferencia = _chamar_innovaro_transferir_chapa_corte(ordem, dados_chapa)

    if transferencia.get('erro'):
        return JsonResponse(
            {
                'status': 'error',
                'message': transferencia.get('erro'),
                'transferencia': transferencia,
            },
            status=502 if tipo_apontamento == 'api' else 422,
        )

    return JsonResponse({
        'status': 'success',
        'message': 'Transferencia registrada com sucesso.',
        'transferencia': transferencia,
    })


@login_required
@require_POST
def api_erp_apontar_item_corte(request, pk):
    try:
        body = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        body = {}

    tipo_apontamento = (body.get('tipo_apontamento') or 'manual').strip().lower()
    if tipo_apontamento not in ('manual', 'api'):
        return JsonResponse({'status': 'error', 'message': 'tipo_apontamento invalido.'}, status=400)

    item = get_object_or_404(
        PecasOrdem.objects.select_related('ordem', 'ordem__propriedade', 'resp_apontamento'),
        pk=pk,
        ordem__status_atual='finalizada',
        ordem__grupo_maquina__in=['plasma', 'laser_1', 'laser_2', 'laser_3'],
    )

    if item.apontado:
        resp_ref = getattr(item, 'resp_apontamento', None)
        return JsonResponse(
            {
                'status': 'error',
                'message': 'Este item ja foi apontado e nao pode ser apontado novamente.',
                'already_apontado': True,
                'detalhes': {
                    'item_id': item.id,
                    'ordem_id': item.ordem_id,
                    'tipo_apontamento': item.tipo_apontamento or '',
                    'data_apontamento': localtime(item.data_apontamento).strftime('%d/%m/%Y %H:%M') if item.data_apontamento else '',
                    'resp_apontamento': (resp_ref.get_full_name() or resp_ref.username) if resp_ref else '',
                    'chave_apontamento': item.chave_apontamento or '',
                },
            },
            status=409
        )

    if tipo_apontamento == 'api' and (item.qtd_morta or 0) > 0:
        msg_qtd_morta = (
            'Apontamento via API bloqueado automaticamente: item com qtd_morta > 0. '
            'A funcionalidade de desvio precisa ser ajustada na API.'
        )
        item.erro_apontamento = msg_qtd_morta
        item.tipo_apontamento = 'api'
        item.resp_apontamento = request.user
        item.save(update_fields=['erro_apontamento', 'tipo_apontamento', 'resp_apontamento'])
        return JsonResponse(
            {
                'status': 'error',
                'message': 'Apontamento via API bloqueado para item com qtd_morta.',
                'description': msg_qtd_morta,
            },
            status=422
        )

    payload_integracao = None
    if tipo_apontamento == 'api':
        propriedade = getattr(item.ordem, 'propriedade', None)
        dados_chapa = _calcular_peso_chapas_corte(
            propriedade,
            propriedade.quantidade if propriedade else None,
        ) or {}
        codigo_chapa_ordem = dados_chapa.get('codigo')
        transferencia = (
            TransferenciaChapaCorte.objects
            .filter(ordem_id=item.ordem_id, status='sucesso')
            .order_by('-transferido_em', '-id')
            .first()
        )
        if not transferencia and _item_precisa_transferencia_chapa_corte(item, codigo_chapa_ordem):
            return JsonResponse(
                {
                    'status': 'error',
                    'message': 'Transfira a chapa antes de apontar este item.',
                },
                status=409
            )

        peca_valida, erro_peca, ficha_tecnica = _resolver_ficha_tecnica_chapa_corte(
            item,
            transferencia,
            codigo_chapa_ordem,
        )
        if not peca_valida:
            _registrar_erro_apontamento_api_corte(item, erro_peca, request.user)
            return JsonResponse(
                {
                    'status': 'error',
                    'message': 'Nao foi possivel montar a ficha tecnica para validar a chapa da peca.',
                    'description': erro_peca,
                },
                status=422
            )

        payload_integracao = _payload_apontamento_item_corte(item, ficha_tecnica)
        print(
            "[CORTE][INNOVARO][APONTAMENTO][BODY]",
            json.dumps(payload_integracao, ensure_ascii=False, indent=2),
        )

        try:
            response_integracao = _post_apontamento_erp_corte(payload_integracao)
        except requests.RequestException as exc:
            return JsonResponse(
                {
                    'status': 'error',
                    'message': f'Falha de comunicacao com API ERP: {exc}',
                    'payload_enviado': payload_integracao,
                },
                status=502
            )

        try:
            resposta_api_json = response_integracao.json()
        except ValueError:
            resposta_api_json = None

        if not response_integracao.ok:
            descricao_erro = ''
            if isinstance(resposta_api_json, dict):
                descricao_erro = str(resposta_api_json.get('description') or '')

            try:
                retorno_texto = response_integracao.text[:500]
            except Exception:
                retorno_texto = 'Sem detalhes'

            item.erro_apontamento = descricao_erro or retorno_texto
            item.tipo_apontamento = 'api'
            item.resp_apontamento = request.user
            item.save(update_fields=['erro_apontamento', 'tipo_apontamento', 'resp_apontamento'])

            return JsonResponse(
                {
                    'status': 'error',
                    'message': f'API ERP retornou status {response_integracao.status_code}.',
                    'payload_enviado': payload_integracao,
                    'description': descricao_erro,
                    'retorno_api': retorno_texto,
                },
                status=502
            )

        if isinstance(resposta_api_json, dict):
            status_erp = str(resposta_api_json.get('status') or '').strip()
            if status_erp.lower() == 'error':
                descricao_erro = str(resposta_api_json.get('description') or 'Erro retornado pela API ERP.')
                if _erro_depositodest_indefinido_corte(descricao_erro):
                    payload_tentativa, retorno_tentativa, tentativas = (
                        _tentar_apontamento_depositodest_processos_alternativos_corte(payload_integracao)
                    )
                    if payload_tentativa and retorno_tentativa:
                        payload_original = payload_integracao
                        payload_integracao = payload_tentativa
                        resposta_api_json = retorno_tentativa
                        item.chave_apontamento, aviso_chave = _normalizar_chave_apontamento_erp(
                            resposta_api_json,
                            payload_integracao,
                        )
                        avisos = [
                            aviso_chave,
                            _mensagem_ficha_tecnica_apontamento(payload_integracao.get('fichaTecnica')),
                            _mensagem_processo_alternativo_depositodest(
                                payload_original,
                                payload_integracao,
                            ),
                        ]
                        item.erro_apontamento = ' '.join(aviso for aviso in avisos if aviso) or None
                    else:
                        item.erro_apontamento = descricao_erro
                        item.tipo_apontamento = 'api'
                        item.resp_apontamento = request.user
                        item.save(update_fields=['erro_apontamento', 'tipo_apontamento', 'resp_apontamento'])
                        return JsonResponse(
                            {
                                'status': 'error',
                                'message': 'API ERP retornou erro de negocio.',
                                'description': descricao_erro,
                                'payload_enviado': payload_integracao,
                                'retorno_api': resposta_api_json,
                                'tentativas_processos_alternativos': tentativas,
                            },
                            status=422
                        )
                else:
                    item.erro_apontamento = descricao_erro
                    item.tipo_apontamento = 'api'
                    item.resp_apontamento = request.user
                    item.save(update_fields=['erro_apontamento', 'tipo_apontamento', 'resp_apontamento'])
                    return JsonResponse(
                        {
                            'status': 'error',
                            'message': 'API ERP retornou erro de negocio.',
                            'description': descricao_erro,
                            'payload_enviado': payload_integracao,
                            'retorno_api': resposta_api_json,
                        },
                        status=422
                    )
            elif status_erp.lower() == 'success':
                item.chave_apontamento, aviso_chave = _normalizar_chave_apontamento_erp(
                    resposta_api_json,
                    payload_integracao,
                )
                item.erro_apontamento = aviso_chave or _mensagem_ficha_tecnica_apontamento(
                    payload_integracao.get('fichaTecnica')
                )
            else:
                item.erro_apontamento = str(resposta_api_json)
                item.tipo_apontamento = 'api'
                item.resp_apontamento = request.user
                item.save(update_fields=['erro_apontamento', 'tipo_apontamento', 'resp_apontamento'])
                return JsonResponse(
                    {
                        'status': 'error',
                        'message': 'Resposta da API ERP em formato inesperado.',
                        'payload_enviado': payload_integracao,
                        'retorno_api': resposta_api_json,
                    },
                    status=502
                )
        else:
            item.erro_apontamento = (response_integracao.text or '')[:2000]
            item.tipo_apontamento = 'api'
            item.resp_apontamento = request.user
            item.save(update_fields=['erro_apontamento', 'tipo_apontamento', 'resp_apontamento'])
            return JsonResponse(
                {
                    'status': 'error',
                    'message': 'API ERP nao retornou JSON valido.',
                    'payload_enviado': payload_integracao,
                    'retorno_api': item.erro_apontamento,
                },
                status=502
            )

    item.apontado = True
    item.tipo_apontamento = tipo_apontamento
    item.resp_apontamento = request.user
    item.data_apontamento = now()
    if tipo_apontamento == 'manual':
        item.chave_apontamento = f"MANUAL-CORTE-ITEM-{item.id}"
        item.erro_apontamento = None
    item.save(update_fields=[
        'apontado',
        'tipo_apontamento',
        'resp_apontamento',
        'data_apontamento',
        'chave_apontamento',
        'erro_apontamento',
    ])

    return JsonResponse({
        'status': 'success',
        'message': 'Apontamento registrado com sucesso.',
        'tipo_apontamento': tipo_apontamento,
        'chave_apontamento': item.chave_apontamento or '',
        'data_apontamento': localtime(item.data_apontamento).strftime('%d/%m/%Y %H:%M') if item.data_apontamento else '',
        'payload_enviado': payload_integracao,
    })


@login_required
@require_POST
def api_erp_apontar_itens_corte_bloco(request):
    try:
        body = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        body = {}

    tipo_apontamento = (body.get('tipo_apontamento') or 'manual').strip().lower()
    if tipo_apontamento not in ('manual', 'api'):
        return JsonResponse({'status': 'error', 'message': 'tipo_apontamento invalido.'}, status=400)

    ids = body.get('ids') or []
    if not isinstance(ids, list):
        return JsonResponse({'status': 'error', 'message': 'ids deve ser uma lista.'}, status=400)

    ids = [int(item_id) for item_id in ids if str(item_id).isdigit()]
    if not ids:
        return JsonResponse({'status': 'error', 'message': 'Selecione ao menos um item.'}, status=400)

    itens = list(
        PecasOrdem.objects
        .select_related('ordem', 'ordem__propriedade', 'resp_apontamento')
        .filter(
            pk__in=ids,
            ordem__status_atual='finalizada',
            ordem__grupo_maquina__in=['plasma', 'laser_1', 'laser_2', 'laser_3'],
        )
        .order_by('id')
    )

    itens_por_id = {item.id: item for item in itens}
    erros = []
    itens_validos = []
    fichas_tecnicas = {}
    dados_chapa_por_ordem = {}

    for item_id in ids:
        item = itens_por_id.get(item_id)
        if not item:
            erros.append({'id': item_id, 'erro': 'Item nao encontrado.'})
            continue

        if item.apontado:
            erros.append({'id': item.id, 'erro': 'Item ja apontado.'})
            continue

        if tipo_apontamento == 'api':
            if item.ordem_id not in dados_chapa_por_ordem:
                propriedade = getattr(item.ordem, 'propriedade', None)
                dados_chapa_por_ordem[item.ordem_id] = _calcular_peso_chapas_corte(
                    propriedade,
                    propriedade.quantidade if propriedade else None,
                )
            dados_chapa = dados_chapa_por_ordem.get(item.ordem_id) or {}
            codigo_chapa_ordem = dados_chapa.get('codigo')

            transferencia = (
                TransferenciaChapaCorte.objects
                .filter(ordem_id=item.ordem_id, status='sucesso')
                .order_by('-transferido_em', '-id')
                .first()
            )
            if not transferencia and _item_precisa_transferencia_chapa_corte(item, codigo_chapa_ordem):
                erros.append({'id': item.id, 'erro': 'Transfira a chapa antes de apontar este item.'})
                continue

            peca_valida, erro_peca, ficha_tecnica = _resolver_ficha_tecnica_chapa_corte(
                item,
                transferencia,
                codigo_chapa_ordem,
            )
            if not peca_valida:
                _registrar_erro_apontamento_api_corte(item, erro_peca, request.user)
                erros.append({'id': item.id, 'erro': erro_peca})
                continue
            if ficha_tecnica:
                fichas_tecnicas[item.id] = ficha_tecnica

        if tipo_apontamento == 'api' and (item.qtd_morta or 0) > 0:
            msg_qtd_morta = (
                'Apontamento via API bloqueado automaticamente: item com qtd_morta > 0. '
                'A funcionalidade de desvio precisa ser ajustada na API.'
            )
            item.erro_apontamento = msg_qtd_morta
            item.tipo_apontamento = 'api'
            item.resp_apontamento = request.user
            item.save(update_fields=['erro_apontamento', 'tipo_apontamento', 'resp_apontamento'])
            erros.append({'id': item.id, 'erro': msg_qtd_morta})
            continue

        itens_validos.append(item)

    if not itens_validos:
        return JsonResponse(
            {
                'status': 'error',
                'message': 'Nenhum item valido para apontar.',
                'erros': erros,
            },
            status=422
        )

    if tipo_apontamento == 'manual':
        sucessos = []
        for item in itens_validos:
            item.apontado = True
            item.tipo_apontamento = 'manual'
            item.resp_apontamento = request.user
            item.data_apontamento = now()
            item.chave_apontamento = f"MANUAL-CORTE-ITEM-{item.id}"
            item.erro_apontamento = None
            item.save(update_fields=[
                'apontado',
                'tipo_apontamento',
                'resp_apontamento',
                'data_apontamento',
                'chave_apontamento',
                'erro_apontamento',
            ])
            sucessos.append({
                'id': item.id,
                'chave_apontamento': item.chave_apontamento,
            })

        return JsonResponse({
            'status': 'success',
            'message': 'Apontamento manual em bloco registrado com sucesso.',
            'tipo_apontamento': tipo_apontamento,
            'sucessos': sucessos,
            'erros': erros,
        })

    payload_integracao = [
        _payload_apontamento_item_corte(item, fichas_tecnicas.get(item.id))
        for item in itens_validos
    ]
    print(
        "[CORTE][INNOVARO][APONTAMENTO_BLOCO][BODY]",
        json.dumps(payload_integracao, ensure_ascii=False, indent=2),
    )

    try:
        response_integracao = _post_apontamento_erp_corte(payload_integracao)
    except requests.RequestException as exc:
        return JsonResponse(
            {
                'status': 'error',
                'message': f'Falha de comunicacao com API ERP: {exc}',
                'payload_enviado': payload_integracao,
                'erros': erros,
            },
            status=502
        )

    try:
        resposta_api_json = response_integracao.json()
    except ValueError:
        resposta_api_json = None

    if not response_integracao.ok:
        retorno_texto = response_integracao.text[:500] if response_integracao.text else 'Sem detalhes'
        for item in itens_validos:
            item.erro_apontamento = retorno_texto
            item.tipo_apontamento = 'api'
            item.resp_apontamento = request.user
            item.save(update_fields=['erro_apontamento', 'tipo_apontamento', 'resp_apontamento'])

        return JsonResponse(
            {
                'status': 'error',
                'message': f'API ERP retornou status {response_integracao.status_code}.',
                'payload_enviado': payload_integracao,
                'retorno_api': retorno_texto,
                'erros': erros,
            },
            status=502
        )

    respostas = resposta_api_json if isinstance(resposta_api_json, list) else [resposta_api_json]
    sucessos = []
    erro_negocio = False

    for index, item in enumerate(itens_validos):
        retorno_item = respostas[index] if index < len(respostas) else resposta_api_json
        if isinstance(retorno_item, dict) and str(retorno_item.get('status') or '').lower() == 'error':
            descricao_erro = str(retorno_item.get('description') or 'Erro retornado pela API ERP.')
            if _erro_depositodest_indefinido_corte(descricao_erro):
                payload_tentativa, retorno_tentativa, tentativas = (
                    _tentar_apontamento_depositodest_processos_alternativos_corte(payload_integracao[index])
                )
                if payload_tentativa and retorno_tentativa:
                    item.chave_apontamento, aviso_chave = _normalizar_chave_apontamento_erp(
                        retorno_tentativa,
                        payload_tentativa,
                    )
                    avisos = [
                        aviso_chave,
                        _mensagem_ficha_tecnica_apontamento(payload_tentativa.get('fichaTecnica')),
                        _mensagem_processo_alternativo_depositodest(
                            payload_integracao[index],
                            payload_tentativa,
                        ),
                    ]
                    item.erro_apontamento = ' '.join(aviso for aviso in avisos if aviso) or None
                    item.apontado = True
                    item.tipo_apontamento = 'api'
                    item.resp_apontamento = request.user
                    item.data_apontamento = now()
                    item.save(update_fields=[
                        'apontado',
                        'tipo_apontamento',
                        'resp_apontamento',
                        'data_apontamento',
                        'chave_apontamento',
                        'erro_apontamento',
                    ])
                    payload_integracao[index] = payload_tentativa
                    sucessos.append({
                        'id': item.id,
                        'chave_apontamento': item.chave_apontamento,
                        'processo': payload_tentativa.get('processo'),
                    })
                    continue
                retorno_item['tentativas_processos_alternativos'] = tentativas
            item.erro_apontamento = descricao_erro
            item.tipo_apontamento = 'api'
            item.resp_apontamento = request.user
            item.save(update_fields=['erro_apontamento', 'tipo_apontamento', 'resp_apontamento'])
            erros.append({'id': item.id, 'erro': descricao_erro, 'retorno_api': retorno_item})
            erro_negocio = True
            continue

        item.chave_apontamento, aviso_chave = _normalizar_chave_apontamento_erp(
            retorno_item if isinstance(retorno_item, dict) else {},
            payload_integracao[index],
        )
        aviso_ficha = _mensagem_ficha_tecnica_apontamento(payload_integracao[index].get('fichaTecnica'))
        item.erro_apontamento = aviso_chave or aviso_ficha
        item.apontado = True
        item.tipo_apontamento = 'api'
        item.resp_apontamento = request.user
        item.data_apontamento = now()
        item.save(update_fields=[
            'apontado',
            'tipo_apontamento',
            'resp_apontamento',
            'data_apontamento',
            'chave_apontamento',
            'erro_apontamento',
        ])
        sucessos.append({
            'id': item.id,
            'chave_apontamento': item.chave_apontamento,
        })

    return JsonResponse({
        'status': 'success' if sucessos else 'error',
        'message': 'Apontamento em bloco enviado para o ERP.' if sucessos else 'Nenhum item foi apontado.',
        'tipo_apontamento': tipo_apontamento,
        'sucessos': sucessos,
        'erros': erros,
        'payload_enviado': payload_integracao,
        'retorno_api': resposta_api_json,
    }, status=207 if erro_negocio and sucessos else (422 if not sucessos else 200))

def excluir_ordem(request):
    """
    API para excluir ordens apenas do corte.
    """

    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)

    try:
        data = json.loads(request.body)
        ordem_id = data.get('ordem_id')
        motivo_id = data.get('motivo')

        print(ordem_id)
        print(motivo_id)
        
        ordem = get_object_or_404(Ordem, pk=ordem_id)
        motivo = get_object_or_404(MotivoExclusao, pk=int(motivo_id))

        # Atualiza os campos da ordem
        ordem.sequenciada = None
        ordem.status_atual = 'aguardando_iniciar'
        ordem.motivo_retirar_sequenciada = motivo
        
        ordem.save()
        transaction.on_commit(lambda: notificar_ordem(ordem))

        # Apaga os processos associados a essa ordem
        OrdemProcesso.objects.filter(ordem=ordem).delete()

        return JsonResponse({'success': 'Ordem excluída com sucesso.'}, status=201)

    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
def definir_prioridade(request):
    """
    Define a prioridade de uma ordem de corte.
    
    - Se já existir uma ordem com a prioridade escolhida, ela terá a prioridade removida.
    - A nova ordem recebe a prioridade definida.
    """

    try:
        data = json.loads(request.body)
        ordem_id = data.get('ordemId')
        prioridade = data.get('prioridade')

        if not ordem_id or not prioridade:
            return JsonResponse({'error': 'Parâmetros ordemId e prioridade são obrigatórios.'}, status=400)

        ordem = get_object_or_404(Ordem, pk=ordem_id)

        with transaction.atomic():
            # Remove a prioridade de outras ordens, se já atribuída
            Ordem.objects.filter(ordem_prioridade=prioridade, grupo_maquina=ordem.grupo_maquina).exclude(pk=ordem_id).update(ordem_prioridade=None)

            # Atualiza a ordem solicitada com a nova prioridade
            ordem.ordem_prioridade = prioridade
            ordem.save()
            transaction.on_commit(lambda: notificar_ordem(ordem))

        return JsonResponse({'success': 'Prioridade definida com sucesso.'}, status=201)

    except Ordem.DoesNotExist:
        return JsonResponse({'error': 'Ordem não encontrada.'}, status=404)

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Formato JSON inválido.'}, status=400)

    except Exception as e:
        return JsonResponse({'error': f'Ocorreu um erro inesperado: {str(e)}'}, status=500)
    
class ProcessarArquivoView(View):
    def post(self, request):
        
        """
        Faz o upload do arquivo, processa os dados e retorna como JSON.
        """

        # Verifica se o arquivo foi enviado
        uploaded_file = request.FILES.get('file')
        tipo_maquina = request.POST.get('tipoMaquina')
        print(tipo_maquina)
        print(uploaded_file)
        
        if not uploaded_file:
            return JsonResponse({'error': 'Nenhum arquivo enviado.'}, status=400)

        # Extrai a numeração do nome do arquivo
        numeracao = extrair_numeracao(uploaded_file.name)
        # deverá ser tratado de forma diferente dos laser
            
        if numeracao:
            # Verifica se a numeração já existe no banco de dados
            if Ordem.objects.filter(ordem=int(numeracao),grupo_maquina=tipo_maquina).exists():
                return JsonResponse({
                    'error': f"A ordem {numeracao} já foi gerada.",
                    'exists': True,
                }, status=400)
        else:
            return JsonResponse({'error': 'Numeração não encontrada no nome do arquivo.'}, status=400)

        try:
            # Ler o arquivo Excel enviado
            if tipo_maquina == 'laser_3':
                ordem_producao_excel = ET.parse(uploaded_file)
            else:
                ordem_producao_excel = pd.read_excel(uploaded_file)

            # Realizar o tratamento da planilha
            if tipo_maquina=='plasma':
                excel_tratado,propriedades = tratamento_planilha_plasma(ordem_producao_excel)
            elif tipo_maquina == 'laser_2':
                try:
                    # Tenta carregar a aba em inglês
                    ordem_producao_excel_2 = pd.read_excel(uploaded_file, sheet_name='AllPartsList')
                    ordem_producao_excel_3 = pd.read_excel(uploaded_file, sheet_name='Cost List')
                except ValueError:
                    try:
                        # Se não achar, tenta a aba em português
                        ordem_producao_excel_2 = pd.read_excel(uploaded_file, sheet_name='Lista de Todas as Peças')
                        ordem_producao_excel_3 = pd.read_excel(uploaded_file, sheet_name='Lista de custos')
                    except ValueError:
                        # Se nenhuma das duas existir, levanta erro claro
                        raise ValueError("Nenhuma das abas 'AllPartsList' ou 'Lista de Todas as Peças' foi encontrada na planilha.")
                
                excel_tratado,propriedades = tratamento_planilha_laser2(ordem_producao_excel,ordem_producao_excel_2,ordem_producao_excel_3)
            elif tipo_maquina == 'laser_3':
                excel_tratado,propriedades = tratamento_planilha_laser3(ordem_producao_excel)

            # Converter para uma lista de dicionários
            relevant_data = excel_tratado.to_dict(orient='records')

            # Retornar os dados processados como JSON
            return JsonResponse({'data': relevant_data})
        except Exception as e:
            # Lidar com possíveis erros durante o processamento
            return JsonResponse({'error': f"Erro ao processar o arquivo: {str(e)}"}, status=500)

class SalvarArquivoView(View):

    @staticmethod
    def corrigir_aproveitamento(valor):
        """
        Corrige valores de aproveitamento que foram inseridos de forma incorreta.
        Exemplo:
        - 9855 -> 0.9855
        - 006 -> 0.6
        - 49.85 -> 0.4985
        """
        valor = str(valor)
        valor = valor.replace("%","").replace(",",".")

        if valor is None:
            return 0  # Garante que valores nulos não quebrem a ordenação

        try:
            valor = float(valor)

            # Se for maior que 1, assumimos que foi multiplicado por 10^n e ajustamos
            if valor > 1:
                num_digitos = len(str(int(valor)))  # Conta os dígitos inteiros
                valor = valor / (10 ** num_digitos)  # Ajusta dividindo por 10^n

            # Se for menor que 0.01, assume erro de casas decimais e ajusta
            elif valor < 0.001:
                valor = valor * 1000  # Multiplica por 10 e arredonda para 1 casa decimal
            elif valor < 0.01:
                valor = valor * 100  # Multiplica por 10 e arredonda para 1 casa decimal
            
            return valor

        except ValueError:
            return 0  # Se não for possível converter, assume 0

    def post(self, request):

        """
        Recebe o caminho do arquivo e os dados confirmados pelo usuário.
        Salva as informações no banco de dados.
        """

        uploaded_file = request.FILES.get('file')
        descricao = request.POST.get('descricao')
        tipo_chapa = request.POST.get('tipo_chapa')
        retalho = request.POST.get('retalho') == 'true'  # Converte 'true' para True e 'false' para False
        tipo_maquina = request.POST.get('maquina')
        maquina_planejada = request.POST.get('maquinaPlanejada')
        data_programacao = request.POST.get('dataProgramacao')

        if not uploaded_file:
            return JsonResponse({'error': 'Nenhum arquivo enviado.'}, status=400)

        numeracao_op = extrair_numeracao(uploaded_file.name)

        # Ler o arquivo Excel enviado
        if tipo_maquina == 'laser_3':
            ordem_producao_excel = ET.parse(uploaded_file)
        else:
            ordem_producao_excel = pd.read_excel(uploaded_file)

        tipo_maquina_tratada = tipo_maquina.replace("_"," ").title()

        if tipo_maquina == 'plasma':
            if not maquina_planejada:
                return JsonResponse({'error': 'Selecione a máquina de plasma.'}, status=400)
            tipo_maquina_object = get_object_or_404(Maquina, pk=int(maquina_planejada), setor__nome='corte')
        else:
            tipo_maquina_object = get_object_or_404(Maquina, nome__contains=tipo_maquina_tratada) if tipo_maquina in ['laser_1','laser_2','laser_3'] else None

        if tipo_maquina =='plasma':
            excel_tratado,propriedades = tratamento_planilha_plasma(ordem_producao_excel)
        elif tipo_maquina_object.nome=='Laser 2 (JFY)':

            # apenas para o laser2
            try:
                # Tenta carregar a aba em inglês
                ordem_producao_excel_2 = pd.read_excel(uploaded_file, sheet_name='AllPartsList')
                ordem_producao_excel_3 = pd.read_excel(uploaded_file, sheet_name='Cost List')
            except ValueError:
                try:
                    # Se não achar, tenta a aba em português
                    ordem_producao_excel_2 = pd.read_excel(uploaded_file, sheet_name='Lista de Todas as Peças')
                    ordem_producao_excel_3 = pd.read_excel(uploaded_file, sheet_name='Lista de custos')
                except ValueError:
                    # Se nenhuma das duas existir, levanta erro claro
                    raise ValueError("Nenhuma das abas 'AllPartsList' ou 'Lista de Todas as Peças' foi encontrada na planilha.")

            excel_tratado,propriedades = tratamento_planilha_laser2(ordem_producao_excel,ordem_producao_excel_2,ordem_producao_excel_3)
        elif tipo_maquina_object.nome=='Laser 1':

            comprimento = request.POST.get('comprimento')
            largura=request.POST.get('largura')

            espessura=get_object_or_404(Espessura, pk=request.POST.get('espessura'))
            
            # apenas para o laser1
            ordem_producao_excel_2 = pd.read_excel(uploaded_file, sheet_name='Nestings_Cost', dtype={'Unnamed: 3': str})
            excel_tratado,propriedades = tratamento_planilha_laser1(ordem_producao_excel,ordem_producao_excel_2,comprimento,largura,espessura.nome)
        elif tipo_maquina_object.nome == 'Laser 3 Trumpf':
            excel_tratado,propriedades = tratamento_planilha_laser3(ordem_producao_excel)

        pecas = excel_tratado.to_dict(orient='records')  # Converter para uma lista de dicionários

        with transaction.atomic():

            # buscar tempo estimado
            for prop in propriedades:
                tempo_estimado = prop['tempo_estimado_total']

            # criar ordem
            nova_ordem = Ordem.objects.create(
                ordem=int(numeracao_op),
                obs=descricao,
                grupo_maquina=tipo_maquina,
                data_programacao=data_programacao,
                maquina=tipo_maquina_object,
                tempo_estimado=tempo_estimado
            )
            
            # salvar propriedades
            for prop in propriedades:

                PropriedadesOrdem.objects.create(
                    ordem=nova_ordem,
                    descricao_mp=prop['descricao_mp'],
                    espessura=str(prop['espessura']).rstrip(),
                    quantidade=prop['quantidade'],
                    aproveitamento=SalvarArquivoView.corrigir_aproveitamento(prop['aproveitamento']),
                    tipo_chapa=tipo_chapa,
                    retalho=retalho,
                )
            
            # salvar peças
            for peca in pecas:
                print(peca['qtd_planejada'])
                if peca['qtd_planejada'] == 0:
                    continue

                PecasOrdem.objects.create(
                    ordem=nova_ordem,
                    peca=peca['peca'],
                    qtd_planejada=peca['qtd_planejada']
                )

            transaction.on_commit(lambda: notificar_ordem(nova_ordem))

        return JsonResponse({'message': 'Dados salvos com sucesso!'})
    
#### dashboard

def dashboard(request):

    return render(request, 'dashboard/dashboard-corte.html')

def parse_tempo(hora_str):
    h, m, s = map(float, hora_str.split(':'))
    return timedelta(hours=h, minutes=m, seconds=s)

def merge_metricas(horas_producao, horas_parada):
    resultado = defaultdict(dict)

    # Produção
    for item in horas_producao:
        key = (item['maquina'], item['dia'])
        resultado[key]['maquina'] = item['maquina']
        resultado[key]['dia'] = item['dia']
        resultado[key]['producao_total'] = item.get('total_dia', '00:00:00')

    # Parada
    for item in horas_parada:
        key = (item['maquina'], item['dia'])
        resultado[key].setdefault('maquina', item['maquina'])
        resultado[key].setdefault('dia', item['dia'])
        resultado[key]['parada_total'] = item.get('total_dia', '00:00:00')

    # Calcular tempo ocioso
    for key, val in resultado.items():
        prod = parse_tempo(val.get('producao_total', '00:00:00'))
        parada = parse_tempo(val.get('parada_total', '00:00:00'))
        usado = prod + parada

        ocioso = timedelta(hours=20) - usado
        ocioso = max(ocioso, timedelta(seconds=0))  # nunca negativo
        val['tempo_ocioso'] = formatar_timedelta(ocioso)

    return sorted(resultado.values(), key=lambda x: (x['dia'], x['maquina']))

@login_required
def indicador_hora_operacao_maquina(request):
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    maquina_param = request.GET.get('maquina')

    horas_producao = hora_operacao_maquina(maquina_param, data_inicio, data_fim)
    horas_parada = hora_parada_maquina(maquina_param, data_inicio, data_fim)

    resultado_unificado = merge_metricas(horas_producao, horas_parada)

    return JsonResponse(resultado_unificado, safe=False)

@login_required
def indicador_ordem_finalizada_maquina(request):
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')

    resultado = ordem_por_maquina(data_inicio, data_fim)

    return JsonResponse(resultado)

@login_required
def indicador_peca_produzida_maquina(request):
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')

    resultado = producao_por_maquina(data_inicio, data_fim)

    return JsonResponse(resultado)    
