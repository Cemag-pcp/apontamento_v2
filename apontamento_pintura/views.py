from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.timezone import now
from django.core.paginator import Paginator
from django.db.models import Sum, Q, Prefetch, Count, OuterRef, Subquery, F, Value, Avg
from core.models import Profile
from apontamento_pintura.models import Retrabalho
from inspecao.models import Reinspecao, DadosExecucaoInspecao, Inspecao
from django.db.models.functions import Coalesce
from django.db import transaction, models
from django.shortcuts import get_object_or_404, render

import json
from datetime import datetime, timedelta
from pytz import timezone

from .models import PecasOrdem, CambaoPecas, Cambao
from core.models import Ordem
from cadastro.models import Operador


def planejamento(request):
    return render(request, "apontamento_pintura/planejamento.html")


def ordens_criadas(request):
    data_carga = request.GET.get(
        "data_carga", now().date()
    )  # Garantindo que seja apenas a data

    if not data_carga:
        data_carga = now().date()

    # Subquery para obter a primeira peça associada à ordem
    primeira_peca = PecasOrdem.objects.filter(ordem=OuterRef("pk")).order_by("id")

    # Subquery para calcular a soma total de `quantidade_pendurada` no cambão para essa ordem
    soma_qtd_pendurada = (
        CambaoPecas.objects.filter(peca_ordem__ordem=OuterRef("pk"))
        .values("peca_ordem__ordem")
        .annotate(
            total_quantidade_pendurada=Sum(
                "quantidade_pendurada", output_field=models.FloatField()
            )
        )
        .values("total_quantidade_pendurada")
    )

    # Subquery para obter a quantidade planejada da primeira peça
    qt_planejada = primeira_peca.values("qtd_planejada")[:1]

    # Query principal das ordens
    ordens_queryset = (
        Ordem.objects.filter(
            grupo_maquina="pintura", excluida=False, data_carga=data_carga
        )
        .annotate(
            peca_ordem_id=Subquery(
                primeira_peca.values("id")[:1]
            ),  # ID da primeira peça associada à ordem
            peca_codigo=Subquery(
                primeira_peca.values("peca")[:1]
            ),  # Código da primeira peça associada à ordem
            peca_qt_planejada=Subquery(
                qt_planejada, output_field=models.FloatField()
            ),  # Quantidade planejada
            soma_qtd_pendurada=Coalesce(
                Subquery(soma_qtd_pendurada, output_field=models.FloatField()),
                Value(0.0),  # Garante que valores NULL sejam 0.0
                output_field=models.FloatField(),
            ),
        )
        .annotate(
            qt_restante=F("peca_qt_planejada")
            - F("soma_qtd_pendurada")  # Subtração correta
        )
        .filter(qt_restante__gt=0)
        .order_by("-status_prioridade")
    )

    return JsonResponse({"ordens": list(ordens_queryset.values())})


@csrf_exempt
def criar_ordem(request):
    """
    Maneira de chamar a API:
    {
        "cor": "Azul",
        "obs": "testes",
        "peca_nome": "123456",
        "qtd_planejada": 5
        "data_carga": "2025-02-19"
    }
    """

    if request.method == "POST":
        try:
            data = json.loads(request.body)

            # Capturar dados da ordem
            grupo_maquina = data.get(
                "grupo_maquina", "pintura"
            )  # Define 'pintura' como padrão
            cor = data.get("cor")
            obs = data.get("obs", "")
            nome_peca = data.get("peca_nome")
            qtd_planejada = data.get("qtd_planejada", 0)
            data_carga_str = data.get("data_carga")  # Mantém como string inicialmente

            # ✅ Converter data_carga para datetime.date, se fornecida
            if data_carga_str:
                try:
                    data_carga = datetime.strptime(data_carga_str, "%Y-%m-%d").date()
                except ValueError:
                    return JsonResponse(
                        {"error": "Formato de data inválido! Use YYYY-MM-DD."},
                        status=400,
                    )
            else:
                data_carga = now().date()

            if not nome_peca:
                return JsonResponse(
                    {"error": "Nome da peça é obrigatório!"}, status=400
                )

            with transaction.atomic():

                ordem = Ordem.objects.create(
                    grupo_maquina=grupo_maquina,
                    status_atual="aguardando_iniciar",
                    cor=cor,
                    obs=obs,
                    data_criacao=now(),
                    data_carga=data_carga,
                )

                # Criar a única peça associada à ordem
                peca = PecasOrdem.objects.create(
                    ordem=ordem,
                    peca=nome_peca,
                    qtd_planejada=qtd_planejada,
                    qtd_boa=0,  # Inicialmente 0
                    qtd_morta=0,
                )

                return JsonResponse(
                    {
                        "message": "Ordem e peça criadas com sucesso!",
                        "ordem_id": ordem.id,
                        "peca": {
                            "id": peca.id,
                            "nome": peca.peca,
                            "qtd_planejada": peca.qtd_planejada,
                        },
                    }
                )

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Método não permitido!"}, status=405)


