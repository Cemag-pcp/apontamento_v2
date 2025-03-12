from django.shortcuts import render
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Prefetch
from django.utils import timezone
from .models import (
    Inspecao,
    DadosExecucaoInspecao,
    Reinspecao,
    Causas,
    CausasNaoConformidade,
    ArquivoCausa,
    InspecaoEstanqueidade,
    DadosExecucaoInspecaoEstanqueidade,
    ReinspecaoEstanqueidade,
    DetalhesPressaoTanque,
    InfoAdicionaisExecTubosCilindros,
    CausasEstanqueidadeTubosCilindros,
)
from core.models import Profile
from datetime import datetime, timedelta
import json


def inspecao_montagem(request):
    return render(request, "inspecao_montagem.html")


def inspecao_pintura(request):

    users = Profile.objects.filter(
        tipo_acesso="inspetor", permissoes__nome="inspecao/pintura"
    )
    causas = Causas.objects.filter(setor="pintura")

    cores = ["Amarelo", "Azul", "Cinza", "Laranja", "Verde", "Vermelho"]

    list_causas = [{"nome": causa.nome} for causa in causas]

    lista_inspetores = [
        {"nome_usuario": user.user.username, "id": user.user.id} for user in users
    ]

    return render(
        request,
        "inspecao_pintura.html",
        {"inspetores": lista_inspetores, "causas": list_causas, "cores": cores},
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
    itens_por_pagina = 12  # Itens por página

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
            "qtd_apontada": data.pecas_ordem_pintura.qtd_boa,
            "tipo": data.pecas_ordem_pintura.tipo,
            "operador": matricula_nome_operador,
        }

        dados.append(item)

    return JsonResponse(
        {
            "dados": dados,
            "total": quantidade_total,
            "total_filtrado": paginador.count,  # Total de itens após filtro
            "pagina_atual": pagina_obj.number,
            "total_paginas": paginador.num_pages,
        },
        status=200,
    )


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

        item = {
            "id": data.id,
            "data": data_ajustada.strftime("%d/%m/%Y %H:%M:%S"),
            "peca": data.pecas_ordem_pintura.peca,
            "maquina": data.pecas_ordem_pintura.ordem.maquina,
            "cor": data.pecas_ordem_pintura.ordem.cor,
            "tipo": data.pecas_ordem_pintura.tipo,
            "conformidade": DadosExecucaoInspecao.objects.filter(inspecao=data)
            .values_list("conformidade", flat=True)
            .first(),
            "nao_conformidade": DadosExecucaoInspecao.objects.filter(inspecao=data)
            .values_list("nao_conformidade", flat=True)
            .first(),
            "inspetor": DadosExecucaoInspecao.objects.filter(inspecao=data)
            .values_list("inspetor__user__username", flat=True)
            .first(),
        }

        dados.append(item)

    return JsonResponse(
        {
            "dados": dados,
            "total": quantidade_total,
            "total_filtrado": paginador.count,  # Total de itens após filtro
            "pagina_atual": pagina_obj.number,
            "total_paginas": paginador.num_pages,
        },
        status=200,
    )


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
    itens_por_pagina = 2  # Itens por página

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
        data_ajustada = DadosExecucaoInspecao.objects.filter(inspecao=data).values_list(
            "data_execucao", flat=True
        ).last() - timedelta(hours=3)

        possui_nao_conformidade = DadosExecucaoInspecao.objects.filter(
            inspecao=data, nao_conformidade__gt=0
        ).exists()

        item = {
            "id": data.id,
            "id_dados_execucao": DadosExecucaoInspecao.objects.filter(inspecao=data)
            .values_list("id", flat=True)
            .first(),
            "data": data_ajustada.strftime("%d/%m/%Y %H:%M:%S"),
            "peca": data.pecas_ordem_pintura.peca,
            "maquina": data.pecas_ordem_pintura.ordem.maquina,
            "cor": data.pecas_ordem_pintura.ordem.cor,
            "tipo": data.pecas_ordem_pintura.tipo,
            "inspetor": DadosExecucaoInspecao.objects.filter(inspecao=data)
            .values_list("inspetor__user__username", flat=True)
            .first(),
            "possui_nao_conformidade": possui_nao_conformidade,
        }

        dados.append(item)

    return JsonResponse(
        {
            "dados": dados,
            "total": quantidade_total,
            "total_filtrado": paginador.count,  # Total de itens após filtro
            "pagina_atual": pagina_obj.number,
            "total_paginas": paginador.num_pages,
        },
        status=200,
    )


