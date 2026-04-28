from __future__ import annotations

from collections import defaultdict
from datetime import date

import pandas as pd
from django.db import transaction
from django.db.models import Prefetch

from cargas.models import (
    CargaLiberada,
    CargaLiberadaAlteracao,
    CargaLiberadaItem,
    CargaLiberadaVersao,
    LinkAcompanhamento,
)
from cargas.utils import consultar_carretas, consultar_carretas_detalhado


def _normalizar_itens(itens):
    itens_ordenados = sorted(
        itens,
        key=lambda item: (
            item["codigo_recurso"],
            item.get("cliente_codigo", ""),
            item.get("numero_serie", ""),
        ),
    )
    return [
        {
            "codigo_recurso": str(item["codigo_recurso"]),
            "quantidade": float(item["quantidade"]),
            "presente_no_carreta": str(item.get("presente_no_carreta", "") or ""),
            "cliente": str(item.get("cliente", item.get("cliente_codigo", "")) or ""),
            "cliente_codigo": str(item.get("cliente_codigo", "") or ""),
            "numero_serie": str(item.get("numero_serie", "") or ""),
        }
        for item in itens_ordenados
    ]


def _calcular_diff(itens_anteriores, itens_atuais):
    mapa_anterior = {
        (
            item["codigo_recurso"],
            item.get("cliente_codigo", ""),
            item.get("numero_serie", ""),
        ): float(item["quantidade"])
        for item in itens_anteriores
    }
    mapa_atual = {
        (
            item["codigo_recurso"],
            item.get("cliente_codigo", ""),
            item.get("numero_serie", ""),
        ): float(item["quantidade"])
        for item in itens_atuais
    }

    codigos = sorted(set(mapa_anterior) | set(mapa_atual))
    alteracoes = []

    for chave in codigos:
        codigo, cliente_codigo, numero_serie = chave
        qtd_anterior = mapa_anterior.get(chave)
        qtd_atual = mapa_atual.get(chave)

        if qtd_anterior is None:
            alteracoes.append(
                {
                    "tipo_alteracao": "item_adicionado",
                    "codigo_recurso": codigo,
                    "cliente_codigo": cliente_codigo,
                    "numero_serie": numero_serie,
                    "quantidade_anterior": None,
                    "quantidade_nova": qtd_atual,
                }
            )
        elif qtd_atual is None:
            alteracoes.append(
                {
                    "tipo_alteracao": "item_removido",
                    "codigo_recurso": codigo,
                    "cliente_codigo": cliente_codigo,
                    "numero_serie": numero_serie,
                    "quantidade_anterior": qtd_anterior,
                    "quantidade_nova": None,
                }
            )
        elif qtd_anterior != qtd_atual:
            alteracoes.append(
                {
                    "tipo_alteracao": "quantidade_alterada",
                    "codigo_recurso": codigo,
                    "cliente_codigo": cliente_codigo,
                    "numero_serie": numero_serie,
                    "quantidade_anterior": qtd_anterior,
                    "quantidade_nova": qtd_atual,
                }
            )

    return alteracoes


