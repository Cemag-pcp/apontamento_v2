from django.shortcuts import render
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q, Max
from django.db import transaction
from django.utils import timezone
from django.db import connection

from apontamento_pintura.models import Retrabalho
from ..models import (
    Inspecao,
    DadosExecucaoInspecao,
    Reinspecao,
    Causas,
    CausasNaoConformidade,
    ArquivoCausa,
    ArquivoConformidade,
)
from core.models import Profile

from datetime import datetime, timedelta
from collections import defaultdict

from storages.backends.s3boto3 import S3Boto3Storage


def inspecao_pintura(request):

    users = Profile.objects.filter(
        tipo_acesso="inspetor", permissoes__nome="inspecao/pintura"
    )
    causas = Causas.objects.filter(setor="pintura")

    cores = ["Amarelo", "Azul", "Cinza", "Laranja", "Verde", "Vermelho"]
    tipos_tinta = ["PÓ", "PU"]

    list_causas = [{"id": causa.id, "nome": causa.nome} for causa in causas]

    lista_inspetores = [
        {"nome_usuario": user.user.username, "id": user.user.id} for user in users
    ]

    user_profile = Profile.objects.filter(user=request.user).first()
    if (
        user_profile
        and user_profile.tipo_acesso == "inspetor"
        and user_profile.permissoes.filter(nome="inspecao/pintura").exists()
    ):
        inspetor_logado = {"nome_usuario": request.user.username, "id": request.user.id}
    else:
        inspetor_logado = None

    return render(
        request,
        "inspecao_pintura.html",
        {
            "inspetor_logado": inspetor_logado,
            "inspetores": lista_inspetores,
            "causas": list_causas,
            "cores": cores,
            "tipos_tinta": tipos_tinta,
        },
    )