def get_historico_pintura(request, id):

    if request.method != "GET":
        return JsonResponse({"error": "Método não permitido"}, status=405)

    dados = DadosExecucaoInspecao.objects.filter(inspecao__id=id).order_by("-id")

    list_history = []

    for dado in dados:

        data_ajustada = dado.data_execucao - timedelta(hours=3)

        list_history.append(
            {
                "id": dado.id,
                "data_execucao": data_ajustada.strftime("%d/%m/%Y %H:%M:%S"),
                "num_execucao": dado.num_execucao,
                "conformidade": dado.conformidade,
                "nao_conformidade": dado.nao_conformidade,
                "inspetor": dado.inspetor.user.username,
            }
        )

    return JsonResponse({"history": list_history}, status=200)


def envio_inspecao_pintura(request):
    if request.method != "POST":
        return JsonResponse({"error": "Método não permitido!"}, status=405)
    
    id_inspecao = request.POST.get("id-inspecao-pintura")

    teste = DadosExecucaoInspecao.objects.filter(inspecao__pk=id_inspecao).first()

    if teste:
        return JsonResponse({"error": "Item já inspecionado."}, status=400)

    with transaction.atomic():
        # Dados básicos
        data_inspecao = request.POST.get("data-inspecao-pintura")
        conformidade = request.POST.get("conformidade-inspecao-pintura")
        inspetor = request.POST.get("inspetor")
        nao_conformidade = request.POST.get("nao-conformidade-inspecao-pintura")
        quantidade_total_causas = request.POST.get("quantidade-total-causas")

        # Convertendo a string para um objeto datetime
        data_ajustada = timezone.make_aware(datetime.fromisoformat(data_inspecao))

        # Cria uma instância de DadosExecucaoInspecao
        inspecao = Inspecao.objects.get(id=id_inspecao)
        inspetor = Profile.objects.get(user__pk=inspetor)

        dados_execucao = DadosExecucaoInspecao(
            inspecao=inspecao,
            inspetor=inspetor,
            data_execucao=data_ajustada,
            conformidade=int(conformidade),
            nao_conformidade=int(nao_conformidade),
        )
        dados_execucao.save()

        # Verifica se há não conformidade
        if int(nao_conformidade) > 0:
            # Cria uma instância de Reinspecao
            reinspecao = Reinspecao(dados_execucao=dados_execucao)
            reinspecao.save()

            # Itera sobre todas as causas (causas_1, causas_2, etc.)
            for i in range(1, int(quantidade_total_causas) + 1):
                causas = request.POST.getlist(f"causas_{i}[]")  # Lista de causas
                quantidade = request.POST.get(f"quantidade_{i}")
                imagens = request.FILES.getlist(f"imagens_{i}[]")  # Lista de arquivos

                # Itera sobre cada causa
                for causa_nome in causas:
                    causa = Causas.objects.get(nome=causa_nome)
                    causa_nao_conformidade, created = (
                        CausasNaoConformidade.objects.get_or_create(
                            dados_execucao=dados_execucao, quantidade=int(quantidade)
                        )
                    )
                    causa_nao_conformidade.causa.add(causa)

                # Itera sobre cada imagem
                for imagem in imagens:
                    arquivo_causa = ArquivoCausa(
                        causa_nao_conformidade=causa_nao_conformidade, arquivo=imagem
                    )
                    arquivo_causa.save()

    return JsonResponse({"success": True})


def inspecao_estamparia(request):
    return render(request, "inspecao_estamparia.html")


def inspecao_tanque(request):
    return render(request, "inspecao_tanque.html")


def inspecao_tubos_cilindros(request):
    return render(request, "inspecao_tubos_cilindros.html")


def reteste_estanqueidade_tubos_cilindros(request):
    return