@csrf_exempt
def adicionar_pecas_cambao(request):
    """
    Inicia um cambão com peças penduradas.
    {
        "cambao_id": 2,
        "peca_ordens": [12, 15],
        "quantidade": [1, 1],
        "cor": "Azul"  # cor do cambão
        "tipo":"PU"
    }
    """

    if request.method == "POST":
        try:
            data = json.loads(request.body)

            cambao_id = data.get("cambao_id")
            peca_ordens = data.get("peca_ordens", [])  # Lista de IDs de PecasOrdem
            quantidades = data.get(
                "quantidade", []
            )  # Lista de quantidades correspondentes
            cor = data.get("cor")
            tipo_tinta = data.get("tipo")
            operador_inicial = data.get("operador")

            if not cambao_id or not peca_ordens or not quantidades or not cor:
                return JsonResponse(
                    {"error": "Todos os campos são obrigatórios!"}, status=400
                )

            if len(peca_ordens) != len(quantidades):
                return JsonResponse(
                    {"error": "A quantidade de peças e de IDs deve ser a mesma!"},
                    status=400,
                )

            # Buscar o cambão e garantir que está livre
            try:
                cambao = Cambao.objects.get(id=cambao_id)
            except Cambao.DoesNotExist:
                return JsonResponse(
                    {"error": "O cambão informado não existe!"}, status=400
                )

            if cambao.status != "livre":
                return JsonResponse(
                    {"error": "Cambão já está em uso! Escolha outro."}, status=400
                )

            cambao.cor = cor  # Atualiza a cor caso necessário
            cambao.tipo = tipo_tinta

            with transaction.atomic():
                pecas_selecionadas = []

                # Valida e adiciona peças ao cambão
                for idx, peca_ordem_id in enumerate(peca_ordens):
                    quantidade = quantidades[idx]

                    try:
                        peca_ordem = PecasOrdem.objects.get(id=peca_ordem_id)
                    except PecasOrdem.DoesNotExist:
                        return JsonResponse(
                            {
                                "error": f"A peça com ID {peca_ordem_id} não foi encontrada!"
                            },
                            status=400,
                        )

                    if peca_ordem.ordem.cor != cor:
                        return JsonResponse(
                            {
                                "error": f"A peça {peca_ordem.peca} não pertence à cor {cor}!"
                            },
                            status=400,
                        )

                    # Verificar quantidade disponível para pendurar
                    qtd_pendurada = (
                        CambaoPecas.objects.filter(peca_ordem=peca_ordem).aggregate(
                            Sum("quantidade_pendurada")
                        )["quantidade_pendurada__sum"]
                        or 0
                    )

                    qtd_disponivel = peca_ordem.qtd_planejada - qtd_pendurada
                    if quantidade > qtd_disponivel:
                        return JsonResponse(
                            {
                                "error": f"A peça {peca_ordem.peca} só pode ter mais {qtd_disponivel} unidades penduradas!"
                            },
                            status=400,
                        )

                    pecas_selecionadas.append((peca_ordem, quantidade))

                # Criar as associações no cambão
                for peca_ordem, quantidade in pecas_selecionadas:
                    CambaoPecas.objects.create(
                        cambao=cambao,
                        peca_ordem=peca_ordem,
                        quantidade_pendurada=quantidade,
                        data_pendura=now(),
                        status="pendurada",
                        operador_inicio=get_object_or_404(
                            Operador, pk=operador_inicial
                        ),
                    )

                # Atualizar status do cambão para "em uso"
                cambao.status = "em uso"
                cambao.save()

            return JsonResponse(
                {"success": True, "message": "Peças adicionadas ao cambão com sucesso!"}
            )

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Método não permitido!"}, status=405)