def alerta_itens_pintura(request):

    finalizados_nao_reinspecionados = Retrabalho.objects.filter(
        status="finalizado",
        reinspecao__reinspecionado=False,
        reinspecao__inspecao__pecas_ordem_pintura__isnull=False,
    ).count()

    em_processo_e_retrabalhar = Retrabalho.objects.filter(
        Q(status="a retrabalhar") | Q(status="em processo"),
        reinspecao__inspecao__pecas_ordem_pintura__isnull=False,
    ).count()

    data = {
        "finalizados_nao_reinspecionados": finalizados_nao_reinspecionados,
        "em_processo_e_retrabalhar": em_processo_e_retrabalhar,
        "exibir_alerta": finalizados_nao_reinspecionados > 0
        or em_processo_e_retrabalhar > 0,
    }

    return JsonResponse(data)


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
    tipos_tinta_filtradas = (
        request.GET.get("tipos_tinta", "").split(",") if request.GET.get("tipos_tinta") else []
    )
    
    data_inicio = request.GET.get("data_inicio", None)
    data_fim = request.GET.get("data_fim", None)
    
    pesquisa_filtrada = request.GET.get("pesquisar", None)
    pagina = int(request.GET.get("pagina", 1))  # Página atual, padrão é 1
    itens_por_pagina = 12  # Itens por página

    # Filtra os dados
    datas = Inspecao.objects.filter(pecas_ordem_pintura__isnull=False, pecas_ordem_pintura__qtd_boa__gt=0).exclude(
        id__in=inspecoes_ids
    )

    quantidade_total = datas.count()  # Total de itens sem filtro

    if cores_filtradas:
        datas = datas.filter(pecas_ordem_pintura__ordem__cor__in=cores_filtradas)

    if tipos_tinta_filtradas:
        datas = datas.filter(pecas_ordem_pintura__tipo__in=tipos_tinta_filtradas)

    if not data_fim:
        data_fim = data_inicio

    # Filtra por dia inteiro usando lookup __date para não perder registros do dia
    if data_inicio and data_fim:
        datas = datas.filter(
            data_inspecao__date__gte=data_inicio, data_inspecao__date__lte=data_fim
        )
    elif data_inicio:
        datas = datas.filter(data_inspecao__date__gte=data_inicio)
    elif data_fim:
        datas = datas.filter(data_inspecao__date__lte=data_fim)

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

    # 1. Pré-filtrar reinspeções não realizadas
    reinspecao_ids = Reinspecao.objects.filter(reinspecionado=False).values_list(
        "inspecao", flat=True
    )

    # 2. Capturar parâmetros de filtro uma vez
    params = {
        "cores": (
            request.GET.get("cores", "").split(",") if request.GET.get("cores") else []
        ),
        "tipos_tinta": (
            request.GET.get("tipos_tinta", "").split(",") if request.GET.get("tipos_tinta") else []
        ),
        "inspetores": (
            request.GET.get("inspetores", "").split(",")
            if request.GET.get("inspetores")
            else []
        ),
        "data_inicio": request.GET.get("data_inicio"),
        "data_fim": request.GET.get("data_fim"),
        "pesquisa": request.GET.get("pesquisar"),
        "pagina": int(request.GET.get("pagina", 1)),
        "itens_por_pagina": 12,
    }

    # 3. Construir a consulta base com select_related e prefetch_related
    queryset = (
        Inspecao.objects.filter(
            id__in=reinspecao_ids, pecas_ordem_pintura__isnull=False
        )
        .select_related(
            "pecas_ordem_pintura__ordem", "pecas_ordem_pintura__operador_fim"
        )
        .prefetch_related("dadosexecucaoinspecao_set", "reinspecao_set__retrabalho_set")
        .order_by("-id")
    )

    # 4. Aplicar filtros de forma otimizada
    if params["cores"]:
        queryset = queryset.filter(
            pecas_ordem_pintura__ordem__cor__in=params["cores"]
        ).distinct()

    if params["tipos_tinta"]:
        queryset = queryset.filter(
            pecas_ordem_pintura__tipo__in=params["tipos_tinta"]
        ).distinct()

    # if params["data"]:
    #     queryset = queryset.filter(data_inspecao__date=params["data"]).distinct()

    data_inicio = params.get("data_inicio")
    data_fim = params.get("data_fim")

    print(data_inicio)

    if data_inicio and not data_fim:
        data_fim = data_inicio

    if data_inicio and data_fim:
        queryset = queryset.filter(
            dadosexecucaoinspecao__data_execucao__date__gte=data_inicio,
            dadosexecucaoinspecao__data_execucao__date__lte=data_fim,
        ).distinct()
    elif data_inicio:
        queryset = queryset.filter(
            dadosexecucaoinspecao__data_execucao__date__gte=data_inicio
        ).distinct()
    elif data_fim:
        queryset = queryset.filter(
            dadosexecucaoinspecao__data_execucao__date__lte=data_fim
        ).distinct()

    if params["pesquisa"]:
        pesquisa = params["pesquisa"].lower()
        queryset = queryset.filter(
            pecas_ordem_pintura__peca__icontains=pesquisa
        ).distinct()

    if params["inspetores"]:
        queryset = queryset.filter(
            dadosexecucaoinspecao__inspetor__user__username__in=params["inspetores"]
        ).distinct()

    # 5. Contagem total antes da paginação
    quantidade_total = queryset.count()

    # 6. Paginação mais eficiente
    paginador = Paginator(queryset, params["itens_por_pagina"])
    pagina_obj = paginador.get_page(params["pagina"])

    # 7. Pré-carregar dados relacionados para evitar N+1 queries
    dados_execucao = {
        item.inspecao_id: item
        for item in DadosExecucaoInspecao.objects.filter(
            inspecao_id__in=[i.id for i in pagina_obj]
        ).select_related("inspetor__user")
    }

    status_reinspecoes = {
        item.reinspecao.inspecao_id: item.status
        for item in Retrabalho.objects.filter(
            reinspecao__inspecao_id__in=[i.id for i in pagina_obj]
        )
    }

    # 8. Construir resposta de forma otimizada
    dados = []
    for data in pagina_obj:
        dados_exec = dados_execucao.get(data.id)
        data_ajustada = (
            (dados_exec.data_execucao - timedelta(hours=3)) if dados_exec else None
        )

        item = {
            "id": data.id,
            "data": (
                data_ajustada.strftime("%d/%m/%Y %H:%M:%S") if data_ajustada else None
            ),
            "peca": data.pecas_ordem_pintura.peca,
            "cor": data.pecas_ordem_pintura.ordem.cor,
            "tipo": data.pecas_ordem_pintura.tipo,
            "conformidade": dados_exec.conformidade if dados_exec else None,
            "nao_conformidade": dados_exec.nao_conformidade if dados_exec else None,
            "inspetor": (
                dados_exec.inspetor.user.username
                if dados_exec and dados_exec.inspetor
                else None
            ),
            "status_reinspecao": status_reinspecoes.get(data.id),
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
    tipos_tinta_filtradas = (
        request.GET.get("tipos_tinta", "").split(",") if request.GET.get("tipos_tinta") else []
    )
    inspetores_filtrados = (
        request.GET.get("inspetores", "").split(",")
        if request.GET.get("inspetores")
        else []
    )

    status_conformidade_filtrados = (
        request.GET.get("status-conformidade", "").split(",")
        if request.GET.get("status-conformidade")
        else []
    )

    data_inicio = request.GET.get("data_inicio", None)
    data_fim = request.GET.get("data_fim", None)

    pesquisa_filtrada = request.GET.get("pesquisar", None)
    pagina = int(request.GET.get("pagina", 1))  # Página atual, padrão é 1
    itens_por_pagina = 6  # Itens por página

    # Filtra os dados
    datas = Inspecao.objects.filter(
        id__in=inspecionados_ids, pecas_ordem_pintura__isnull=False
    )

    quantidade_total = datas.count()  # Total de itens sem filtro

    if cores_filtradas:
        datas = datas.filter(
            pecas_ordem_pintura__ordem__cor__in=cores_filtradas
        ).distinct()

    if tipos_tinta_filtradas:
        datas = datas.filter(
            pecas_ordem_pintura__tipo__in=tipos_tinta_filtradas
        ).distinct()

    # if data_filtrada:
    #     datas = datas.filter(
    #         dadosexecucaoinspecao__data_execucao__date=data_filtrada
    #     ).distinct()
    
    datas = datas.annotate(
        ultima_data_execucao=Max("dadosexecucaoinspecao__data_execucao")
    )

    if data_inicio and data_fim:
        datas = datas.filter(
            ultima_data_execucao__date__gte=data_inicio,
            ultima_data_execucao__date__lte=data_fim,
        ).order_by("-ultima_data_execucao")
    elif data_inicio:
        datas = datas.filter(
            ultima_data_execucao__date__gte=data_inicio
        ).order_by("-ultima_data_execucao")
    elif data_fim:
        datas = datas.filter(
            ultima_data_execucao__date__lte=data_fim
        ).order_by("-ultima_data_execucao")

    if pesquisa_filtrada:
        datas = datas.filter(
            pecas_ordem_pintura__peca__icontains=pesquisa_filtrada
        ).distinct()

    if inspetores_filtrados:
        datas = datas.filter(
            dadosexecucaoinspecao__inspetor__user__username__in=inspetores_filtrados
        ).distinct()

    # Filtro de status de conformidade
    if status_conformidade_filtrados:
        # Verifica os casos possíveis de combinação de filtros
        if set(status_conformidade_filtrados) == {"conforme", "nao_conforme"}:
            pass
        elif "conforme" in status_conformidade_filtrados:
            # Apenas itens conformes (nao_conformidades = 0) E num_execucao=0
            datas = datas.filter(
                dadosexecucaoinspecao__nao_conformidade=0,
                dadosexecucaoinspecao__num_execucao=0,
            )
        elif "nao_conforme" in status_conformidade_filtrados:
            # Apenas itens não conformes (nao_conformidades > 0) E num_execucao=0
            datas = datas.filter(
                dadosexecucaoinspecao__nao_conformidade__gt=0,
                dadosexecucaoinspecao__num_execucao=0,
            )

    datas = datas.select_related(
        "pecas_ordem_pintura",
        "pecas_ordem_pintura__ordem",
        "pecas_ordem_pintura__operador_fim",
    ).order_by("-dadosexecucaoinspecao__data_execucao")

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
            "id_inspecao": id,
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

def get_imagens_causas_conformidades_pintura(request, id, num_execucao):

    if not DadosExecucaoInspecao.objects.filter(pk=id).exists():
        return JsonResponse({'error': 'Execução de Inspeção não encontrada'}, status=404)
    

    arquivos_qs = ArquivoConformidade.objects.filter(dados_execucao_id=id, dados_execucao__num_execucao=num_execucao).only('arquivo')

    print(arquivos_qs)

    storage = S3Boto3Storage()

    imagens = [
        {'url': storage.url(arquivo.arquivo.name)}
        for arquivo in arquivos_qs if arquivo.arquivo
    ]

    return JsonResponse({'imagens': imagens})

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
            inspetor_id = request.POST.get("inspetor-reinspecao-pintura")
            nao_conformidade = request.POST.get("nao-conformidade-reinspecao-pintura")
            quantidade_total_causas = request.POST.get("quantidade-total-causas", 0) # Default para 0

            # Validações básicas de entrada
            if not all([id_inspecao, data_inspecao, conformidade, inspetor_id, nao_conformidade]):
                return JsonResponse({"error": "Dados essenciais estão faltando."}, status=400)

            data_ajustada = timezone.make_aware(datetime.fromisoformat(data_inspecao))

            inspecao = Inspecao.objects.get(id=id_inspecao)
            inspetor = Profile.objects.get(user__pk=inspetor_id)

            # Este objeto é criado em ambos os casos (conforme ou não conforme)
            dados_execucao = DadosExecucaoInspecao.objects.create(
                inspecao=inspecao,
                inspetor=inspetor,
                data_execucao=data_ajustada,
                conformidade=int(conformidade),
                nao_conformidade=int(nao_conformidade),
            )

            # Cenário 1: Existem não conformidades
            if int(nao_conformidade) > 0:
                for i in range(1, int(quantidade_total_causas) + 1):
                    # O nome da lista de causas no frontend estava errado, corrigido aqui
                    causas_ids = request.POST.getlist(f"causas_reinspecao_{i}[]") 
                    quantidade = request.POST.get(f"quantidade_reinspecao_{i}")
                    # O nome da lista de imagens no frontend estava errado, corrigido aqui
                    imagens = request.FILES.getlist(f"imagens_reinspecao_{i}[]") 

                    if not causas_ids or not quantidade:
                        raise ValueError(f"Causa ou quantidade faltando para o item {i}.")

                    causas_objs = Causas.objects.filter(id__in=causas_ids)
                    causa_nao_conformidade = CausasNaoConformidade.objects.create(
                        dados_execucao=dados_execucao, quantidade=int(quantidade)
                    )
                    causa_nao_conformidade.causa.add(*causas_objs)

                    for imagem in imagens:
                        ArquivoCausa.objects.create(
                            causa_nao_conformidade=causa_nao_conformidade,
                            arquivo=imagem,
                        )
            
            # Cenário 2: Tudo está conforme
            else:
                # Busca as imagens do campo de conformidade
                imagens_conformidade = request.FILES.getlist('imagens_conformidade')

                if imagens_conformidade:
                    ArquivoConformidade.objects.create(
                        dados_execucao=dados_execucao,
                        arquivo=imagens_conformidade[0]
                    )

            # Em ambos os cenários, marcamos a reinspeção como concluída
            reinspecao = Reinspecao.objects.filter(inspecao=inspecao).first()
            if reinspecao:
                reinspecao.reinspecionado = True
                reinspecao.save()

        return JsonResponse({"success": True})

    except Inspecao.DoesNotExist:
        return JsonResponse({"error": "Inspeção não encontrada."}, status=404)
    except Profile.DoesNotExist:
        return JsonResponse({"error": "Inspetor não encontrado."}, status=404)
    except Exception as e:
        # Retorna um erro mais descritivo para depuração
        return JsonResponse({"error": f"Ocorreu um erro interno: {str(e)}"}, status=500)


def dashboard_pintura(request):

    return render(request, "dashboard/pintura.html")


### dashboard pintura ###


def indicador_pintura_analise_temporal(request):
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

    sql = """
    WITH producao_total AS (
        SELECT 
            EXTRACT(YEAR FROM data) AS ano,
            EXTRACT(MONTH FROM data) AS mes,
            SUM(qtd_boa) AS total_produzido
        FROM apontamento_v2.apontamento_pintura_pecasordem
        WHERE qtd_boa IS NOT NULL
            AND data BETWEEN %(data_inicio)s AND %(data_fim)s
        GROUP BY EXTRACT(YEAR FROM data), EXTRACT(MONTH FROM data)
    ),
    inspecoes_total AS (
        SELECT
            EXTRACT(YEAR FROM app.data) AS ano,
            EXTRACT(MONTH FROM app.data) AS mes,
            SUM(dei.conformidade) AS total_conforme,
            SUM(dei.nao_conformidade) AS total_nao_conforme
        FROM apontamento_v2.apontamento_pintura_pecasordem app
        INNER JOIN apontamento_v2.inspecao_inspecao i ON i.pecas_ordem_pintura_id = app.id
        INNER JOIN apontamento_v2.inspecao_dadosexecucaoinspecao dei ON dei.inspecao_id = i.id
        WHERE app.data BETWEEN %(data_inicio)s AND %(data_fim)s
        GROUP BY EXTRACT(YEAR FROM app.data), EXTRACT(MONTH FROM app.data)
    )
    SELECT 
        concat(p.ano, '-', p.mes) as mes,
        p.total_produzido,
        (COALESCE(i.total_conforme, 0) - COALESCE(i.total_nao_conforme, 0)) AS total_conforme,
        COALESCE(i.total_nao_conforme, 0) AS total_nao_conforme
    FROM producao_total p
    LEFT JOIN inspecoes_total i ON p.ano = i.ano AND p.mes = i.mes
    ORDER BY p.ano, p.mes;
    """

    with connection.cursor() as cursor:
        cursor.execute(
            sql,
            {
                "data_inicio": data_inicio,
                "data_fim": data_fim,
            },
        )
        rows = cursor.fetchall()

    resultado = []
    for row in rows:
        mes, qtd_produzida, soma_conformidade, soma_nao_conformidade = row
        qtd_inspecionada = soma_conformidade + soma_nao_conformidade
        taxa_nc = (
            (soma_nao_conformidade / soma_conformidade) if soma_conformidade else 0
        )

        resultado.append(
            {
                "mes": mes,
                "qtd_peca_produzida": qtd_produzida or 0,
                "qtd_peca_inspecionada": qtd_inspecionada or 0,
                "taxa_nao_conformidade": round(taxa_nc, 4),
            }
        )

    return JsonResponse(resultado, safe=False)


def indicador_pintura_resumo_analise_temporal(request):
    data_inicio = request.GET.get("data_inicio")
    data_fim = request.GET.get("data_fim")

    try:
        if data_inicio:
            data_inicio = datetime.strptime(data_inicio, "%Y-%m-%d")
        if data_fim:
            data_fim = datetime.strptime(data_fim, "%Y-%m-%d")
    except ValueError:
        return JsonResponse(
            {"erro": "Formato de data inválido. Use YYYY-MM-DD."}, status=400
        )

    sql = """
    WITH producao_total AS (
    SELECT 
        EXTRACT(YEAR FROM data) AS ano,
        EXTRACT(MONTH FROM data) AS mes,
        SUM(qtd_boa) AS total_produzido
    FROM apontamento_v2.apontamento_pintura_pecasordem
    WHERE qtd_boa IS NOT NULL
        AND data BETWEEN %(data_inicio)s AND %(data_fim)s
    GROUP BY EXTRACT(YEAR FROM data), EXTRACT(MONTH FROM data)
    ),
    inspecoes_total AS (
        SELECT
            EXTRACT(YEAR FROM app.data) AS ano,
            EXTRACT(MONTH FROM app.data) AS mes,
            SUM(dei.conformidade) AS total_conforme,
            SUM(dei.nao_conformidade) AS total_nao_conforme
        FROM apontamento_v2.apontamento_pintura_pecasordem app
        INNER JOIN apontamento_v2.inspecao_inspecao i ON i.pecas_ordem_pintura_id = app.id
        INNER JOIN apontamento_v2.inspecao_dadosexecucaoinspecao dei ON dei.inspecao_id = i.id
        WHERE app.data BETWEEN %(data_inicio)s AND %(data_fim)s
        GROUP BY EXTRACT(YEAR FROM app.data), EXTRACT(MONTH FROM app.data)
    )
    SELECT 
        p.ano,
        p.mes,
        p.total_produzido,
        (COALESCE(i.total_conforme, 0) - COALESCE(i.total_nao_conforme, 0)) AS total_conforme,
        COALESCE(i.total_nao_conforme, 0) AS total_nao_conforme
    FROM producao_total p
    LEFT JOIN inspecoes_total i ON p.ano = i.ano AND p.mes = i.mes
    ORDER BY p.ano, p.mes;
    """

    with connection.cursor() as cursor:
        cursor.execute(
            sql,
            {
                "data_inicio": data_inicio,
                "data_fim": data_fim,
            },
        )
        rows = cursor.fetchall()

    resultado = []
    for row in rows:
        ano, mes_num, total_prod, total_conf, total_nc = row
        total_insp = total_nc + total_conf
        perc_insp = (total_insp / total_prod) * 100 if total_prod else 0

        resultado.append(
            {
                "Data": f"{int(ano)}-{int(mes_num):02}",
                "N° de peças produzidas": int(total_prod or 0),
                "N° de inspeções": int(total_insp or 0),
                "N° de não conformidades": int(total_nc or 0),
                "% de inspeção": f"{perc_insp:.2f} %",
            }
        )

    return JsonResponse(resultado, safe=False)


def causas_nao_conformidade_mensal(request):
    # Obtém parâmetros de data da requisição
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

    sql = """
        SELECT
        TO_CHAR(i.data_inspecao, 'YYYY-MM') AS mes,
        c.nome AS causa,
        SUM(cnc.quantidade) AS total_nao_conformidades,
        app.peca as peca
    FROM apontamento_v2.inspecao_causasnaoconformidade cnc
    JOIN apontamento_v2.inspecao_dadosexecucaoinspecao de ON cnc.dados_execucao_id = de.id
    JOIN apontamento_v2.inspecao_inspecao i ON de.inspecao_id = i.id
    JOIN apontamento_v2.inspecao_causasnaoconformidade_causa cnc_c ON cnc.id = cnc_c.causasnaoconformidade_id
    JOIN apontamento_v2.inspecao_causas c ON c.id = cnc_c.causas_id 
    join apontamento_v2.apontamento_pintura_pecasordem app on app.id = i.pecas_ordem_pintura_id 
    WHERE i.data_inspecao IS NOT NULL
    AND i.pecas_ordem_pintura_id IS NOT NULL
    AND i.data_inspecao >= %(data_inicio)s
    AND i.data_inspecao < %(data_fim)s
    GROUP BY mes, c.nome, app.peca
    ORDER BY mes ASC, c.nome ASC;
    """

    with connection.cursor() as cursor:
        cursor.execute(
            sql,
            {
                "data_inicio": data_inicio,
                "data_fim": data_fim,
            },
        )
        rows = cursor.fetchall()

    resultado = [
        {
            "data_execucao": row[0],
            "nome_causa": row[1],
            "quantidade": row[2],
            "peca": row[3],
        }
        for row in rows
    ]

    return JsonResponse(resultado, safe=False)


def imagens_nao_conformidade_pintura(request):
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

    sql = """
        SELECT
            (i.data_inspecao - INTERVAL '3 hour') AS data_execucao,
            cnc.quantidade,
            a.arquivo AS arquivo_url,
            ARRAY_AGG(c.nome) AS causas
        FROM apontamento_v2.inspecao_causasnaoconformidade cnc
        JOIN apontamento_v2.inspecao_dadosexecucaoinspecao de ON cnc.dados_execucao_id = de.id
        JOIN apontamento_v2.inspecao_inspecao i ON de.inspecao_id = i.id
        LEFT JOIN apontamento_v2.inspecao_arquivocausa a ON a.causa_nao_conformidade_id = cnc.id
        LEFT JOIN apontamento_v2.inspecao_causasnaoconformidade_causa cnc_c ON cnc.id = cnc_c.causasnaoconformidade_id
        LEFT JOIN apontamento_v2.inspecao_causas c ON cnc_c.causas_id  = c.id
        WHERE de.data_execucao IS NOT NULL
        AND i.pecas_ordem_pintura_id IS NOT NULL
        AND de.data_execucao >= %(data_inicio)s
        AND de.data_execucao < %(data_fim)s
        AND a.arquivo IS NOT NULL
        GROUP BY cnc.id, i.data_inspecao, a.arquivo, cnc.quantidade
        ORDER BY i.data_inspecao DESC;
    """

    with connection.cursor() as cursor:
        cursor.execute(
            sql,
            {
                "data_inicio": data_inicio,
                "data_fim": data_fim,
            },
        )
        rows = cursor.fetchall()

    resultado = []
    for data_execucao, quantidade, arquivo_url, causas in rows:
        resultado.append(
            {
                "data_execucao": data_execucao.strftime("%Y-%m-%d %H:%M:%S"),
                "quantidade": quantidade,
                "arquivo_url": arquivo_url,
                "causas": causas,
            }
        )

    return JsonResponse(resultado, safe=False)


def causas_nao_conformidade_por_tipo(request):
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

    sql = """
    SELECT
        TO_CHAR(i.data_inspecao, 'YYYY-MM') AS data_inspecao,
        c.nome AS Causa,
        UPPER(pop.tipo) AS Tipo,
        pop.peca AS Peça,
        SUM(cnc.quantidade) AS Quantidade
    FROM apontamento_v2.inspecao_causasnaoconformidade cnc
    JOIN apontamento_v2.inspecao_dadosexecucaoinspecao de ON cnc.dados_execucao_id = de.id
    JOIN apontamento_v2.inspecao_inspecao i ON de.inspecao_id = i.id
    JOIN apontamento_v2.apontamento_pintura_pecasordem pop ON i.pecas_ordem_pintura_id = pop.id
    JOIN apontamento_v2.inspecao_causasnaoconformidade_causa link ON cnc.id = link.causasnaoconformidade_id
    JOIN apontamento_v2.inspecao_causas c ON link.causas_id = c.id
    WHERE i.data_inspecao IS NOT NULL
      AND i.pecas_ordem_pintura_id IS NOT NULL
      AND i.data_inspecao >= %(data_inicio)s
      AND i.data_inspecao < %(data_fim)s
    GROUP BY data_inspecao, Causa, Tipo, Peça
    ORDER BY data_inspecao, Causa, Tipo, Peça;
    """

    with connection.cursor() as cursor:
        cursor.execute(
            sql,
            {
                "data_inicio": data_inicio,
                "data_fim": data_fim,
            },
        )
        rows = cursor.fetchall()

    resultado = []
    for data, causa, tipo, peca, quantidade in rows:
        resultado.append(
            {
                "Data": data,
                "Causa": causa,
                "Tipo": tipo,
                "Peça": peca,
                "Quantidade": quantidade,
            }
        )

    return JsonResponse(resultado, safe=False)
