import json
from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.db.models import Exists, OuterRef, Q, Value
from django.db.models.functions import Replace
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from comercial.models import ConferenciaPedido, PendenciaImportacaoPlanilha
from comercial.services.agente_conferencia import analisar_pedido
from comercial.services.ploomes import (
    PloomesAPIError,
    PloomesConfigError,
    consultar_conf_pedido_por_referencia,
)


def _build_conferencia_quote_id(payload: dict) -> str:
    return f"pedido::{payload.get('id_negociacao', '').strip()}::{payload.get('chcriacao', '').strip()}"


def _serialize_pendencia(
    pendencia: PendenciaImportacaoPlanilha,
    conferencia: dict | None = None,
) -> dict:
    return {
        "regiao_nome": pendencia.ped_ufpessoaop_regiao_nome,
        "uf_codigo": pendencia.ped_pessoa_uf_codigo,
        "observacao": pendencia.ped_observacao,
        "localidade_codigo": pendencia.ped_pessoa_localidade_codigo,
        "chcriacao": pendencia.ped_chcriacao,
        "emissao": pendencia.ped_emissao.strftime("%d/%m/%Y") if pendencia.ped_emissao else "",
        "previsaoemissaodoc": (
            pendencia.ped_previsaoemissaodoc.strftime("%d/%m/%Y")
            if pendencia.ped_previsaoemissaodoc
            else ""
        ),
        "programaca": pendencia.ped_programaca.strftime("%d/%m/%Y") if pendencia.ped_programaca else "",
        "classe_nome": pendencia.ped_classe_nome,
        "pessoa_codigo": pendencia.ped_pessoa_codigo,
        "recurso_codigo": pendencia.ped_recurso_codigo,
        "recurso_nome": pendencia.ped_recurso_nome,
        "recurso_classe_nome": pendencia.ped_recurso_classe_nome,
        "numero_serie": pendencia.ped_numeroserie,
        "nucleo_codigo": pendencia.ped_nucleo_codigo,
        "quantidade": str(pendencia.ped_quantidade),
        "unitario": str(pendencia.ped_unitario),
        "total": str(pendencia.ped_total),
        "descricaogenerica": pendencia.ped_recurso_descricaogenerica,
        "representa_codigo": pendencia.ped_representa_codigo,
        "id_negociacao": pendencia.ped_idnegociacao,
        "conferencia": conferencia,
    }


def _serialize_conferencia(conferencia: ConferenciaPedido) -> dict:
    payload = ((conferencia.itens or [None])[0] or {}).copy()
    if not payload:
        payload = {
            "observacao": conferencia.observacao,
            "emissao": conferencia.data_criacao,
            "pessoa_codigo": conferencia.contato,
        }

    # Sempre garante as chaves de identificação do pedido a partir do banco
    payload["chcriacao"] = conferencia.chave_pedido
    payload["id_negociacao"] = conferencia.deal_id

    payload["conferencia"] = {
        "conferido_por": conferencia.conferido_por.get_full_name() or conferencia.conferido_por.username,
        "conferido_em": conferencia.conferido_em.isoformat(),
    }
    return payload


@login_required
def conf_pedido(request):
    return render(request, "comercial/conf_pedido.html")


_PAGE_SIZE = 15
_COLUMNS = [
    {"key": "regiao_nome", "label": "Região"},
    {"key": "uf_codigo", "label": "UF"},
    {"key": "observacao", "label": "Observação"},
    {"key": "localidade_codigo", "label": "Localidade"},
    {"key": "chcriacao", "label": "Ch Criação"},
    {"key": "emissao", "label": "Emissão"},
    {"key": "previsaoemissaodoc", "label": "Prev. Emissão Doc"},
    {"key": "programaca", "label": "Programação"},
    {"key": "classe_nome", "label": "Classe"},
    {"key": "pessoa_codigo", "label": "Pessoa"},
    {"key": "recurso_codigo", "label": "Recurso Código"},
    {"key": "recurso_nome", "label": "Recurso Nome"},
    {"key": "recurso_classe_nome", "label": "Recurso Classe"},
    {"key": "numero_serie", "label": "Número Série"},
    {"key": "nucleo_codigo", "label": "Núcleo"},
    {"key": "quantidade", "label": "Quantidade"},
    {"key": "unitario", "label": "Unitário"},
    {"key": "total", "label": "Total"},
    {"key": "descricaogenerica", "label": "Descrição Genérica"},
    {"key": "representa_codigo", "label": "Representante"},
    {"key": "id_negociacao", "label": "ID Negociação"},
]