@csrf_exempt
def finalizar_cambao(request):
    """
    Finaliza um cambão, registrando as peças e liberando-o para novo uso.

    Exemplo de JSON esperado:
    {
        "cambao_id": 2,
        "operador": 1
    }
    """

    if request.method == "POST":
        try:
            data = json.loads(request.body)

            cambao_id = data.get("cambao_id")
            operador_id = data.get("operador")

            if not cambao_id:
                return JsonResponse(
                    {"error": "ID do cambão é obrigatório!"}, status=400
                )

            if not operador_id:
                return JsonResponse(
                    {"error": "ID do operador é obrigatório!"}, status=400
                )

            # Buscar o cambão
            cambao = get_object_or_404(Cambao, id=cambao_id)

            # O cambão deve estar em uso para ser finalizado
            if cambao.status != "em uso":
                return JsonResponse(
                    {"error": "Apenas cambões em uso podem ser finalizados!"},
                    status=400,
                )

            # Recupera todas as peças penduradas no cambão
            pecas_no_cambao = CambaoPecas.objects.filter(
                cambao=cambao, status="pendurada"
            )

            if not pecas_no_cambao.exists():
                return JsonResponse(
                    {"error": "Não há peças associadas a este cambão!"}, status=400
                )

            operador = get_object_or_404(Operador, id=operador_id)

            with transaction.atomic():
                # Criar novas entradas em PecasOrdem para cada peça finalizada
                for item in pecas_no_cambao:
                    peca_ordem_original = item.peca_ordem

                    # Soma total de peças já finalizadas
                    qtd_finalizadas = (
                        PecasOrdem.objects.filter(
                            ordem=peca_ordem_original.ordem,
                            peca=peca_ordem_original.peca,
                        ).aggregate(Sum("qtd_boa"))["qtd_boa__sum"]
                        or 0
                    )

                    qtd_restante = peca_ordem_original.qtd_planejada - qtd_finalizadas

                    # Garantir que a quantidade finalizada não ultrapasse o total planejado
                    if item.quantidade_pendurada > qtd_restante:
                        return JsonResponse(
                            {
                                "error": f"A quantidade finalizada ({item.quantidade_pendurada}) excede o planejado ({qtd_restante})."
                            },
                            status=400,
                        )

                    # Criar um novo registro em PecasOrdem para registrar o apontamento do cambão
                    nova_peca_ordem = PecasOrdem.objects.create(
                        ordem=peca_ordem_original.ordem,
                        peca=peca_ordem_original.peca,
                        qtd_planejada=peca_ordem_original.qtd_planejada,
                        qtd_morta=0,
                        qtd_boa=item.quantidade_pendurada,
                        data=now(),
                        tipo=cambao.tipo,
                        operador_fim=operador,
                    )

                    # Atualizar o status da peça no cambão para "finalizada"
                    item.status = "finalizada"
                    item.data_fim = now()
                    item.save()

                # Atualizar status do cambão para "finalizado"
                cambao.status = "livre"
                cambao.data_fim = now()
                cambao.save()

            return JsonResponse(
                {
                    "success": True,
                    "message": "Cambão finalizado e peças registradas com sucesso!",
                }
            )

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Método não permitido!"}, status=405)


def cambao_livre(request):

    cambao_livres = Cambao.objects.filter(status="livre")

    return JsonResponse({"cambao_livres": list(cambao_livres.values())})


def cambao_em_processo(request):
    """
    Retorna os cambões que estão em processo, agrupando suas peças corretamente.

    Resposta esperada:
    {
        "cambao_em_processo": [
            {
                "id": 1,
                "pecas": [
                    {"peca_ordem_id": 40, "quantidade_pendurada": 1.0},
                    {"peca_ordem_id": 41, "quantidade_pendurada": 2.0}
                ],
                "data_pendura": "2025-02-20T20:08:42.030Z",
                "status": "pendurada",
                "data_fim": null
            }
        ]
    }
    """

    # Filtra apenas os cambões que possuem peças penduradas
    cambao_queryset = (
        Cambao.objects.filter(pecas_no_cambao__status="pendurada")
        .distinct()
        .prefetch_related(
            Prefetch(
                "pecas_no_cambao",
                queryset=CambaoPecas.objects.filter(status="pendurada"),
            )
        )
    )

    resultado = []

    for cambao in cambao_queryset:
        pecas = [
            {
                "peca_ordem_id": peca.peca_ordem.id,
                "peca": peca.peca_ordem.peca,
                "quantidade_pendurada": peca.quantidade_pendurada,
            }
            for peca in cambao.pecas_no_cambao.all()
        ]

        resultado.append(
            {
                "id": cambao.id,
                "cor": cambao.cor,
                "pecas": pecas,
                "data_pendura": (
                    cambao.pecas_no_cambao.first().data_pendura if pecas else None
                ),
                "status": "pendurada",
                "tipo": cambao.tipo,
                # "data_fim": cambao.data_fim
            }
        )

    return JsonResponse({"cambao_em_processo": resultado})


