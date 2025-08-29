from django.shortcuts import render
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import (
    Q,
    Sum,
)
from django.db import transaction
from django.utils import timezone
from django.db.models.functions import (
    TruncMonth,
)
from django.db import connection

from apontamento_montagem.models import ConjuntosInspecionados
from ..models import (
    Inspecao,
    DadosExecucaoInspecao,
    Reinspecao,
    Causas,
    CausasNaoConformidade,
    ArquivoCausa,
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

    list_causas = [{"id": causa.id, "nome": causa.nome} for causa in causas]

    lista_inspetores = [
        {"nome_usuario": user.user.username, "id": user.user.id} for user in users
    ]

    user_profile = Profile.objects.filter(user=request.user).first()
    if (
        user_profile
        and user_profile.tipo_acesso == "inspetor"
        and user_profile.permissoes.filter(nome="inspecao/montagem").exists()
    ):
        inspetor_logado = {"nome_usuario": request.user.username, "id": request.user.id}
    else:
        inspetor_logado = None

    return render(
        request,
        "inspecao_montagem.html",
        {
            "inspetor_logado": inspetor_logado,
            "inspetores": lista_inspetores,
            "causas": list_causas,
            "maquinas": maquinas,
        },
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

    # Mantém a lógica original: traz tanto montagem quanto tanque
    query = Q(id__in=reinspecao_ids) & (Q(pecas_ordem_montagem__isnull=False) | Q(estanqueidade__isnull=False))

    if maquinas_filtradas:
        query &= Q(pecas_ordem_montagem__ordem__maquina__nome__in=maquinas_filtradas)

    if data_filtrada:
        query &= Q(data_inspecao__date=data_filtrada)

    if pesquisa_filtrada:
        pesquisa_filtrada = pesquisa_filtrada.lower()
        # Pesquisa tanto em peças de montagem quanto em estanqueidades
        query &= (Q(pecas_ordem_montagem__peca__icontains=pesquisa_filtrada) | 
                 Q(estanqueidade__peca__codigo__icontains=pesquisa_filtrada) |
                 Q(estanqueidade__peca__descricao__icontains=pesquisa_filtrada))

    if inspetores_filtrados:
        query &= Q(
            dadosexecucaoinspecao__inspetor__user__username__in=inspetores_filtrados
        )

    # Otimização: Pré-carregamento de relacionamentos para ambos os casos
    datas = (
        Inspecao.objects.filter(query)
        .select_related(
            "pecas_ordem_montagem",
            "pecas_ordem_montagem__ordem",
            "pecas_ordem_montagem__ordem__maquina",
            "estanqueidade",
            "estanqueidade__peca",  # Adicionado para carregar relacionamento com peça do tanque
        )
        .prefetch_related(
            "dadosexecucaoinspecao_set",
            "dadosexecucaoinspecao_set__inspetor",
            "dadosexecucaoinspecao_set__inspetor__user",
        )
        .order_by("-id")
    ).distinct()

    quantidade_total = Inspecao.objects.filter(
        id__in=reinspecao_ids
    ).filter(
        Q(pecas_ordem_montagem__isnull=False) | Q(estanqueidade__isnull=False)
    ).count()

    # Paginação
    paginador = Paginator(datas, itens_por_pagina)
    pagina_obj = paginador.get_page(pagina)

    # Processamento dos dados
    dados = []
    for data in pagina_obj:
        dados_execucao = data.dadosexecucaoinspecao_set.last()

        if dados_execucao:
            data_ajustada = dados_execucao.data_execucao - timedelta(hours=3)
            
            # Determina se é montagem ou tanque
            if data.pecas_ordem_montagem:
                # Item de montagem
                item = {
                    "id": data.id,
                    "tipo": "montagem",
                    "data": data_ajustada.strftime("%d/%m/%Y %H:%M:%S"),
                    "peca": data.pecas_ordem_montagem.peca,
                    "maquina": data.pecas_ordem_montagem.ordem.maquina.nome,
                    "conformidade": dados_execucao.conformidade,
                    "nao_conformidade": dados_execucao.nao_conformidade,
                    "inspetor": (
                        dados_execucao.inspetor.user.username
                        if dados_execucao.inspetor
                        else None
                    ),
                }
            else:
                # Item de tanque
                item = {
                    "id": data.id,
                    "tipo": "tanque",
                    "data": data_ajustada.strftime("%d/%m/%Y %H:%M:%S"),
                    "peca": f"{data.estanqueidade.peca.codigo} - {data.estanqueidade.peca.descricao}",
                    "maquina": "Tanque",  # Ou outro identificador apropriado
                    "conformidade": dados_execucao.conformidade,
                    "nao_conformidade": dados_execucao.nao_conformidade,
                    "inspetor": (
                        dados_execucao.inspetor.user.username
                        if dados_execucao.inspetor
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

    status_conformidade_filtrados = (
        request.GET.get("status-conformidade", "").split(",")
        if request.GET.get("status-conformidade")
        else []
    )
    data_filtrada = request.GET.get("data", None)
    pesquisa_filtrada = request.GET.get("pesquisar", None)
    pagina = int(request.GET.get("pagina", 1))  # Página atual, padrão é 1
    itens_por_pagina = 12  # Itens por página

    # CORREÇÃO: Filtra tanto inspeções de montagem quanto de tanque
    datas = Inspecao.objects.filter(
        (Q(pecas_ordem_montagem__isnull=False) | Q(estanqueidade__isnull=False)),
        id__in=inspecionados_ids
    )

    quantidade_total = datas.count()  # Total de itens sem filtro

    # CORREÇÃO: Aplica filtro de máquinas apenas para itens de montagem
    if maquinas_filtradas:
        datas = datas.filter(
            Q(pecas_ordem_montagem__ordem__maquina__nome__in=maquinas_filtradas) |
            Q(estanqueidade__isnull=False)  # Mantém os tanques mesmo com filtro de máquinas
        ).distinct()

    if data_filtrada:
        datas = datas.filter(
            dadosexecucaoinspecao__data_execucao__date=data_filtrada
        ).distinct()

    # CORREÇÃO: Pesquisa tanto em peças de montagem quanto em tanques
    if pesquisa_filtrada:
        datas = datas.filter(
            Q(pecas_ordem_montagem__peca__icontains=pesquisa_filtrada) |
            Q(estanqueidade__peca__codigo__icontains=pesquisa_filtrada) |
            Q(estanqueidade__peca__descricao__icontains=pesquisa_filtrada)
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

    # CORREÇÃO: Pré-carrega relacionamentos tanto para montagem quanto para tanque
    datas = datas.select_related(
        "pecas_ordem_montagem",
        "pecas_ordem_montagem__ordem",
        "pecas_ordem_montagem__ordem__maquina",
        "estanqueidade",
        "estanqueidade__peca",
    ).order_by("-dadosexecucaoinspecao__data_execucao")

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

            # CORREÇÃO: Determina se é montagem ou tanque
            if data.pecas_ordem_montagem:
                # Item de montagem
                item = {
                    "id": data.id,
                    "tipo": "montagem",
                    "id_dados_execucao": de.id,
                    "data": data_ajustada.strftime("%d/%m/%Y %H:%M:%S"),
                    "peca": data.pecas_ordem_montagem.peca,
                    "qtd_produzida": data.pecas_ordem_montagem.qtd_boa,
                    "qtd_inspecionada": de.nao_conformidade + de.conformidade,
                    "maquina": data.pecas_ordem_montagem.ordem.maquina.nome,
                    "inspetor": de.inspetor.user.username if de.inspetor else None,
                    "possui_nao_conformidade": possui_nao_conformidade,
                }
            else:
                # Item de tanque
                item = {
                    "id": data.id,
                    "tipo": "tanque",
                    "id_dados_execucao": de.id,
                    "data": data_ajustada.strftime("%d/%m/%Y %H:%M:%S"),
                    "peca": f"{data.estanqueidade.peca.codigo} - {data.estanqueidade.peca.descricao}",
                    "qtd_produzida": 1,  # Tanques geralmente são unitários
                    "qtd_inspecionada": de.nao_conformidade + de.conformidade,
                    "maquina": "Tanque",  # Identificador apropriado para tanques
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


### dashboard montagem ###


def dashboard_montagem(request):

    return render(request, "dashboard/montagem.html")


def indicador_montagem_analise_temporal(request):
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
        FROM apontamento_v2.apontamento_montagem_pecasordem
        WHERE qtd_boa IS NOT NULL
            AND data BETWEEN %(data_inicio)s AND %(data_fim)s
        GROUP BY EXTRACT(YEAR FROM data), EXTRACT(MONTH FROM data)
    ),
    inspecoes_total AS (
        SELECT
            EXTRACT(YEAR FROM amp.data) AS ano,
            EXTRACT(MONTH FROM amp.data) AS mes,
            SUM(dei.conformidade) AS total_conforme,
            SUM(dei.nao_conformidade) AS total_nao_conforme
        FROM apontamento_v2.apontamento_montagem_pecasordem amp
        INNER JOIN apontamento_v2.inspecao_inspecao i ON i.pecas_ordem_montagem_id = amp.id
        INNER JOIN apontamento_v2.inspecao_dadosexecucaoinspecao dei ON dei.inspecao_id = i.id
        WHERE amp.data BETWEEN %(data_inicio)s AND %(data_fim)s
        GROUP BY EXTRACT(YEAR FROM amp.data), EXTRACT(MONTH FROM amp.data)
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


def indicador_montagem_resumo_analise_temporal(request):
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
    FROM apontamento_v2.apontamento_montagem_pecasordem
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
        FROM apontamento_v2.apontamento_montagem_pecasordem app
        INNER JOIN apontamento_v2.inspecao_inspecao i ON i.pecas_ordem_montagem_id = app.id
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


def causas_nao_conformidade_mensal_montagem(request):
    # Obtém parâmetros de data da requisição
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

    # Filtra os dados para o setor de montagem
    queryset = (
        CausasNaoConformidade.objects.filter(
            dados_execucao__inspecao__pecas_ordem_montagem__isnull=False,
            causa__setor="montagem",  # Filtra apenas causas do setor de montagem
        )
        .select_related(
            "dados_execucao",
            "dados_execucao__inspecao",
            "dados_execucao__inspecao__pecas_ordem_montagem",
        )
        .prefetch_related("causa")
    )

    # Aplica filtros de data se fornecidos
    if data_inicio:
        queryset = queryset.filter(
            dados_execucao__inspecao__data_inspecao__gte=data_inicio
        )
    if data_fim:
        queryset = queryset.filter(
            dados_execucao__inspecao__data_inspecao__lte=data_fim
        )

    # Agrupa por mês/ano, peça e causa, somando as quantidades
    resultados = (
        queryset.annotate(
            data_mes=TruncMonth(
                "dados_execucao__inspecao__data_inspecao"
            )  # Agrupa por mês/ano
        )
        .values(
            "data_mes",
            "dados_execucao__inspecao__pecas_ordem_montagem__peca",  # Campo da peça de montagem
            "causa__nome",
        )
        .annotate(quantidade_total=Sum("quantidade"))
        .order_by("data_mes")
    )

    # Formata os resultados para JSON
    dados_formatados = []
    for item in resultados:
        dados_formatados.append(
            {
                "data": (
                    item["data_mes"].strftime("%Y-%m") if item["data_mes"] else None
                ),  # Formata como YYYY-MM
                "peca": item["dados_execucao__inspecao__pecas_ordem_montagem__peca"],
                "causa": item["causa__nome"],
                "quantidade": item["quantidade_total"],
                "setor": "montagem",
            }
        )

    return JsonResponse(dados_formatados, safe=False)


def imagens_nao_conformidade_montagem(request):
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

    queryset = CausasNaoConformidade.objects.filter(
        dados_execucao__data_execucao__isnull=False,
        dados_execucao__inspecao__pecas_ordem_montagem__isnull=False,  # filtro para montagem
    ).prefetch_related("causa", "arquivos")

    if data_inicio:
        queryset = queryset.filter(dados_execucao__data_execucao__gte=data_inicio)
    if data_fim:
        queryset = queryset.filter(dados_execucao__data_execucao__lte=data_fim)

    resultado = []
    for item in queryset:
        date = item.dados_execucao.data_execucao - timedelta(hours=3)
        data_execucao = date.strftime("%Y-%m-%d %H:%M:%S")
        causas = [c.nome for c in item.causa.all()]
        arquivos = [
            arquivo.arquivo.url for arquivo in item.arquivos.all() if arquivo.arquivo
        ]

        for url in arquivos:
            resultado.append(
                {
                    "data_execucao": data_execucao,
                    "causas": causas,
                    "quantidade": item.quantidade,
                    "arquivo_url": url,
                }
            )

    return JsonResponse(resultado, safe=False)