@login_required
@require_GET
def api_conf_pedido(request):
    start_raw = (request.GET.get("data_inicio") or "").strip()
    end_raw = (request.GET.get("data_fim") or "").strip()

    start_date = None
    end_date = None

    if start_raw or end_raw:
        try:
            if start_raw:
                start_date = datetime.strptime(start_raw, "%Y-%m-%d").date()
            if end_raw:
                end_date = datetime.strptime(end_raw, "%Y-%m-%d").date()
        except ValueError:
            return JsonResponse({"error": "Datas inválidas. Use o formato YYYY-MM-DD."}, status=400)

        if start_date and end_date and start_date > end_date:
            return JsonResponse({"error": "A data inicial não pode ser maior que a data final."}, status=400)

    filtro_classe = (request.GET.get("classe") or "").strip()
    filtro_pessoa = (request.GET.get("pessoa") or "").strip()
    filtro_numero_serie = (request.GET.get("numero_serie") or "").strip()
    filtro_id_negociacao = (request.GET.get("id_negociacao") or "").strip()
    filtro_chcriacao = (request.GET.get("chcriacao") or "").strip()

    try:
        page = max(1, int(request.GET.get("page", 1)))
    except ValueError:
        page = 1

    qs = PendenciaImportacaoPlanilha.objects.exclude(
        Exists(
            ConferenciaPedido.objects.filter(
                chave_pedido=OuterRef("ped_chcriacao"),
                deal_id=OuterRef("ped_idnegociacao"),
            )
        )
    )

    if start_date:
        qs = qs.filter(ped_emissao__gte=start_date)
    if end_date:
        qs = qs.filter(ped_emissao__lte=end_date)

    if filtro_classe:
        qs = qs.filter(ped_classe_nome__icontains=filtro_classe)
    if filtro_pessoa:
        qs = qs.filter(ped_pessoa_codigo__icontains=filtro_pessoa)
    if filtro_numero_serie:
        qs = qs.filter(ped_numeroserie__icontains=filtro_numero_serie)
    if filtro_id_negociacao:
        filtro_id_negociacao_limpo = filtro_id_negociacao.replace(".", "").replace(" ", "")
        qs = qs.annotate(
            _id_neg_limpo=Replace(
                Replace("ped_idnegociacao", Value("."), Value("")),
                Value(" "),
                Value(""),
            )
        ).filter(_id_neg_limpo__icontains=filtro_id_negociacao_limpo)
    if filtro_chcriacao:
        qs = qs.filter(ped_chcriacao__icontains=filtro_chcriacao)

    order_keys = (
        qs.values("ped_chcriacao", "ped_idnegociacao", "ped_emissao")
        .distinct()
        .order_by("-ped_emissao", "ped_chcriacao", "ped_idnegociacao")
    )

    total_orders = order_keys.count()
    total_pages = max(1, (total_orders + _PAGE_SIZE - 1) // _PAGE_SIZE)
    page = min(page, total_pages)
    start_idx = (page - 1) * _PAGE_SIZE
    page_keys = list(order_keys[start_idx : start_idx + _PAGE_SIZE])

    resultados = []
    if page_keys:
        key_filter = Q()
        for key in page_keys:
            key_filter |= Q(
                ped_chcriacao=key["ped_chcriacao"],
                ped_idnegociacao=key["ped_idnegociacao"],
            )
        items_qs = qs.filter(key_filter).order_by(
            "ped_chcriacao", "ped_idnegociacao", "ped_recurso_codigo", "ped_numeroserie"
        )
        resultados = [_serialize_pendencia(item) for item in items_qs]

    return JsonResponse(
        {
            "results": resultados,
            "total": total_orders,
            "page": page,
            "page_size": _PAGE_SIZE,
            "total_pages": total_pages,
            "columns": _COLUMNS,
        }
    )


@login_required
@require_GET
def api_conferidos(request):
    queryset = ConferenciaPedido.objects.select_related("conferido_por").all()

    conferido_por = (request.GET.get("conferido_por") or "").strip()
    data_inicio_raw = (request.GET.get("data_conferencia_inicio") or "").strip()
    data_fim_raw = (request.GET.get("data_conferencia_fim") or "").strip()

    if conferido_por:
        queryset = queryset.filter(
            Q(conferido_por__username__icontains=conferido_por)
            | Q(conferido_por__first_name__icontains=conferido_por)
            | Q(conferido_por__last_name__icontains=conferido_por)
        )

    try:
        if data_inicio_raw:
            data_inicio = datetime.strptime(data_inicio_raw, "%Y-%m-%d").date()
            queryset = queryset.filter(conferido_em__date__gte=data_inicio)
        if data_fim_raw:
            data_fim = datetime.strptime(data_fim_raw, "%Y-%m-%d").date()
            queryset = queryset.filter(conferido_em__date__lte=data_fim)
    except ValueError:
        return JsonResponse(
            {"error": "Datas de conferência inválidas. Use o formato YYYY-MM-DD."},
            status=400,
        )

    resultados = [_serialize_conferencia(item) for item in queryset]
    return JsonResponse({"results": resultados, "total": len(resultados)})


@login_required
@require_GET
def api_conf_pedido_ploomes(request):
    id_negociacao = (request.GET.get("id_negociacao") or "").strip()
    chcriacao = (request.GET.get("chcriacao") or "").strip()

    if not id_negociacao and not chcriacao:
        return JsonResponse(
            {"error": "Informe ID Negociação ou Chave do Pedido para consultar a Ploomes."},
            status=400,
        )

    try:
        resultados = consultar_conf_pedido_por_referencia(
            deal_id=id_negociacao or None,
            chave_pedido=chcriacao or None,
        )
    except PloomesConfigError as exc:
        return JsonResponse({"error": str(exc)}, status=500)
    except PloomesAPIError as exc:
        return JsonResponse({"error": str(exc)}, status=502)
    except Exception as exc:
        return JsonResponse({"error": f"Erro interno ao consultar Ploomes: {exc}"}, status=500)

    return JsonResponse({"results": resultados, "total": len(resultados)})


@login_required
@require_GET
def api_conf_pedido_ploomes_debug(request):
    """Retorna o payload bruto da Ploomes — todos os campos de Products sem filtro."""
    import requests as req
    from django.conf import settings
    from comercial.services.ploomes import PLOOMES_ORDERS_URL, ORDER_FIELD_KEY

    id_negociacao = (request.GET.get("id_negociacao") or "").strip()

    if not id_negociacao:
        return JsonResponse({"error": "Informe id_negociacao."}, status=400)

    api_key = getattr(settings, "PLOOMES_USER_KEY", "")
    if not api_key:
        return JsonResponse({"error": "PLOOMES_USER_KEY não configurado."}, status=500)

    params = {
        "$top": 5,
        "$skip": 0,
        "$filter": f"Deal/Id eq {int(id_negociacao.replace('.', ''))}",
        "$expand": (
            "Deal("
            "$select=Id,CreateDate,Quotes;"
            "$expand=Quotes("
            "$select=Id,ContactName,Products,Notes;"
            "$expand=Products("
            "$expand="
            "Product($select=Code),"
            "OtherProperties($select=FieldKey,StringValue,IntegerValue,DecimalValue,ObjectValueName)"
            ")"
            ")"
            ")"
        ),
    }

    resp = req.get(
        PLOOMES_ORDERS_URL,
        headers={"User-Key": api_key, "Content-Type": "application/json"},
        params=params,
        timeout=30,
    )
    return JsonResponse(resp.json(), safe=False)


@login_required
@require_POST
def api_marcar_conferido(request):
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON inválido."}, status=400)

    required_fields = ["chcriacao", "id_negociacao"]
    if any(not str(payload.get(field, "")).strip() for field in required_fields):
        return JsonResponse({"error": "Registro inválido para conferência."}, status=400)

    conferencia, _ = ConferenciaPedido.objects.update_or_create(
        chave_pedido=str(payload.get("chcriacao")).strip(),
        deal_id=str(payload.get("id_negociacao")).strip(),
        quote_id=_build_conferencia_quote_id(payload),
        defaults={
            "data_criacao": str(payload.get("emissao") or ""),
            "contato": str(payload.get("pessoa_codigo") or ""),
            "observacao": str(payload.get("observacao") or ""),
            "itens": payload.get("itens") or [payload],
            "conferido_por": request.user,
        },
    )

    return JsonResponse(
        {
            "message": "Registro conferido com sucesso.",
            "result": _serialize_conferencia(conferencia),
        }
    )


@login_required
@require_POST
def api_agente_conferencia(request):
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON inválido."}, status=400)

    itens_innovaro = payload.get("itens_innovaro") or []
    itens_ploomes = payload.get("itens_ploomes") or []
    observacoes = payload.get("observacoes") or []

    if not itens_innovaro and not itens_ploomes:
        return JsonResponse({"error": "Informe ao menos os itens do pedido."}, status=400)

    try:
        analise = analisar_pedido(itens_innovaro, itens_ploomes, observacoes)
    except RuntimeError as exc:
        return JsonResponse({"error": str(exc)}, status=502)
    except Exception as exc:
        return JsonResponse({"error": f"Erro ao executar análise: {exc}"}, status=500)

    return JsonResponse(analise)


@login_required
@require_POST
def api_desfazer_conferido(request):
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON inválido."}, status=400)

    required_fields = ["chcriacao", "id_negociacao"]
    if any(not str(payload.get(field, "")).strip() for field in required_fields):
        return JsonResponse({"error": "Registro inválido para desfazer conferência."}, status=400)

    deleted_count, _ = ConferenciaPedido.objects.filter(
        chave_pedido=str(payload.get("chcriacao")).strip(),
        deal_id=str(payload.get("id_negociacao")).strip(),
        quote_id=_build_conferencia_quote_id(payload),
    ).delete()

    if deleted_count == 0:
        return JsonResponse({"error": "Conferência não encontrada."}, status=404)

    return JsonResponse({"message": "Conferência desfeita com sucesso."})
