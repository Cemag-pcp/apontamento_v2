from django.shortcuts import render
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q 
from django.db import transaction
from django.utils import timezone
from cadastro.models import PecasEstanqueidade
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
from core.models import Profile, Maquina
from datetime import datetime, timedelta
from collections import defaultdict


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
        Reinspecao.objects.filter(reinspecionado=False).values_list(
            "inspecao", flat=True
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
                reinspecao = Reinspecao(inspecao=inspecao)
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
                reinspecao = Reinspecao(inspecao=inspecao)
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
    return render(request, "inspecao_tanque.html")


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

    datas = InspecaoEstanqueidade.objects.filter(id__in=reinspecao_ids)

    quantidade_total = datas.count()

    print(datas)

    if data_filtrada:
        datas = datas.filter(data_inspecao__date=data_filtrada)

    if pesquisa_filtrada:
        datas = datas.filter(
            Q(peca__codigo__icontains=pesquisa_filtrada) | Q(peca__descricao__icontains=pesquisa_filtrada)
        )
    
    print(datas)

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
        .prefetch_related("infoadicionaisexectuboscilindros_set")
    )

    # Cria um dicionário para mapear inspecao_id para seus dados de execução e informações adicionais
    dados_execucao_dict = {}
    for de in dados_execucao:
        info_adicionais = (
            de.infoadicionaisexectuboscilindros_set.first()
        )  # Pega a primeira informação adicional (se existir)
        dados_execucao_dict[de.inspecao_estanqueidade_id] = {
            "dados_execucao": de,
            "info_adicionais": info_adicionais,
        }

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
                "tipo_inspecao": data.peca.tipo,
                "id_dados_execucao": de.id,
                "data": data_ajustada.strftime("%d/%m/%Y %H:%M:%S"),
                "peca": f"{data.peca.codigo} - {data.peca.descricao}",  # Ajustado para pegar o código da peça
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
            "total_filtrado": paginador.count,  # Total de itens após filtro
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
    datas = InspecaoEstanqueidade.objects.filter(id__in=inspecionados_ids)

    quantidade_total = datas.count()

    if data_filtrada:
        datas = datas.filter(data_inspecao__date=data_filtrada)

    if pesquisa_filtrada:
        datas = datas.filter(peca__codigo__icontains=pesquisa_filtrada)

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
        .prefetch_related("infoadicionaisexectuboscilindros_set")
    )

    # Cria um dicionário para mapear inspecao_id para seus dados de execução e informações adicionais
    dados_execucao_dict = {}
    for de in dados_execucao:
        info_adicionais = (
            de.infoadicionaisexectuboscilindros_set.first()
        )  # Pega a primeira informação adicional (se existir)
        dados_execucao_dict[de.inspecao_estanqueidade_id] = {
            "dados_execucao": de,
            "info_adicionais": info_adicionais,
        }

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
                "peca": f"{data.peca.codigo} - {data.peca.descricao}",  # Ajustado para pegar o código da peça
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
            "total_filtrado": paginador.count,  # Total de itens após filtro
            "pagina_atual": pagina_obj.number,
            "total_paginas": paginador.num_pages,
        },
        status=200,
    )


def envio_inspecao_tubos_cilindros(request):
    if request.method != "POST":
        return JsonResponse({"error":"Método não permitido"}, status=405)

    return JsonResponse({"success":"Data"}, status=200)


def reteste_estanqueidade_tubos_cilindros(request):
    return
