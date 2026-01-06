from datetime import datetime
import json

from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Max, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from apontamento_corte.models import PecasOrdem
from core.models import Profile
from inspecao.models import (
    ArquivoCausa,
    ArquivoConformidade,
    Causas,
    CausasNaoConformidade,
    DadosExecucaoInspecao,
    Inspecao,
)


def inspecao_corte(request):
    return render(request, "inspecao_corte.html")


def get_itens_inspecao_corte(request):
    if request.method != "GET":
        return JsonResponse({"error": "Metodo nao permitido"}, status=405)

    pesquisa = request.GET.get("pesquisar", "").strip()
    data_inicio = request.GET.get("data_inicio")
    data_fim = request.GET.get("data_fim")
    pagina = int(request.GET.get("pagina", 1))
    itens_por_pagina = 12

    queryset = PecasOrdem.objects.select_related("ordem", "ordem__maquina").all()

    total_ordens = queryset.values("ordem_id").distinct().count()

    if pesquisa:
        queryset = queryset.filter(
            Q(peca__icontains=pesquisa) | Q(ordem__ordem__icontains=pesquisa)
        )

    try:
        if data_inicio:
            data_inicio = datetime.strptime(data_inicio, "%Y-%m-%d").date()
        if data_fim:
            data_fim = datetime.strptime(data_fim, "%Y-%m-%d").date()
    except ValueError:
        data_inicio = None
        data_fim = None

    if data_inicio and data_fim:
        queryset = queryset.filter(data__date__gte=data_inicio, data__date__lte=data_fim)
    elif data_inicio:
        queryset = queryset.filter(data__date__gte=data_inicio)
    elif data_fim:
        queryset = queryset.filter(data__date__lte=data_fim)

    agrupado = (
        queryset.values("ordem_id", "ordem__ordem", "ordem__maquina__nome")
        .annotate(total_qtd_boa=Sum("qtd_boa"), data_ultima=Max("data"))
        .order_by("-data_ultima")
    )

    paginador = Paginator(agrupado, itens_por_pagina)
    pagina_obj = paginador.get_page(pagina)

    dados = []
    for item in pagina_obj:
        data_ultima = item["data_ultima"].strftime("%d/%m/%Y") if item["data_ultima"] else ""
        dados.append(
            {
                "ordem_id": item["ordem_id"],
                "ordem_numero": item["ordem__ordem"],
                "conjunto": item["ordem__maquina__nome"] or "-",
                "qtd_boa": item["total_qtd_boa"] or 0,
                "data": data_ultima,
            }
        )

    return JsonResponse(
        {
            "dados": dados,
            "total": total_ordens,
            "total_filtrado": paginador.count,
            "pagina_atual": pagina_obj.number,
            "total_paginas": paginador.num_pages,
        }
    )


def get_itens_inspecionados_corte(request):
    if request.method != "GET":
        return JsonResponse({"error": "Metodo nao permitido"}, status=405)

    return JsonResponse(
        {
            "dados": [],
            "total": 0,
            "total_filtrado": 0,
            "pagina_atual": 1,
            "total_paginas": 1,
        }
    )


def get_ordem_corte(request, ordem_id):
    if request.method != "GET":
        return JsonResponse({"error": "Metodo nao permitido"}, status=405)

    pecas = (
        PecasOrdem.objects.filter(ordem_id=ordem_id)
        .values("id", "peca", "qtd_boa", "qtd_planejada", "qtd_morta")
        .order_by("id")
    )

    return JsonResponse({"pecas": list(pecas)})


@require_POST
@transaction.atomic
def envio_inspecao_corte(request):
    try:
        if request.content_type and "application/json" in request.content_type:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        else:
            payload = request.POST.dict()

        peca_id = payload.get("peca_id") or payload.get("pecaId")
        if not peca_id:
            return JsonResponse({"error": "peca_id obrigatorio"}, status=400)

        peca = get_object_or_404(PecasOrdem, pk=peca_id)
        observacao = payload.get("observacao", "")
        inspecao_total = payload.get("inspecao_total") or payload.get("inspecaoTotal")
        inspecao_total = True if str(inspecao_total).lower() == "sim" else False

        medidas_raw = payload.get("medicoes", "[]")
        if isinstance(medidas_raw, str):
            try:
                medidas = json.loads(medidas_raw)
            except json.JSONDecodeError:
                medidas = []
        else:
            medidas = medidas_raw or []

        nao_conformidades_raw = payload.get("naoConformidades", "[]")
        if isinstance(nao_conformidades_raw, str):
            try:
                nao_conformidades = json.loads(nao_conformidades_raw)
            except json.JSONDecodeError:
                nao_conformidades = []
        else:
            nao_conformidades = nao_conformidades_raw or []

        total_amostras = min(3, int(peca.qtd_boa or 0))
        linhas_nao_conforme = sum(1 for item in medidas if not item.get("conforme", True))
        total_pecas_afetadas = sum(
            int(item.get("quantidadeAfetada", 0) or 0) for item in nao_conformidades
        )

        if linhas_nao_conforme and total_pecas_afetadas > linhas_nao_conforme:
            return JsonResponse(
                {"error": "Quantidade afetada excede o numero de nao conformes."},
                status=400,
            )

        nao_conformidade = total_pecas_afetadas
        conformidade = max(total_amostras - nao_conformidade, 0)

        inspecao = Inspecao.objects.filter(pecas_ordem_corte=peca).order_by("-id").first()
        if not inspecao:
            inspecao = Inspecao.objects.create(pecas_ordem_corte=peca)

        inspetor = Profile.objects.filter(user=request.user).first()
        dados_execucao = DadosExecucaoInspecao.objects.create(
            inspecao=inspecao,
            inspetor=inspetor,
            conformidade=conformidade,
            nao_conformidade=nao_conformidade,
            observacao=observacao,
        )

        if inspecao_total and request.FILES.get("ficha"):
            ArquivoConformidade.objects.create(
                dados_execucao=dados_execucao,
                arquivo=request.FILES["ficha"],
            )

        CausasNaoConformidade.objects.filter(dados_execucao=dados_execucao).delete()
        for idx, nc_data in enumerate(nao_conformidades, 1):
            causas_ids = nc_data.get("causas", [])
            quantidade = int(nc_data.get("quantidadeAfetada", 0) or 0)
            destino = nc_data.get("destino") or None
            if not causas_ids:
                continue

            causa_nc = CausasNaoConformidade.objects.create(
                dados_execucao=dados_execucao,
                quantidade=quantidade,
                destino=destino,
            )
            causas = Causas.objects.filter(id__in=causas_ids)
            causa_nc.causa.add(*causas)

            for arquivo in request.FILES.getlist(f"nc_files_{idx}"):
                ArquivoCausa.objects.create(
                    causa_nao_conformidade=causa_nc,
                    arquivo=arquivo,
                )

        return JsonResponse({"success": True, "execucao_id": dados_execucao.id})
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)
