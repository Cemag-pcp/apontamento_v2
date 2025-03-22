from django.shortcuts import render
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q, Prefetch, OuterRef, Subquery, Max
from django.db import transaction
from django.utils import timezone
from cadastro.models import PecasEstanqueidade
from apontamento_pintura.models import Retrabalho
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
    CausasNaoConformidadeEstanqueidade,
    ArquivoCausaEstanqueidade,
)
from core.models import Profile, Maquina
from datetime import datetime, timedelta
from collections import defaultdict
import json


def inspecao_montagem(request):
    users = Profile.objects.filter(
        tipo_acesso="inspetor", permissoes__nome="inspecao/montagem"
    )
    causas = Causas.objects.filter(setor="montagem")

    maquinas = list(
        Maquina.objects.filter(tipo="maquina", setor_id__nome="montagem").values_list(
            "nome", flat=True
        )
    )

    print(maquinas)

    list_causas = [{"id": causa.id, "nome": causa.nome} for causa in causas]

    lista_inspetores = [
        {"nome_usuario": user.user.username, "id": user.user.id} for user in users
    ]

    return render(
        request,
        "inspecao_montagem.html",
        {"inspetores": lista_inspetores, "causas": list_causas, "maquinas": maquinas},
    )


def inspecao_pintura(request):

    users = Profile.objects.filter(
        tipo_acesso="inspetor", permissoes__nome="inspecao/pintura"
    )
    causas = Causas.objects.filter(setor="pintura")

    cores = ["Amarelo", "Azul", "Cinza", "Laranja", "Verde", "Vermelho"]

    list_causas = [{"id": causa.id, "nome": causa.nome} for causa in causas]

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
        Reinspecao.objects.filter(
            reinspecionado=False  # Mantém o filtro original
        ).values_list("inspecao", flat=True)
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
    itens_por_pagina = 12  # Itens por página

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

        status_reinspecao = (
            Retrabalho.objects.filter(reinspecao__inspecao=data)
            .values_list("status", flat=True)
            .first()
        )
        print(status_reinspecao )

        item = {
            "id": data.id,
            "data": data_ajustada.strftime("%d/%m/%Y %H:%M:%S"),
            "peca": data.pecas_ordem_pintura.peca,
            "cor": data.pecas_ordem_pintura.ordem.cor,
            "tipo": data.pecas_ordem_pintura.tipo,
            "conformidade": DadosExecucaoInspecao.objects.filter(inspecao=data)
            .values_list("conformidade", flat=True)
            .last(),
            "nao_conformidade": DadosExecucaoInspecao.objects.filter(inspecao=data)
            .values_list("nao_conformidade", flat=True)
            .last(),
            "inspetor": DadosExecucaoInspecao.objects.filter(inspecao=data)
            .values_list("inspetor__user__username", flat=True)
            .last(),
            "status_reinspecao": status_reinspecao,
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
    itens_por_pagina = 12  # Itens por página

    # Filtra os dados
    datas = Inspecao.objects.filter(
        id__in=inspecionados_ids, pecas_ordem_pintura__isnull=False
    )

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

    # Otimiza a consulta usando select_related para trazer dados relacionados
    dados = (
        DadosExecucaoInspecao.objects.filter(inspecao__id=id)
        .select_related("inspetor__user")
        .order_by("-id")
    )

    # Usa list comprehension para construir a lista de histórico
    list_history = [
        {
            "id": dado.id,
            "data_execucao": (dado.data_execucao - timedelta(hours=3)).strftime(
                "%d/%m/%Y %H:%M:%S"
            ),
            "num_execucao": dado.num_execucao,
            "conformidade": dado.conformidade,
            "nao_conformidade": dado.nao_conformidade,
            "inspetor": dado.inspetor.user.username,  # Já está otimizado com select_related
        }
        for dado in dados
    ]

    return JsonResponse({"history": list_history}, status=200)


def get_historico_causas_pintura(request, id):
    if request.method != "GET":
        return JsonResponse({"error": "Método não permitido"}, status=405)

    causas_nao_conformidade = CausasNaoConformidade.objects.filter(
        dados_execucao__id=id
    ).prefetch_related("causa", "arquivos")

    causas_dict = defaultdict(
        lambda: {
            "id_cnc": None,
            "nomes": [],
            "setor": None,
            "quantidade": None,
            "imagens": [],
        }
    )

    for cnc in causas_nao_conformidade:
        for causa in cnc.causa.all():
            if causas_dict[cnc.id]["id_cnc"] is None:
                causas_dict[cnc.id]["id_cnc"] = cnc.id
                causas_dict[cnc.id]["setor"] = causa.setor
                causas_dict[cnc.id]["quantidade"] = cnc.quantidade
                causas_dict[cnc.id]["imagens"] = [
                    {"id": arquivo.id, "url": arquivo.arquivo.url}
                    for arquivo in cnc.arquivos.all()
                ]
            causas_dict[cnc.id]["nomes"].append(causa.nome)

    causas_list = list(causas_dict.values())

    print(causas_list)

    return JsonResponse({"causas": causas_list}, status=200)


def envio_inspecao_pintura(request):
    if request.method != "POST":
        return JsonResponse({"error": "Método não permitido!"}, status=405)

    id_inspecao = request.POST.get("id-inspecao-pintura")
    # Verifica se já existe uma inspeção com o mesmo ID
    if DadosExecucaoInspecao.objects.filter(inspecao__pk=id_inspecao).exists():
        return JsonResponse({"error": "Item já inspecionado."}, status=400)

    try:
        with transaction.atomic():
            # Dados básicos
            data_inspecao = request.POST.get("data-inspecao-pintura")
            conformidade = request.POST.get("conformidade-inspecao-pintura")
            inspetor_id = request.POST.get("inspetor")
            nao_conformidade = request.POST.get("nao-conformidade-inspecao-pintura")
            quantidade_total_causas = int(
                request.POST.get("quantidade-total-causas", 0)
            )

            # Convertendo a string para um objeto datetime
            data_ajustada = timezone.make_aware(datetime.fromisoformat(data_inspecao))

            # Obtém a inspeção e o inspetor
            inspecao = Inspecao.objects.get(id=id_inspecao)
            inspetor = Profile.objects.get(user__pk=inspetor_id)

            # Cria uma instância de DadosExecucaoInspecao
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
                reinspecao = Reinspecao(inspecao=inspecao, reinspecionado=False)
                reinspecao.save()

                retrabalho = Retrabalho(reinspecao=reinspecao, status="a retrabalhar")
                retrabalho.save()

                # Itera sobre todas as causas (causas_1, causas_2, etc.)
                for i in range(1, quantidade_total_causas + 1):
                    causas = request.POST.getlist(f"causas_{i}")  # Lista de causas
                    quantidade = request.POST.get(f"quantidade_{i}")
                    imagens = request.FILES.getlist(f"imagens_{i}")  # Lista de arquivos

                    # Obtém todas as causas de uma vez
                    causas_objs = Causas.objects.filter(id__in=causas)
                    causa_nao_conformidade = CausasNaoConformidade.objects.create(
                        dados_execucao=dados_execucao, quantidade=int(quantidade)
                    )
                    causa_nao_conformidade.causa.add(*causas_objs)

                    # Itera sobre cada imagem
                    for imagem in imagens:
                        ArquivoCausa.objects.create(
                            causa_nao_conformidade=causa_nao_conformidade,
                            arquivo=imagem,
                        )

        return JsonResponse({"success": True})

    except Exception as e:
        return JsonResponse({"error": e}, status=400)


def envio_reinspecao_pintura(request):
    if request.method != "POST":
        return JsonResponse({"error": "Método não permitido!"}, status=405)

    try:
        with transaction.atomic():
            id_inspecao = request.POST.get("id-reinspecao-pintura")
            data_inspecao = request.POST.get("data-reinspecao-pintura")
            conformidade = request.POST.get("conformidade-reinspecao-pintura")
            inspetor = request.POST.get("inspetor-reinspecao-pintura")
            nao_conformidade = request.POST.get("nao-conformidade-reinspecao-pintura")
            quantidade_total_causas = request.POST.get("quantidade-total-causas")

            data_ajustada = timezone.make_aware(datetime.fromisoformat(data_inspecao))

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

            if int(nao_conformidade) > 0:

                for i in range(1, int(quantidade_total_causas) + 1):
                    causas = request.POST.getlist(
                        f"causas_reinspecao_{i}"
                    )  # Lista de causas
                    quantidade = request.POST.get(f"quantidade_reinspecao_{i}")
                    imagens = request.FILES.getlist(f"imagens_reinspecao_{i}")

                    # Obtém todas as causas de uma vez
                    causas_objs = Causas.objects.filter(id__in=causas)
                    causa_nao_conformidade = CausasNaoConformidade.objects.create(
                        dados_execucao=dados_execucao, quantidade=int(quantidade)
                    )
                    causa_nao_conformidade.causa.add(*causas_objs)

                    # Itera sobre cada imagem
                    for imagem in imagens:
                        ArquivoCausa.objects.create(
                            causa_nao_conformidade=causa_nao_conformidade,
                            arquivo=imagem,
                        )
            else:
                print(inspecao)
                reinspecao = Reinspecao.objects.filter(inspecao=inspecao).first()
                reinspecao.reinspecionado = True
                reinspecao.save()

        return JsonResponse({"success": True})

    except Exception as e:
        return JsonResponse({"error": "Erro"}, status=400)


def get_itens_inspecao_montagem(request):
    if request.method != "GET":
        return JsonResponse({"error": "Método não permitido"}, status=405)

    inspecoes_ids = set(
        DadosExecucaoInspecao.objects.values_list("inspecao", flat=True)
    )

    # Captura os parâmetros enviados na URL
    maquinas_filtradas = (
        request.GET.get("maquinas", "").split(",")
        if request.GET.get("maquinas")
        else []
    )
    data_filtrada = request.GET.get("data", None)
    pesquisa_filtrada = request.GET.get("pesquisar", None)
    pagina = int(request.GET.get("pagina", 1))  # Página atual, padrão é 1
    itens_por_pagina = 12  # Itens por página

    # Filtra os dados
    datas = Inspecao.objects.filter(pecas_ordem_montagem__isnull=False).exclude(
        id__in=inspecoes_ids
    )

    quantidade_total = datas.count()  # Total de itens sem filtro

    if maquinas_filtradas:
        datas = datas.filter(
            pecas_ordem_montagem__ordem__maquina__nome__in=maquinas_filtradas
        )

    if data_filtrada:
        datas = datas.filter(data_inspecao__date=data_filtrada)

    if pesquisa_filtrada:
        pesquisa_filtrada = pesquisa_filtrada.lower()
        datas = datas.filter(pecas_ordem_montagem__peca__icontains=pesquisa_filtrada)

    datas = datas.select_related(
        "pecas_ordem_montagem",
        "pecas_ordem_montagem__ordem",
        "pecas_ordem_montagem__operador",
    ).order_by("-id")

    # Paginação
    paginador = Paginator(datas, itens_por_pagina)
    pagina_obj = paginador.get_page(pagina)

    dados = []
    for data in pagina_obj:
        data_ajustada = data.data_inspecao - timedelta(hours=3)
        matricula_nome_operador = None

        if data.pecas_ordem_montagem.operador:
            matricula_nome_operador = f"{data.pecas_ordem_montagem.operador.matricula} - {data.pecas_ordem_montagem.operador.nome}"

        item = {
            "id": data.id,
            "data": data_ajustada.strftime("%d/%m/%Y %H:%M:%S"),
            "peca": data.pecas_ordem_montagem.peca,
            "maquina": data.pecas_ordem_montagem.ordem.maquina.nome,
            "qtd_apontada": data.pecas_ordem_montagem.qtd_boa,
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


def get_itens_reinspecao_montagem(request):
    if request.method != "GET":
        return JsonResponse({"error": "Método não permitido"}, status=405)

    reinspecao_ids = set(
        Reinspecao.objects.filter(reinspecionado=False).values_list(
            "inspecao", flat=True
        )
    )

    # Captura os filtros enviados pela URL
    maquinas_filtradas = (
        request.GET.get("maquinas", "").split(",")
        if request.GET.get("maquinas")
        else []
    )
    inspetores_filtrados = (
        request.GET.get("inspetores", "").split(",")
        if request.GET.get("inspetores")
        else []
    )
    data_filtrada = request.GET.get("data", None)
    pesquisa_filtrada = request.GET.get("pesquisar", None)
    pagina = int(request.GET.get("pagina", 1))  # Página atual, padrão é 1
    itens_por_pagina = 12  # Itens por página

    # Filtra os dados
    datas = Inspecao.objects.filter(
        id__in=reinspecao_ids, pecas_ordem_montagem__isnull=False
    )

    quantidade_total = datas.count()  # Total de itens sem filtro

    if maquinas_filtradas:
        datas = datas.filter(
            pecas_ordem_montagem__ordem__maquina__nome__in=maquinas_filtradas
        )

    if data_filtrada:
        datas = datas.filter(data_inspecao__date=data_filtrada)

    if pesquisa_filtrada:
        pesquisa_filtrada = pesquisa_filtrada.lower()
        datas = datas.filter(pecas_ordem_montagem__peca__icontains=pesquisa_filtrada)

    if inspetores_filtrados:
        datas = datas.filter(
            dadosexecucaoinspecao__inspetor__user__username__in=inspetores_filtrados
        )

    datas = datas.select_related(
        "pecas_ordem_montagem",
        "pecas_ordem_montagem__ordem",
        "pecas_ordem_montagem__operador",
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
            "peca": data.pecas_ordem_montagem.peca,
            "maquina": data.pecas_ordem_montagem.ordem.maquina.nome,
            "conformidade": DadosExecucaoInspecao.objects.filter(inspecao=data)
            .values_list("conformidade", flat=True)
            .last(),
            "nao_conformidade": DadosExecucaoInspecao.objects.filter(inspecao=data)
            .values_list("nao_conformidade", flat=True)
            .last(),
            "inspetor": DadosExecucaoInspecao.objects.filter(inspecao=data)
            .values_list("inspetor__user__username", flat=True)
            .last(),
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


def get_itens_inspecionados_montagem(request):
    if request.method != "GET":
        return JsonResponse({"error": "Método não permitido"}, status=405)

    inspecionados_ids = set(
        DadosExecucaoInspecao.objects.values_list("inspecao", flat=True)
    )

    print(inspecionados_ids)

    # Captura os filtros aplicados pela URL
    maquinas_filtradas = (
        request.GET.get("maquinas", "").split(",")
        if request.GET.get("maquinas")
        else []
    )
    inspetores_filtrados = (
        request.GET.get("inspetores", "").split(",")
        if request.GET.get("inspetores")
        else []
    )
    data_filtrada = request.GET.get("data", None)
    pesquisa_filtrada = request.GET.get("pesquisar", None)
    pagina = int(request.GET.get("pagina", 1))  # Página atual, padrão é 1
    itens_por_pagina = 12  # Itens por página

    # Filtra os dados
    datas = Inspecao.objects.filter(
        id__in=inspecionados_ids, pecas_ordem_montagem__isnull=False
    )

    quantidade_total = datas.count()  # Total de itens sem filtro

    if maquinas_filtradas:
        datas = datas.filter(
            pecas_ordem_montagem__ordem__maquina__nome__in=maquinas_filtradas
        )

    if data_filtrada:
        datas = datas.filter(data_inspecao__date=data_filtrada)

    if pesquisa_filtrada:
        datas = datas.filter(pecas_ordem_montagem__peca__icontains=pesquisa_filtrada)

    if inspetores_filtrados:
        datas = datas.filter(
            dadosexecucaoinspecao__inspetor__user__username__in=inspetores_filtrados
        )

    datas = datas.select_related(
        "pecas_ordem_montagem",
        "pecas_ordem_montagem__ordem",
        "pecas_ordem_montagem__operador",
    ).order_by("-id")

    # Paginação
    paginador = Paginator(datas, itens_por_pagina)
    pagina_obj = paginador.get_page(pagina)

    dados_execucao = DadosExecucaoInspecao.objects.filter(
        inspecao__in=pagina_obj
    ).select_related(
        "inspecao", "inspetor__user", "inspecao__pecas_ordem_montagem__ordem__maquina"
    )

    # Cria um dicionário para mapear inspecao_id para seus dados de execução
    dados_execucao_dict = {de.inspecao_id: de for de in dados_execucao}

    dados = []
    for data in pagina_obj:
        de = dados_execucao_dict.get(data.id)

        if de:
            data_ajustada = de.data_execucao - timedelta(hours=3)
            possui_nao_conformidade = de.nao_conformidade > 0 or de.num_execucao > 0

            item = {
                "id": data.id,
                "id_dados_execucao": de.id,
                "data": data_ajustada.strftime("%d/%m/%Y %H:%M:%S"),
                "peca": data.pecas_ordem_montagem.peca,
                "maquina": data.pecas_ordem_montagem.ordem.maquina.nome,
                "inspetor": de.inspetor.user.username if de.inspetor else None,
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


def get_historico_montagem(request, id):
    if request.method != "GET":
        return JsonResponse({"error": "Método não permitido"}, status=405)

    # Otimiza a consulta usando select_related para trazer dados relacionados
    dados = (
        DadosExecucaoInspecao.objects.filter(inspecao__id=id)
        .select_related("inspetor__user")
        .order_by("-id")
    )

    # Usa list comprehension para construir a lista de histórico
    list_history = [
        {
            "id": dado.id,
            "data_execucao": (dado.data_execucao - timedelta(hours=3)).strftime(
                "%d/%m/%Y %H:%M:%S"
            ),
            "num_execucao": dado.num_execucao,
            "conformidade": dado.conformidade,
            "nao_conformidade": dado.nao_conformidade,
            "inspetor": dado.inspetor.user.username,  # Já está otimizado com select_related
        }
        for dado in dados
    ]

    return JsonResponse({"history": list_history}, status=200)


def get_historico_causas_montagem(request, id):
    if request.method != "GET":
        return JsonResponse({"error": "Método não permitido"}, status=405)

    causas_nao_conformidade = CausasNaoConformidade.objects.filter(
        dados_execucao__id=id
    ).prefetch_related("causa", "arquivos")

    causas_dict = defaultdict(
        lambda: {
            "id_cnc": None,
            "nomes": [],
            "setor": None,
            "quantidade": None,
            "imagens": [],
        }
    )

    for cnc in causas_nao_conformidade:
        for causa in cnc.causa.all():
            if causas_dict[cnc.id]["id_cnc"] is None:
                causas_dict[cnc.id]["id_cnc"] = cnc.id
                causas_dict[cnc.id]["setor"] = causa.setor
                causas_dict[cnc.id]["quantidade"] = cnc.quantidade
                causas_dict[cnc.id]["imagens"] = [
                    {"id": arquivo.id, "url": arquivo.arquivo.url}
                    for arquivo in cnc.arquivos.all()
                ]
            causas_dict[cnc.id]["nomes"].append(causa.nome)

    causas_list = list(causas_dict.values())

    print(causas_list)

    return JsonResponse({"causas": causas_list}, status=200)


def envio_inspecao_montagem(request):
    if request.method != "POST":
        return JsonResponse({"error": "Método não permitido!"}, status=405)

    id_inspecao = request.POST.get("id-inspecao-montagem")

    if DadosExecucaoInspecao.objects.filter(inspecao__pk=id_inspecao).exists():
        return JsonResponse({"error": "Item já inspecionado."}, status=400)

    try:
        with transaction.atomic():
            data_inspecao = request.POST.get("data-inspecao-montagem")
            conformidade = request.POST.get("conformidade-inspecao-montagem")
            inspetor_id = request.POST.get("inspetor-inspecao-montagem")
            nao_conformidade = request.POST.get("nao-conformidade-inspecao-montagem")
            observacao = request.POST.get("observacao-inspecao-montagem")
            quantidade_total_causas = int(
                request.POST.get("quantidade-total-causas", 0)
            )

            # Convertendo a string para um objeto datetime
            data_ajustada = timezone.make_aware(datetime.fromisoformat(data_inspecao))

            # Obtém a inspeção e o inspetor
            inspecao = Inspecao.objects.get(id=id_inspecao)
            inspetor = Profile.objects.get(user__pk=inspetor_id)

            # Cria uma instância de DadosExecucaoInspecao
            dados_execucao = DadosExecucaoInspecao(
                inspecao=inspecao,
                inspetor=inspetor,
                data_execucao=data_ajustada,
                conformidade=int(conformidade),
                nao_conformidade=int(nao_conformidade),
                observacao=observacao,
            )
            dados_execucao.save()

            # Verifica se há não conformidade
            if int(nao_conformidade) > 0:
                # Cria uma instância de Reinspecao
                reinspecao = Reinspecao(inspecao=inspecao, reinspecionado=False)
                reinspecao.save()

                # Itera sobre todas as causas (causas_1, causas_2, etc.)
                for i in range(1, quantidade_total_causas + 1):
                    causas = request.POST.getlist(f"causas_{i}")  # Lista de causas
                    quantidade = request.POST.get(f"quantidade_{i}")
                    imagens = request.FILES.getlist(f"imagens_{i}")  # Lista de arquivos

                    # Obtém todas as causas de uma vez
                    causas_objs = Causas.objects.filter(id__in=causas)
                    causa_nao_conformidade = CausasNaoConformidade.objects.create(
                        dados_execucao=dados_execucao, quantidade=int(quantidade)
                    )
                    causa_nao_conformidade.causa.add(*causas_objs)

                    # Itera sobre cada imagem
                    for imagem in imagens:
                        ArquivoCausa.objects.create(
                            causa_nao_conformidade=causa_nao_conformidade,
                            arquivo=imagem,
                        )

        return JsonResponse({"success": True})

    except Exception as e:
        return JsonResponse({"error": "Erro"}, status=400)


def envio_reinspecao_montagem(request):
    if request.method != "POST":
        return JsonResponse({"error": "Método não permitido!"}, status=405)

    try:
        with transaction.atomic():
            id_inspecao = request.POST.get("id-reinspecao-montagem")
            data_inspecao = request.POST.get("data-reinspecao-montagem")
            conformidade = request.POST.get("conformidade-reinspecao-montagem")
            inspetor = request.POST.get("inspetor-reinspecao-montagem")
            nao_conformidade = request.POST.get("nao-conformidade-reinspecao-montagem")
            quantidade_total_causas = request.POST.get("quantidade-total-causas")
            observacao = request.POST.get("observacao-reinspecao-montagem")

            data_ajustada = timezone.make_aware(datetime.fromisoformat(data_inspecao))

            inspecao = Inspecao.objects.get(id=id_inspecao)
            inspetor = Profile.objects.get(user__pk=inspetor)

            dados_execucao = DadosExecucaoInspecao(
                inspecao=inspecao,
                inspetor=inspetor,
                data_execucao=data_ajustada,
                conformidade=int(conformidade),
                nao_conformidade=int(nao_conformidade),
                observacao=observacao,
            )
            dados_execucao.save()

            if int(nao_conformidade) > 0:

                for i in range(1, int(quantidade_total_causas) + 1):
                    causas = request.POST.getlist(
                        f"causas_reinspecao_{i}"
                    )  # Lista de causas
                    quantidade = request.POST.get(f"quantidade_reinspecao_{i}")
                    imagens = request.FILES.getlist(
                        f"imagens_reinspecao_{i}"
                    )  # Lista de arquivos

                    # Obtém todas as causas de uma vez
                    causas_objs = Causas.objects.filter(id__in=causas)
                    causa_nao_conformidade = CausasNaoConformidade.objects.create(
                        dados_execucao=dados_execucao, quantidade=int(quantidade)
                    )
                    causa_nao_conformidade.causa.add(*causas_objs)

                    # Itera sobre cada imagem
                    for imagem in imagens:
                        ArquivoCausa.objects.create(
                            causa_nao_conformidade=causa_nao_conformidade,
                            arquivo=imagem,
                        )
            else:
                reinspecao = Reinspecao.objects.filter(inspecao=inspecao).first()
                reinspecao.reinspecionado = True
                reinspecao.save()

        return JsonResponse({"success": True})

    except Exception as e:
        return JsonResponse({"error": e}, status=400)


def inspecao_estamparia(request):
    return render(request, "inspecao_estamparia.html")


def inspecao_tanque(request):

    users = Profile.objects.filter(
        tipo_acesso="inspetor", permissoes__nome="inspecao/tanque"
    )

    lista_inspetores = [
        {"nome_usuario": user.user.username, "id": user.user.id} for user in users
    ]

    tanques = PecasEstanqueidade.objects.filter(tipo="tanque")

    dict_tanques = [
        {"peca": f"{tanque.codigo} - {tanque.descricao}"} for tanque in tanques
    ]

    return render(
        request,
        "inspecao_tanque.html",
        {"tanques": dict_tanques, "inspetores": lista_inspetores},
    )


def inspecao_tubos_cilindros(request):

    users = Profile.objects.filter(
        tipo_acesso="inspetor", permissoes__nome="inspecao/tubos-cilindros"
    )

    lista_inspetores = [
        {"nome_usuario": user.user.username, "id": user.user.id} for user in users
    ]

    causas = Causas.objects.filter(setor="tubos cilindros")

    list_causas = [{"id": causa.id, "nome": causa.nome} for causa in causas]

    pecas = PecasEstanqueidade.objects.filter(tipo__in=["tubo", "cilindro"])

    list_pecas_tubos = [
        {"peca": f"{peca.codigo} - {peca.descricao}"}
        for peca in pecas
        if peca.tipo == "tubo"
    ]
    list_pecas_cilindros = [
        {"peca": f"{peca.codigo} - {peca.descricao}"}
        for peca in pecas
        if peca.tipo == "cilindro"
    ]

    return render(
        request,
        "inspecao_tubos_cilindros.html",
        {
            "inspetores": lista_inspetores,
            "causas": list_causas,
            "pecas_tubos": list_pecas_tubos,
            "pecas_cilindros": list_pecas_cilindros,
        },
    )


def get_itens_reinspecao_tubos_cilindros(request):
    if request.method != "GET":
        return JsonResponse({"error": "Método não permitido"}, status=405)

    # Filtros
    inspetores_filtrados = (
        request.GET.get("inspetores", "").split(",")
        if request.GET.get("inspetores")
        else []
    )
    data_filtrada = request.GET.get("data", None)
    pesquisa_filtrada = request.GET.get("pesquisar", None)
    pagina = int(request.GET.get("pagina", 1))  # Página atual, padrão é 1
    itens_por_pagina = 12  # Itens por página

    # Consulta base
    reinspecao_ids = ReinspecaoEstanqueidade.objects.filter(
        reinspecionado=False
    ).values_list("inspecao", flat=True)
    datas = InspecaoEstanqueidade.objects.filter(
        id__in=reinspecao_ids, peca__tipo__in=["tubo", "cilindro"]
    )

    # Aplicar filtros
    if data_filtrada:
        datas = datas.filter(data_inspecao__date=data_filtrada)
    if pesquisa_filtrada:
        datas = datas.filter(
            Q(peca__codigo__icontains=pesquisa_filtrada)
            | Q(peca__descricao__icontains=pesquisa_filtrada)
        )
    if inspetores_filtrados:
        datas = datas.filter(
            dadosexecucaoinspecaoestanqueidade__inspetor__user__username__in=inspetores_filtrados
        )

    # Ordenação e paginação
    datas = datas.select_related("peca").order_by("-id")
    paginador = Paginator(datas, itens_por_pagina)
    pagina_obj = paginador.get_page(pagina)

    # Prefetch para otimizar a consulta dos dados de execução e informações adicionais
    dados_execucao = (
        DadosExecucaoInspecaoEstanqueidade.objects.filter(
            inspecao_estanqueidade__in=pagina_obj
        )
        .select_related("inspetor__user", "inspecao_estanqueidade__peca")
        .prefetch_related(
            Prefetch("infoadicionaisexectuboscilindros_set", to_attr="info_adicionais")
        )
    )

    # Cria um dicionário para mapear inspecao_id para seus dados de execução e informações adicionais
    dados_execucao_dict = {de.inspecao_estanqueidade_id: de for de in dados_execucao}

    # Montagem dos dados
    dados = []
    for data in pagina_obj:
        de = dados_execucao_dict.get(data.id)
        if de:
            info_adicionais = de.info_adicionais[0] if de.info_adicionais else None
            data_ajustada = de.data_exec - timedelta(hours=3)
            possui_nao_conformidade = (
                (
                    info_adicionais.nao_conformidade
                    + info_adicionais.nao_conformidade_refugo
                    > 0
                )
                if info_adicionais
                else False
            ) or de.num_execucao > 0

            item = {
                "id": data.id,
                "tipo_inspecao": data.peca.tipo,
                "id_dados_execucao": de.id,
                "data": data_ajustada.strftime("%d/%m/%Y %H:%M:%S"),
                "peca": f"{data.peca.codigo} - {data.peca.descricao}",
                "inspetor": de.inspetor.user.username if de.inspetor else None,
                "possui_nao_conformidade": possui_nao_conformidade,
                "nao_conformidade": (
                    info_adicionais.nao_conformidade if info_adicionais else 0
                ),
                "nao_conformidade_refugo": (
                    info_adicionais.nao_conformidade_refugo if info_adicionais else 0
                ),
                "qtd_inspecionada": (
                    info_adicionais.qtd_inspecionada if info_adicionais else 0
                ),
                "observacao": info_adicionais.observacao if info_adicionais else None,
            }
            dados.append(item)

    return JsonResponse(
        {
            "dados": dados,
            "total": paginador.count,  # Total de itens após filtro
            "pagina_atual": pagina_obj.number,
            "total_paginas": paginador.num_pages,
        },
        status=200,
    )


def get_itens_inspecionados_tubos_cilindros(request):
    if request.method != "GET":
        return JsonResponse({"error": "Método não permitido"}, status=405)

    # Filtra apenas peças do tipo "tubo" ou "cilindro"
    pecas_filtradas = PecasEstanqueidade.objects.filter(tipo__in=["tubo", "cilindro"])
    inspecionados_ids = set(
        DadosExecucaoInspecaoEstanqueidade.objects.filter(
            inspecao_estanqueidade__peca__in=pecas_filtradas
        ).values_list("inspecao_estanqueidade", flat=True)
    )

    # Filtros
    inspetores_filtrados = (
        request.GET.get("inspetores", "").split(",")
        if request.GET.get("inspetores")
        else []
    )
    data_filtrada = request.GET.get("data", None)
    pesquisa_filtrada = request.GET.get("pesquisar", None)
    pagina = int(request.GET.get("pagina", 1))  # Página atual, padrão é 1
    itens_por_pagina = 12  # Itens por página

    # Filtra os dados
    datas = InspecaoEstanqueidade.objects.filter(id__in=inspecionados_ids).order_by(
        "-id"
    )

    quantidade_total = datas.count()

    if data_filtrada:
        datas = datas.filter(data_inspecao__date=data_filtrada)

    if pesquisa_filtrada:
        if " - " in pesquisa_filtrada:
            codigo, descricao = pesquisa_filtrada.split(" - ", 1)
            codigo = codigo.strip()
            descricao = descricao.strip()
            datas = datas.filter(
                Q(peca__codigo__icontains=codigo)
                & Q(peca__descricao__icontains=descricao)
            )
        else:
            datas = datas.filter(
                Q(peca__codigo__icontains=pesquisa_filtrada)
                | Q(peca__descricao__icontains=pesquisa_filtrada)
            )

    if inspetores_filtrados:
        datas = datas.filter(
            dadosexecucaoinspecaoestanqueidade__inspetor__user__username__in=inspetores_filtrados
        )

    # Subconsulta para obter o maior num_execucao para cada inspecao_estanqueidade
    maior_num_execucao_subquery = (
        DadosExecucaoInspecaoEstanqueidade.objects.filter(
            inspecao_estanqueidade=OuterRef("inspecao_estanqueidade")
        )
        .values("inspecao_estanqueidade")
        .annotate(max_num_execucao=Max("num_execucao"))
        .values("max_num_execucao")
    )

    # Filtra os dados de execução para incluir apenas os registros com o maior num_execucao
    dados_execucao = (
        DadosExecucaoInspecaoEstanqueidade.objects.filter(
            inspecao_estanqueidade__in=datas,
            num_execucao=Subquery(maior_num_execucao_subquery),
        )
        .select_related("inspetor__user", "inspecao_estanqueidade__peca")
        .prefetch_related("infoadicionaisexectuboscilindros_set")
    )

    # Cria um dicionário para mapear inspecao_id para seus dados de execução e informações adicionais
    dados_execucao_dict = {
        de.inspecao_estanqueidade_id: {
            "dados_execucao": de,
            "info_adicionais": de.infoadicionaisexectuboscilindros_set.first(),
        }
        for de in dados_execucao
    }

    # Paginação
    paginador = Paginator(datas, itens_por_pagina)
    pagina_obj = paginador.get_page(pagina)

    dados = []
    for data in pagina_obj:
        de_info = dados_execucao_dict.get(data.id)
        if de_info:
            de = de_info["dados_execucao"]
            info_adicionais = de_info["info_adicionais"]

            data_ajustada = de.data_exec - timedelta(hours=3)
            possui_nao_conformidade = (
                info_adicionais.nao_conformidade
                + info_adicionais.nao_conformidade_refugo
                > 0
            ) or de.num_execucao > 0

            item = {
                "id": data.id,
                "id_dados_execucao": de.id,
                "data": data_ajustada.strftime("%d/%m/%Y %H:%M:%S"),
                "peca": f"{data.peca.codigo} - {data.peca.descricao}",
                "inspetor": de.inspetor.user.username if de.inspetor else None,
                "possui_nao_conformidade": possui_nao_conformidade,
                "nao_conformidade": (
                    info_adicionais.nao_conformidade if info_adicionais else 0
                ),
                "nao_conformidade_refugo": (
                    info_adicionais.nao_conformidade_refugo if info_adicionais else 0
                ),
                "qtd_inspecionada": (
                    info_adicionais.qtd_inspecionada if info_adicionais else 0
                ),
                "observacao": info_adicionais.observacao if info_adicionais else None,
            }

            dados.append(item)

    return JsonResponse(
        {
            "dados": dados,
            "total": quantidade_total,
            "total_filtrado": paginador.count,
            "pagina_atual": pagina_obj.number,
            "total_paginas": paginador.num_pages,
        },
        status=200,
    )


def envio_inspecao_tubos_cilindros(request):

    if request.method != "POST":
        return JsonResponse({"error": "Método não permitido!"}, status=405)

    try:
        with transaction.atomic():
            # Dados básicos
            print(request.POST)
            data_inspecao = request.POST.get("data_inspecao")
            inspetor_id = request.POST.get("inspetor")
            peca = request.POST.get("peca")
            quantidade_inspecionada = int(
                request.POST.get("quantidade_inspecionada", 0)
            )
            nao_conformidade = int(request.POST.get("nao_conformidade", 0))
            nao_conformidade_refugo = int(
                request.POST.get("nao_conformidade_refugo", 0)
            )
            observacao = request.POST.get("observacao")
            quantidade_total_causas = int(
                request.POST.get("quantidade-total-causas", 0)
            )
            tipo_inspecao = request.POST.get("tipo_inspecao")  # "Cilindro" ou "Tubo"
            conformidade = (
                quantidade_inspecionada - nao_conformidade - nao_conformidade_refugo
            )
            nao_conformidade_total = nao_conformidade + nao_conformidade_refugo

            # Convertendo a string para um objeto datetime
            data_ajustada = timezone.make_aware(datetime.fromisoformat(data_inspecao))

            codigo = peca.split(" - ", maxsplit=1)[0]
            descricao = peca.split(" - ", maxsplit=1)[1]

            peca_estanqueidade = PecasEstanqueidade.objects.filter(
                codigo=codigo
            ).first()

            inspecao = InspecaoEstanqueidade(
                data_inspecao=data_ajustada, peca=peca_estanqueidade
            )
            inspecao.save()

            inspetor = Profile.objects.get(user__pk=inspetor_id)
            dados_execucao = DadosExecucaoInspecaoEstanqueidade(
                inspecao_estanqueidade=inspecao,
                inspetor=inspetor,
                data_exec=data_ajustada,
            )
            dados_execucao.save()

            informacoes_tubos_cilindros = InfoAdicionaisExecTubosCilindros(
                dados_exec_inspecao=dados_execucao,
                nao_conformidade=nao_conformidade,
                nao_conformidade_refugo=nao_conformidade_refugo,
                qtd_inspecionada=quantidade_inspecionada,
                observacao=observacao,
            )
            informacoes_tubos_cilindros.save()

            # Verifica se há não conformidade
            if int(nao_conformidade_total) > 0:
                reinspecao = ReinspecaoEstanqueidade(inspecao=inspecao)
                reinspecao.save()
                # Itera sobre todas as causas (causas_1, causas_2, etc.)
                for i in range(1, quantidade_total_causas + 1):
                    causas = request.POST.getlist(f"causas_{i}")  # Lista de causas
                    quantidade = request.POST.get(f"quantidade_{i}")
                    imagens = request.FILES.getlist(f"imagens_{i}")  # Lista de arquivos

                    # Obtém todas as causas de uma vez
                    causas_objs = Causas.objects.filter(id__in=causas)
                    causa_nao_conformidade = (
                        CausasNaoConformidadeEstanqueidade.objects.create(
                            info_tubos_cilindros=informacoes_tubos_cilindros,
                            quantidade=int(quantidade),
                        )
                    )
                    causa_nao_conformidade.causa.add(*causas_objs)

                    # Itera sobre cada imagem
                    for imagem in imagens:
                        ArquivoCausaEstanqueidade.objects.create(
                            causa_nao_conformidade=causa_nao_conformidade,
                            arquivos=imagem,
                        )

        return JsonResponse({"success": True})

    except Exception as e:
        print(e)
        return JsonResponse({"error": "Erro"}, status=400)


def envio_reinspecao_tubos_cilindros(request):
    if request.method != "POST":
        return JsonResponse({"error": "Método não permitido!"}, status=405)

    try:
        with transaction.atomic():
            data_reinspecao = request.POST.get("data_reinspecao")
            inspecao_id = request.POST.get("inspecao_id")
            inspetor_id = request.POST.get("inspetor_reteste_estanqueidade")
            reteste_status_estanqueidade = request.POST.get(
                "reteste_status_estanqueidade"
            )
            nao_conformidade_tubo_retrabalho = int(
                request.POST.get("nao-conformidade-tubo-retrabalho", 0)
            )
            nao_conformidade_tubo_refugo = int(
                request.POST.get("nao-conformidade-tubo-refugo", 0)
            )
            nao_conformidade_cilindro = int(
                request.POST.get("nao-conformidade-reinspecao-cilindro", 0)
            )
            tipo_inspecao_estanqueidade = request.POST.get(
                "tipo_inspecao_estanqueidade"
            )

            quantidade_total_causas = int(
                request.POST.get("quantidade-total-causas", 0)
            )

            quantidade_reinspecionada = int(
                request.POST.get("quantidade_reinspecionada", 0)
            )

            observacao = request.POST.get("observacao_reteste_estanqueidade")

            data_ajustada = timezone.make_aware(datetime.fromisoformat(data_reinspecao))

            if (
                tipo_inspecao_estanqueidade == "tubo"
                and reteste_status_estanqueidade == "Não Conforme"
            ):
                nao_conformidade = int(nao_conformidade_tubo_retrabalho)
            elif (
                tipo_inspecao_estanqueidade == "cilindro"
                and reteste_status_estanqueidade == "Não Conforme"
            ):
                nao_conformidade = int(nao_conformidade_cilindro)
            else:
                nao_conformidade = 0

            # Obtém a inspeção e o inspetor
            inspecao = InspecaoEstanqueidade.objects.get(id=inspecao_id)
            inspetor = Profile.objects.get(user__pk=inspetor_id)

            # Cria uma instância de DadosExecucaoInspecao
            dados_execucao = DadosExecucaoInspecaoEstanqueidade(
                inspecao_estanqueidade=inspecao,
                inspetor=inspetor,
                data_exec=data_ajustada,
            )
            dados_execucao.save()

            informacoes_tubos_cilindros = InfoAdicionaisExecTubosCilindros(
                dados_exec_inspecao=dados_execucao,
                nao_conformidade=nao_conformidade,
                nao_conformidade_refugo=nao_conformidade_tubo_refugo,
                qtd_inspecionada=quantidade_reinspecionada,
                observacao=observacao,
            )
            informacoes_tubos_cilindros.save()

            # Verifica se há não conformidade
            if reteste_status_estanqueidade == "Não Conforme":
                # Itera sobre todas as causas (causas_1, causas_2, etc.)
                for i in range(1, quantidade_total_causas + 1):
                    causas = request.POST.getlist(
                        f"causas_reinspecao_{i}"
                    )  # Lista de causas
                    quantidade = request.POST.get(f"quantidade_reinspecao_{i}")
                    imagens = request.FILES.getlist(
                        f"imagens_reinspecao_{i}"
                    )  # Lista de arquivos

                    # Obtém todas as causas de uma vez
                    causas_objs = Causas.objects.filter(id__in=causas)
                    causa_nao_conformidade = (
                        CausasNaoConformidadeEstanqueidade.objects.create(
                            info_tubos_cilindros=informacoes_tubos_cilindros,
                            quantidade=quantidade,
                        )
                    )
                    causa_nao_conformidade.causa.add(*causas_objs)

                    # Itera sobre cada imagem
                    for imagem in imagens:
                        ArquivoCausaEstanqueidade.objects.create(
                            causa_nao_conformidade=causa_nao_conformidade,
                            arquivos=imagem,
                        )
            else:
                reinspecao = ReinspecaoEstanqueidade.objects.filter(
                    inspecao=inspecao
                ).first()
                reinspecao.reinspecionado = True
                reinspecao.save()

        return JsonResponse({"success": True})

    except Exception as e:
        print(e)
        return JsonResponse({"error": "Erro"}, status=400)


def get_historico_tubos_cilindros(request, id):
    if request.method != "GET":
        return JsonResponse({"error": "Método não permitido"}, status=405)

    # Otimiza a consulta usando select_related e prefetch_related
    dados = (
        DadosExecucaoInspecaoEstanqueidade.objects.filter(inspecao_estanqueidade__id=id)
        .select_related("inspetor__user")
        .prefetch_related(
            Prefetch(
                "infoadicionaisexectuboscilindros_set",
                queryset=InfoAdicionaisExecTubosCilindros.objects.all(),
            )
        )
        .order_by("-id")
    )

    # Usa list comprehension para construir a lista de histórico
    list_history = []
    for dado in dados:
        info_adicional = dado.infoadicionaisexectuboscilindros_set.first()
        list_history.append(
            {
                "id": dado.id,
                "id_tubos_cilindros": info_adicional.id if info_adicional else None,
                "data_execucao": (dado.data_exec - timedelta(hours=3)).strftime(
                    "%d/%m/%Y %H:%M:%S"
                ),
                "num_execucao": dado.num_execucao,
                "inspetor": dado.inspetor.user.username if dado.inspetor else None,
                "nao_conformidade": (
                    info_adicional.nao_conformidade if info_adicional else None
                ),
                "nao_conformidade_refugo": (
                    info_adicional.nao_conformidade_refugo if info_adicional else None
                ),
                "qtd_inspecionada": (
                    info_adicional.qtd_inspecionada if info_adicional else None
                ),
            }
        )

    return JsonResponse({"history": list_history}, status=200)


def get_historico_causas_tubos_cilindros(request, id):
    if request.method != "GET":
        return JsonResponse({"error": "Método não permitido"}, status=405)

    causas_nao_conformidade = CausasNaoConformidadeEstanqueidade.objects.filter(
        info_tubos_cilindros__id=id
    ).prefetch_related("causa", "arquivos_estanqueidade")

    causas_dict = defaultdict(
        lambda: {
            "id_cnc": None,
            "nomes": [],
            "setor": None,
            "quantidade": None,
            "imagens": [],
        }
    )

    print(causas_nao_conformidade)

    for cnc in causas_nao_conformidade:
        for causa in cnc.causa.all():
            if causas_dict[cnc.id]["id_cnc"] is None:
                causas_dict[cnc.id]["id_cnc"] = cnc.id
                causas_dict[cnc.id]["setor"] = causa.setor
                causas_dict[cnc.id]["quantidade"] = cnc.quantidade
                causas_dict[cnc.id]["imagens"] = [
                    {"id": arquivo.id, "url": arquivo.arquivos.url}
                    for arquivo in cnc.arquivos_estanqueidade.all()
                ]
            causas_dict[cnc.id]["nomes"].append(causa.nome)

    causas_list = list(causas_dict.values())

    print(causas_list)

    return JsonResponse({"causas": causas_list}, status=200)


def envio_inspecao_tanque(request):

    if request.method != "POST":
        return JsonResponse({"error": "Método não permitido"}, status=405)

    try:
        with transaction.atomic():
            tipo_inspecao = request.POST.get("tipo_inspecao")
            data_inspecao = request.POST.get("data_inspecao")
            data_carga = request.POST.get("data_carga")
            inspetor = request.POST.get("inspetor")
            produto = request.POST.get("produto")

            # Capturar os dados dos testes (aninhados)
            testes = {
                "parte_inferior": {
                    "pressao_inicial": request.POST.get(
                        "testes[parte_inferior][pressao_inicial]"
                    ),
                    "duracao": request.POST.get("testes[parte_inferior][duracao]"),
                    "pressao_final": request.POST.get(
                        "testes[parte_inferior][pressao_final]"
                    ),
                    "vazamento": request.POST.get("testes[parte_inferior][vazamento]")
                    == "true",
                },
                "corpo_longarina": {
                    "pressao_inicial": request.POST.get(
                        "testes[corpo_longarina][pressao_inicial]"
                    ),
                    "duracao": request.POST.get("testes[corpo_longarina][duracao]"),
                    "pressao_final": request.POST.get(
                        "testes[corpo_longarina][pressao_final]"
                    ),
                    "vazamento": request.POST.get("testes[corpo_longarina][vazamento]")
                    == "true",
                },
                "corpo_tanque": {
                    "pressao_inicial": request.POST.get(
                        "testes[corpo_tanque][pressao_inicial]"
                    ),
                    "duracao": request.POST.get("testes[corpo_tanque][duracao]"),
                    "pressao_final": request.POST.get(
                        "testes[corpo_tanque][pressao_final]"
                    ),
                    "vazamento": request.POST.get("testes[corpo_tanque][vazamento]")
                    == "true",
                },
                "corpo_chassi": {
                    "pressao_inicial": request.POST.get(
                        "testes[corpo_chassi][pressao_inicial]"
                    ),
                    "duracao": request.POST.get("testes[corpo_chassi][duracao]"),
                    "pressao_final": request.POST.get(
                        "testes[corpo_chassi][pressao_final]"
                    ),
                    "vazamento": request.POST.get("testes[corpo_chassi][vazamento]")
                    == "true",
                },
            }

            # Exibir os dados no console para depuração
            print("Tipo de Inspeção:", tipo_inspecao)
            print("Data da Inspeção:", data_inspecao)
            print("Data de Carga:", data_carga)
            print("Inspetor:", inspetor)
            print("Produto:", produto)
            print("Testes:", json.dumps(testes, indent=4))

            data_inspecao_ajustada = timezone.make_aware(
                datetime.fromisoformat(data_inspecao)
            )
            data_carga_ajustada = timezone.make_aware(
                datetime.fromisoformat(data_carga)
            )

            codigo = produto.split(" - ", maxsplit=1)[0]
            descricao = produto.split(" - ", maxsplit=1)[1]

            peca_estanqueidade = PecasEstanqueidade.objects.filter(
                codigo=codigo
            ).first()

            inspecao = InspecaoEstanqueidade(
                data_inspecao=data_inspecao_ajustada,
                peca=peca_estanqueidade,
                data_carga=data_carga_ajustada,
            )
            inspecao.save()

            inspetor = Profile.objects.get(user__pk=inspetor)
            dados_execucao = DadosExecucaoInspecaoEstanqueidade(
                inspecao_estanqueidade=inspecao,
                inspetor=inspetor,
                data_exec=data_inspecao_ajustada,
            )
            dados_execucao.save()

            if "6500" in descricao or "4300" in descricao:
                detalhes_parte_inferior = DetalhesPressaoTanque(
                    dados_exec_inspecao=dados_execucao,
                    pressao_inicial=testes["parte_inferior"]["pressao_inicial"],
                    pressao_final=testes["parte_inferior"]["pressao_final"],
                    nao_conformidade=testes["parte_inferior"]["vazamento"],
                    tipo_teste="ctpi",
                    tempo_execucao=testes["parte_inferior"]["duracao"],
                )
                detalhes_parte_inferior.save()

                detalhes_corpo_longarina = DetalhesPressaoTanque(
                    dados_exec_inspecao=dados_execucao,
                    pressao_inicial=testes["corpo_longarina"]["pressao_inicial"],
                    pressao_final=testes["corpo_longarina"]["pressao_final"],
                    nao_conformidade=testes["corpo_longarina"]["vazamento"],
                    tipo_teste="ctl",
                    tempo_execucao=testes["corpo_longarina"]["duracao"],
                )
                detalhes_corpo_longarina.save()
            else:
                detalhes_corpo_tanque = DetalhesPressaoTanque(
                    dados_exec_inspecao=dados_execucao,
                    pressao_inicial=testes["corpo_tanque"]["pressao_inicial"],
                    pressao_final=testes["corpo_tanque"]["pressao_final"],
                    nao_conformidade=testes["corpo_tanque"]["vazamento"],
                    tipo_teste="ct",
                    tempo_execucao=testes["corpo_tanque"]["duracao"],
                )
                detalhes_corpo_tanque.save()

                detalhes_corpo_chassi = DetalhesPressaoTanque(
                    dados_exec_inspecao=dados_execucao,
                    pressao_inicial=testes["corpo_chassi"]["pressao_inicial"],
                    pressao_final=testes["corpo_chassi"]["pressao_final"],
                    nao_conformidade=testes["corpo_chassi"]["vazamento"],
                    tipo_teste="ctc",
                    tempo_execucao=testes["corpo_chassi"]["duracao"],
                )
                detalhes_corpo_chassi.save()

            if any(
                [
                    testes["parte_inferior"]["vazamento"],
                    testes["corpo_longarina"]["vazamento"],
                    testes["corpo_tanque"]["vazamento"],
                    testes["corpo_chassi"]["vazamento"],
                ]
            ):

                reinspecao_parte_inferior = ReinspecaoEstanqueidade(
                    inspecao=inspecao, data_reinsp=data_inspecao_ajustada
                )
                reinspecao_parte_inferior.save()

        return JsonResponse({"success": True})

    except Exception as e:
        print(e)
        return JsonResponse({"error": "Erro"}, status=400)


def envio_inspecao_tanque(request):

    if request.method != "POST":
        return JsonResponse({"error": "Método não permitido"}, status=405)

    try:
        with transaction.atomic():
            tipo_inspecao = request.POST.get("tipo_inspecao")
            data_inspecao = request.POST.get("data_inspecao")
            data_carga = request.POST.get("data_carga")
            inspetor = request.POST.get("inspetor")
            produto = request.POST.get("produto")

            # Capturar os dados dos testes (aninhados)
            testes = {
                "parte_inferior": {
                    "pressao_inicial": request.POST.get(
                        "testes[parte_inferior][pressao_inicial]"
                    ),
                    "duracao": request.POST.get("testes[parte_inferior][duracao]"),
                    "pressao_final": request.POST.get(
                        "testes[parte_inferior][pressao_final]"
                    ),
                    "vazamento": request.POST.get("testes[parte_inferior][vazamento]")
                    == "true",
                },
                "corpo_longarina": {
                    "pressao_inicial": request.POST.get(
                        "testes[corpo_longarina][pressao_inicial]"
                    ),
                    "duracao": request.POST.get("testes[corpo_longarina][duracao]"),
                    "pressao_final": request.POST.get(
                        "testes[corpo_longarina][pressao_final]"
                    ),
                    "vazamento": request.POST.get("testes[corpo_longarina][vazamento]")
                    == "true",
                },
                "corpo_tanque": {
                    "pressao_inicial": request.POST.get(
                        "testes[corpo_tanque][pressao_inicial]"
                    ),
                    "duracao": request.POST.get("testes[corpo_tanque][duracao]"),
                    "pressao_final": request.POST.get(
                        "testes[corpo_tanque][pressao_final]"
                    ),
                    "vazamento": request.POST.get("testes[corpo_tanque][vazamento]")
                    == "true",
                },
                "corpo_chassi": {
                    "pressao_inicial": request.POST.get(
                        "testes[corpo_chassi][pressao_inicial]"
                    ),
                    "duracao": request.POST.get("testes[corpo_chassi][duracao]"),
                    "pressao_final": request.POST.get(
                        "testes[corpo_chassi][pressao_final]"
                    ),
                    "vazamento": request.POST.get("testes[corpo_chassi][vazamento]")
                    == "true",
                },
            }

            # Exibir os dados no console para depuração
            print("Tipo de Inspeção:", tipo_inspecao)
            print("Data da Inspeção:", data_inspecao)
            print("Data de Carga:", data_carga)
            print("Inspetor:", inspetor)
            print("Produto:", produto)
            print("Testes:", json.dumps(testes, indent=4))

            data_inspecao_ajustada = timezone.make_aware(
                datetime.fromisoformat(data_inspecao)
            )
            data_carga_ajustada = timezone.make_aware(
                datetime.fromisoformat(data_carga)
            )

            codigo = produto.split(" - ", maxsplit=1)[0]
            descricao = produto.split(" - ", maxsplit=1)[1]

            peca_estanqueidade = PecasEstanqueidade.objects.filter(
                codigo=codigo
            ).first()

            inspecao = InspecaoEstanqueidade(
                data_inspecao=data_inspecao_ajustada,
                peca=peca_estanqueidade,
                data_carga=data_carga_ajustada,
            )
            inspecao.save()

            inspetor = Profile.objects.get(user__pk=inspetor)
            dados_execucao = DadosExecucaoInspecaoEstanqueidade(
                inspecao_estanqueidade=inspecao,
                inspetor=inspetor,
                data_exec=data_inspecao_ajustada,
            )
            dados_execucao.save()

            if "6500" in descricao or "4300" in descricao:
                detalhes_parte_inferior = DetalhesPressaoTanque(
                    dados_exec_inspecao=dados_execucao,
                    pressao_inicial=testes["parte_inferior"]["pressao_inicial"],
                    pressao_final=testes["parte_inferior"]["pressao_final"],
                    nao_conformidade=testes["parte_inferior"]["vazamento"],
                    tipo_teste="ctpi",
                    tempo_execucao=testes["parte_inferior"]["duracao"],
                )
                detalhes_parte_inferior.save()

                detalhes_corpo_longarina = DetalhesPressaoTanque(
                    dados_exec_inspecao=dados_execucao,
                    pressao_inicial=testes["corpo_longarina"]["pressao_inicial"],
                    pressao_final=testes["corpo_longarina"]["pressao_final"],
                    nao_conformidade=testes["corpo_longarina"]["vazamento"],
                    tipo_teste="ctl",
                    tempo_execucao=testes["corpo_longarina"]["duracao"],
                )
                detalhes_corpo_longarina.save()
            else:
                detalhes_corpo_tanque = DetalhesPressaoTanque(
                    dados_exec_inspecao=dados_execucao,
                    pressao_inicial=testes["corpo_tanque"]["pressao_inicial"],
                    pressao_final=testes["corpo_tanque"]["pressao_final"],
                    nao_conformidade=testes["corpo_tanque"]["vazamento"],
                    tipo_teste="ct",
                    tempo_execucao=testes["corpo_tanque"]["duracao"],
                )
                detalhes_corpo_tanque.save()

                detalhes_corpo_chassi = DetalhesPressaoTanque(
                    dados_exec_inspecao=dados_execucao,
                    pressao_inicial=testes["corpo_chassi"]["pressao_inicial"],
                    pressao_final=testes["corpo_chassi"]["pressao_final"],
                    nao_conformidade=testes["corpo_chassi"]["vazamento"],
                    tipo_teste="ctc",
                    tempo_execucao=testes["corpo_chassi"]["duracao"],
                )
                detalhes_corpo_chassi.save()

            if any(
                [
                    testes["parte_inferior"]["vazamento"],
                    testes["corpo_longarina"]["vazamento"],
                    testes["corpo_tanque"]["vazamento"],
                    testes["corpo_chassi"]["vazamento"],
                ]
            ):

                reinspecao_parte_inferior = ReinspecaoEstanqueidade(
                    inspecao=inspecao, data_reinsp=data_inspecao_ajustada
                )
                reinspecao_parte_inferior.save()

        return JsonResponse({"success": True})

    except Exception as e:
        print(e)
        return JsonResponse({"error": "Erro"}, status=400)


def get_itens_reinspecao_tanque(request):
    if request.method != "GET":
        return JsonResponse({"error": "Método não permitido"}, status=405)

    reinspecao_ids = set(
        ReinspecaoEstanqueidade.objects.filter(reinspecionado=False).values_list(
            "inspecao", flat=True
        )
    )

    inspetores_filtrados = (
        request.GET.get("inspetores", "").split(",")
        if request.GET.get("inspetores")
        else []
    )
    data_filtrada = request.GET.get("data", None)
    pesquisa_filtrada = request.GET.get("pesquisar", None)
    pagina = int(request.GET.get("pagina", 1))  # Página atual, padrão é 1
    itens_por_pagina = 12  # Itens por página

    datas = InspecaoEstanqueidade.objects.filter(
        id__in=reinspecao_ids, peca__tipo="tanque"
    )

    quantidade_total = datas.count()

    if data_filtrada:
        datas = datas.filter(data_inspecao__date=data_filtrada)

    if pesquisa_filtrada:
        datas = datas.filter(
            Q(peca__codigo__icontains=pesquisa_filtrada)
            | Q(peca__descricao__icontains=pesquisa_filtrada)
        )

    if inspetores_filtrados:
        datas = datas.filter(
            dadosexecucaoinspecaoestanqueidade__inspetor__user__username__in=inspetores_filtrados
        )

    datas = datas.select_related("peca").order_by("-id")

    # Paginação
    paginador = Paginator(datas, itens_por_pagina)
    pagina_obj = paginador.get_page(pagina)

    # Prefetch para otimizar a consulta dos dados de execução e informações adicionais
    dados_execucao = (
        DadosExecucaoInspecaoEstanqueidade.objects.filter(
            inspecao_estanqueidade__in=pagina_obj
        )
        .select_related("inspetor__user", "inspecao_estanqueidade__peca")
        .prefetch_related("detalhespressaotanque_set")
    )

    # Cria um dicionário para mapear inspecao_id para seus dados de execução e informações adicionais
    dados_execucao_dict = {}
    for de in dados_execucao:
        info_adicionais = list(
            de.detalhespressaotanque_set.all()
        )  # Pega todas as informações adicionais
        dados_execucao_dict[de.inspecao_estanqueidade_id] = {
            "dados_execucao": de,
            "info_adicionais": info_adicionais,
        }

    dados = []
    for data in pagina_obj:
        de_info = dados_execucao_dict.get(data.id)
        if de_info:
            de = de_info["dados_execucao"]
            info_adicionais_list = de_info["info_adicionais"]

            data_ajustada = de.data_exec - timedelta(hours=3)
            data_carga_ajustada = data.data_carga - timedelta(hours=3)

            possui_nao_conformidade = any(
                info.nao_conformidade for info in info_adicionais_list
            )

            # Inicializa os campos para as duas informações adicionais
            pressao_inicial_1 = None
            pressao_final_1 = None
            tipo_teste_1 = None
            tempo_execucao_1 = None
            nao_conformidade_1 = None
            pressao_inicial_2 = None
            pressao_final_2 = None
            tipo_teste_2 = None
            tempo_execucao_2 = None
            nao_conformidade_2 = None

            # Preenche os campos com as informações adicionais
            if len(info_adicionais_list) > 0:
                pressao_inicial_1 = info_adicionais_list[0].pressao_inicial
                pressao_final_1 = info_adicionais_list[0].pressao_final
                tipo_teste_1 = info_adicionais_list[0].tipo_teste
                nao_conformidade_1 = info_adicionais_list[0].nao_conformidade
                tempo_execucao_1 = (
                    info_adicionais_list[0].tempo_execucao.strftime("%H:%M:%S")
                    if info_adicionais_list[0].tempo_execucao
                    else None
                )

            if len(info_adicionais_list) > 1:
                pressao_inicial_2 = info_adicionais_list[1].pressao_inicial
                pressao_final_2 = info_adicionais_list[1].pressao_final
                tipo_teste_2 = info_adicionais_list[1].tipo_teste
                nao_conformidade_2 = info_adicionais_list[1].nao_conformidade
                tempo_execucao_2 = (
                    info_adicionais_list[1].tempo_execucao.strftime("%H:%M:%S")
                    if info_adicionais_list[1].tempo_execucao
                    else None
                )

            item = {
                "id": data.id,
                "tipo_inspecao": data.peca.tipo,
                "id_dados_execucao": de.id,
                "data": data_ajustada.strftime("%d/%m/%Y %H:%M:%S"),
                "data_carga": data_carga_ajustada.strftime("%d/%m/%Y %H:%M:%S"),
                "peca": f"{data.peca.codigo} - {data.peca.descricao}",  # Ajustado para pegar o código da peça
                "inspetor": de.inspetor.user.username if de.inspetor else None,
                "possui_nao_conformidade": possui_nao_conformidade,
                "pressao_inicial_1": pressao_inicial_1,
                "pressao_final_1": pressao_final_1,
                "tipo_teste_1": tipo_teste_1,
                "nao_conformidade_1": nao_conformidade_1,
                "tempo_execucao_1": tempo_execucao_1,
                "pressao_inicial_2": pressao_inicial_2,
                "pressao_final_2": pressao_final_2,
                "tipo_teste_2": tipo_teste_2,
                "tempo_execucao_2": tempo_execucao_2,
                "nao_conformidade_2": nao_conformidade_2,
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


def get_itens_inspecionados_tanque(request):
    if request.method != "GET":
        return JsonResponse({"error": "Método não permitido"}, status=405)

    # Filtra apenas peças do tipo "tubo" ou "cilindro"
    pecas_filtradas = PecasEstanqueidade.objects.filter(tipo="tanque")
    inspecionados_ids = set(
        DadosExecucaoInspecaoEstanqueidade.objects.filter(
            inspecao_estanqueidade__peca__in=pecas_filtradas
        ).values_list("inspecao_estanqueidade", flat=True)
    )

    # Filtros
    inspetores_filtrados = (
        request.GET.get("inspetores", "").split(",")
        if request.GET.get("inspetores")
        else []
    )
    data_filtrada = request.GET.get("data", None)
    pesquisa_filtrada = request.GET.get("pesquisar", None)
    pagina = int(request.GET.get("pagina", 1))  # Página atual, padrão é 1
    itens_por_pagina = 12  # Itens por página

    # Filtra os dados
    datas = InspecaoEstanqueidade.objects.filter(id__in=inspecionados_ids).order_by(
        "-id"
    )

    quantidade_total = datas.count()

    if data_filtrada:
        datas = datas.filter(data_inspecao__date=data_filtrada)

    if pesquisa_filtrada:
        datas = datas.filter(
            Q(peca__codigo__icontains=pesquisa_filtrada)
            | Q(peca__descricao__icontains=pesquisa_filtrada)
        )

    if inspetores_filtrados:
        datas = datas.filter(
            dadosexecucaoinspecaoestanqueidade__inspetor__user__username__in=inspetores_filtrados
        )

    datas = datas.select_related("peca").order_by("-id")

    # Paginação
    paginador = Paginator(datas, itens_por_pagina)
    pagina_obj = paginador.get_page(pagina)

    # Prefetch para otimizar a consulta dos dados de execução e informações adicionais
    dados_execucao = (
        DadosExecucaoInspecaoEstanqueidade.objects.filter(
            inspecao_estanqueidade__in=pagina_obj
        )
        .select_related("inspetor__user", "inspecao_estanqueidade__peca")
        .prefetch_related("detalhespressaotanque_set")
    )

    # Subconsulta para obter o maior num_execucao para cada inspecao_estanqueidade
    maior_num_execucao_subquery = (
        DadosExecucaoInspecaoEstanqueidade.objects.filter(
            inspecao_estanqueidade=OuterRef("inspecao_estanqueidade")
        )
        .values("inspecao_estanqueidade")
        .annotate(max_num_execucao=Max("num_execucao"))
        .values("max_num_execucao")
    )

    # Filtra os dados de execução para incluir apenas os registros com o maior num_execucao
    dados_execucao = (
        DadosExecucaoInspecaoEstanqueidade.objects.filter(
            inspecao_estanqueidade__in=datas,
            num_execucao=Subquery(maior_num_execucao_subquery),
        )
        .select_related("inspetor__user", "inspecao_estanqueidade__peca")
        .prefetch_related("infoadicionaisexectuboscilindros_set")
    )

    # Cria um dicionário para mapear inspecao_id para seus dados de execução e informações adicionais
    dados_execucao_dict = {}
    for de in dados_execucao:
        info_adicionais = list(
            de.detalhespressaotanque_set.all()
        )  # Pega todas as informações adicionais
        dados_execucao_dict[de.inspecao_estanqueidade_id] = {
            "dados_execucao": de,
            "info_adicionais": info_adicionais,
        }

    dados = []
    for data in pagina_obj:
        de_info = dados_execucao_dict.get(data.id)
        if de_info:
            de = de_info["dados_execucao"]
            info_adicionais_list = de_info["info_adicionais"]

            data_ajustada = de.data_exec - timedelta(hours=3)
            data_carga_ajustada = data.data_carga - timedelta(hours=3)

            possui_nao_conformidade = any(
                info.nao_conformidade for info in info_adicionais_list
            )

            item = {
                "id": data.id,
                "tipo_inspecao": data.peca.tipo,
                "id_dados_execucao": de.id,
                "data": data_ajustada.strftime("%d/%m/%Y %H:%M:%S"),
                "data_carga": data_carga_ajustada.strftime("%d/%m/%Y %H:%M:%S"),
                "peca": f"{data.peca.codigo} - {data.peca.descricao}",  # Ajustado para pegar o código da peça
                "inspetor": de.inspetor.user.username if de.inspetor else None,
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
