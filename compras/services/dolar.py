from datetime import date, datetime, timedelta

import requests
from django.core.cache import cache


CACHE_KEY = 'compras_cotacao_dolar_atual'
CACHE_TTL = 30
AWESOME_API_URL = 'https://economia.awesomeapi.com.br/json/daily/USD-BRL/1'
BCB_PTAX_URL = (
    'https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/'
    'CotacaoDolarPeriodo(dataInicial=@dataInicial,dataFinalCotacao=@dataFinalCotacao)'
)


def _formatar_data_bcb(valor):
    return valor.strftime('%m-%d-%Y')


def _formatar_data_hora(raw_value):
    if not raw_value:
        return ''

    formatos = (
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d %H:%M:%S.%f',
    )
    for formato in formatos:
        try:
            data_hora = datetime.strptime(raw_value, formato)
            return data_hora.strftime('%d/%m/%Y %H:%M')
        except ValueError:
            continue

    return str(raw_value)


def _consultar_awesomeapi():
    response = requests.get(AWESOME_API_URL, timeout=10)
    response.raise_for_status()

    payload = response.json()
    if not payload:
        raise ValueError('Resposta vazia da AwesomeAPI.')

    cotacao = payload[0]
    return {
        'moeda': 'USD/BRL',
        'cotacao_compra': cotacao.get('bid'),
        'cotacao_venda': cotacao.get('ask'),
        'data_hora_cotacao': cotacao.get('create_date'),
        'data_hora_formatada': _formatar_data_hora(cotacao.get('create_date')),
        'fonte': 'AwesomeAPI',
        'modo': 'tempo_real',
        'atualizado_em': datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
    }


def _consultar_bcb_ptax():
    data_final = date.today()
    data_inicial = data_final - timedelta(days=7)
    params = {
        '@dataInicial': f"'{_formatar_data_bcb(data_inicial)}'",
        '@dataFinalCotacao': f"'{_formatar_data_bcb(data_final)}'",
        '$top': 100,
        '$format': 'json',
        '$select': 'cotacaoCompra,cotacaoVenda,dataHoraCotacao',
    }

    response = requests.get(BCB_PTAX_URL, params=params, timeout=10)
    response.raise_for_status()

    valores = response.json().get('value', [])
    if not valores:
        raise ValueError('Nenhuma cotacao PTAX disponivel no periodo consultado.')

    valores.sort(key=lambda item: item.get('dataHoraCotacao') or '', reverse=True)
    cotacao = valores[0]
    return {
        'moeda': 'USD/BRL',
        'cotacao_compra': cotacao.get('cotacaoCompra'),
        'cotacao_venda': cotacao.get('cotacaoVenda'),
        'data_hora_cotacao': cotacao.get('dataHoraCotacao'),
        'data_hora_formatada': _formatar_data_hora(cotacao.get('dataHoraCotacao')),
        'fonte': 'Banco Central do Brasil (PTAX)',
        'modo': 'fallback_oficial',
        'atualizado_em': datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
    }


def get_cotacao_dolar_atual(force_refresh=False):
    if not force_refresh:
        cached = cache.get(CACHE_KEY)
        if cached is not None:
            return cached

    ultima_excecao = None
    for consulta in (_consultar_awesomeapi, _consultar_bcb_ptax):
        try:
            resultado = consulta()
            cache.set(CACHE_KEY, resultado, CACHE_TTL)
            return resultado
        except Exception as exc:
            ultima_excecao = exc

    raise ValueError(f'Falha ao consultar cotacao do dolar: {ultima_excecao}')
