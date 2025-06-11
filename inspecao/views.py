from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import (
    Q, Prefetch, OuterRef, Subquery, Max, Sum, F, FloatField, 
    IntegerField,ExpressionWrapper, Func, Value, CharField, Count, Case, When
)
from django.db import transaction
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.db.models.functions import Concat, Cast, TruncMonth, ExtractYear, ExtractMonth
from django.db import connection

from cadastro.models import PecasEstanqueidade
from apontamento_montagem.models import ConjuntosInspecionados
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
from apontamento_estamparia.models import (
    InfoAdicionaisInspecaoEstamparia,
    MedidasInspecaoEstamparia,
    DadosNaoConformidade,
    ImagemNaoConformidade,
)

from datetime import datetime, timedelta
from collections import defaultdict
import json

def motivos_causas(request, setor):

    motivos = Causas.objects.filter(setor=setor)

    return JsonResponse({"motivos": list(motivos.values())})


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

    list_causas = [{"id": causa.id, "nome": causa.nome} for causa in causas]

    lista_inspetores = [
        {"nome_usuario": user.user.username, "id": user.user.id} for user in users
    ]

    user_profile = Profile.objects.filter(user=request.user).first()
    if user_profile and user_profile.tipo_acesso == "inspetor" and user_profile.permissoes.filter(nome="inspecao/montagem").exists():
        inspetor_logado = {
            "nome_usuario": request.user.username,
            "id": request.user.id
        }
    else:
        inspetor_logado = None

    return render(
        request,
        "inspecao_montagem.html",
        {"inspetor_logado":inspetor_logado, "inspetores": lista_inspetores, 
         "causas": list_causas, "maquinas": maquinas},
    )


def conjuntos_inspecionados_montagem(request):

    if request.method == "GET":

        conjuntos = ConjuntosInspecionados.objects.all()

        conjuntos_inspecionados = [
            {
                "id": conjunto.id,
                "codigo": conjunto.codigo,
                "descricao": conjunto.descricao,
            }
            for conjunto in conjuntos
        ]

        return render(
            request,
            "conjuntos_inspecionados.html",
            {"conjuntos": conjuntos_inspecionados},
        )
    else:
        return JsonResponse({"error": "Método não permitido"}, status=403)


def add_remove_conjuntos_inspecionados(request, codigo=None):

    if request.method == "DELETE":

        try:
            conjunto = ConjuntosInspecionados.objects.filter(codigo=codigo)
            conjunto.delete()
            return JsonResponse({"status": "success"})
        except ConjuntosInspecionados.DoesNotExist:
            return JsonResponse(
                {"status": "error", "message": "Conjunto não encontrado"}, status=404
            )

    elif request.method == "POST":
        try:
            data = json.loads(request.body)
            codigo_peca = data.get("codigo")
            descricao = data.get("descricao")

            if not codigo_peca or not descricao:
                return JsonResponse({"error": "Campos obrigatórios"}, status=400)

            # Verificar se já existe o código
            if ConjuntosInspecionados.objects.filter(codigo=codigo_peca).exists():
                return JsonResponse({"error": "Código já existe"}, status=400)

            novo_conjunto = ConjuntosInspecionados.objects.create(
                codigo=codigo_peca, descricao=descricao
            )

            return JsonResponse(
                {
                    "success": "Conjunto adicionado com sucesso",
                    "codigo": novo_conjunto.codigo,
                    "descricao": novo_conjunto.descricao,
                },
                status=201,
            )

        except Exception as e:
            print("Erro ao adicionar conjunto:", e)
            return JsonResponse({"error": "Erro interno do servidor"}, status=500)
    else:
        return JsonResponse({"error": "Método não permitido"}, status=403)


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

    user_profile = Profile.objects.filter(user=request.user).first()
    if user_profile and user_profile.tipo_acesso == "inspetor" and user_profile.permissoes.filter(nome="inspecao/pintura").exists():
        inspetor_logado = {
            "nome_usuario": request.user.username,
            "id": request.user.id
        }
    else:
        inspetor_logado = None

    return render(
        request,
        "inspecao_pintura.html",
        {"inspetor_logado":inspetor_logado, "inspetores": lista_inspetores, 
         "causas": list_causas, "cores": cores},
    )