def listar_operadores(request):

    operadores = Operador.objects.filter(setor__nome="pintura")

    return JsonResponse({"operadores": list(operadores.values())})


def listar_cores_carga(request):
    data_carga = request.GET.get(
        "data_carga", now().date()
    )  # Garantindo que seja apenas a data

    if data_carga == "":
        data_carga = now().date()

    # Obtém cores únicas
    cores = (
        Ordem.objects.filter(data_carga=data_carga, grupo_maquina="pintura")
        .values_list("cor", flat=True)
        .distinct()
    )

    return JsonResponse({"cores": list(cores)})  # Retorna lista simples de cores únicas


def percentual_concluido_carga(request):
    data_carga = request.GET.get(
        "data_carga", now().date()
    )  # Garantindo que seja apenas a data

    # Soma correta da quantidade planejada por peça e ordem (evitando duplicação)
    total_planejado = (
        PecasOrdem.objects.filter(
            ordem__data_carga=data_carga, ordem__grupo_maquina="pintura"
        )
        .values("ordem", "peca")
        .distinct()
        .aggregate(
            total_planejado=Coalesce(
                Sum("qtd_planejada", output_field=models.FloatField()), Value(0.0)
            )
        )["total_planejado"]
    )

    # Soma total da quantidade boa produzida
    total_finalizado = PecasOrdem.objects.filter(
        ordem__data_carga=data_carga, ordem__grupo_maquina="pintura"
    ).aggregate(
        total_finalizado=Coalesce(
            Sum("qtd_boa", output_field=models.FloatField()), Value(0.0)
        )
    )[
        "total_finalizado"
    ]

    # Evitar divisão por zero
    percentual_concluido = (
        (total_finalizado / total_planejado * 100) if total_planejado > 0 else 0.0
    )

    return JsonResponse(
        {
            "percentual_concluido": round(
                percentual_concluido, 2
            ),  # Arredonda para 2 casas decimais
            "total_planejado": total_planejado,
            "total_finalizado": total_finalizado,
        }
    )


def andamento_ultimas_cargas(request):
    # Obtém as últimas 5 datas de carga disponíveis para pintura
    ultimas_cargas = (
        Ordem.objects.filter(grupo_maquina="pintura")
        .order_by("-data_carga")
        .values_list("data_carga", flat=True)
        .distinct()[:5]
    )

    andamento_cargas = []

    for data in ultimas_cargas:
        # Soma correta da quantidade planejada (evitando duplicações)
        total_planejado = (
            PecasOrdem.objects.filter(
                ordem__data_carga=data, ordem__grupo_maquina="pintura"
            )
            .values("ordem", "peca")
            .distinct()
            .aggregate(
                total_planejado=Coalesce(
                    Sum("qtd_planejada", output_field=models.FloatField()), Value(0.0)
                )
            )["total_planejado"]
        )

        # Soma total da quantidade boa produzida
        total_finalizado = PecasOrdem.objects.filter(
            ordem__data_carga=data, ordem__grupo_maquina="pintura"
        ).aggregate(
            total_finalizado=Coalesce(
                Sum("qtd_boa", output_field=models.FloatField()), Value(0.0)
            )
        )[
            "total_finalizado"
        ]

        # Evita divisão por zero e calcula o percentual corretamente
        percentual_concluido = (
            (total_finalizado / total_planejado * 100) if total_planejado > 0 else 0.0
        )

        andamento_cargas.append(
            {
                "data_carga": data.strftime("%d/%m/%Y"),
                "percentual_concluido": round(percentual_concluido, 2),
                "total_planejado": total_planejado,
                "total_finalizado": total_finalizado,
            }
        )

    return JsonResponse({"andamento_cargas": andamento_cargas})


