from django.shortcuts import render
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import (
    Q,
    Prefetch,
    OuterRef,
    Subquery,
    Max,
    Sum,
    F,
    IntegerField,
    ExpressionWrapper,
    Value,
    CharField,
    Count,
    Case,
    When,
)
from django.db import transaction
from django.utils import timezone
from django.db.models.functions import (
    Concat,
    Cast,
    TruncMonth,
    ExtractYear,
    ExtractMonth,
)

from cadastro.models import PecasEstanqueidade
from ..models import (
    Inspecao,
    Causas,
    InspecaoEstanqueidade,
    DadosExecucaoInspecaoEstanqueidade,
    DadosExecucaoInspecao,
    ReinspecaoEstanqueidade,
    Reinspecao,
    DetalhesPressaoTanque,
    InfoAdicionaisExecTubosCilindros,
    CausasNaoConformidade,
    CausasNaoConformidadeEstanqueidade,
    ArquivoCausaEstanqueidade,
    ArquivoCausa
)
from core.models import Profile

from datetime import datetime, timedelta
from collections import defaultdict
import json


def inspecao_tanque(request):

    users = Profile.objects.filter(
        tipo_acesso="inspetor", permissoes__nome="inspecao/tanque"
    )
    causas = Causas.objects.filter(setor="montagem")

    lista_inspetores = [
        {"nome_usuario": user.user.username, "id": user.user.id} for user in users
    ]

    list_causas = [{"id": causa.id, "nome": causa.nome} for causa in causas]

    tanques = PecasEstanqueidade.objects.filter(tipo="tanque")

    dict_tanques = [
        {"peca": f"{tanque.codigo} - {tanque.descricao}"} for tanque in tanques
    ]

    user_profile = Profile.objects.filter(user=request.user).first()
    if (
        user_profile
        and user_profile.tipo_acesso == "inspetor"
        and user_profile.permissoes.filter(nome="inspecao/tanque").exists()
    ):
        inspetor_logado = {"nome_usuario": request.user.username, "id": request.user.id}
    else:
        inspetor_logado = None

    return render(
        request,
        "inspecao_tanque.html",
        {
            "tanques": dict_tanques,
            "inspetores": lista_inspetores,
            "inspetor_logado": inspetor_logado,
            "causas": list_causas
        },
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

    user_profile = Profile.objects.filter(user=request.user).first()
    if (
        user_profile
        and user_profile.tipo_acesso == "inspetor"
        and user_profile.permissoes.filter(nome="inspecao/tubos-cilindros").exists()
    ):
        inspetor_logado = {"nome_usuario": request.user.username, "id": request.user.id}
    else:
        inspetor_logado = None

    return render(
        request,
        "inspecao_tubos_cilindros.html",
        {
            "inspetores": lista_inspetores,
            "causas": list_causas,
            "pecas_tubos": list_pecas_tubos,
            "pecas_cilindros": list_pecas_cilindros,
            "inspetor_logado": inspetor_logado,
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

    quantidade_total = datas.count()  # Total de itens sem filtro

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
            "total": quantidade_total,  # Total de itens após filtro
            "total_filtrado": paginador.count,  # Total de itens após filtro
            "pagina_atual": pagina_obj.number,
            "total_paginas": paginador.num_pages,
        },
        status=200,
    )


def get_itens_inspecionados_tubos_cilindros(request):

    if request.method != "GET":
        return JsonResponse({"error": "Método não permitido"}, status=405)

    pecas_filtradas = PecasEstanqueidade.objects.filter(
        tipo__in=["tubo", "cilindro"]
    ).only("id")

    inspecionados_ids = (
        DadosExecucaoInspecaoEstanqueidade.objects.filter(
            inspecao_estanqueidade__peca__in=pecas_filtradas
        )
        .values_list("inspecao_estanqueidade_id", flat=True)
        .distinct()
    )

    # Filtros
    inspetores_filtrados = (
        request.GET.get("inspetores", "").split(",")
        if request.GET.get("inspetores")
        else []
    )
    data_filtrada = request.GET.get("data", None)
    pesquisa_filtrada = request.GET.get("pesquisar", None)
    pagina = int(request.GET.get("pagina", 1))
    itens_por_pagina = 6

    base_query = InspecaoEstanqueidade.objects.filter(
        id__in=inspecionados_ids
    ).order_by("-data_inspecao")

    if data_filtrada:
        base_query = base_query.filter(
            dadosexecucaoinspecaoestanqueidade__data_exec__date=data_filtrada
        ).distinct()

    if pesquisa_filtrada:
        if " - " in pesquisa_filtrada:
            codigo, descricao = pesquisa_filtrada.split(" - ", 1)
            base_query = base_query.filter(
                Q(peca__codigo__icontains=codigo.strip())
                & Q(peca__descricao__icontains=descricao.strip())
            ).distinct()
        else:
            base_query = base_query.filter(
                Q(peca__codigo__icontains=pesquisa_filtrada)
                | Q(peca__descricao__icontains=pesquisa_filtrada)
            ).distinct()

    if inspetores_filtrados:
        base_query = base_query.filter(
            dadosexecucaoinspecaoestanqueidade__inspetor__user__username__in=inspetores_filtrados
        ).distinct()

    quantidade_total = base_query.count()

    maior_num_execucao_subquery = (
        DadosExecucaoInspecaoEstanqueidade.objects.filter(
            inspecao_estanqueidade_id=OuterRef("inspecao_estanqueidade_id")
        )
        .order_by("-num_execucao")
        .values("num_execucao")[:1]
    )

    dados_execucao = (
        DadosExecucaoInspecaoEstanqueidade.objects.filter(
            inspecao_estanqueidade__in=base_query,
        )
        .annotate(max_num_execucao=Subquery(maior_num_execucao_subquery))
        .filter(num_execucao=F("max_num_execucao"))
        .select_related("inspetor__user", "inspecao_estanqueidade__peca")
        .prefetch_related("infoadicionaisexectuboscilindros_set")
    )

    dados_execucao_dict = {}
    for de in dados_execucao:
        dados_execucao_dict[de.inspecao_estanqueidade_id] = {
            "dados_execucao": de,
            "info_adicionais": de.infoadicionaisexectuboscilindros_set.first(),
        }

    # Paginação
    paginador = Paginator(base_query, itens_por_pagina)
    pagina_obj = paginador.get_page(pagina)

    dados = []
    for data in pagina_obj:
        de_info = dados_execucao_dict.get(data.id)
        if not de_info:
            continue

        de = de_info["dados_execucao"]
        info_adicionais = de_info["info_adicionais"]

        data_ajustada = de.data_exec - timedelta(hours=3)
        possui_nao_conformidade = (
            info_adicionais.nao_conformidade + info_adicionais.nao_conformidade_refugo
            > 0
        ) or de.num_execucao > 0

        dados.append(
            {
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
        )

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
            ficha_inspecao = request.FILES.get("ficha_inspecao")
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
                ficha=ficha_inspecao,
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
            ficha_reinspecao = request.FILES.get("ficha_reinspecao")

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
                ficha=ficha_reinspecao,
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


def envio_reinspecao_tanque(request):

    if request.method != "POST":
        return JsonResponse({"error": "Método não permitido"}, status=405)

    try:
        with transaction.atomic():
            id = request.POST.get("id")
            id_dados_execucao = request.POST.get("id_dados_execucao")
            print(id_dados_execucao)
            tipo_inspecao = request.POST.get("tipo_inspecao")
            data_reinspecao = request.POST.get("data_reinspecao")
            data_carga = request.POST.get("data_carga")
            inspetor = request.POST.get("inspetor")
            produto = request.POST.get("produto")

            # Capturar os dados dos testes (aninhados)
            testes = {
                "ctpi": {
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
                "ctl": {
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
                "ct": {
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
                "ctc": {
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

            data_reinspecao_ajustada = timezone.make_aware(
                datetime.fromisoformat(data_reinspecao)
            )

            # Exibir os dados no console para depuração
            print("Tipo de Inspeção:", tipo_inspecao)
            print("Data da Reinspeção:", data_reinspecao_ajustada)
            print("Data de Carga:", data_carga)
            print("Inspetor:", inspetor)
            print("Produto:", produto)
            print("Testes:", json.dumps(testes, indent=4))

            inspecao = InspecaoEstanqueidade.objects.filter(id=id).first()
            inspetor = Profile.objects.get(user__pk=inspetor)

            dados_execucao = DadosExecucaoInspecaoEstanqueidade(
                inspecao_estanqueidade=inspecao,
                inspetor=inspetor,
                data_exec=data_reinspecao_ajustada,
            )
            dados_execucao.save()

            detalhes_pressao = DetalhesPressaoTanque.objects.filter(
                dados_exec_inspecao=id_dados_execucao,
                nao_conformidade=True,
            )

            print(detalhes_pressao)

            for detalhe in detalhes_pressao:
                detalhes_reinspecao = DetalhesPressaoTanque(
                    dados_exec_inspecao=dados_execucao,
                    pressao_inicial=testes[detalhe.tipo_teste]["pressao_inicial"],
                    pressao_final=testes[detalhe.tipo_teste]["pressao_final"],
                    nao_conformidade=testes[detalhe.tipo_teste]["vazamento"],
                    tipo_teste=detalhe.tipo_teste,
                    tempo_execucao=testes[detalhe.tipo_teste]["duracao"],
                )
                detalhes_reinspecao.save()

            if not any(
                [
                    testes["ctpi"]["vazamento"],
                    testes["ctl"]["vazamento"],
                    testes["ct"]["vazamento"],
                    testes["ctc"]["vazamento"],
                ]
            ):

                reinspecao = ReinspecaoEstanqueidade.objects.filter(
                    inspecao=inspecao,
                ).first()
                reinspecao.reinspecionado = True

                reinspecao.save()

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
        datas = datas.filter(
            dadosexecucaoinspecaoestanqueidade__data_exec__date=data_filtrada
        ).distinct()

    if pesquisa_filtrada:
        datas = datas.filter(
            Q(peca__codigo__icontains=pesquisa_filtrada)
            | Q(peca__descricao__icontains=pesquisa_filtrada)
        ).distinct()

    if inspetores_filtrados:
        datas = datas.filter(
            dadosexecucaoinspecaoestanqueidade__inspetor__user__username__in=inspetores_filtrados
        ).distinct()

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
        
    # --- INÍCIO DA MODIFICAÇÃO ---
    # 1. Pega os IDs de InspecaoEstanqueidade da página atual.
    ids_pagina_atual = [item.id for item in pagina_obj]

    # 2. Busca na tabela Inspecao quais desses IDs já existem no campo 'tanque'.
    #    Usar 'values_list' com 'flat=True' é muito eficiente para obter uma lista de IDs.
    #    Colocamos em um set() para uma verificação de existência (in) super rápida (O(1)).
    ids_em_inspecao_geral = set(
        Inspecao.objects.filter(tanque_id__in=ids_pagina_atual).values_list(
            "tanque_id", flat=True
        )
    )
    # --- FIM DA MODIFICAÇÃO ---

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

            existe_em_inspecao = data.id in ids_em_inspecao_geral

            item = {
                "id": data.id,
                "tipo_inspecao": data.peca.tipo,
                "id_dados_execucao": de.id,
                "data": data_ajustada.strftime("%d/%m/%Y %H:%M:%S"),
                "data_carga": data_carga_ajustada.strftime("%d/%m/%Y %H:%M:%S"),
                "peca": f"{data.peca.codigo} - {data.peca.descricao}",
                "inspetor": de.inspetor.user.username if de.inspetor else None,
                "possui_nao_conformidade": possui_nao_conformidade,
                "inspecao_geral_realizada": existe_em_inspecao,
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


def itens_enviados_tanque(request, tanque_id):
    try:
        # Buscar o tanque
        tanque = InspecaoEstanqueidade.objects.get(id=tanque_id)
        
        # Buscar a última inspeção deste tanque (se existir)
        ultima_inspecao = DadosExecucaoInspecao.objects.filter(
            inspecao__tanque=tanque
        ).prefetch_related(
            'causasnaoconformidade_set__causa',
            'causasnaoconformidade_set__arquivos'
        ).order_by('-num_execucao').first()
        
        # Buscar as causas da não conformidade da última inspeção
        causas_data = []
        if ultima_inspecao:
            # Recuperar todas as CausasNaoConformidade relacionadas a esta execução
            causas_nao_conformidade = ultima_inspecao.causasnaoconformidade_set.all()
            
            for causa_nc in causas_nao_conformidade:
                # Para cada causa de não conformidade, recuperar as causas específicas
                causas_relacionadas = causa_nc.causa.all()
                # Recuperar imagens associadas
                imagens = []
                for arquivo in causa_nc.arquivos.all():
                    if arquivo.arquivo:
                        imagens.append({
                            'url': arquivo.arquivo.url,
                            'nome': arquivo.arquivo.name
                        })
                
                for causa in causas_relacionadas:
                    causas_data.append({
                        'id': causa.id,
                        'nome': causa.nome,
                        'quantidade': causa_nc.quantidade,
                        'imagens': imagens
                    })
        
        # Preparar dados para retorno
        dados = {
            'id': tanque.id,
            'nome': f"{tanque.peca.codigo} - {tanque.peca.descricao}",
            'data_inspecao': ultima_inspecao.data_execucao.isoformat() if ultima_inspecao else None,
            'quantidade_produzida': getattr(ultima_inspecao, 'quantidade_produzida', 1) if ultima_inspecao else 1,
            'inspetor': ultima_inspecao.inspetor.id if ultima_inspecao and ultima_inspecao.inspetor else None,
            'conformidade': ultima_inspecao.conformidade if ultima_inspecao else 0,
            'nao_conformidade': ultima_inspecao.nao_conformidade if ultima_inspecao else 0,
            'observacao': ultima_inspecao.observacao if ultima_inspecao else '',
            'causas': causas_data
        }
        
        return JsonResponse(dados)
        
    except InspecaoEstanqueidade.DoesNotExist:
        return JsonResponse({'error': 'Tanque não encontrado'}, status=404)

def get_historico_tanque(request, id):
    if request.method != "GET":
        return JsonResponse({"error": "Método não permitido"}, status=405)

    # Otimiza a consulta usando select_related e prefetch_related
    dados = (
        DadosExecucaoInspecaoEstanqueidade.objects.filter(inspecao_estanqueidade__id=id)
        .select_related("inspetor__user")
        .prefetch_related(
            Prefetch(
                "detalhespressaotanque_set",
                queryset=DetalhesPressaoTanque.objects.all(),
            )
        )
        .order_by("-id")
    )

    print(dados)

    # Usa list comprehension para construir a lista de histórico
    list_history = []
    for dado in dados:
        detalhes_pressao_list = dado.detalhespressaotanque_set.all()
        for detalhes_pressao in detalhes_pressao_list:
            list_history.append(
                {
                    "id": dado.id,
                    "id_detalhes_pressao": detalhes_pressao.id,
                    "data_execucao": (dado.data_exec - timedelta(hours=3)).strftime(
                        "%d/%m/%Y %H:%M:%S"
                    ),
                    "num_execucao": dado.num_execucao,
                    "inspetor": dado.inspetor.user.username if dado.inspetor else None,
                    "pressao_inicial": detalhes_pressao.pressao_inicial,
                    "pressao_final": detalhes_pressao.pressao_final,
                    "nao_conformidade": detalhes_pressao.nao_conformidade,
                    "tipo_teste": detalhes_pressao.tipo_teste,
                    "tempo_execucao": (
                        detalhes_pressao.tempo_execucao.strftime("%H:%M:%S")
                        if detalhes_pressao.tempo_execucao
                        else None
                    ),
                }
            )

    return JsonResponse({"history": list_history}, status=200)


### dashboard tanque ###


def dashboard_tanque(request):

    return render(request, "dashboard/tanque.html")


def indicador_tanque_analise_temporal(request):
    """
    Endpoint para análise temporal de inspeções de estanqueidade - APENAS TANQUES
    """
    data_inicio = request.GET.get("data_inicio")
    data_fim = request.GET.get("data_fim")

    try:
        if data_inicio:
            data_inicio = datetime.strptime(data_inicio, "%Y-%m-%d")
        if data_fim:
            data_fim = datetime.strptime(data_fim, "%Y-%m-%d") + timedelta(days=1)
    except ValueError:
        return JsonResponse(
            {"erro": "Formato de data inválido. Use YYYY-MM-DD."}, status=400
        )

    # Filtra somente as inspeções de estanqueidade para tanques
    queryset = InspecaoEstanqueidade.objects.filter(peca__tipo="tanque")

    if data_inicio:
        queryset = queryset.filter(data_inspecao__gte=data_inicio)
    if data_fim:
        queryset = queryset.filter(data_inspecao__lte=data_fim)

    # Dados de pressão dos tanques
    tanques_pressao = (
        DetalhesPressaoTanque.objects.filter(
            dados_exec_inspecao__inspecao_estanqueidade__in=queryset
        )
        .annotate(
            mes=Cast(
                TruncMonth("dados_exec_inspecao__data_exec"), output_field=CharField()
            ),
            nc_calculada=Case(  # Mudei o nome da anotação para evitar conflito
                When(nao_conformidade=True, then=1),
                default=0,
                output_field=IntegerField(),
            ),
        )
        .values("mes")
        .annotate(
            qtd_inspecionada=Count("id"),
            soma_nao_conformidade=Sum("nc_calculada"),  # Usando o novo nome aqui
        )
        .order_by("mes")
    )

    resultado = []
    for item in tanques_pressao:
        total_inspecionada = item["qtd_inspecionada"] or 0
        total_nc = item["soma_nao_conformidade"] or 0
        taxa_nc = (total_nc / total_inspecionada) if total_inspecionada else 0

        resultado.append(
            {
                "mes": item["mes"][:7],  # YYYY-MM
                "qtd_peca_inspecionada": total_inspecionada,
                "taxa_nao_conformidade": round(taxa_nc, 4),
            }
        )

    return JsonResponse(resultado, safe=False)


def indicador_tanque_resumo_analise_temporal(request):
    """
    Endpoint para resumo temporal de inspeções - APENAS TANQUES
    """
    data_inicio = request.GET.get("data_inicio")
    data_fim = request.GET.get("data_fim")

    try:
        if data_inicio:
            data_inicio = datetime.strptime(data_inicio, "%Y-%m-%d")
        if data_fim:
            data_fim = datetime.strptime(data_fim, "%Y-%m-%d") + timedelta(days=1)
    except ValueError:
        return JsonResponse(
            {"erro": "Formato de data inválido. Use YYYY-MM-DD."}, status=400
        )

    # Query para tanques (pressão)
    tanques_pressao = DetalhesPressaoTanque.objects.filter(
        dados_exec_inspecao__inspecao_estanqueidade__peca__tipo="tanque",
        dados_exec_inspecao__data_exec__isnull=False,
    )

    if data_inicio:
        tanques_pressao = tanques_pressao.filter(
            dados_exec_inspecao__data_exec__gte=data_inicio
        )
    if data_fim:
        tanques_pressao = tanques_pressao.filter(
            dados_exec_inspecao__data_exec__lte=data_fim
        )

    # Agregações
    tanques_agg = (
        tanques_pressao.annotate(
            ano=ExtractYear("dados_exec_inspecao__data_exec"),
            mes_num=ExtractMonth("dados_exec_inspecao__data_exec"),
            nc=Case(
                When(nao_conformidade=True, then=1),
                default=0,
                output_field=IntegerField(),
            ),
        )
        .values("ano", "mes_num")
        .annotate(total_inspecionada=Count("id"), total_nc=Sum("nc"))
        .order_by("ano", "mes_num")
    )

    resultado = []
    for item in tanques_agg:
        mes_formatado = f"{item['ano']}-{item['mes_num']}"

        resultado.append(
            {
                "Data": mes_formatado,
                "N° de inspeções": int(item["total_inspecionada"]),
                "N° de não conformidades": int(item["total_nc"] or 0),
            }
        )

    return JsonResponse(resultado, safe=False)


def causas_nao_conformidade_mensal_tanque(request):

    data_inicio = request.GET.get("data_inicio")
    data_fim = request.GET.get("data_fim")

    try:
        if data_inicio:
            data_inicio = datetime.strptime(data_inicio, "%Y-%m-%d")
        if data_fim:
            data_fim = datetime.strptime(data_fim, "%Y-%m-%d") + timedelta(days=1)
    except ValueError:
        return JsonResponse(
            {"erro": "Formato de data inválido. Use YYYY-MM-DD."}, status=400
        )

    # Filtra as não conformidades de tanques na primeira execução (num_execucao=0)
    nao_conformidades = DetalhesPressaoTanque.objects.filter(
        nao_conformidade=True,
        dados_exec_inspecao__inspecao_estanqueidade__peca__tipo="tanque",
    )

    # Aplica filtros de data se fornecidos
    if data_inicio:
        nao_conformidades = nao_conformidades.filter(
            dados_exec_inspecao__data_exec__gte=data_inicio
        )
    if data_fim:
        nao_conformidades = nao_conformidades.filter(
            dados_exec_inspecao__data_exec__lte=data_fim
        )

    # Agrupa por mês e conta as ocorrências
    resultados = (
        nao_conformidades.annotate(
            mes_formatado=Concat(
                ExtractYear("dados_exec_inspecao__data_exec"),
                Value("-"),
                ExtractMonth("dados_exec_inspecao__data_exec"),
                output_field=CharField(),
            )
        )
        .values("mes_formatado")
        .annotate(quantidade=Count("id"))
        .order_by("mes_formatado")
    )

    # Formata a resposta conforme solicitado
    resposta = [
        {
            "data": item["mes_formatado"],
            "causa": "Vazamento",
            "quantidade": item["quantidade"],
        }
        for item in resultados
    ]

    print(resposta)

    return JsonResponse(resposta, safe=False)


### dashboard tubos e cilindros ###


def dashboard_tubos_cilindros(request):

    return render(request, "dashboard/tubos-cilindros.html")


def indicador_tubos_cilindros_analise_temporal(request):

    data_inicio = request.GET.get("data_inicio")
    data_fim = request.GET.get("data_fim")

    try:
        if data_inicio:
            data_inicio = datetime.strptime(data_inicio, "%Y-%m-%d")
        if data_fim:
            data_fim = datetime.strptime(data_fim, "%Y-%m-%d") + timedelta(days=1)
    except ValueError:
        return JsonResponse(
            {"erro": "Formato de data inválido. Use YYYY-MM-DD."}, status=400
        )

    # Filtra somente as produções com peça ligada e do tipo especificado
    queryset = InspecaoEstanqueidade.objects.filter(
        Q(peca__tipo="tubo") | Q(peca__tipo="cilindro")
    )

    if data_inicio:
        queryset = queryset.filter(data_inspecao__gte=data_inicio)
    if data_fim:
        queryset = queryset.filter(data_inspecao__lte=data_fim)

    queryset = (
        queryset.annotate(
            mes=Cast(TruncMonth("data_inspecao"), output_field=CharField()),
            qtd_inspecionada=F(
                "dadosexecucaoinspecaoestanqueidade__infoadicionaisexectuboscilindros__qtd_inspecionada"
            ),
            nao_conformidade=F(
                "dadosexecucaoinspecaoestanqueidade__infoadicionaisexectuboscilindros__nao_conformidade"
            ),
        )
        .values("mes")
        .annotate(
            soma_nao_conformidade=Sum("nao_conformidade"),
            soma_qtd_inspecionada=Sum("qtd_inspecionada"),
        )
        .order_by("mes")
    )

    resultado = []
    for item in queryset:
        qtd_inspecionada = item["soma_qtd_inspecionada"] or 0
        nao_conformidade = item["soma_nao_conformidade"] or 0
        taxa_nc = (nao_conformidade / qtd_inspecionada) if qtd_inspecionada else 0

        resultado.append(
            {
                "mes": item["mes"][:7],  # YYYY-MM
                "qtd_peca_inspecionada": item["soma_qtd_inspecionada"] or 0,
                "taxa_nao_conformidade": round(taxa_nc, 4),
            }
        )

    return JsonResponse(resultado, safe=False)


def indicador_tubos_cilindros_resumo_analise_temporal(request):

    data_inicio = request.GET.get("data_inicio")
    data_fim = request.GET.get("data_fim")

    try:
        if data_inicio:
            data_inicio = datetime.strptime(data_inicio, "%Y-%m-%d")
        if data_fim:
            data_fim = datetime.strptime(data_fim, "%Y-%m-%d") + timedelta(days=1)
    except ValueError:
        return JsonResponse(
            {"erro": "Formato de data inválido. Use YYYY-MM-DD."}, status=400
        )

    # Query principal
    queryset = InspecaoEstanqueidade.objects.filter(
        Q(peca__tipo="tubo") | Q(peca__tipo="cilindro"), peca__isnull=False
    )

    if data_inicio:
        queryset = queryset.filter(data_inspecao__gte=data_inicio)
    if data_fim:
        queryset = queryset.filter(data_inspecao__lte=data_fim)

    # Anotações e agregações
    queryset = (
        queryset.annotate(
            ano=ExtractYear("data_inspecao"),
            mes_num=ExtractMonth("data_inspecao"),
            qtd_inspecionada=F(
                "dadosexecucaoinspecaoestanqueidade__infoadicionaisexectuboscilindros__qtd_inspecionada"
            ),
            nao_conformidade=F(
                "dadosexecucaoinspecaoestanqueidade__infoadicionaisexectuboscilindros__nao_conformidade"
            ),
            nao_conformidade_refugo=F(
                "dadosexecucaoinspecaoestanqueidade__infoadicionaisexectuboscilindros__nao_conformidade_refugo"
            ),
        )
        .values("ano", "mes_num")
        .annotate(
            total_nc=Sum("nao_conformidade"),
            total_refugo=Sum("nao_conformidade_refugo"),
            total_nao_conforme=ExpressionWrapper(
                F("total_nc") + F("total_refugo"), output_field=IntegerField()
            ),
            total_qtd_inspecionada=Sum("qtd_inspecionada"),
        )
        .order_by("ano", "mes_num")
    )

    print(queryset)
    # Monta JSON
    resultado = []
    for item in queryset:

        mes_formatado = f"{item['ano']}-{item['mes_num']}"

        total_nc = item["total_nao_conforme"] or 0
        total_qtd_insp = item["total_qtd_inspecionada"] or 0

        taxa_nc = (total_nc / total_qtd_insp) * 100 if total_qtd_insp else 0

        resultado.append(
            {
                "Data": mes_formatado,
                "N° de inspeções": int(total_qtd_insp),
                "N° de não conformidades": int(total_nc),
                "% de não conformidade": f"{taxa_nc:.2f} %",
            }
        )

    return JsonResponse(resultado, safe=False)


def causas_nao_conformidade_mensal_tubos_cilindros(request):

    data_inicio = request.GET.get("data_inicio")
    data_fim = request.GET.get("data_fim")

    try:
        if data_inicio:
            data_inicio = datetime.strptime(data_inicio, "%Y-%m-%d")
        if data_fim:
            data_fim = datetime.strptime(data_fim, "%Y-%m-%d") + timedelta(days=1)
    except ValueError:
        return JsonResponse(
            {"erro": "Formato de data inválido. Use YYYY-MM-DD."}, status=400
        )

    queryset = CausasNaoConformidadeEstanqueidade.objects.filter(
        info_tubos_cilindros__dados_exec_inspecao__data_exec__isnull=False,
        info_tubos_cilindros__dados_exec_inspecao__inspecao_estanqueidade__peca__isnull=False,
        causa__isnull=False,  # Filtra registros sem causa antes da agregação
    )

    if data_inicio:
        queryset = queryset.filter(
            info_tubos_cilindros__dados_exec_inspecao__data_exec__gte=data_inicio
        )
    if data_fim:
        queryset = queryset.filter(
            info_tubos_cilindros__dados_exec_inspecao__data_exec__lte=data_fim
        )

    resultados = (
        queryset.annotate(
            ano=ExtractYear("info_tubos_cilindros__dados_exec_inspecao__data_exec"),
            mes=ExtractMonth("info_tubos_cilindros__dados_exec_inspecao__data_exec"),
            mes_formatado=Concat(
                ExtractYear("info_tubos_cilindros__dados_exec_inspecao__data_exec"),
                Value("-"),
                ExtractMonth("info_tubos_cilindros__dados_exec_inspecao__data_exec"),
                output_field=CharField(),
            ),
        )
        .values("mes_formatado", "causa__nome")
        .annotate(total_nao_conformidades=Sum("quantidade"))
        .order_by("mes_formatado", "causa__nome")
    )

    # Formatação final
    resultado = [
        {
            "Data": item["mes_formatado"],
            "Causa": item["causa__nome"],
            "Soma do N° Total de não conformidades": item["total_nao_conformidades"],
        }
        for item in resultados
    ]

    return JsonResponse(resultado, safe=False)


def imagens_nao_conformidade_tubos_cilindros(request):

    data_inicio = request.GET.get("data_inicio")
    data_fim = request.GET.get("data_fim")

    try:
        if data_inicio:
            data_inicio = datetime.strptime(data_inicio, "%Y-%m-%d")
        if data_fim:
            data_fim = datetime.strptime(data_fim, "%Y-%m-%d") + timedelta(days=1)
    except ValueError:
        return JsonResponse(
            {"erro": "Formato de data inválido. Use YYYY-MM-DD."}, status=400
        )

    # Query otimizada com select_related e prefetch_related específicos
    queryset = (
        CausasNaoConformidadeEstanqueidade.objects.filter(
            info_tubos_cilindros__dados_exec_inspecao__data_exec__isnull=False,
            info_tubos_cilindros__dados_exec_inspecao__inspecao_estanqueidade__peca__isnull=False,
        )
        .select_related(
            "info_tubos_cilindros",
            "info_tubos_cilindros__dados_exec_inspecao",
            "info_tubos_cilindros__dados_exec_inspecao__inspecao_estanqueidade",
        )
        .prefetch_related(
            "causa",
            Prefetch(
                "arquivos_estanqueidade",
                queryset=ArquivoCausaEstanqueidade.objects.only("arquivos"),
            ),
        )
    )

    if data_inicio:
        queryset = queryset.filter(
            info_tubos_cilindros__dados_exec_inspecao__data_exec__gte=data_inicio
        )
    if data_fim:
        queryset = queryset.filter(
            info_tubos_cilindros__dados_exec_inspecao__data_exec__lte=data_fim
        )

    # Pré-carrega todos os dados relacionados de uma vez
    dados_completos = list(queryset)

    resultado = []
    for item in dados_completos:
        date = item.info_tubos_cilindros.dados_exec_inspecao.data_exec - timedelta(
            hours=3
        )
        data_execucao = date.strftime("%Y-%m-%d %H:%M:%S")

        # Acessa os dados já pré-carregados
        causas = [c.nome for c in item.causa.all()]
        imagens = [
            arquivo.arquivos.url
            for arquivo in item.arquivos_estanqueidade.all()
            if hasattr(arquivo, "arquivos")
        ]

        for url in imagens:
            resultado.append(
                {
                    "data_execucao": data_execucao,
                    "causas": causas,
                    "quantidade": item.quantidade,
                    "imagem_url": url,
                }
            )

    return JsonResponse(resultado, safe=False)

def envio_inspecao_solda_tanque(request):
    if request.method != "POST":
        return JsonResponse({"error": "Método não permitido!"}, status=405)

    id_inspecao = request.POST.get("id-inspecao-solda-tanque")

    try:
        with transaction.atomic():
            data_inspecao = request.POST.get("data-inspecao-solda-tanque")
            conformidade = request.POST.get("conformidade-inspecao-solda-tanque")
            inspetor_id = request.POST.get("inspetor-inspecao-solda-tanque")
            nao_conformidade = request.POST.get("nao-conformidade-inspecao-solda-tanque")
            observacao = request.POST.get("observacao-inspecao-solda-tanque")
            quantidade_total_causas = int(
                request.POST.get("quantidade-total-causas", 0)
            )

            # Convertendo a string para um objeto datetime
            data_ajustada = timezone.make_aware(datetime.fromisoformat(data_inspecao))

            tanque_obj = InspecaoEstanqueidade.objects.get(pk=id_inspecao)

            # Obtém a inspeção e o inspetor
            inspecao = Inspecao.objects.create(
                tanque=tanque_obj
            )
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
    
    except InspecaoEstanqueidade.DoesNotExist:
        return JsonResponse({"error": "O tanque especificado não existe."}, status=404)

    except Exception as e:
        return JsonResponse({"error": "Erro"}, status=400)