def liberar_cargas_periodo(usuario, data_inicio: date, data_fim: date):
    if data_inicio > data_fim:
        raise ValueError("A data de início deve ser menor ou igual à data fim.")

    retorno = consultar_carretas_detalhado(pd.to_datetime(data_inicio), pd.to_datetime(data_fim))
    linhas = retorno.get("cargas", [])

    grupos = defaultdict(list)
    for linha in linhas:
        data_carga = linha.get("data_carga")
        nome_carga = linha.get("carga")
        if not data_carga or not nome_carga:
            continue

        grupos[(data_carga, nome_carga)].append(
            {
                "codigo_recurso": linha.get("codigo_recurso", ""),
                "quantidade": float(linha.get("quantidade", 0) or 0),
                "presente_no_carreta": linha.get("presente_no_carreta", ""),
                "cliente": linha.get("cliente", linha.get("cliente_codigo", "")),
                "cliente_codigo": linha.get("cliente_codigo", linha.get("cliente", "")),
                "numero_serie": linha.get("numero_serie", ""),
            }
        )

    resultados = []

    with transaction.atomic():
        for (data_carga_str, carga_nome), itens_brutos in sorted(grupos.items()):
            data_carga = date.fromisoformat(data_carga_str)
            itens = _normalizar_itens(itens_brutos)

            carga_liberada, _ = CargaLiberada.objects.get_or_create(
                data_carga=data_carga,
                carga_nome=carga_nome,
            )
            carga_liberada = CargaLiberada.objects.select_for_update().get(
                pk=carga_liberada.pk
            )

            ultima_versao = carga_liberada.versoes.order_by("-versao").first()
            numero_versao = (ultima_versao.versao if ultima_versao else 0) + 1

            payload_snapshot = {
                "data_carga": data_carga.isoformat(),
                "carga": carga_nome,
                "itens": itens,
            }

            nova_versao = CargaLiberadaVersao.objects.create(
                carga_liberada=carga_liberada,
                versao=numero_versao,
                data_inicio_pesquisa=data_inicio,
                data_fim_pesquisa=data_fim,
                liberado_por=usuario,
                payload_snapshot=payload_snapshot,
            )

            CargaLiberadaItem.objects.bulk_create(
                [
                    CargaLiberadaItem(
                        carga_versao=nova_versao,
                        codigo_recurso=item["codigo_recurso"],
                        quantidade=item["quantidade"],
                        presente_no_carreta=item["presente_no_carreta"],
                        cliente=item["cliente"],
                        cliente_codigo=item["cliente_codigo"],
                        numero_serie=item["numero_serie"],
                    )
                    for item in itens
                ]
            )

            if ultima_versao is None:
                CargaLiberadaAlteracao.objects.create(
                    carga_liberada=carga_liberada,
                    versao_origem=None,
                    versao_destino=nova_versao,
                    tipo_alteracao="liberacao_inicial",
                    detalhes={"mensagem": "Primeira liberação da carga."},
                )
            else:
                alteracoes = _calcular_diff(
                    ultima_versao.payload_snapshot.get("itens", []),
                    itens,
                )
                CargaLiberadaAlteracao.objects.bulk_create(
                    [
                        CargaLiberadaAlteracao(
                            carga_liberada=carga_liberada,
                            versao_origem=ultima_versao,
                            versao_destino=nova_versao,
                            tipo_alteracao=alteracao["tipo_alteracao"],
                            codigo_recurso=alteracao["codigo_recurso"],
                            quantidade_anterior=alteracao["quantidade_anterior"],
                            quantidade_nova=alteracao["quantidade_nova"],
                            detalhes={
                                "cliente_codigo": alteracao["cliente_codigo"],
                                "numero_serie": alteracao["numero_serie"],
                            },
                        )
                        for alteracao in alteracoes
                    ]
                )

            # Gera links de acompanhamento para cada cliente único desta carga
            clientes_unicos = {item["cliente"] for item in itens if item.get("cliente")}
            links_gerados = []
            for cliente in clientes_unicos:
                link, _ = LinkAcompanhamento.objects.get_or_create(
                    data_carga=data_carga,
                    cliente=cliente,
                )
                links_gerados.append({"cliente": cliente, "token": str(link.token)})

            resultados.append(
                {
                    "carga_uuid": str(carga_liberada.carga_uuid),
                    "data_carga": data_carga.isoformat(),
                    "carga": carga_nome,
                    "versao": numero_versao,
                    "links_acompanhamento": links_gerados,
                }
            )

    return {
        "total_cargas_liberadas": len(resultados),
        "total_versoes_criadas": len(resultados),
        "cargas": resultados,
    }


