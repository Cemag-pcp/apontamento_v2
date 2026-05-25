from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import requests
from django.conf import settings


PLOOMES_ORDERS_URL = 'https://api2.ploomes.com/Orders'
PLOOMES_TIMEZONE = ZoneInfo(settings.TIME_ZONE)
PAGE_SIZE = 50

COR_FIELD_KEY = 'quote_product_76A1F57A-B40F-4C4E-B412-44361EB118D8'
ORDER_FIELD_KEY = 'order_B3C1AABD-00AB-4306-8163-2D2BF76051A3'


class PloomesConfigError(Exception):
    pass


class PloomesAPIError(Exception):
    pass


@dataclass(frozen=True)
class ConfPedidoItem:
    chave_pedido: str
    deal_id: str
    data_criacao: str
    quote_id: int | None
    contato: str
    codigo_produto: str
    cor: str
    observacao: str

    def as_dict(self) -> dict:
        return {
            'chave_pedido': self.chave_pedido,
            'deal_id': self.deal_id,
            'data_criacao': self.data_criacao,
            'quote_id': self.quote_id,
            'contato': self.contato,
            'codigo_produto': self.codigo_produto,
            'cor': self.cor,
            'observacao': self.observacao,
        }


def _format_datetime_range(day: date, end_of_day: bool) -> str:
    current_time = time.max if end_of_day else time.min
    dt = datetime.combine(day, current_time).replace(tzinfo=PLOOMES_TIMEZONE)
    return dt.isoformat(timespec='milliseconds')


def _build_query_params(start_date: date, end_date: date, skip: int) -> dict:
    filtro = (
        f"Deal/CreateDate ge {_format_datetime_range(start_date, end_of_day=False)} "
        f"and Deal/CreateDate le {_format_datetime_range(end_date, end_of_day=True)} "
        "and Deal/Status/Name eq 'Ganha'"
    )

    expand = (
        "OtherProperties("
        "$select=IntegerValue;"
        f"$filter=FieldKey eq '{ORDER_FIELD_KEY}'"
        "),"
        "Deal("
        "$select=Id,CreateDate,Quotes;"
        "$expand=Quotes("
        "$select=Id,ContactName,Products,Notes;"
        "$filter=ContactName ne 'TESTE - APP CEMAG';"
        "$expand=Products("
        "$select=Product,OtherProperties;"
        "$expand="
        "Product($select=Code),"
        "OtherProperties("
        "$select=ObjectValueName;"
        f"$filter=FieldKey eq '{COR_FIELD_KEY}'"
        ")"
        ")"
        ")"
        ")"
    )

    return {
        '$top': PAGE_SIZE,
        '$skip': skip,
        '$select': 'Deal,OtherProperties',
        '$filter': filtro,
        '$expand': expand,
        '$orderby': 'Deal/CreateDate,Id',
        'preload': 'true',
    }


def _build_lookup_query_params(skip: int, deal_id: str | None = None, chave_pedido: str | None = None) -> dict:
    filters = ["Deal/Status/Name eq 'Ganha'"]
    if deal_id:
        filters.append(f"Deal/Id eq {int(deal_id)}")
    if chave_pedido:
        filters.append(
            "OtherProperties/any(op: "
            f"op/FieldKey eq '{ORDER_FIELD_KEY}' and op/IntegerValue eq {int(chave_pedido)})"
        )

    expand = (
        "OtherProperties("
        "$select=FieldKey,IntegerValue;"
        f"$filter=FieldKey eq '{ORDER_FIELD_KEY}'"
        "),"
        "Deal("
        "$select=Id,CreateDate,Quotes;"
        "$expand=Quotes("
        "$select=Id,ContactName,Products,Notes;"
        "$filter=ContactName ne 'TESTE - APP CEMAG';"
        "$expand=Products("
        "$select=Product,OtherProperties;"
        "$expand="
        "Product($select=Code),"
        "OtherProperties("
        "$select=ObjectValueName;"
        f"$filter=FieldKey eq '{COR_FIELD_KEY}'"
        ")"
        ")"
        ")"
        ")"
    )

    return {
        "$top": PAGE_SIZE,
        "$skip": skip,
        "$select": "Deal,OtherProperties",
        "$filter": " and ".join(filters),
        "$expand": expand,
        "$orderby": "Deal/CreateDate,Id",
        "preload": "true",
    }


def _extract_chave_pedido(order_item: dict) -> str:
    for prop in order_item.get('OtherProperties') or []:
        integer_value = prop.get('IntegerValue')
        if integer_value is not None:
            return str(integer_value)
    return 'N/D'


