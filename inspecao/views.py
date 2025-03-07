from django.shortcuts import render
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Prefetch
from .models import (
    Inspecao,
    DadosExecucaoInspecao,
    Reinspecao,
    Causas,
    CausasNaoConformidade,
    InspecaoEstanqueidade,
    DadosExecucaoInspecaoEstanqueidade,
    ReinspecaoEstanqueidade,
    DetalhesPressaoTanque,
    InfoAdicionaisExecTubosCilindros,
    CausasEstanqueidadeTubosCilindros,
)
from core.models import Profile
from datetime import timezone, datetime, timedelta


def inspecao_montagem(request):
    return render(request, "inspecao_montagem.html")


def inspecao_pintura(request):

    users = Profile.objects.filter(tipo_acesso="inspetor")
    cores = ["Amarelo", "Azul", "Cinza", "Laranja", "Verde", "Vermelho"]

    lista_inspetores = [{"nome_usuario": user.user.username} for user in users]

    return render(
        request,
        "inspecao_pintura.html",
        {"inspetores": lista_inspetores, "cores": cores},
    )


def get_itens_inspecao_pintura(request):
    if request.method != "GET":
        return JsonResponse({"error": "Método não permitido"}, status=405)

    inspecoes_ids = set(
        DadosExecucaoInspecao.objects.values_list("inspecao", flat=True)
    )

    # Captura os parâmetros enviados na URL
    cores_filtradas = (
        request.GET.get("cores", "").split(",") if request.GET.get("cores") else []
    )
    data_filtrada = request.GET.get("data", None)
    pesquisa_filtrada = request.GET.get("pesquisar", None)
    pagina = int(request.GET.get("pagina", 1))  # Página atual, padrão é 1
    itens_por_pagina = 3  # Itens por página

    # Filtra os dados
    datas = Inspecao.objects.filter(pecas_ordem_pintura__isnull=False).exclude(
        id__in=inspecoes_ids
    )

    quantidade_total = datas.count()  # Total de itens sem filtro

    if cores_filtradas:
        datas = datas.filter(pecas_ordem_pintura__ordem__cor__in=cores_filtradas)

    if data_filtrada:
        datas = datas.filter(data_inspecao__date=data_filtrada)

    if pesquisa_filtrada:
        pesquisa_filtrada = pesquisa_filtrada.lower()
        datas = datas.filter(pecas_ordem_pintura__peca__icontains=pesquisa_filtrada)

    datas = datas.select_related(
        "pecas_ordem_pintura",
        "pecas_ordem_pintura__ordem",
        "pecas_ordem_pintura__operador_fim",
    ).order_by("-id")

    # Paginação
    paginador = Paginator(datas, itens_por_pagina)
    pagina_obj = paginador.get_page(pagina)

    dados = []
    for data in pagina_obj:
        data_ajustada = data.data_inspecao - timedelta(hours=3)
        matricula_nome_operador = None

        if data.pecas_ordem_pintura.operador_fim:
            matricula_nome_operador = f"{data.pecas_ordem_pintura.operador_fim.matricula} - {data.pecas_ordem_pintura.operador_fim.nome}"

        item = {
            "id": data.id,
            "data": data_ajustada.strftime("%d/%m/%Y %H:%M:%S"),
            "peca": data.pecas_ordem_pintura.peca,
            "maquina": data.pecas_ordem_pintura.ordem.maquina,
            "cor": data.pecas_ordem_pintura.ordem.cor,
            "tipo": data.pecas_ordem_pintura.tipo,
            "operador": matricula_nome_operador,
        }

        dados.append(item)

    return JsonResponse({
        "dados": dados,
        "total": quantidade_total,
        "total_filtrado": paginador.count,  # Total de itens após filtro
        "pagina_atual": pagina_obj.number,
        "total_paginas": paginador.num_pages,
    }, status=200)