def retrabalho_pintura(request):

    users = Profile.objects.filter(
        tipo_acesso="inspetor", permissoes__nome="inspecao/pintura"
    )

    cores = ["Amarelo", "Azul", "Cinza", "Laranja", "Verde", "Vermelho"]

    lista_inspetores = [
        {"nome_usuario": user.user.username, "id": user.user.id} for user in users
    ]

    return render(
        request,
        "retrabalho_pintura/retrabalho.html",
        {"inspetores": lista_inspetores, "cores": cores},
    )


def get_itens_retrabalho_pintura(request):

    if request.method != "GET":
        return JsonResponse({"error": "Método não permitido"}, status=405)

    reinspecao_ids = set(
        Reinspecao.objects.filter(
            retrabalho__status="a retrabalhar",  # Filtra pelo status "finalizado" no modelo Retrabalho
            reinspecionado=False,  # Mantém o filtro original
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


        item = {
            "id": data.id,
            "id_dados_execucao": DadosExecucaoInspecao.objects.filter(inspecao=data)
            .values_list("id", flat=True)
            .last(),
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


def get_itens_em_processo_pintura(request):

    if request.method != "GET":
        return JsonResponse({"error": "Método não permitido"}, status=405)

    reinspecao_ids = set(
        Reinspecao.objects.filter(
            retrabalho__status="em processo",  # Filtra pelo status "finalizado" no modelo Retrabalho
            reinspecionado=False,  # Mantém o filtro original
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


def get_itens_retrabalhados_pintura(request):

    if request.method != "GET":
        return JsonResponse({"error": "Método não permitido"}, status=405)

    reinspecao_ids = set(
        Reinspecao.objects.filter(
            retrabalho__status="finalizado",  # Filtra pelo status "finalizado" no modelo Retrabalho
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

        item = {
            "id": data.id,
            "id_dados_execucao": DadosExecucaoInspecao.objects.filter(inspecao=data)
            .values_list("id", flat=True)
            .last(),
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


def confirmar_retrabalho_pintura(request):

    if request.method != "POST":
        return JsonResponse({"error": "Método não permitido"}, status=405)

    id = request.POST.get("id")

    if not id:
        return JsonResponse({"error": "ID não fornecido"}, status=400)

    try:
        # Busca o retrabalho associado à reinspeção
        retrabalho = Retrabalho.objects.filter(reinspecao__inspecao_id=id).first()

        if not retrabalho:
            return JsonResponse(
                {"error": "Nenhum retrabalho encontrado para esta reinspeção"},
                status=404,
            )

        brasil_tz = timezone("America/Sao_Paulo")
        retrabalho.data_inicio = now().astimezone(brasil_tz)

        retrabalho.status = "em processo"

        retrabalho.save()

        return JsonResponse(
            {
                "success": "Retrabalho confirmado com sucesso",
                "retrabalho_id": retrabalho.id,
            }
        )

    except Exception as e:
        return JsonResponse(
            {"error": f"Erro interno do servidor: {str(e)}"}, status=500
        )


def finalizar_retrabalho_pintura(request):

    if request.method != "POST":
        return JsonResponse({"error": "Método não permitido"}, status=405)

    id = request.POST.get("id")

    if not id:
        return JsonResponse({"error": "ID não fornecido"}, status=400)

    try:
        # Busca a reinspeção relacionada ao ID fornecido
        reinspecao = get_object_or_404(Reinspecao, inspecao_id=id)

        # Busca o retrabalho associado à reinspeção
        retrabalho = Retrabalho.objects.filter(reinspecao=reinspecao).first()

        if not retrabalho:
            return JsonResponse(
                {"error": "Nenhum retrabalho encontrado para esta reinspeção"},
                status=404,
            )

        brasil_tz = timezone("America/Sao_Paulo")
        retrabalho.data_fim = now().astimezone(brasil_tz)

        retrabalho.status = "finalizado"

        retrabalho.save()

        return JsonResponse(
            {
                "success": "Retrabalho confirmado com sucesso",
                "retrabalho_id": retrabalho.id,
            }
        )

    except Exception as e:
        return JsonResponse(
            {"error": f"Erro interno do servidor: {str(e)}"}, status=500
        )
