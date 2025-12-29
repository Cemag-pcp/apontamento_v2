from datetime import datetime

from django.core.paginator import Paginator
from django.db.models import Max, Q, Sum
from django.http import JsonResponse
from django.shortcuts import render

from apontamento_corte.models import PecasOrdem


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