def get_itens_reinspecao_pintura(request):
    if request.method != "GET":
        return JsonResponse({"error": "Método não permitido"}, status=405)

    reinspecao_ids = set(
        Reinspecao.objects.filter(reinspecionado=False).values_list(
            "dados_execucao__inspecao", flat=True
        )
    )

    # Captura os filtros enviados pela URL
    cores_filtradas = (
        request.GET.get("cores", "").split(",") if request.GET.get("cores") else []
    )
    inspetores_filtrados = (
        request.GET.get("inspetores", "").split(",")
        if request.GET.get("inspetores")
        else []
    )
    data_filtrada = request.GET.get("data", None)
    pesquisa_filtrada = request.GET.get("pesquisar", None)
    pagina = int(request.GET.get("pagina", 1))  # Página atual, padrão é 1
    itens_por_pagina = 3  # Itens por página

    # Filtra os dados
    datas = Inspecao.objects.filter(
        id__in=reinspecao_ids, pecas_ordem_pintura__isnull=False
    )

    quantidade_total = datas.count()  # Total de itens sem filtro

    if cores_filtradas:
        datas = datas.filter(pecas_ordem_pintura__ordem__cor__in=cores_filtradas)

    if data_filtrada:
        datas = datas.filter(data_inspecao__date=data_filtrada)

    if pesquisa_filtrada:
        pesquisa_filtrada = pesquisa_filtrada.lower()
        datas = datas.filter(pecas_ordem_pintura__peca__icontains=pesquisa_filtrada)

    if inspetores_filtrados:
        datas = datas.filter(
            dadosexecucaoinspecao__inspetor__user__username__in=inspetores_filtrados
        )

    datas = datas.select_related(
        "pecas_ordem_pintura",
        "pecas_ordem_pintura__ordem",
        "pecas_ordem_pintura__operador_fim",
    ).order_by("-id")

    # Paginação
    paginador = Paginator(datas, itens_por_pagina)
    pagina_obj = paginador.get_page(pagina)

    dados = []
    for data in pagina_obj:
        data_ajustada = data.data_inspecao - timedelta(hours=3)

        matricula_nome_operador = None
        if data.pecas_ordem_pintura.operador_fim:
            matricula_nome_operador = f"{data.pecas_ordem_pintura.operador_fim.matricula} - {data.pecas_ordem_pintura.operador_fim.nome}"

        item = {
            "id": data.id,
            "data": data_ajustada.strftime("%d/%m/%Y %H:%M:%S"),
            "peca": data.pecas_ordem_pintura.peca,
            "maquina": data.pecas_ordem_pintura.ordem.maquina,
            "cor": data.pecas_ordem_pintura.ordem.cor,
            "tipo": data.pecas_ordem_pintura.tipo,
            "operador": matricula_nome_operador,
        }

        dados.append(item)

    return JsonResponse({
        "dados": dados,
        "total": quantidade_total,
        "total_filtrado": paginador.count,  # Total de itens após filtro
        "pagina_atual": pagina_obj.number,
        "total_paginas": paginador.num_pages,
    }, status=200)


def get_itens_inspecionados_pintura(request):
    if request.method != "GET":
        return JsonResponse({"error": "Método não permitido"}, status=405)

    inspecionados_ids = set(
        DadosExecucaoInspecao.objects.values_list("inspecao", flat=True)
    )

    # Captura os filtros aplicados pela URL
    cores_filtradas = (
        request.GET.get("cores", "").split(",") if request.GET.get("cores") else []
    )
    inspetores_filtrados = (
        request.GET.get("inspetores", "").split(",")
        if request.GET.get("inspetores")
        else []
    )
    data_filtrada = request.GET.get("data", None)
    pesquisa_filtrada = request.GET.get("pesquisar", None)
    pagina = int(request.GET.get("pagina", 1))  # Página atual, padrão é 1
    itens_por_pagina = 3  # Itens por página

    # Filtra os dados
    datas = Inspecao.objects.filter(id__in=inspecionados_ids)

    quantidade_total = datas.count()  # Total de itens sem filtro

    if cores_filtradas:
        datas = datas.filter(pecas_ordem_pintura__ordem__cor__in=cores_filtradas)

    if data_filtrada:
        datas = datas.filter(data_inspecao__date=data_filtrada)

    if pesquisa_filtrada:
        datas = datas.filter(pecas_ordem_pintura__peca__icontains=pesquisa_filtrada)

    if inspetores_filtrados:
        datas = datas.filter(
            dadosexecucaoinspecao__inspetor__user__username__in=inspetores_filtrados
        )

    datas = datas.select_related(
        "pecas_ordem_pintura",
        "pecas_ordem_pintura__ordem",
        "pecas_ordem_pintura__operador_fim",
    ).order_by("-id")

    # Paginação
    paginador = Paginator(datas, itens_por_pagina)
    pagina_obj = paginador.get_page(pagina)

    dados = []
    for data in pagina_obj:
        data_ajustada = data.data_inspecao - timedelta(hours=3)

        matricula_nome_operador = None
        if data.pecas_ordem_pintura.operador_fim:
            matricula_nome_operador = f"{data.pecas_ordem_pintura.operador_fim.matricula} - {data.pecas_ordem_pintura.operador_fim.nome}"

        possui_nao_conformidade = DadosExecucaoInspecao.objects.filter(
            inspecao=data, nao_conformidade__gt=0
        ).exists()

        item = {
            "id": data.id,
            "data": data_ajustada.strftime("%d/%m/%Y %H:%M:%S"),
            "peca": data.pecas_ordem_pintura.peca,
            "maquina": data.pecas_ordem_pintura.ordem.maquina,
            "cor": data.pecas_ordem_pintura.ordem.cor,
            "tipo": data.pecas_ordem_pintura.tipo,
            "operador": matricula_nome_operador,
            "possui_nao_conformidade": possui_nao_conformidade,
        }

        dados.append(item)

    return JsonResponse({
        "dados": dados,
        "total": quantidade_total,
        "total_filtrado": paginador.count,  # Total de itens após filtro
        "pagina_atual": pagina_obj.number,
        "total_paginas": paginador.num_pages,
    }, status=200)


def inspecao_estamparia(request):
    return render(request, "inspecao_estamparia.html")


def inspecao_tanque(request):
    return render(request, "inspecao_tanque.html")


def inspecao_tubos_cilindros(request):
    return render(request, "inspecao_tubos_cilindros.html")


def reteste_estanqueidade_tubos_cilindros(request):
    return