def listar_cargas_liberadas_periodo(data_inicio: date, data_fim: date):
    if data_inicio > data_fim:
        raise ValueError("A data de início deve ser menor ou igual à data fim.")

    versoes_prefetch = Prefetch(
        "versoes",
        queryset=CargaLiberadaVersao.objects.order_by("-versao").prefetch_related("itens"),
        to_attr="versoes_ordenadas",
    )

    cargas = (
        CargaLiberada.objects.filter(data_carga__gte=data_inicio, data_carga__lte=data_fim)
        .prefetch_related(versoes_prefetch)
        .order_by("data_carga", "carga_nome")
    )

    itens_saida = []
    for carga in cargas:
        ultima_versao = (
            carga.versoes_ordenadas[0] if getattr(carga, "versoes_ordenadas", []) else None
        )
        if ultima_versao is None:
            continue

        agrupado = {}
        for item in ultima_versao.itens.all():
            chave = (item.codigo_recurso, item.presente_no_carreta)
            if chave not in agrupado:
                agrupado[chave] = 0.0
            agrupado[chave] += float(item.quantidade)

        for (codigo_recurso, presente_no_carreta), quantidade in agrupado.items():
            itens_saida.append(
                {
                    "data_carga": carga.data_carga.isoformat(),
                    "data_sugerida_planejamento": (
                        carga.data_sugerida_planejamento.isoformat()
                        if carga.data_sugerida_planejamento
                        else ""
                    ),
                    "codigo_recurso": codigo_recurso,
                    "quantidade": quantidade,
                    "presente_no_carreta": presente_no_carreta,
                    "carga": carga.carga_nome,
                    "versao": ultima_versao.versao,
                }
            )

    return {
        "cargas": itens_saida,
        "celulas": [],
    }


def listar_cargas_liberadas_para_planejamento(data_inicio: date, data_fim: date):
    if data_inicio > data_fim:
        raise ValueError("A data de inÃ­cio deve ser menor ou igual Ã  data fim.")

    versoes_prefetch = Prefetch(
        "versoes",
        queryset=CargaLiberadaVersao.objects.order_by("-versao"),
        to_attr="versoes_ordenadas",
    )

    cargas = (
        CargaLiberada.objects.filter(data_carga__gte=data_inicio, data_carga__lte=data_fim)
        .prefetch_related(versoes_prefetch)
        .order_by("data_carga", "carga_nome")
    )

    resultado = []
    for carga in cargas:
        versoes_ordenadas = getattr(carga, "versoes_ordenadas", [])
        if not versoes_ordenadas:
            continue

        ultima_versao = versoes_ordenadas[0]
        resultado.append(
            {
                "carga_liberada_id": carga.id,
                "carga_liberada_versao_id": ultima_versao.id,
                "carga_uuid": str(carga.carga_uuid),
                "versao_uuid": str(ultima_versao.versao_uuid),
                "data_carga": carga.data_carga,
                "data_sugerida_planejamento": carga.data_sugerida_planejamento,
                "carga": carga.carga_nome,
                "versao": ultima_versao.versao,
            }
        )

    return resultado


def atualizar_datas_sugeridas_planejamento(mapa_datas_sugeridas: dict[int, date | None]):
    if not mapa_datas_sugeridas:
        return

    with transaction.atomic():
        for carga_id, data_sugerida in mapa_datas_sugeridas.items():
            CargaLiberada.objects.filter(pk=carga_id).update(
                data_sugerida_planejamento=data_sugerida
            )


def listar_itens_liberados_expedicao(data_carga: date, carga_nome: str | None = None, cliente_codigo: str | None = None):
    versoes_prefetch = Prefetch(
        "versoes",
        queryset=CargaLiberadaVersao.objects.order_by("-versao").prefetch_related("itens"),
        to_attr="versoes_ordenadas",
    )

    cargas = CargaLiberada.objects.filter(data_carga=data_carga)
    if carga_nome:
        cargas = cargas.filter(carga_nome=carga_nome)

    cargas = cargas.prefetch_related(versoes_prefetch).order_by("carga_nome")

    itens_saida = []
    for carga in cargas:
        versoes_ordenadas = getattr(carga, "versoes_ordenadas", [])
        if not versoes_ordenadas:
            continue

        ultima_versao = versoes_ordenadas[0]
        for item in ultima_versao.itens.all():
            cliente_item = item.cliente or item.cliente_codigo
            if cliente_codigo and cliente_item != cliente_codigo:
                continue

            itens_saida.append(
                {
                    "data_carga": carga.data_carga.isoformat(),
                    "carga": carga.carga_nome,
                    "versao": ultima_versao.versao,
                    "codigo_recurso": item.codigo_recurso,
                    "quantidade": float(item.quantidade),
                    "presente_no_carreta": item.presente_no_carreta,
                    "cliente_codigo": cliente_item,
                    "cliente": cliente_item,
                    "numero_serie": item.numero_serie,
                }
            )

    return itens_saida