def _extract_cor(product_item: dict) -> str:
    for prop in product_item.get('OtherProperties') or []:
        color_name = prop.get('ObjectValueName')
        if color_name:
            return str(color_name).upper()
    return 'LARANJA'


def _format_create_date(raw_value: str | None) -> str:
    if not raw_value:
        return ''

    normalized = raw_value.replace('Z', '+00:00')
    created_at = datetime.fromisoformat(normalized)
    created_at = created_at.astimezone(PLOOMES_TIMEZONE)
    return created_at.strftime('%d/%m/%Y %H:%M:%S')


def _parse_order_item(order_item: dict) -> list[ConfPedidoItem]:
    deal = order_item.get('Deal') or {}
    quotes = deal.get('Quotes') or []
    if not quotes:
        return []

    chave_pedido = _extract_chave_pedido(order_item)
    data_criacao = _format_create_date(deal.get('CreateDate'))
    deal_id = str(deal.get('Id') or 'N/D')

    items: list[ConfPedidoItem] = []
    for quote in quotes:
        quote_id = quote.get('Id')
        contato = quote.get('ContactName') or 'N/D'
        observacao = quote.get('Notes') or ''
        products = quote.get('Products') or []

        if not products:
            items.append(
                ConfPedidoItem(
                    chave_pedido=chave_pedido,
                    deal_id=deal_id,
                    data_criacao=data_criacao,
                    quote_id=quote_id,
                    contato=contato,
                    codigo_produto='N/D',
                    cor='LARANJA',
                    observacao=observacao,
                )
            )
            continue

        for product in products:
            product_data = product.get('Product') or {}
            items.append(
                ConfPedidoItem(
                    chave_pedido=chave_pedido,
                    deal_id=deal_id,
                    data_criacao=data_criacao,
                    quote_id=quote_id,
                    contato=contato,
                    codigo_produto=product_data.get('Code') or 'N/D',
                    cor=_extract_cor(product),
                    observacao=observacao,
                )
            )

    return items


def consultar_conf_pedido(start_date: date, end_date: date) -> list[dict]:
    api_key = getattr(settings, 'PLOOMES_USER_KEY', '')
    if not api_key:
        raise PloomesConfigError('A variável de ambiente PLOOMES_USER_KEY não está configurada.')

    headers = {
        'User-Key': api_key,
        'Content-Type': 'application/json',
    }

    all_items: list[dict] = []
    skip = 0

    while True:
        response = requests.get(
            PLOOMES_ORDERS_URL,
            headers=headers,
            params=_build_query_params(start_date, end_date, skip),
            timeout=60,
        )

        if response.status_code != 200:
            body_preview = response.text[:500]
            raise PloomesAPIError(
                f'Erro ao consultar Ploomes ({response.status_code}). Resposta: {body_preview}'
            )

        payload = response.json()
        batch = payload.get('value') or []
        if not batch:
            break

        for order_item in batch:
            all_items.extend(item.as_dict() for item in _parse_order_item(order_item))

        skip += PAGE_SIZE

    return all_items


def consultar_conf_pedido_por_referencia(
    *,
    deal_id: str | None = None,
    chave_pedido: str | None = None,
) -> list[dict]:
    api_key = getattr(settings, "PLOOMES_USER_KEY", "")
    if not api_key:
        raise PloomesConfigError("A variável de ambiente PLOOMES_USER_KEY não está configurada.")

    if not deal_id and not chave_pedido:
        raise PloomesAPIError("Informe ID Negociação ou Chave do Pedido para consultar a Ploomes.")

    headers = {
        "User-Key": api_key,
        "Content-Type": "application/json",
    }

    all_items: list[dict] = []
    skip = 0

    while True:
        response = requests.get(
            PLOOMES_ORDERS_URL,
            headers=headers,
            params=_build_lookup_query_params(skip=skip, deal_id=deal_id, chave_pedido=chave_pedido),
            timeout=60,
        )

        if response.status_code != 200:
            body_preview = response.text[:500]
            raise PloomesAPIError(
                f"Erro ao consultar Ploomes ({response.status_code}). Resposta: {body_preview}"
            )

        payload = response.json()
        batch = payload.get("value") or []
        if not batch:
            break

        for order_item in batch:
            all_items.extend(item.as_dict() for item in _parse_order_item(order_item))

        if len(batch) < PAGE_SIZE:
            break
        skip += PAGE_SIZE

    return all_items