def alerta_itens_pintura(request):

    finalizados_nao_reinspecionados = Retrabalho.objects.filter(
        status='finalizado',
        reinspecao__reinspecionado=False,
        reinspecao__inspecao__pecas_ordem_pintura__isnull=False
    ).count()

    em_processo_e_retrabalhar = Retrabalho.objects.filter(
        Q(status='a retrabalhar') | Q(status='em processo'),
        reinspecao__inspecao__pecas_ordem_pintura__isnull=False
    ).count()

    data = {
        'finalizados_nao_reinspecionados':finalizados_nao_reinspecionados,
        'em_processo_e_retrabalhar':em_processo_e_retrabalhar,
        'exibir_alerta': finalizados_nao_reinspecionados > 0 or em_processo_e_retrabalhar > 0
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

    # 1. Pré-filtrar reinspeções não realizadas
    reinspecao_ids = Reinspecao.objects.filter(
        reinspecionado=False
    ).values_list("inspecao", flat=True)

    # 2. Capturar parâmetros de filtro uma vez
    params = {
        "cores": request.GET.get("cores", "").split(",") if request.GET.get("cores") else [],
        "inspetores": request.GET.get("inspetores", "").split(",") if request.GET.get("inspetores") else [],
        "data": request.GET.get("data"),
        "pesquisa": request.GET.get("pesquisar"),
        "pagina": int(request.GET.get("pagina", 1)),
        "itens_por_pagina": 12
    }

    # 3. Construir a consulta base com select_related e prefetch_related
    queryset = Inspecao.objects.filter(
        id__in=reinspecao_ids,
        pecas_ordem_pintura__isnull=False
    ).select_related(
        "pecas_ordem_pintura__ordem",
        "pecas_ordem_pintura__operador_fim"
    ).prefetch_related(
        "dadosexecucaoinspecao_set",
        "reinspecao_set__retrabalho_set"
    ).order_by("-id")

    # 4. Aplicar filtros de forma otimizada
    if params["cores"]:
        queryset = queryset.filter(
            pecas_ordem_pintura__ordem__cor__in=params["cores"]
        ).distinct()

    if params["data"]:
        queryset = queryset.filter(
            data_inspecao__date=params["data"]
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
        ).select_related('inspetor__user')
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
        data_ajustada = (dados_exec.data_execucao - timedelta(hours=3)) if dados_exec else None

        item = {
            "id": data.id,
            "data": data_ajustada.strftime("%d/%m/%Y %H:%M:%S") if data_ajustada else None,
            "peca": data.pecas_ordem_pintura.peca,
            "cor": data.pecas_ordem_pintura.ordem.cor,
            "tipo": data.pecas_ordem_pintura.tipo,
            "conformidade": dados_exec.conformidade if dados_exec else None,
            "nao_conformidade": dados_exec.nao_conformidade if dados_exec else None,
            "inspetor": dados_exec.inspetor.user.username if dados_exec and dados_exec.inspetor else None,
            "status_reinspecao": status_reinspecoes.get(data.id),
        }
        dados.append(item)

    return JsonResponse({
        "dados": dados,
        "total": quantidade_total,
        "total_filtrado": paginador.count,
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
    itens_por_pagina = 6  # Itens por página

    # Filtra os dados
    datas = Inspecao.objects.filter(
        id__in=inspecionados_ids, pecas_ordem_pintura__isnull=False
    )

    quantidade_total = datas.count()  # Total de itens sem filtro

    if cores_filtradas:
        datas = datas.filter(pecas_ordem_pintura__ordem__cor__in=cores_filtradas).distinct()

    if data_filtrada:
        datas = datas.filter(dadosexecucaoinspecao__data_execucao__date=data_filtrada).distinct()

    if pesquisa_filtrada:
        datas = datas.filter(pecas_ordem_pintura__peca__icontains=pesquisa_filtrada).distinct()

    if inspetores_filtrados:
        datas = datas.filter(
            dadosexecucaoinspecao__inspetor__user__username__in=inspetores_filtrados
        ).distinct()

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

    # Otimização 1: Consulta mais eficiente para reinspeções
    reinspecao_ids = Reinspecao.objects.filter(reinspecionado=False).values_list(
        "inspecao_id", flat=True
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
    pagina = int(request.GET.get("pagina", 1))
    itens_por_pagina = 12

    # Otimização 2: Construção de query com Q objects
    query = Q(id__in=reinspecao_ids) & Q(pecas_ordem_montagem__isnull=False)

    if maquinas_filtradas:
        query &= Q(pecas_ordem_montagem__ordem__maquina__nome__in=maquinas_filtradas)

    if data_filtrada:
        query &= Q(data_inspecao__date=data_filtrada)

    if pesquisa_filtrada:
        pesquisa_filtrada = pesquisa_filtrada.lower()
        query &= Q(pecas_ordem_montagem__peca__icontains=pesquisa_filtrada)

    if inspetores_filtrados:
        query &= Q(
            dadosexecucaoinspecao__inspetor__user__username__in=inspetores_filtrados
        )

    # Otimização 3: Pré-carregamento de relacionamentos
    datas = (
        Inspecao.objects.filter(query)
        .select_related(
            "pecas_ordem_montagem",
            "pecas_ordem_montagem__ordem",
            "pecas_ordem_montagem__ordem__maquina",
        )
        .prefetch_related(
            "dadosexecucaoinspecao_set",
            "dadosexecucaoinspecao_set__inspetor",
            "dadosexecucaoinspecao_set__inspetor__user",
        )
        .order_by("-id")
    ).distinct()

    quantidade_total = Inspecao.objects.filter(
        id__in=reinspecao_ids, pecas_ordem_montagem__isnull=False
    ).count()

    # Paginação
    paginador = Paginator(datas, itens_por_pagina)
    pagina_obj = paginador.get_page(pagina)

    # Otimização 4: Processamento eficiente dos dados
    dados = []
    for data in pagina_obj:
        dados_execucao = data.dadosexecucaoinspecao_set.last()  # Já pré-carregado

        data_ajustada = DadosExecucaoInspecao.objects.filter(inspecao=data).values_list(
            "data_execucao", flat=True
        ).last() - timedelta(hours=3)

        item = {
            "id": data.id,
            "data": data_ajustada.strftime("%d/%m/%Y %H:%M:%S"),
            "peca": data.pecas_ordem_montagem.peca,  # Assumindo que peca é uma string ou tem __str__ definido
            "maquina": data.pecas_ordem_montagem.ordem.maquina.nome,
            "conformidade": dados_execucao.conformidade if dados_execucao else None,
            "nao_conformidade": (
                dados_execucao.nao_conformidade if dados_execucao else None
            ),
            "inspetor": (
                dados_execucao.inspetor.user.username
                if dados_execucao and dados_execucao.inspetor
                else None
            ),
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
        ).distinct()

    if data_filtrada:
        datas = datas.filter(dadosexecucaoinspecao__data_execucao__date=data_filtrada).distinct()

    if pesquisa_filtrada:
        datas = datas.filter(pecas_ordem_montagem__peca__icontains=pesquisa_filtrada).distinct()

    if inspetores_filtrados:
        datas = datas.filter(
            dadosexecucaoinspecao__inspetor__user__username__in=inspetores_filtrados
        ).distinct()

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
            data_ajustada = DadosExecucaoInspecao.objects.filter(
                inspecao=data
            ).values_list("data_execucao", flat=True).last() - timedelta(hours=3)
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

    maquinas = Maquina.objects.filter(setor__nome="estamparia", tipo="maquina")
    motivos = Causas.objects.filter(setor="estamparia")
    inspetores = Profile.objects.filter(
        tipo_acesso="inspetor", permissoes__nome="inspecao/estamparia"
    )

    inspetores = [
        {"nome_usuario": inspetor.user.username, "id": inspetor.user.id}
        for inspetor in inspetores
    ]

    user_profile = Profile.objects.filter(user=request.user).first()
    if user_profile and user_profile.tipo_acesso == "inspetor" and user_profile.permissoes.filter(nome="inspecao/estamparia").exists():
        inspetor_logado = {
            "nome_usuario": request.user.username,
            "id": request.user.id
        }
    else:
        inspetor_logado = None

    context = {"maquinas": maquinas, "motivos": motivos, "inspetores": inspetores, "inspetor_logado":inspetor_logado}

    return render(request, "inspecao_estamparia.html", context)


def inspecionar_estamparia(request):

    if request.method != "POST":
        return JsonResponse({"error": "Método não permitido!"}, status=405)

    if request.method == "POST":

        print(request.POST)
        print(request.FILES)

        itemInspecionado = DadosExecucaoInspecao.objects.filter(
            inspecao__id=request.POST.get("id-inspecao")
        )

        if itemInspecionado:
            return JsonResponse({"error": "Item já inspecionado!"}, status=400)

        # Coletar dados simples do formulário
        dataInspecao = request.POST.get("dataInspecao")
        pecasProduzidas = int(request.POST.get("pecasProduzidas"))
        inspetor = request.POST.get("inspetor")
        numPecaDefeituosa = (
            int(request.POST.get("numPecaDefeituosa", None))
            if request.POST.get("numPecaDefeituosa", None)
            else 0
        )

        # Coletar causas de peças mortas (JSON convertido para lista)
        causasPecaMorta_raw = request.POST.get("causasPecaMorta")
        causasPecaMorta = json.loads(causasPecaMorta_raw) if causasPecaMorta_raw else []

        inspecao = get_object_or_404(Inspecao, pk=request.POST.get("id-inspecao"))
        inspetor = Profile.objects.get(user__pk=inspetor)

        # Coletar não conformidades (JSON convertido para lista de dicionários)
        nao_conformidades_raw = request.POST.get("naoConformidades")
        nao_conformidades = (
            json.loads(nao_conformidades_raw) if nao_conformidades_raw else []
        )

        total_pecas_afetadas = 0

        # Faz um loop para percorrer cada não conformidade e somar a quantidade afetada
        for nao_conformidade in nao_conformidades:
            quantidade = (
                int(nao_conformidade.get("quantidadeAfetada", 0))
                if nao_conformidade.get("quantidadeAfetada", 0)
                else 0
            )
            total_pecas_afetadas += quantidade  # Acumula a quantidade afetada

        # model: DadosExecucaoInspecao
        tamanho_amostra = min(3, pecasProduzidas - numPecaDefeituosa)

        nao_conformidade = total_pecas_afetadas  # soma de todas não conformidade, não considera peças mortas

        conformidade = tamanho_amostra - nao_conformidade

        with transaction.atomic():

            new_dados_execucao_inspecao = DadosExecucaoInspecao.objects.create(
                inspecao=inspecao,
                inspetor=inspetor,
                conformidade=conformidade,
                nao_conformidade=nao_conformidade,
            )

            # model: InfoAdicionalEstamparia
            dados_exec_inspecao = get_object_or_404(
                DadosExecucaoInspecao, inspecao=inspecao
            )
            inspecao_completa = request.POST.get("inspecao_total")  # campo boleano

            new_info_adicionais = InfoAdicionaisInspecaoEstamparia.objects.create(
                dados_exec_inspecao=dados_exec_inspecao,
                inspecao_completa=True if inspecao_completa == "sim" else False,
                qtd_mortas=numPecaDefeituosa if numPecaDefeituosa > 0 else 0,
            )

            # Relacionar as causas ao objeto criado
            if causasPecaMorta:
                new_info_adicionais.motivo_mortas.set(
                    causasPecaMorta
                )  # Relaciona as causas pelo ManyToManyField

            # model: MedidasInspecaoEstamparia
            informacoes_adicionais_estamparia = get_object_or_404(
                InfoAdicionaisInspecaoEstamparia, pk=new_info_adicionais.pk
            )

            # Dicionários para armazenar os valores dinamicamente
            medidas_raw = request.POST.get("medidas")
            medidas = json.loads(medidas_raw) if medidas_raw else []

            for linha in medidas:
                campos = {
                    "informacoes_adicionais_estamparia": informacoes_adicionais_estamparia
                }

                for i in range(1, 5):
                    chave = f"medida{i}"
                    letra = chr(96 + i)  # 1→a, 2→b, etc.

                    if chave in linha:
                        campos[f"cabecalho_medida_{letra}"] = linha[chave]["nome"]
                        campos[f"medida_{letra}"] = linha[chave]["valor"]
                    else:
                        campos[f"cabecalho_medida_{letra}"] = None
                        campos[f"medida_{letra}"] = None

                MedidasInspecaoEstamparia.objects.create(**campos)

            if medidas:
                primeira_linha = medidas[0]  # pega a primeira linha de medidas

                cabecalho_medida_a = medida_a = None
                cabecalho_medida_b = medida_b = None
                cabecalho_medida_c = medida_c = None
                cabecalho_medida_d = medida_d = None

                if "medida1" in primeira_linha:
                    cabecalho_medida_a = primeira_linha["medida1"]["nome"]
                    medida_a = primeira_linha["medida1"]["valor"]

                if "medida2" in primeira_linha:
                    cabecalho_medida_b = primeira_linha["medida2"]["nome"]
                    medida_b = primeira_linha["medida2"]["valor"]

                if "medida3" in primeira_linha:
                    cabecalho_medida_c = primeira_linha["medida3"]["nome"]
                    medida_c = primeira_linha["medida3"]["valor"]

                if "medida4" in primeira_linha:
                    cabecalho_medida_d = primeira_linha["medida4"]["nome"]
                    medida_d = primeira_linha["medida4"]["valor"]

            MedidasInspecaoEstamparia.objects.create(
                informacoes_adicionais_estamparia=informacoes_adicionais_estamparia,
                cabecalho_medida_a=cabecalho_medida_a,
                medida_a=medida_a,
                cabecalho_medida_b=cabecalho_medida_b,
                medida_b=medida_b,
                cabecalho_medida_c=cabecalho_medida_c,
                medida_c=medida_c,
                cabecalho_medida_d=cabecalho_medida_d,
                medida_d=medida_d,
            )

            soma_qtd_nao_conformidade = 0
            # model: DadosNaoConformidade
            for index, nao_conformidade in enumerate(nao_conformidades, start=1):

                qt_nao_conformidade = (
                    int(nao_conformidade.get("quantidadeAfetada", 0))
                    if nao_conformidade.get("quantidadeAfetada") != ""
                    else 0
                )
                destino = nao_conformidade.get("destino")

                if destino != "sucata":
                    soma_qtd_nao_conformidade += qt_nao_conformidade

                causas = nao_conformidade.get(
                    "causas", []
                )  # Recebe a lista de IDs das causas
                imagens = request.FILES.getlist(
                    f"fotoNaoConformidade{index}"
                )  # Pega as imagens enviadas

                # Criar o objeto principal da não conformidade
                new_dados_nao_conformidade = DadosNaoConformidade.objects.create(
                    informacoes_adicionais_estamparia=informacoes_adicionais_estamparia,
                    qt_nao_conformidade=qt_nao_conformidade,
                    destino=destino,
                )

                # Relacionar as causas ao objeto criado
                if causas:
                    new_dados_nao_conformidade.causas.set(
                        causas
                    )  # Relaciona as causas pelo ManyToManyField

                # Salvar as imagens relacionadas
                for img in imagens:
                    ImagemNaoConformidade.objects.create(
                        nao_conformidade=new_dados_nao_conformidade, imagem=img
                    )

                # Salva o objeto principal
                new_dados_nao_conformidade.save()

            # Reinspecao
            if soma_qtd_nao_conformidade > 0:
                reinspecao = Reinspecao(inspecao=inspecao)
                reinspecao.save()

    return JsonResponse({"success": True, "message": "Inspeção realizada com sucesso!"})


def get_itens_inspecao_estamparia(request):
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
    datas = Inspecao.objects.filter(pecas_ordem_estamparia__isnull=False).exclude(
        id__in=inspecoes_ids
    )

    quantidade_total = datas.count()  # Total de itens sem filtro

    if maquinas_filtradas:
        datas = datas.filter(
            pecas_ordem_estamparia__ordem__maquina__nome__in=maquinas_filtradas
        )

    if data_filtrada:
        datas = datas.filter(data_inspecao__date=data_filtrada)

    if pesquisa_filtrada:
        pesquisa_filtrada = pesquisa_filtrada.lower()
        datas = datas.filter(
            pecas_ordem_estamparia__peca__codigo__icontains=pesquisa_filtrada
        )

    datas = datas.select_related(
        "pecas_ordem_estamparia",
        "pecas_ordem_estamparia__ordem",
        "pecas_ordem_estamparia__operador",
    ).order_by("-id")

    # Paginação
    paginador = Paginator(datas, itens_por_pagina)
    pagina_obj = paginador.get_page(pagina)

    dados = []
    for data in pagina_obj:
        data_ajustada = data.data_inspecao - timedelta(hours=3)
        matricula_nome_operador = None

        if data.pecas_ordem_estamparia.operador:
            matricula_nome_operador = f"{data.pecas_ordem_estamparia.operador.matricula} - {data.pecas_ordem_estamparia.operador.nome}"

        # Operador
        if data.pecas_ordem_estamparia.operador:
            matricula_nome_operador = f"{data.pecas_ordem_estamparia.operador.matricula} - {data.pecas_ordem_estamparia.operador.nome}"

        # Peça
        peca_info = ""
        if data.pecas_ordem_estamparia.peca:
            peca_info = f"{data.pecas_ordem_estamparia.peca.codigo} - {data.pecas_ordem_estamparia.peca.descricao}"

        # Máquina
        maquina_nome = None
        if (
            data.pecas_ordem_estamparia.ordem
            and data.pecas_ordem_estamparia.ordem.maquina
        ):
            maquina_nome = data.pecas_ordem_estamparia.ordem.maquina.nome

        item = {
            "id": data.id,
            "data": data_ajustada.strftime("%d/%m/%Y %H:%M:%S"),
            "peca": peca_info,
            "maquina": maquina_nome,
            "qtd_apontada": data.pecas_ordem_estamparia.qtd_boa,
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


def get_itens_reinspecao_estamparia(request):
    if request.method != "GET":
        return JsonResponse({"error": "Método não permitido"}, status=405)

    # Otimização 1: Usar exists() em vez de values_list para verificar reinspeções
    reinspecao_ids = Reinspecao.objects.filter(reinspecionado=False).values_list(
        "inspecao_id", flat=True
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
    pagina = int(request.GET.get("pagina", 1))
    itens_por_pagina = 6

    # Otimização 2: Construir a query de forma incremental
    query = Q(id__in=reinspecao_ids) & Q(pecas_ordem_estamparia__isnull=False)

    if maquinas_filtradas:
        query &= Q(pecas_ordem_estamparia__ordem__maquina__nome__in=maquinas_filtradas)

    if data_filtrada:
        try:
            data_filtrada_date = datetime.strptime(data_filtrada, "%Y-%m-%d").date()
            query &= Q(dadosexecucaoinspecao__data_execucao__date=data_filtrada_date)
        except ValueError:
            pass  # Data inválida, ignora o filtro ou trate como preferir

    if pesquisa_filtrada:
        pesquisa_filtrada = pesquisa_filtrada.lower()
        query &= Q(pecas_ordem_estamparia__peca__icontains=pesquisa_filtrada)

    if inspetores_filtrados:
        query &= Q(
            dadosexecucaoinspecao__inspetor__user__username__in=inspetores_filtrados
        )

    # Otimização 3: Selecionar apenas os campos necessários e pré-carregar relacionamentos
    datas = (
        Inspecao.objects.filter(query)
        .select_related(
            "pecas_ordem_estamparia",
            "pecas_ordem_estamparia__ordem",
            "pecas_ordem_estamparia__ordem__maquina",
            "pecas_ordem_estamparia__peca",
        )
        .prefetch_related(
            "dadosexecucaoinspecao_set",
            "dadosexecucaoinspecao_set__inspetor",
            "dadosexecucaoinspecao_set__inspetor__user",
        )
        .order_by("-id")
    ).distinct()

    quantidade_total = Inspecao.objects.filter(
        id__in=reinspecao_ids, pecas_ordem_estamparia__isnull=False
    ).count()

    # Paginação
    paginador = Paginator(datas, itens_por_pagina)
    pagina_obj = paginador.get_page(pagina)

    conformidades_dict = {
        item["inspecao_id"]: item["total_conformidade"]
        for item in DadosExecucaoInspecao.objects.filter(
            inspecao_id__in=[inspecao.id for inspecao in pagina_obj]
        )
        .values("inspecao_id")
        .annotate(total_conformidade=Sum("conformidade"))
    }

    # Otimização 4: Reduzir consultas no loop usando prefetch_related e valores já carregados
    dados = []
    for data in pagina_obj:
        last_dados_execucao = data.dadosexecucaoinspecao_set.last()
        first_dados_execucao = data.dadosexecucaoinspecao_set.first()
        
        data_ajustada = DadosExecucaoInspecao.objects.filter(inspecao=data).values_list(
            "data_execucao", flat=True
        ).last() - timedelta(hours=3)

        try:
            info_adicionais = InfoAdicionaisInspecaoEstamparia.objects.get(
                dados_exec_inspecao=first_dados_execucao
            )
            qtd_mortas = info_adicionais.qtd_mortas if info_adicionais else 0
        except InfoAdicionaisInspecaoEstamparia.DoesNotExist:
            info_adicionais = None
            qtd_mortas = 0

        qtd_total = (
            data.pecas_ordem_estamparia.qtd_boa
            - conformidades_dict.get(data.id, 0)
            - qtd_mortas
        )

        # Se houver info adicionais, buscar nao conformidades destino sucata
        if info_adicionais:
            dados_nao_conformidade = DadosNaoConformidade.objects.filter(
                informacoes_adicionais_estamparia=info_adicionais, destino="sucata"
            )
            total_sucata = (
                dados_nao_conformidade.aggregate(total=Sum("qt_nao_conformidade"))[
                    "total"
                ]
                or 0
            )

            qtd_total -= total_sucata  # Subtrair as sucatas

        item = {
            "id": data.id,
            "data": data_ajustada.strftime(
                "%d/%m/%Y %H:%M:%S"
            ),
            "peca": f"{data.pecas_ordem_estamparia.peca.codigo} - {data.pecas_ordem_estamparia.peca.descricao}",
            "maquina": data.pecas_ordem_estamparia.ordem.maquina.nome if data.pecas_ordem_estamparia.ordem.maquina
            else "Não identificada",
            "conformidade": (
                last_dados_execucao.conformidade if last_dados_execucao else None
            ),
            "qtd_total": qtd_total,
            "nao_conformidade": (
                last_dados_execucao.nao_conformidade if last_dados_execucao else None
            ),
            "inspetor": (
                last_dados_execucao.inspetor.user.username
                if last_dados_execucao and last_dados_execucao.inspetor
                else None
            ),
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


def get_itens_inspecionados_estamparia(request):
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
    itens_por_pagina = 6  # Itens por página

    # Filtra os dados
    datas = Inspecao.objects.filter(
        id__in=inspecionados_ids, pecas_ordem_estamparia__isnull=False
    )

    quantidade_total = datas.count()  # Total de itens sem filtro

    if maquinas_filtradas:
        datas = datas.filter(
            pecas_ordem_estamparia__ordem__maquina__nome__in=maquinas_filtradas
        )

    if data_filtrada:
        datas = (
            datas.annotate(
                ultima_data_execucao=Max("dadosexecucaoinspecao__data_execucao")
            )
            .filter(ultima_data_execucao__date=data_filtrada)
            .order_by("-ultima_data_execucao")
        )

    if pesquisa_filtrada:
        datas = datas.annotate(
            codigo_descricao=Concat(
                "pecas_ordem_estamparia__peca__codigo",
                Value(" - "),
                "pecas_ordem_estamparia__peca__descricao",
            )
        ).filter(codigo_descricao__icontains=pesquisa_filtrada)

    if inspetores_filtrados:
        datas = datas.filter(
            dadosexecucaoinspecao__inspetor__user__username__in=inspetores_filtrados
        )

    datas = datas.select_related(
        "pecas_ordem_estamparia",
        "pecas_ordem_estamparia__ordem",
        "pecas_ordem_estamparia__operador",
    ).order_by("-id")

    # Paginação
    paginador = Paginator(datas, itens_por_pagina)
    pagina_obj = paginador.get_page(pagina)

    dados_execucao = DadosExecucaoInspecao.objects.filter(
        inspecao__in=pagina_obj
    ).select_related(
        "inspecao", "inspetor__user", "inspecao__pecas_ordem_estamparia__ordem__maquina"
    )

    # Cria um dicionário para mapear inspecao_id para seus dados de execução
    dados_execucao_dict = {de.inspecao_id: de for de in dados_execucao}

    print(dados_execucao_dict)

    dados = []
    for data in pagina_obj:
        de = dados_execucao_dict.get(data.id)

        if de:
            data_ajustada = DadosExecucaoInspecao.objects.filter(
                inspecao=data
            ).values_list("data_execucao", flat=True).last() - timedelta(hours=3)

            possui_nao_conformidade = de.nao_conformidade > 0 or de.num_execucao > 0

            item = {
                "id": data.id,
                "id_dados_execucao": de.id,
                "data": data_ajustada.strftime("%d/%m/%Y %H:%M:%S"),
                "peca": f"{data.pecas_ordem_estamparia.peca.codigo} - {data.pecas_ordem_estamparia.peca.descricao}",
                "maquina": data.pecas_ordem_estamparia.ordem.maquina.nome if data.pecas_ordem_estamparia.ordem.maquina
                else "Não identificada",
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


def get_historico_estamparia(request, id):
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

    print(list_history)

    return JsonResponse({"history": list_history}, status=200)


def get_historico_causas_estamparia(request, id):
    if request.method != "GET":
        return JsonResponse({"error": "Método não permitido"}, status=405)

    try:
        dados_nao_conformidades = DadosNaoConformidade.objects.filter(
            informacoes_adicionais_estamparia__dados_exec_inspecao__id=id
        ).prefetch_related("causas", "imagens")

        causas_dict = defaultdict(
            lambda: {
                "id_nc": None,
                "nomes": [],
                "destino": None,
                "quantidade": None,
                "imagens": [],
            }
        )

        for dados in dados_nao_conformidades:
            if causas_dict[dados.id]["id_nc"] is None:
                causas_dict[dados.id]["id_nc"] = dados.id
                causas_dict[dados.id]["destino"] = dados.destino
                causas_dict[dados.id]["quantidade"] = dados.qt_nao_conformidade
                causas_dict[dados.id]["imagens"] = [
                    {"id": imagem.id, "url": imagem.imagem.url}
                    for imagem in dados.imagens.all()
                ]
            causas_dict[dados.id]["nomes"].extend(
                [causa.nome for causa in dados.causas.all()]
            )

        causas_list = list(causas_dict.values())

        return JsonResponse({"causas": causas_list}, status=200)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


def envio_reinspecao_estamparia(request):
    if request.method != "POST":
        return JsonResponse({"error": "Método não permitido!"}, status=405)

    try:
        with transaction.atomic():
            print(request.POST)
            print(request.FILES)
            id_inspecao = request.POST.get("idInspecao")
            id_execucao = request.POST.get("execucaoId")
            data_inspecao = request.POST.get("dataReinspecao")
            maquina = request.POST.get("maquinaReinspecao")
            pecas = request.POST.get("pecasProduzidasReinspecao")
            inspetor_id = request.POST.get("inspetorReinspecao")
            conformidade = request.POST.get("qtdConformidadeReinspecao")
            nao_conformidade = request.POST.get("qtdNaoConformidadeReinspecao")
            ficha_reinspecao = request.FILES.get("ficha_reinspecao")

            data_convertida = timezone.make_aware(datetime.fromisoformat(data_inspecao))

            inspecao = Inspecao.objects.get(id=id_inspecao)
            inspetor = Profile.objects.get(id=inspetor_id)

            # Criação do registro de execução
            dados_execucao = DadosExecucaoInspecao.objects.create(
                inspecao=inspecao,
                inspetor=inspetor,
                data_execucao=data_convertida,
                conformidade=int(conformidade),
                nao_conformidade=int(nao_conformidade),
            )

            # Criação das informações adicionais
            info_adicionais = InfoAdicionaisInspecaoEstamparia.objects.create(
                dados_exec_inspecao=dados_execucao,
                inspecao_completa=True,
                ficha=ficha_reinspecao,
            )

            if int(nao_conformidade) > 0:
                quantidade_total_causas = int(
                    request.POST.get("quantidade_total_causas", 0)
                )

                for i in range(1, quantidade_total_causas + 1):
                    causas_ids = request.POST.getlist(f"causas_reinspecao_{i}")
                    quantidade_afetada = request.POST.get(f"quantidade_reinspecao_{i}")
                    imagens = request.FILES.getlist(f"imagens_reinspecao_{i}")

                    # Criar o objeto principal da não conformidade
                    dados_nao_conformidade = DadosNaoConformidade.objects.create(
                        informacoes_adicionais_estamparia=info_adicionais,
                        qt_nao_conformidade=int(quantidade_afetada),
                        destino="Reinspeção",  # Aqui você pode ajustar o destino conforme o seu fluxo
                    )

                    # Relacionar as causas
                    if causas_ids:
                        dados_nao_conformidade.causas.set(causas_ids)

                    # Salvar as imagens relacionadas
                    for imagem in imagens:
                        ImagemNaoConformidade.objects.create(
                            nao_conformidade=dados_nao_conformidade,
                            imagem=imagem,
                        )
            else:
                reinspecao = Reinspecao.objects.filter(inspecao=inspecao).first()
                if reinspecao:
                    reinspecao.reinspecionado = True
                    reinspecao.save()

        return JsonResponse({"success": True})

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


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

    user_profile = Profile.objects.filter(user=request.user).first()
    if user_profile and user_profile.tipo_acesso == "inspetor" and user_profile.permissoes.filter(nome="inspecao/tanque").exists():
        inspetor_logado = {
            "nome_usuario": request.user.username,
            "id": request.user.id
        }
    else:
        inspetor_logado = None

    return render(
        request,
        "inspecao_tanque.html",
        {"tanques": dict_tanques, "inspetores": lista_inspetores, 
         "inspetor_logado":inspetor_logado},
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
    if user_profile and user_profile.tipo_acesso == "inspetor" and user_profile.permissoes.filter(nome="inspecao/tubos-cilindros").exists():
        inspetor_logado = {
            "nome_usuario": request.user.username,
            "id": request.user.id
        }
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
            "inspetor_logado":inspetor_logado
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
        datas = datas.filter(dadosexecucaoinspecaoestanqueidade__data_exec__date=data_filtrada).distinct()

    if pesquisa_filtrada:
        if " - " in pesquisa_filtrada:
            codigo, descricao = pesquisa_filtrada.split(" - ", 1)
            codigo = codigo.strip()
            descricao = descricao.strip()
            datas = datas.filter(
                Q(peca__codigo__icontains=codigo)
                & Q(peca__descricao__icontains=descricao)
            ).distinct()
        else:
            datas = datas.filter(
                Q(peca__codigo__icontains=pesquisa_filtrada)
                | Q(peca__descricao__icontains=pesquisa_filtrada)
            ).distinct()

    if inspetores_filtrados:
        datas = datas.filter(
            dadosexecucaoinspecaoestanqueidade__inspetor__user__username__in=inspetores_filtrados
        ).distinct()

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
        datas = datas.filter(dadosexecucaoinspecaoestanqueidade__data_exec__date=data_filtrada).distinct()

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
                    "data_execucao": (dado.data_exec - timedelta(hours=3)).strftime("%d/%m/%Y %H:%M:%S"),
                    "num_execucao": dado.num_execucao,
                    "inspetor": dado.inspetor.user.username if dado.inspetor else None,
                    "pressao_inicial": detalhes_pressao.pressao_inicial,
                    "pressao_final": detalhes_pressao.pressao_final,
                    "nao_conformidade": detalhes_pressao.nao_conformidade,
                    "tipo_teste": detalhes_pressao.tipo_teste,
                    "tempo_execucao": detalhes_pressao.tempo_execucao.strftime("%H:%M:%S") if detalhes_pressao.tempo_execucao else None,
                }
            )

    return JsonResponse({"history": list_history}, status=200)


def delete_execution(request):

    if request.method != "DELETE":
        return JsonResponse({"error": "Método não permitido"}, status=405)

    try:
        with transaction.atomic():
            id_execucao = request.GET.get("idDadosExecucao")
            id_inspecao = request.GET.get("idInspecao")
            primeira_execucao = request.GET.get("primeiraExecucao")

            execucao = DadosExecucaoInspecao.objects.get(pk=id_execucao)
            reinspecao = Reinspecao.objects.filter(inspecao=id_inspecao).first()

            execucao.delete()

            if primeira_execucao == "true" and reinspecao:
                reinspecao.delete()
            elif reinspecao:
                reinspecao.reinspecionado = False
                reinspecao.save()

        return JsonResponse(
            {"success": True, "message": "Execução deletada com sucesso"}
        )

    except DadosExecucaoInspecao.DoesNotExist:
        return JsonResponse({"error": "Execução não encontrada"}, status=404)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def delete_execution_estanqueidade(request):

    if request.method != "DELETE":
        return JsonResponse({"error": "Método não permitido"}, status=405)

    try:
        with transaction.atomic():
            id_execucao = request.GET.get("idDadosExecucao")
            id_inspecao = request.GET.get("idInspecao")
            primeira_execucao = request.GET.get("primeiraExecucao")

            execucao = DadosExecucaoInspecao.objects.get(pk=id_execucao)
            reinspecao = Reinspecao.objects.filter(inspecao=id_inspecao).first()

            execucao.delete()

            if primeira_execucao == "true" and reinspecao:
                reinspecao.delete()
            elif reinspecao:
                reinspecao.reinspecionado = False
                reinspecao.save()

        return JsonResponse(
            {"success": True, "message": "Execução deletada com sucesso"}
        )

    except DadosExecucaoInspecao.DoesNotExist:
        return JsonResponse({"error": "Execução não encontrada"}, status=404)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

### Dashboard ###

def dashboard_pintura(request):

    return render(request, "dashboard/pintura.html")

### dashboard pintura ###

def indicador_pintura_analise_temporal(request):
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')

    try:
        if data_inicio:
            data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d')
        if data_fim:
            data_fim = datetime.strptime(data_fim, '%Y-%m-%d') + timedelta(days=1)
    except ValueError:
        return JsonResponse({'erro': 'Formato de data inválido. Use YYYY-MM-DD.'}, status=400)

    sql = """
    SELECT
        TO_CHAR(i.data_inspecao, 'YYYY-MM') AS mes,
        SUM(pop.qtd_boa) AS qtd_peca_produzida,
        SUM(COALESCE(de.conformidade, 0) + COALESCE(de.nao_conformidade, 0)) AS qtd_peca_inspecionada,
        SUM(COALESCE(de.conformidade, 0)) AS soma_conformidade,
        SUM(COALESCE(de.nao_conformidade, 0)) AS soma_nao_conformidade
    FROM apontamento_v2.inspecao_inspecao i
    JOIN apontamento_v2.apontamento_pintura_pecasordem pop ON i.pecas_ordem_pintura_id = pop.id
    LEFT JOIN apontamento_v2.inspecao_dadosexecucaoinspecao de ON de.inspecao_id = i.id
    WHERE i.pecas_ordem_pintura_id IS NOT NULL
    AND i.data_inspecao >= %(data_inicio)s
    AND i.data_inspecao < %(data_fim)s
    GROUP BY mes
    ORDER BY mes;
    """

    with connection.cursor() as cursor:
        cursor.execute(sql, {
            'data_inicio': data_inicio,
            'data_fim': data_fim,
        })
        rows = cursor.fetchall()

    resultado = []
    for row in rows:
        mes, qtd_produzida, qtd_inspecionada, soma_conformidade, soma_nao_conformidade = row
        taxa_nc = (soma_nao_conformidade / soma_conformidade) if soma_conformidade else 0

        resultado.append({
            'mes': mes,
            'qtd_peca_produzida': qtd_produzida or 0,
            'qtd_peca_inspecionada': qtd_inspecionada or 0,
            'taxa_nao_conformidade': round(taxa_nc, 4),
        })

    return JsonResponse(resultado, safe=False)

def indicador_pintura_resumo_analise_temporal(request):
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')

    try:
        if data_inicio:
            data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d')
        if data_fim:
            data_fim = datetime.strptime(data_fim, '%Y-%m-%d') + timedelta(days=1)
    except ValueError:
        return JsonResponse({'erro': 'Formato de data inválido. Use YYYY-MM-DD.'}, status=400)

    sql = """
    SELECT
        EXTRACT(YEAR FROM i.data_inspecao) AS ano,
        EXTRACT(MONTH FROM i.data_inspecao) AS mes_num,
        SUM(pop.qtd_boa) AS total_produzida,
        SUM(COALESCE(de.conformidade, 0) + COALESCE(de.nao_conformidade, 0)) AS total_inspecionada,
        SUM(COALESCE(de.nao_conformidade, 0)) AS total_nao_conforme
    FROM apontamento_v2.inspecao_inspecao i
    JOIN apontamento_v2.apontamento_pintura_pecasordem pop ON i.pecas_ordem_pintura_id = pop.id
    LEFT JOIN apontamento_v2.inspecao_dadosexecucaoinspecao de ON de.inspecao_id = i.id
    WHERE i.pecas_ordem_pintura_id IS NOT NULL
    AND i.data_inspecao >= %(data_inicio)s
    AND i.data_inspecao < %(data_fim)s
    GROUP BY ano, mes_num
    ORDER BY ano, mes_num;
    """

    with connection.cursor() as cursor:
        cursor.execute(sql, {
            'data_inicio': data_inicio,
            'data_fim': data_fim,
        })
        rows = cursor.fetchall()

    resultado = []
    for row in rows:
        ano, mes_num, total_prod, total_insp, total_nc = row
        perc_insp = (total_insp / total_prod) * 100 if total_prod else 0

        resultado.append({
            "Data": f"{int(ano)}-{int(mes_num):02}",
            "N° de peças produzidas": int(total_prod or 0),
            "N° de inspeções": int(total_insp or 0),
            "N° de não conformidades": int(total_nc or 0),
            "% de inspeção": f"{perc_insp:.2f} %"
        })

    return JsonResponse(resultado, safe=False)

def causas_nao_conformidade_mensal(request):
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')

    try:
        if data_inicio:
            data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d')
        if data_fim:
            data_fim = datetime.strptime(data_fim, '%Y-%m-%d') + timedelta(days=1)
    except ValueError:
        return JsonResponse({'erro': 'Formato de data inválido. Use YYYY-MM-DD.'}, status=400)

    sql = """
    SELECT
        TO_CHAR(i.data_inspecao, 'YYYY-MM') AS mes,
        c.nome AS causa,
        SUM(cnc.quantidade) AS total_nao_conformidades
    FROM apontamento_v2.inspecao_causasnaoconformidade cnc
    JOIN apontamento_v2.inspecao_dadosexecucaoinspecao de ON cnc.dados_execucao_id = de.id
    JOIN apontamento_v2.inspecao_inspecao i ON de.inspecao_id = i.id
    JOIN apontamento_v2.inspecao_causasnaoconformidade_causa cnc_c ON cnc.id = cnc_c.causasnaoconformidade_id
    JOIN apontamento_v2.inspecao_causas c ON c.id = cnc_c.causas_id 
    WHERE i.data_inspecao IS NOT NULL
    AND i.pecas_ordem_pintura_id IS NOT NULL
    AND i.data_inspecao >= %(data_inicio)s
    AND i.data_inspecao < %(data_fim)s
    GROUP BY mes, c.nome
    ORDER BY mes ASC, c.nome ASC;
    """

    with connection.cursor() as cursor:
        cursor.execute(sql, {
            'data_inicio': data_inicio,
            'data_fim': data_fim,
        })
        rows = cursor.fetchall()

    resultado = [
        {
            "Data": row[0],
            "Causa": row[1],
            "Soma do N° Total de não conformidades": row[2]
        }
        for row in rows
    ]

    return JsonResponse(resultado, safe=False)

def imagens_nao_conformidade_pintura(request):
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')

    try:
        if data_inicio:
            data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d')
        if data_fim:
            data_fim = datetime.strptime(data_fim, '%Y-%m-%d') + timedelta(days=1)
    except ValueError:
        return JsonResponse({'erro': 'Formato de data inválido. Use YYYY-MM-DD.'}, status=400)

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
        cursor.execute(sql, {
            'data_inicio': data_inicio,
            'data_fim': data_fim,
        })
        rows = cursor.fetchall()

    resultado = []
    for data_execucao, quantidade, arquivo_url, causas in rows:
        resultado.append({
            "data_execucao": data_execucao.strftime('%Y-%m-%d %H:%M:%S'),
            "quantidade": quantidade,
            "arquivo_url": arquivo_url,
            "causas": causas
        })

    return JsonResponse(resultado, safe=False)

def causas_nao_conformidade_por_tipo(request):
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')

    try:
        if data_inicio:
            data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d')
        if data_fim:
            data_fim = datetime.strptime(data_fim, '%Y-%m-%d') + timedelta(days=1)
    except ValueError:
        return JsonResponse({'erro': 'Formato de data inválido. Use YYYY-MM-DD.'}, status=400)

    queryset = CausasNaoConformidade.objects.filter(
        dados_execucao__inspecao__data_inspecao__isnull=False,
        dados_execucao__inspecao__pecas_ordem_pintura__isnull=False  # filtra apenas pintura
    ).prefetch_related('causa', 'dados_execucao__inspecao__pecas_ordem_pintura')

    if data_inicio:
        queryset = queryset.filter(dados_execucao__inspecao__data_inspecao__gte=data_inicio)
    if data_fim:
        queryset = queryset.filter(dados_execucao__inspecao__data_inspecao__lte=data_fim)

    # Acumula resultados agrupados
    agrupado = defaultdict(int)

    for item in queryset:
        execucao = item.dados_execucao
        inspecao = execucao.inspecao
        peca = inspecao.pecas_ordem_pintura

        if not peca or not peca.tipo:
            continue

        mes = execucao.inspecao.data_inspecao.month
        ano = execucao.inspecao.data_inspecao.year
        mes_formatado = f"{ano}-{mes}"
        tipo_tinta = peca.tipo.upper()

        for causa in item.causa.all():
            chave = (mes_formatado, causa.nome, tipo_tinta)
            agrupado[chave] += item.quantidade

    # Monta JSON de saída
    resultado = [
        {
            "Data": data,
            "Causa": causa,
            "Tipo": tipo,
            "N° Total de não conformidades": total
        }
        for (data, causa, tipo), total in sorted(agrupado.items())
    ]

    return JsonResponse(resultado, safe=False)

### dashboard montagem ###

def dashboard_montagem(request):

    return render(request, "dashboard/montagem.html")

def indicador_montagem_analise_temporal(request):

    """
    select
        id.data_execucao as data_inspecao,
        id.conformidade,
        id.nao_conformidade,
        ii.data_inspecao as data_producao,
        ii.pecas_ordem_pintura_id,
        app.peca,
        app.tipo,
        app.qtd_boa,
        ic2.nome as nome_conformidade
    from apontamento_v2.inspecao_inspecao ii
    left join apontamento_v2.inspecao_dadosexecucaoinspecao id on ii.id = id.inspecao_id 
    left join apontamento_v2.apontamento_pintura_pecasordem app on app.id = ii.pecas_ordem_pintura_id
    left join apontamento_v2.inspecao_causasnaoconformidade ic on ic.dados_execucao_id = id.id
    left join apontamento_v2.inspecao_causasnaoconformidade_causa icc on icc.causasnaoconformidade_id = ic.id
    left join apontamento_v2.inspecao_causas ic2 on ic2.id = icc.causas_id 
    where ii.pecas_ordem_pintura_id notnull
    order by id.data_execucao desc;
    """

    # Recebe os parâmetros de data
    setor = request.GET.get('setor')
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')

    try:
        if data_inicio:
            data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d')
        if data_fim:
            data_fim = datetime.strptime(data_fim, '%Y-%m-%d') + timedelta(days=1)
    except ValueError:
        return JsonResponse({'erro': 'Formato de data inválido. Use YYYY-MM-DD.'}, status=400)

    # Filtra somente as produções com peça ligada (mesmo sem inspeção)
    queryset = Inspecao.objects.filter(
        pecas_ordem_montagem__isnull=False
    )

    if data_inicio:
        queryset = queryset.filter(data_inspecao__gte=data_inicio)
    if data_fim:
        queryset = queryset.filter(data_inspecao__lte=data_fim)

    queryset = queryset.annotate(
        mes=Cast(TruncMonth('data_inspecao'), output_field=CharField()),
        qtd_boa=F('pecas_ordem_montagem__qtd_boa'),
        conformidade=F('dadosexecucaoinspecao__conformidade'),
        nao_conformidade=F('dadosexecucaoinspecao__nao_conformidade'),
    ).values('mes').annotate(
        qtd_peca_produzida=Sum('qtd_boa'),
        qtd_peca_inspecionada=Sum(
            ExpressionWrapper(
                F('conformidade') + F('nao_conformidade'),
                output_field=FloatField()
            )
        ) / 2.5,
        soma_conformidade=Sum('conformidade'),
        soma_nao_conformidade=Sum('nao_conformidade'),
    ).order_by('mes')

    resultado = []
    for item in queryset:
        conformidade = item['soma_conformidade'] or 0
        nao_conformidade = item['soma_nao_conformidade'] or 0
        taxa_nc = (nao_conformidade / conformidade) if conformidade else 0

        resultado.append({
            'mes': item['mes'][:7],  # YYYY-MM
            'qtd_peca_produzida': int(item['qtd_peca_produzida']) or 0,
            'qtd_peca_inspecionada': int(item['qtd_peca_inspecionada']) or 0,
            'taxa_nao_conformidade': round(taxa_nc, 4),
        })

    return JsonResponse(resultado, safe=False)

def indicador_montagem_resumo_analise_temporal(request):
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')

    try:
        if data_inicio:
            data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d')
        if data_fim:
            data_fim = datetime.strptime(data_fim, '%Y-%m-%d') + timedelta(days=1)
    except ValueError:
        return JsonResponse({'erro': 'Formato de data inválido. Use YYYY-MM-DD.'}, status=400)

    # Query principal
    queryset = Inspecao.objects.filter(
        pecas_ordem_montagem__isnull=False
    )

    if data_inicio:
        queryset = queryset.filter(data_inspecao__gte=data_inicio)
    if data_fim:
        queryset = queryset.filter(data_inspecao__lte=data_fim)

    # Anotações e agregações
    queryset = queryset.annotate(
        ano=ExtractYear('data_inspecao'),
        mes_num=ExtractMonth('data_inspecao'),
        qtd_boa=F('pecas_ordem_montagem__qtd_boa'),
        conformidade=F('dadosexecucaoinspecao__conformidade'),
        nao_conformidade=F('dadosexecucaoinspecao__nao_conformidade'),
        qtd_inspecionada=ExpressionWrapper(
            F('dadosexecucaoinspecao__conformidade') + F('dadosexecucaoinspecao__nao_conformidade'),
            output_field=FloatField()
        )
    ).values('ano', 'mes_num').annotate(
        total_produzida=Sum('qtd_boa'),
        total_inspecionada=Sum('qtd_inspecionada') / 2.5,
        total_nao_conforme=Sum('nao_conformidade'),
    ).order_by('ano', 'mes_num')

    # Monta JSON
    resultado = []
    for item in queryset:
        mes_formatado = f"{item['ano']}-{item['mes_num']}"

        total_prod = item['total_produzida'] or 0
        total_insp = item['total_inspecionada'] or 0
        total_nc = item['total_nao_conforme'] or 0

        perc_insp = (total_insp / total_prod) * 100 if total_prod else 0

        resultado.append({
            "Data": mes_formatado,
            "N° de peças produzidas": int(total_prod),
            "N° de inspeções": int(total_insp),
            "N° de não conformidades": int(total_nc),
            "% de inspeção": f"{perc_insp:.2f} %"
        })

    return JsonResponse(resultado, safe=False)

def causas_nao_conformidade_mensal_montagem(request):
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')

    try:
        if data_inicio:
            data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d')
        if data_fim:
            data_fim = datetime.strptime(data_fim, '%Y-%m-%d') + timedelta(days=1)
    except ValueError:
        return JsonResponse({'erro': 'Formato de data inválido. Use YYYY-MM-DD.'}, status=400)

    queryset = CausasNaoConformidade.objects.filter(
        dados_execucao__inspecao__data_inspecao__isnull=False,
        dados_execucao__inspecao__pecas_ordem_montagem__isnull=False
    ).prefetch_related('causa')

    if data_inicio:
        queryset = queryset.filter(dados_execucao__inspecao__data_inspecao__gte=data_inicio)
    if data_fim:
        queryset = queryset.filter(dados_execucao__inspecao__data_inspecao__lte=data_fim)

    # Estrutura para agrupar manualmente por mês e causa
    resultado_temp = {}
    for item in queryset:
        ano = item.dados_execucao.inspecao.data_inspecao.year
        mes = item.dados_execucao.inspecao.data_inspecao.month
        mes_formatado = f"{ano}-{mes}"

        for causa in item.causa.all():
            chave = (mes_formatado, causa.nome)
            if chave not in resultado_temp:
                resultado_temp[chave] = 0
            resultado_temp[chave] += item.quantidade

    # Formata para JSON
    resultado = [
        {
            "Data": chave[0],
            "Causa": chave[1],
            "Soma do N° Total de não conformidades": total
        }
        for chave, total in sorted(resultado_temp.items())
    ]

    return JsonResponse(resultado, safe=False)

def imagens_nao_conformidade_montagem(request):
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')

    try:
        if data_inicio:
            data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d')
        if data_fim:
            data_fim = datetime.strptime(data_fim, '%Y-%m-%d') + timedelta(days=1)
    except ValueError:
        return JsonResponse({'erro': 'Formato de data inválido. Use YYYY-MM-DD.'}, status=400)

    queryset = CausasNaoConformidade.objects.filter(
        dados_execucao__data_execucao__isnull=False,
        dados_execucao__inspecao__pecas_ordem_montagem__isnull=False  # filtro para montagem
    ).prefetch_related('causa', 'arquivos')

    if data_inicio:
        queryset = queryset.filter(dados_execucao__data_execucao__gte=data_inicio)
    if data_fim:
        queryset = queryset.filter(dados_execucao__data_execucao__lte=data_fim)

    resultado = []
    for item in queryset:
        date = item.dados_execucao.data_execucao - timedelta(hours=3)
        data_execucao = date.strftime('%Y-%m-%d %H:%M:%S')
        causas = [c.nome for c in item.causa.all()]
        arquivos = [arquivo.arquivo.url for arquivo in item.arquivos.all() if arquivo.arquivo]

        for url in arquivos:
            resultado.append({
                "data_execucao": data_execucao,
                "causas": causas,
                "quantidade": item.quantidade,
                "arquivo_url": url
            })

    return JsonResponse(resultado, safe=False)

### dashboard estamparia ###

def dashboard_estamparia(request):

    return render(request, "dashboard/estamparia.html")

def indicador_estamparia_analise_temporal(request):

    """
    select
        id.data_execucao as data_inspecao,
        id.conformidade,
        id.nao_conformidade,
        ii.data_inspecao as data_producao,
        ii.pecas_ordem_pintura_id,
        app.peca,
        app.tipo,
        app.qtd_boa,
        ic2.nome as nome_conformidade
    from apontamento_v2.inspecao_inspecao ii
    left join apontamento_v2.inspecao_dadosexecucaoinspecao id on ii.id = id.inspecao_id 
    left join apontamento_v2.apontamento_pintura_pecasordem app on app.id = ii.pecas_ordem_pintura_id
    left join apontamento_v2.inspecao_causasnaoconformidade ic on ic.dados_execucao_id = id.id
    left join apontamento_v2.inspecao_causasnaoconformidade_causa icc on icc.causasnaoconformidade_id = ic.id
    left join apontamento_v2.inspecao_causas ic2 on ic2.id = icc.causas_id 
    where ii.pecas_ordem_pintura_id notnull
    order by id.data_execucao desc;
    """

    # Recebe os parâmetros de data
    setor = request.GET.get('setor')
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')

    try:
        if data_inicio:
            data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d')
        if data_fim:
            data_fim = datetime.strptime(data_fim, '%Y-%m-%d') + timedelta(days=1)
    except ValueError:
        return JsonResponse({'erro': 'Formato de data inválido. Use YYYY-MM-DD.'}, status=400)

    # Filtra somente as produções com peça ligada (mesmo sem inspeção)
    queryset = Inspecao.objects.filter(
        pecas_ordem_estamparia__isnull=False
    )

    if data_inicio:
        queryset = queryset.filter(data_inspecao__gte=data_inicio)
    if data_fim:
        queryset = queryset.filter(data_inspecao__lte=data_fim)

    queryset = queryset.annotate(
        mes=Cast(TruncMonth('data_inspecao'), output_field=CharField()),
        qtd_boa=F('pecas_ordem_estamparia__qtd_boa'),
        conformidade=F('dadosexecucaoinspecao__conformidade'),
        nao_conformidade=F('dadosexecucaoinspecao__nao_conformidade'),
    ).values('mes').annotate(
        qtd_peca_produzida=Count('id'),
        qtd_peca_inspecionada=Count('dadosexecucaoinspecao__id'),
        soma_conformidade=Sum('conformidade'),
        soma_nao_conformidade=Sum('nao_conformidade'),
    ).order_by('mes')

    resultado = []
    for item in queryset:
        conformidade = item['soma_conformidade'] or 0
        nao_conformidade = item['soma_nao_conformidade'] or 0
        taxa_nc = (nao_conformidade / conformidade) if conformidade else 0

        resultado.append({
            'mes': item['mes'][:7],  # YYYY-MM
            'qtd_peca_produzida': item['qtd_peca_produzida'] or 0,
            'qtd_peca_inspecionada': item['qtd_peca_inspecionada'] or 0,
            'taxa_nao_conformidade': round(taxa_nc, 4),
        })

    return JsonResponse(resultado, safe=False)

def indicador_estamparia_resumo_analise_temporal(request):
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')

    try:
        if data_inicio:
            data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d')
        if data_fim:
            data_fim = datetime.strptime(data_fim, '%Y-%m-%d') + timedelta(days=1)
    except ValueError:
        return JsonResponse({'erro': 'Formato de data inválido. Use YYYY-MM-DD.'}, status=400)

    # Query principal
    queryset = Inspecao.objects.filter(
        pecas_ordem_estamparia__isnull=False
    )

    if data_inicio:
        queryset = queryset.filter(data_inspecao__gte=data_inicio)
    if data_fim:
        queryset = queryset.filter(data_inspecao__lte=data_fim)

    # Anotações e agregações
    queryset = queryset.annotate(
        ano=ExtractYear('data_inspecao'),
        mes_num=ExtractMonth('data_inspecao'),
        qtd_boa=F('pecas_ordem_estamparia__qtd_boa'),
        conformidade=F('dadosexecucaoinspecao__conformidade'),
        nao_conformidade=F('dadosexecucaoinspecao__nao_conformidade'),
        qtd_inspecionada=ExpressionWrapper(
            F('dadosexecucaoinspecao__conformidade') + F('dadosexecucaoinspecao__nao_conformidade'),
            output_field=FloatField()
        )
    ).values('ano', 'mes_num').annotate(
        total_produzida=Count('id'),
        total_inspecionada=Count('dadosexecucaoinspecao__id'),
        total_nao_conforme=Count(
            'dadosexecucaoinspecao__id',
            filter=Q(nao_conformidade__gt=0)
        ),
    ).order_by('ano', 'mes_num')

    # Monta JSON
    resultado = []
    for item in queryset:
        mes_formatado = f"{item['ano']}-{item['mes_num']}"

        total_prod = item['total_produzida'] or 0
        total_insp = item['total_inspecionada'] or 0
        total_nc = item['total_nao_conforme'] or 0

        perc_insp = (total_insp / total_prod) * 100 if total_prod else 0

        resultado.append({
            "Data": mes_formatado,
            "N° de peças produzidas": int(total_prod),
            "N° de inspeções": int(total_insp),
            "N° de não conformidades": int(total_nc),
            "% de inspeção": f"{perc_insp:.2f} %"
        })

    return JsonResponse(resultado, safe=False)

def causas_nao_conformidade_mensal_estamparia(request):
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')

    try:
        if data_inicio:
            data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d')
        if data_fim:
            data_fim = datetime.strptime(data_fim, '%Y-%m-%d') + timedelta(days=1)
    except ValueError:
        return JsonResponse({'erro': 'Formato de data inválido. Use YYYY-MM-DD.'}, status=400)

    queryset = DadosNaoConformidade.objects.filter(
        informacoes_adicionais_estamparia__dados_exec_inspecao__inspecao__data_inspecao__isnull=False,
        informacoes_adicionais_estamparia__dados_exec_inspecao__inspecao__pecas_ordem_estamparia__isnull=False,
        causas__isnull=False  # Filtra registros sem causa antes da agregação
    )
    
    if data_inicio:
        queryset = queryset.filter(informacoes_adicionais_estamparia__dados_exec_inspecao__inspecao__data_inspecao__gte=data_inicio)
    if data_fim:
        queryset = queryset.filter(informacoes_adicionais_estamparia__dados_exec_inspecao__inspecao__data_inspecao__lte=data_fim)
    
    resultados = queryset.annotate(
        ano=ExtractYear('informacoes_adicionais_estamparia__dados_exec_inspecao__inspecao__data_inspecao'),
        mes=ExtractMonth('informacoes_adicionais_estamparia__dados_exec_inspecao__inspecao__data_inspecao'),
        mes_formatado=Concat(
            ExtractYear('informacoes_adicionais_estamparia__dados_exec_inspecao__inspecao__data_inspecao'),
            Value('-'),
            ExtractMonth('informacoes_adicionais_estamparia__dados_exec_inspecao__inspecao__data_inspecao'),
            output_field=CharField()
        )
    ).values('mes_formatado', 'causas__nome').annotate(
        total_nao_conformidades=Sum('qt_nao_conformidade')
    ).order_by('mes_formatado', 'causas__nome')

    # Formatação final
    resultado = [
        {
            "Data": item['mes_formatado'],
            "Causa": item['causas__nome'],
            "Soma do N° Total de não conformidades": item['total_nao_conformidades']
        }
        for item in resultados
    ]
    
    return JsonResponse(resultado, safe=False)

def imagens_nao_conformidade_estamparia(request):
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')

    try:
        if data_inicio:
            data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d')
        if data_fim:
            data_fim = datetime.strptime(data_fim, '%Y-%m-%d') + timedelta(days=1)
    except ValueError:
        return JsonResponse({'erro': 'Formato de data inválido. Use YYYY-MM-DD.'}, status=400)

    # Query otimizada com select_related e prefetch_related específicos
    queryset = DadosNaoConformidade.objects.filter(
        informacoes_adicionais_estamparia__dados_exec_inspecao__data_execucao__isnull=False,
        informacoes_adicionais_estamparia__dados_exec_inspecao__inspecao__pecas_ordem_estamparia__isnull=False
    ).select_related(
        'informacoes_adicionais_estamparia',
        'informacoes_adicionais_estamparia__dados_exec_inspecao'
    ).prefetch_related(
        Prefetch('causas', queryset=Causas.objects.only('nome')),
        Prefetch('imagens', queryset=ImagemNaoConformidade.objects.only('imagem'))
    ).only(
        'qt_nao_conformidade',
        'informacoes_adicionais_estamparia__dados_exec_inspecao__data_execucao'
    )

    if data_inicio:
        queryset = queryset.filter(informacoes_adicionais_estamparia__dados_exec_inspecao__data_execucao__gte=data_inicio)
    if data_fim:
        queryset = queryset.filter(informacoes_adicionais_estamparia__dados_exec_inspecao__data_execucao__lte=data_fim)

    # Pré-carrega todos os dados relacionados de uma vez
    dados_completos = list(queryset)

    resultado = []
    for item in dados_completos:
        date = item.informacoes_adicionais_estamparia.dados_exec_inspecao.data_execucao - timedelta(hours=3)
        data_execucao = date.strftime('%Y-%m-%d %H:%M:%S')
        
        # Acessa os dados já pré-carregados
        causas = [c.nome for c in item.causas.all()]
        imagens = [imagem.imagem.url for imagem in item.imagens.all() if hasattr(imagem, 'imagem')]

        for url in imagens:
            resultado.append({
                "data_execucao": data_execucao,
                "causas": causas,
                "quantidade": item.qt_nao_conformidade,
                "imagem_url": url
            })
            
    return JsonResponse(resultado, safe=False)

def ficha_inspecao_estamparia(request):
    
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    
    try:
        if data_inicio:
            data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d')
        if data_fim:
            # Adiciona 1 dia para incluir todo o dia especificado
            data_fim = datetime.strptime(data_fim, '%Y-%m-%d') + timedelta(days=1)
    except ValueError:
        return JsonResponse({'erro': 'Formato de data inválido. Use YYYY-MM-DD.'}, status=400)
    
    # Query base com joins e prefetch necessários
    queryset = InfoAdicionaisInspecaoEstamparia.objects.select_related(
        'dados_exec_inspecao'
    ).prefetch_related(
        'motivo_mortas'
    ).filter(
        dados_exec_inspecao__data_execucao__isnull=False,
        ficha__isnull=False  # Apenas registros com ficha
    )
    
    # Aplica filtros de data
    if data_inicio:
        queryset = queryset.filter(dados_exec_inspecao__data_execucao__gte=data_inicio)
    if data_fim:
        queryset = queryset.filter(dados_exec_inspecao__data_execucao__lt=data_fim)
    
    # Annotate com dados adicionais
    queryset = queryset.annotate(
        data_execucao=F('dados_exec_inspecao__data_execucao')
    )
    
    # Prepara os resultados
    resultados = []
    for item in queryset:
        if item.ficha:  # Garante que só retorne itens com ficha
            resultados.append({
                'data_execucao': item.data_execucao.strftime('%Y-%m-%d %H:%M:%S'),
                'inspecao_completa': item.inspecao_completa,
                'qtd_mortas': item.qtd_mortas,
                'motivos_mortas': [causa.nome for causa in item.motivo_mortas.all()],
                'ficha_url': request.build_absolute_uri(item.ficha.url)
                })
    
    return JsonResponse(resultados, safe=False)

### dashboard tanque ###

def dashboard_tanque(request):

    return render(request, "dashboard/tanque.html")

def indicador_tanque_analise_temporal(request):
    """
    Endpoint para análise temporal de inspeções de estanqueidade - APENAS TANQUES
    """
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')

    try:
        if data_inicio:
            data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d')
        if data_fim:
            data_fim = datetime.strptime(data_fim, '%Y-%m-%d') + timedelta(days=1)
    except ValueError:
        return JsonResponse({'erro': 'Formato de data inválido. Use YYYY-MM-DD.'}, status=400)

    # Filtra somente as inspeções de estanqueidade para tanques
    queryset = InspecaoEstanqueidade.objects.filter(peca__tipo='tanque')

    if data_inicio:
        queryset = queryset.filter(data_inspecao__gte=data_inicio)
    if data_fim:
        queryset = queryset.filter(data_inspecao__lte=data_fim)

    # Dados de pressão dos tanques
    tanques_pressao = DetalhesPressaoTanque.objects.filter(
        dados_exec_inspecao__inspecao_estanqueidade__in=queryset
    ).annotate(
        mes=Cast(TruncMonth('dados_exec_inspecao__data_exec'), output_field=CharField()),
        nc_calculada=Case(  # Mudei o nome da anotação para evitar conflito
            When(nao_conformidade=True, then=1),
            default=0,
            output_field=IntegerField()
        )
    ).values('mes').annotate(
        qtd_inspecionada=Count('id'),
        soma_nao_conformidade=Sum('nc_calculada')  # Usando o novo nome aqui
    ).order_by('mes')

    resultado = []
    for item in tanques_pressao:
        total_inspecionada = item['qtd_inspecionada'] or 0
        total_nc = item['soma_nao_conformidade'] or 0
        taxa_nc = (total_nc / total_inspecionada) if total_inspecionada else 0

        resultado.append({
            'mes': item['mes'][:7],  # YYYY-MM
            'qtd_peca_inspecionada': total_inspecionada,
            'taxa_nao_conformidade': round(taxa_nc, 4),
        })

    return JsonResponse(resultado, safe=False)

def indicador_tanque_resumo_analise_temporal(request):
    """
    Endpoint para resumo temporal de inspeções - APENAS TANQUES
    """
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')

    try:
        if data_inicio:
            data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d')
        if data_fim:
            data_fim = datetime.strptime(data_fim, '%Y-%m-%d') + timedelta(days=1)
    except ValueError:
        return JsonResponse({'erro': 'Formato de data inválido. Use YYYY-MM-DD.'}, status=400)

    # Query para tanques (pressão)
    tanques_pressao = DetalhesPressaoTanque.objects.filter(
        dados_exec_inspecao__inspecao_estanqueidade__peca__tipo='tanque',
        dados_exec_inspecao__data_exec__isnull=False
    )
    
    if data_inicio:
        tanques_pressao = tanques_pressao.filter(dados_exec_inspecao__data_exec__gte=data_inicio)
    if data_fim:
        tanques_pressao = tanques_pressao.filter(dados_exec_inspecao__data_exec__lte=data_fim)

    # Agregações
    tanques_agg = tanques_pressao.annotate(
        ano=ExtractYear('dados_exec_inspecao__data_exec'),
        mes_num=ExtractMonth('dados_exec_inspecao__data_exec'),
        nc=Case(
            When(nao_conformidade=True, then=1),
            default=0,
            output_field=IntegerField()
        )
    ).values('ano', 'mes_num').annotate(
        total_inspecionada=Count('id'),
        total_nc=Sum('nc')
    ).order_by('ano', 'mes_num')

    resultado = []
    for item in tanques_agg:
        mes_formatado = f"{item['ano']}-{item['mes_num']}"
        
        resultado.append({
            "Data": mes_formatado,
            "N° de inspeções": int(item['total_inspecionada']),
            "N° de não conformidades": int(item['total_nc'] or 0),
        })

    return JsonResponse(resultado, safe=False)

def causas_nao_conformidade_mensal_tanque(request):

    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')

    try:
        if data_inicio:
            data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d')
        if data_fim:
            data_fim = datetime.strptime(data_fim, '%Y-%m-%d') + timedelta(days=1)
    except ValueError:
        return JsonResponse({'erro': 'Formato de data inválido. Use YYYY-MM-DD.'}, status=400)

    # Filtra as não conformidades de tanques na primeira execução (num_execucao=0)
    nao_conformidades = DetalhesPressaoTanque.objects.filter(
        nao_conformidade=True,
        dados_exec_inspecao__inspecao_estanqueidade__peca__tipo='tanque'
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
    resultados = nao_conformidades.annotate(
        mes_formatado=Concat(
            ExtractYear('dados_exec_inspecao__data_exec'),
            Value('-'),
            ExtractMonth('dados_exec_inspecao__data_exec'),
            output_field=CharField()
        )
    ).values('mes_formatado').annotate(
        quantidade=Count('id')
    ).order_by('mes_formatado')

    # Formata a resposta conforme solicitado
    resposta = [
        {
            "data": item['mes_formatado'],
            "causa": "Vazamento",
            "quantidade": item['quantidade']
        }
        for item in resultados
    ]

    print(resposta)

    return JsonResponse(resposta, safe=False)


def dashboard_tubos_cilindros(request):

    return render(request, 'dashboard/tubos-cilindros.html')

def indicador_tubos_cilindros_analise_temporal(request):

    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')

    try:
        if data_inicio:
            data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d')
        if data_fim:
            data_fim = datetime.strptime(data_fim, '%Y-%m-%d') + timedelta(days=1)
    except ValueError:
        return JsonResponse({'erro': 'Formato de data inválido. Use YYYY-MM-DD.'}, status=400)

    # Filtra somente as produções com peça ligada e do tipo especificado
    queryset = InspecaoEstanqueidade.objects.filter(
        Q(peca__tipo='tubo') | Q(peca__tipo='cilindro')
    )

    if data_inicio:
        queryset = queryset.filter(data_inspecao__gte=data_inicio)
    if data_fim:
        queryset = queryset.filter(data_inspecao__lte=data_fim)

    queryset = queryset.annotate(
        mes=Cast(TruncMonth('data_inspecao'), output_field=CharField()),
        qtd_inspecionada=F('dadosexecucaoinspecaoestanqueidade__infoadicionaisexectuboscilindros__qtd_inspecionada'),
        nao_conformidade=F('dadosexecucaoinspecaoestanqueidade__infoadicionaisexectuboscilindros__nao_conformidade'),
    ).values('mes').annotate(
        soma_nao_conformidade=Sum('nao_conformidade'),
        soma_qtd_inspecionada=Sum('qtd_inspecionada'),
    ).order_by('mes')

    resultado = []
    for item in queryset:
        qtd_inspecionada = item['soma_qtd_inspecionada'] or 0
        nao_conformidade = item['soma_nao_conformidade'] or 0
        taxa_nc = (nao_conformidade / qtd_inspecionada) if qtd_inspecionada else 0

        resultado.append({
            'mes': item['mes'][:7],  # YYYY-MM
            'qtd_peca_inspecionada': item['soma_qtd_inspecionada'] or 0,
            'taxa_nao_conformidade': round(taxa_nc, 4),
        })

    return JsonResponse(resultado, safe=False)

def indicador_tubos_cilindros_resumo_analise_temporal(request):

    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')

    try:
        if data_inicio:
            data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d')
        if data_fim:
            data_fim = datetime.strptime(data_fim, '%Y-%m-%d') + timedelta(days=1)
    except ValueError:
        return JsonResponse({'erro': 'Formato de data inválido. Use YYYY-MM-DD.'}, status=400)

    # Query principal
    queryset = InspecaoEstanqueidade.objects.filter(
        Q(peca__tipo='tubo') | Q(peca__tipo='cilindro'),
        peca__isnull=False
    )

    print(queryset)
    print(len(queryset))

    if data_inicio:
        queryset = queryset.filter(data_inspecao__gte=data_inicio)
    if data_fim:
        queryset = queryset.filter(data_inspecao__lte=data_fim)

    # Anotações e agregações
    queryset = queryset.annotate(
        ano=ExtractYear('data_inspecao'),
        mes_num=ExtractMonth('data_inspecao'),
        qtd_inspecionada=F('dadosexecucaoinspecaoestanqueidade__infoadicionaisexectuboscilindros__qtd_inspecionada'),
        nao_conformidade=F('dadosexecucaoinspecaoestanqueidade__infoadicionaisexectuboscilindros__nao_conformidade'),
        nao_conformidade_refugo=F('dadosexecucaoinspecaoestanqueidade__infoadicionaisexectuboscilindros__nao_conformidade_refugo'),
    ).values('ano', 'mes_num').annotate(
        total_nc=Sum('nao_conformidade'),
        total_refugo=Sum('nao_conformidade_refugo'),
        total_nao_conforme=ExpressionWrapper(
            F('total_nc') + F('total_refugo'),
            output_field=IntegerField()
        ),
        total_qtd_inspecionada=Sum('qtd_inspecionada'),
    ).order_by('ano', 'mes_num')

    print(queryset)
    # Monta JSON
    resultado = []
    for item in queryset:

        mes_formatado = f"{item['ano']}-{item['mes_num']}"

        total_nc = item['total_nao_conforme'] or 0
        total_qtd_insp = item['total_qtd_inspecionada'] or 0

        taxa_nc = (total_nc / total_qtd_insp) * 100 if total_qtd_insp else 0

        resultado.append({
            "Data": mes_formatado,
            "N° de inspeções": int(total_qtd_insp),
            "N° de não conformidades": int(total_nc),
            "% de não conformidade": f"{taxa_nc:.2f} %"
        })


    return JsonResponse(resultado, safe=False)

def causas_nao_conformidade_mensal_tubos_cilindros(request):

    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')

    try:
        if data_inicio:
            data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d')
        if data_fim:
            data_fim = datetime.strptime(data_fim, '%Y-%m-%d') + timedelta(days=1)
    except ValueError:
        return JsonResponse({'erro': 'Formato de data inválido. Use YYYY-MM-DD.'}, status=400)

    queryset = CausasNaoConformidadeEstanqueidade.objects.filter(
        info_tubos_cilindros__dados_exec_inspecao__data_exec__isnull=False,
        info_tubos_cilindros__dados_exec_inspecao__inspecao_estanqueidade__peca__isnull=False,
        causa__isnull=False  # Filtra registros sem causa antes da agregação
    )
    
    if data_inicio:
        queryset = queryset.filter(info_tubos_cilindros__dados_exec_inspecao__data_exec__gte=data_inicio)
    if data_fim:
        queryset = queryset.filter(info_tubos_cilindros__dados_exec_inspecao__data_exec__lte=data_fim)
    
    resultados = queryset.annotate(
        ano=ExtractYear('info_tubos_cilindros__dados_exec_inspecao__data_exec'),
        mes=ExtractMonth('info_tubos_cilindros__dados_exec_inspecao__data_exec'),
        mes_formatado=Concat(
            ExtractYear('info_tubos_cilindros__dados_exec_inspecao__data_exec'),
            Value('-'),
            ExtractMonth('info_tubos_cilindros__dados_exec_inspecao__data_exec'),
            output_field=CharField()
        )
    ).values('mes_formatado', 'causa__nome').annotate(
        total_nao_conformidades=Sum('quantidade')
    ).order_by('mes_formatado', 'causa__nome')

    # Formatação final
    resultado = [
        {
            "Data": item['mes_formatado'],
            "Causa": item['causa__nome'],
            "Soma do N° Total de não conformidades": item['total_nao_conformidades']
        }
        for item in resultados
    ]
    
    return JsonResponse(resultado, safe=False)

def imagens_nao_conformidade_tubos_cilindros(request):

    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')

    try:
        if data_inicio:
            data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d')
        if data_fim:
            data_fim = datetime.strptime(data_fim, '%Y-%m-%d') + timedelta(days=1)
    except ValueError:
        return JsonResponse({'erro': 'Formato de data inválido. Use YYYY-MM-DD.'}, status=400)

    # Query otimizada com select_related e prefetch_related específicos
    queryset = CausasNaoConformidadeEstanqueidade.objects.filter(
        info_tubos_cilindros__dados_exec_inspecao__data_exec__isnull=False,
        info_tubos_cilindros__dados_exec_inspecao__inspecao_estanqueidade__peca__isnull=False
    ).select_related(
        'info_tubos_cilindros',
        'info_tubos_cilindros__dados_exec_inspecao',
        'info_tubos_cilindros__dados_exec_inspecao__inspecao_estanqueidade'
    ).prefetch_related(
        'causa',
        Prefetch('arquivos_estanqueidade', queryset=ArquivoCausaEstanqueidade.objects.only('arquivos'))
    )

    if data_inicio:
        queryset = queryset.filter(info_tubos_cilindros__dados_exec_inspecao__data_exec__gte=data_inicio)
    if data_fim:
        queryset = queryset.filter(info_tubos_cilindros__dados_exec_inspecao__data_exec__lte=data_fim)

    # Pré-carrega todos os dados relacionados de uma vez
    dados_completos = list(queryset)

    resultado = []
    for item in dados_completos:
        date = item.info_tubos_cilindros.dados_exec_inspecao.data_exec - timedelta(hours=3)
        data_execucao = date.strftime('%Y-%m-%d %H:%M:%S')
        
        # Acessa os dados já pré-carregados
        causas = [c.nome for c in item.causa.all()]
        imagens = [arquivo.arquivos.url for arquivo in item.arquivos_estanqueidade.all() if hasattr(arquivo, 'arquivos')]

        for url in imagens:
            resultado.append({
                "data_execucao": data_execucao,
                "causas": causas,
                "quantidade": item.quantidade,
                "imagem_url": url
            })
            
    return JsonResponse(resultado, safe=False)