from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.timezone import now,localtime
from django.core.paginator import Paginator
from django.db.models import Sum, Q, Prefetch, Count, OuterRef, Subquery, F, Value, Avg, Value, CharField
from django.db.models.functions import Coalesce, Concat
from django.db import transaction, models
from django.shortcuts import get_object_or_404, render
from django.db import transaction, models, IntegrityError, connection

import json
from datetime import date, datetime, timedelta
from pytz import timezone
import random
from collections import defaultdict

from core.models import Profile
from apontamento_pintura.models import Retrabalho
from inspecao.models import Reinspecao, DadosExecucaoInspecao, Inspecao
from .models import PecasOrdem, CambaoPecas, Cambao, TesteFuncional
from core.models import Ordem
from cadastro.models import Operador, Conjuntos
from inspecao.models import Inspecao
from core.utils import notificar_ordem

def planejamento(request):
    return render(request, "apontamento_pintura/planejamento.html")

def ordens_criadas(request):
    
    filtros = {}
    filtros_peca = {}

    data_carga = request.GET.get("data_carga", None)

    if data_carga:
        try:
            if data_carga and data_carga.strip():
                data_carga = datetime.strptime(data_carga, "%Y-%m-%d").date()
                filtros['data_carga'] = data_carga
            else:
                data_carga = now().date()
                filtros['data_carga'] = data_carga
        except ValueError:
            data_carga = now().date()
            filtros['data_carga'] = data_carga

    cor = request.GET.get("cor", '')
    conjunto = request.GET.get("conjunto", '')
    data_programacao = request.GET.get("data-programada", '')

    if cor:
        filtros['cor'] = cor
    if data_programacao:
        filtros['data_programacao'] = data_programacao
    if conjunto:
        filtros_peca['peca__contains'] = conjunto

    # Subquery para obter a primeira peça associada à ordem
    primeira_peca = PecasOrdem.objects.filter(ordem=OuterRef("pk"), **filtros_peca).order_by("id")

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
            grupo_maquina="pintura", excluida=False, **filtros
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
        .order_by("-status_prioridade", "data_programacao")
    )

    primeira_data = ordens_queryset.first().data_programacao if ordens_queryset.exists() else None
    data_programacao_formatada = (
        primeira_data.strftime('%d/%m/%Y') if primeira_data else None
    )

    primeira_data_carga = ordens_queryset.first().data_carga if ordens_queryset.exists() else None
    data_programacao_formatada_carga = (
        primeira_data_carga if primeira_data_carga else None
    )

    return JsonResponse({
                            "ordens": list(ordens_queryset.values()),
                            "data_programacao": data_programacao_formatada,
                            "data_carga": data_programacao_formatada_carga
                        })

@csrf_exempt
def criar_ordem(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido!'}, status=405)

    try:
        data = json.loads(request.body)
        ordens_data = data.get('ordens', [])
        atualizacao_ordem = data.get('atualizacao_ordem', None)

        if not ordens_data:
            return JsonResponse({'error': 'Nenhuma ordem fornecida!'}, status=400)

        # Coleta e valida datas
        datas_requisicao = {
            datetime.strptime(ordem['data_carga'], "%Y-%m-%d").date()
            for ordem in ordens_data
            if 'data_carga' in ordem
        }

        datas_existentes = set(
            Ordem.objects.filter(data_carga__in=datas_requisicao, grupo_maquina='pintura')
            .values_list('data_carga', flat=True)
        )
        datas_bloqueadas = datas_existentes & datas_requisicao

        if not atualizacao_ordem and datas_bloqueadas:
            return JsonResponse({
                'error': f"Não é possível adicionar novas ordens. Datas já possuem carga alocada: {', '.join(map(str, datas_bloqueadas))}"
            }, status=400)

        ordens_objs = []
        pecas_objs = []
        ordens_metadata = []

        for ordem in ordens_data:
            try:
                data_carga = datetime.strptime(ordem['data_carga'], "%d/%m/%Y").date()
            except ValueError:
                return JsonResponse({'error': 'Formato de data inválido! Use YYYY-MM-DD.'}, status=400)

            if not ordem.get('peca_nome'):
                return JsonResponse({'error': 'Nome da peça é obrigatório!'}, status=400)

            nova_ordem = Ordem(
                grupo_maquina=ordem.get('grupo_maquina', 'pintura'),
                status_atual='aguardando_iniciar',
                cor=ordem.get('cor'),
                obs=ordem.get('obs', ''),
                data_criacao=now(),
                data_carga=data_carga
            )
            ordens_objs.append(nova_ordem)
            ordens_metadata.append({
                'peca_nome': ordem['peca_nome'],
                'qtd_planejada': ordem.get('qtd_planejada', 0)
            })

        with transaction.atomic():
            Ordem.objects.bulk_create(ordens_objs)

            for ordem_obj, meta in zip(ordens_objs, ordens_metadata):
                pecas_objs.append(PecasOrdem(
                    ordem=ordem_obj,
                    peca=meta['peca_nome'],
                    qtd_planejada=meta['qtd_planejada'],
                    qtd_boa=0,
                    qtd_morta=0
                ))

            PecasOrdem.objects.bulk_create(pecas_objs)

        return JsonResponse({
            'message': 'Ordens e peças criadas com sucesso!',
            'ordens': [
                {
                    'id': ordem.id,
                    'cor': ordem.cor,
                    'data_carga': ordem.data_carga
                }
                for ordem in ordens_objs
            ]
        })

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Erro ao processar JSON. Verifique o formato da requisição!'}, status=400)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
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

            # if cambao.status != "livre":
            #     return JsonResponse(
            #         {"error": "Cambão já está em uso! Escolha outro."}, status=400
            #     )

            if cambao.cor != '' and cambao.cor != cor:
                return JsonResponse(
                    {"error": "A cor do cambão não corresponde à cor da peça!"}, status=400
                )
            
            cambao.cor = cor  # Atualiza a cor caso necessário
            cambao.tipo = tipo_tinta

            tipo_pu = cambao.tipo == 'PU'


            with transaction.atomic():
                if tipo_pu:
                    peca_sorteada = verificar_cor_cambao(cambao.cor, cambao.nome)
                    if peca_sorteada:
                        try:
                            #Registro de teste inicial sem nenhum dado de realização do teste de verificação funcional
                            registro_teste_funcional_pintura = TesteFuncional.objects.create(
                                peca_ordem=peca_sorteada.peca_ordem
                            )
                        except Exception as e:
                            print('teste:',e)

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
                notificar_ordem(peca_ordem.ordem)
                
            return JsonResponse(
                {"success": True, "message": "Peças adicionadas ao cambão com sucesso!"}
            )

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Método não permitido!"}, status=405)

@csrf_exempt
def criar_ordem_fora_sequenciamento(request):

    """
    API para criar uma ordem fora do sequenciamento.
    Verifica se o conjunto escolhido ja tem na data de carga escolhida.
    Caso tenha, apenas acrescenta na quantidade planejada.
    Caso não tenha, cria uma nova ordem com a quantidade planejada.
    """

    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)

    data = json.loads(request.body)

    conjunto = data.get('peca')
    codigo_conjunto = data.get('peca').split(" - ", maxsplit=1)[0]  # Pega apenas o código do conjunto
    quantidade_planejada = data.get('quantidade')
    cor = data.get('cor')
    data_carga = data.get('dataCarga')
    obs = data.get('observacao')

    ordens_existentes = Ordem.objects.filter(
        data_carga=data_carga,
        grupo_maquina='pintura',
        ordem_pecas_pintura__peca__contains=codigo_conjunto,
        cor=cor,
    ).values_list('id', flat=True)

    if ordens_existentes:
        ordem = Ordem.objects.get(id=ordens_existentes[0])
        ordem.status_atual = 'aguardando_iniciar' if ordem.status_atual == 'finalizada' else ordem.status_atual
        ordem.save()
        pecas = PecasOrdem.objects.filter(ordem=ordem, peca__contains=codigo_conjunto)
        for peca in pecas:
            peca.qtd_planejada += int(quantidade_planejada)
            peca.save()
        return JsonResponse({'message': 'Quantidade planejada atualizada com sucesso!'})

    else:
        ordem = Ordem.objects.create(
            grupo_maquina='pintura',
            status_atual='aguardando_iniciar',
            data_carga=datetime.strptime(data_carga, '%Y-%m-%d').date(),
            cor=cor
        )  
        PecasOrdem.objects.create(
            ordem=ordem,
            peca=conjunto,
            qtd_planejada=quantidade_planejada,
            qtd_boa=0,
            qtd_morta=0
        )
        return JsonResponse({'message': 'Ordem criada com sucesso!'})

def listar_conjuntos(request):
    """
    API para listar os conjuntos disponíveis para o setor de montagem.
    Aceita um parâmetro de busca opcional: ?termo=texto
    """
    termo = request.GET.get('termo', '').strip()

    if termo:
        conjuntos = Conjuntos.objects.filter(
            Q(codigo__icontains=termo) | Q(descricao__icontains=termo)
        ).values('id', 'codigo', 'descricao')
    else:
        conjuntos = Conjuntos.objects.values('id', 'codigo', 'descricao')

    return JsonResponse({"conjuntos": list(conjuntos)})

@csrf_exempt
def finalizar_cambao(request):
    
    """
    
    Finaliza um cambão, registrando as peças e liberando para novo uso.
    
    """

    if request.method == "POST":
        try:
            data = json.loads(request.body)
            
            cambao_nome = data.get('cambao_nome')
            cambao_id = data.get("cambao_id")
            operador_id = data.get("operador")

            if cambao_nome:
                cambao_id = Cambao.objects.filter(nome=cambao_nome).values_list('id', flat=True).first()

            if not cambao_id:
                return JsonResponse(
                    {"error": "ID do cambão é obrigatório!"}, status=400
                )

            if not operador_id:
                return JsonResponse(
                    {"error": "ID do operador é obrigatório!"}, status=400
                )

            cambao = get_object_or_404(Cambao, id=cambao_id)

            tipo_po = cambao.tipo == "PÓ"

            if cambao.status != "em uso":
                return JsonResponse(
                    {"error": "Apenas cambões em uso podem ser finalizados!"}, status=400
                )

            pecas_no_cambao = CambaoPecas.objects.filter(
                cambao=cambao, status="pendurada"
            )

            if not pecas_no_cambao.exists():
                return JsonResponse(
                    {"error": "Não há peças associadas a este cambão!"}, status=400
                )

            operador = get_object_or_404(Operador, id=operador_id)

            # Pré-validação de todas as peças antes da transação
            for item in pecas_no_cambao:
                peca_ordem_original = item.peca_ordem

                qtd_finalizadas = (
                    PecasOrdem.objects.filter(
                        ordem=peca_ordem_original.ordem,
                        peca=peca_ordem_original.peca,
                    ).aggregate(Sum("qtd_boa"))["qtd_boa__sum"]
                    or 0
                )

                qtd_restante = peca_ordem_original.qtd_planejada - qtd_finalizadas

                if item.quantidade_pendurada > qtd_restante:
                    return JsonResponse(
                        {
                            "error": f"A quantidade finalizada ({item.quantidade_pendurada}) excede o planejado ({qtd_restante})."
                        },
                        status=400,
                    )
            
            # Se passou pela validação, executa a finalização em bloco atômico
            with transaction.atomic():
                # Só verificar a cor do cambao caso na finalização se o tipo da cor for PÓ
                if tipo_po:
                    # Verificar cor e sortear uma peca
                    peca_sorteada = verificar_cor_cambao(cambao.cor,cambao.nome)
                    if peca_sorteada:
                        #Registro de teste inicial sem nenhum dado de realização do teste de verificação funcional
                        try:
                            registro_teste_funcional_pintura = TesteFuncional.objects.create(
                                peca_ordem=peca_sorteada.peca_ordem
                            )
                        except Exception as e:
                            print(e)
                
                for item in pecas_no_cambao:
                    peca_ordem_original = item.peca_ordem

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

                    Inspecao.objects.create(
                        pecas_ordem_pintura=nova_peca_ordem,
                    )

                    item.status = "finalizada"
                    item.peca_ordem = nova_peca_ordem
                    item.data_fim = now()
                    item.save()

                cambao.status = "livre"
                cambao.cor = ''  # Limpa a cor do cambão
                cambao.data_fim = now()
                cambao.save()
                # ordem = Ordem.objects.get(pk=ordem_id)
                notificar_ordem(peca_ordem_original.ordem)

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
    tipo = request.GET.get('tipo')
    cambao_livres = Cambao.objects.filter(tipo=tipo, ativo=True)

    resultado = []
    for c in cambao_livres:
        if c.status == "livre":
            nome_formatado = f"{c.nome} - livre"
        else:
            nome_formatado = f"{c.nome} - {c.status} - {c.cor}"

        resultado.append({"nome": nome_formatado, "id": c.id})

    return JsonResponse({"cambao_livres": resultado})

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
                "data_carga": peca.peca_ordem.ordem.data_carga,
            }
            for peca in cambao.pecas_no_cambao.all()
        ]

        resultado.append({
            "id": cambao.id,
            "cor": cambao.cor,
            "pecas": pecas,
            "data_pendura": cambao.pecas_no_cambao.first().data_pendura if pecas else None,
            "status": "pendurada",
            "tipo": cambao.tipo,
            "nome": cambao.nome,
            # "data_fim": cambao.data_fim
        })

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
    data_carga_str = request.GET.get("data_carga", "").strip()

    try:
        if data_carga_str:
            data_carga = datetime.strptime(data_carga_str, "%Y-%m-%d").date()
        else:
            data_carga = now().date()
    except ValueError:
        data_carga = now().date()
    
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
        .distinct()[:10]
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

def api_ordens_finalizadas(request):
    mapa_cor = {
        'Laranja': 'LC',
        'Amarelo': 'AV',
        'Verde': 'VJ',
        'Cinza': 'CO',
        'Azul': 'AN',
        'Vermelho': 'VM',
    }

    dados = PecasOrdem.objects.select_related(
        'ordem',
        'operador_fim',
    ).filter(
        qtd_boa__gt=0,
        operador_fim__isnull=False
    ).annotate(
        ordem_numero=F('ordem__ordem'),
        codigo=F('peca'),
        descricao=F('peca'),
        cor=F('ordem__cor'),
        data_carga=F('ordem__data_carga'),
        data_apontamento=F('data'),
        operador_nome=Concat(
            F('operador_fim__matricula'),
            Value(' - '),
            F('operador_fim__nome'),
            output_field=CharField()
        ),
    ).order_by('data_apontamento')

    resultado = []
    for d in dados:
        resultado.append({
            'ordem': d.ordem.ordem,
            'codigo': d.peca.split(" - ")[0],
            'descricao': d.peca.split(" - ")[1],
            'qtd_planejada': d.qtd_planejada,
            'cor': mapa_cor.get(d.ordem.cor, d.ordem.cor),
            'qtd_boa': d.qtd_boa,
            'col5': '',
            'tipo': d.tipo,
            'data_carga': d.ordem.data_carga,
            'data_apontamento': (d.data - timedelta(hours=3)).date(),
            'col1': '',
            'col2': '',
            'col3': '',
            'col4': '',
            'operador': f"{d.operador_fim.matricula} - {d.operador_fim.nome}" if d.operador_fim else '',
        })

    return JsonResponse(resultado, safe=False)

def api_tempos(request):
    """
    formatos de datas para saida: dd/mm/yyyy

    ordem
    codigo
    descricao
    qt_planejada
    cor
    quantidade_pendurada
    cambao
    tipo
    data_carga
    data_fim
    col1 (em branco)
    col2 (em branco)
    col3 (em branco)
    col4 (em branco)
    operador_inicio
    operador_fim
    col5 (em branco)
    data_pendura
    """

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                o.id AS ordem,                              
                po.peca AS conjunto,                   
                po.qtd_planejada AS qt_planejada,        
                o.cor,                                
                cp.quantidade_pendurada,             
                apc.nome as cambao,    
                po.tipo,                              
                o.data_carga,                         
                cp.data_fim,                          
                concat(co_inicio.matricula, ' - ', co_inicio.nome) AS operador_inicio,
                concat(co_fim.matricula, ' - ', co_fim.nome) AS operador_fim,
                cp.data_pendura                       
            FROM apontamento_v2.core_ordem o
            INNER JOIN apontamento_v2.apontamento_pintura_pecasordem po ON po.ordem_id = o.id
            INNER JOIN apontamento_v2.apontamento_pintura_cambaopecas cp ON cp.peca_ordem_id = po.id
            INNER JOIN apontamento_v2.apontamento_pintura_cambao apc on apc.id = cp.cambao_id
            LEFT JOIN apontamento_v2.cadastro_operador co_fim ON co_fim.id = po.operador_fim_id
            LEFT JOIN apontamento_v2.cadastro_operador co_inicio ON co_inicio.id = cp.operador_inicio_id
            ORDER BY o.ordem, cp.data_pendura;
        """)
        columns = [col[0] for col in cursor.description]
        results_raw = [dict(zip(columns, row)) for row in cursor.fetchall()]

    # Trata os dados para saída final
    def format_data(dt):
        if isinstance(dt, (datetime, date)):
            return dt.strftime("%d/%m/%Y")
        return ""

    final_results = []
    for row in results_raw:
        conjunto = row.get('conjunto', '')
        partes = conjunto.split(' - ', maxsplit=1)

        if len(partes) == 2:
            codigo = partes[0].strip()
            descricao = partes[1].strip()
            if descricao.startswith(codigo):
                descricao = descricao[len(codigo):].strip(" -")
        else:
            codigo = conjunto.strip()
            descricao = ""

        final_results.append({
            'ordem': row.get('ordem'),
            'codigo': codigo,
            'descricao': descricao,
            'qt_planejada': row.get('qt_planejada'),
            'cor': row.get('cor'),
            'quantidade_pendurada': row.get('quantidade_pendurada'),
            'cambao': row.get('cambao'),
            'tipo': row.get('tipo'),
            'data_carga': format_data(row.get('data_carga')),
            'data_fim': format_data(row.get('data_fim')),
            'col1': '',
            'col2': '',
            'col3': '',
            'col4': '',
            'operador_inicio': row.get('operador_inicio') or '',
            'operador_fim': row.get('operador_fim') or '',
            'col5': '',
            'data_pendura': format_data(row.get('data_pendura')),
        })

    return JsonResponse(final_results, safe=False)

def verificar_cor_cambao(cor_antes_de_finalizar, cambao_nome):
    # Verificar o tipo de pintura do cambão
    # cambao_nome = 'Único 3'  # Exemplo de ID do cambão
    # cor_antes_de_finalizar = 'Laranja' # Cor do cambao finalizado ou aberto

    cambao = Cambao.objects.filter(nome=cambao_nome).first()
    if 'manual' in cambao.nome.lower():
        print("Cambão é manual, não verificar cor.")
        return None

    tipo = cambao.tipo if cambao else None
    cor = cambao.cor if cambao else None

    print(cor)
    print(cor_antes_de_finalizar)

    # Tipo de pintura igual a PÓ?
    if tipo == 'PÓ':
        cambao_pecas_finalizadas = CambaoPecas.objects.filter(
            status='finalizada', 
            cambao__tipo=tipo
        ).exclude(
            cambao__nome__istartswith='manual'
        ).order_by('-data_fim')

        primeira_peca = cambao_pecas_finalizadas.first()


        print(f"{primeira_peca.cambao.nome} - {primeira_peca.peca_ordem.ordem.cor} {primeira_peca.cambao.tipo} - {primeira_peca.peca_ordem.id}")
        # Cor do útlimo cambão finalizada igual a cor do cambão atual?
        if primeira_peca.peca_ordem.ordem.cor == cor_antes_de_finalizar:
            print(f"Último cambão finalizado com cor {primeira_peca.peca_ordem.ordem.cor} e tipo {primeira_peca.cambao.tipo} é igual ao cambão atual.")
            return None
        else:
            print("Escolhendo peça do cmabão anterior ao acaso para fazer o teste.")
            if primeira_peca:
                ultima_data = primeira_peca.data_fim
                # Define a janela de proximidade (ex: 1 minuto)
                delta = timedelta(minutes=1)

                # Filtra todas as peças finalizadas próximas da última data
                cambao_pecas_finalizadas = cambao_pecas_finalizadas.filter(
                    data_fim__gte=ultima_data - delta
                )
            else:
                cambao_pecas_finalizadas = cambao_pecas_finalizadas.none()
                
            cont = cambao_pecas_finalizadas.count()
            if cont > 0:
                random_index = random.randint(0, cont - 1)
                peca_aleatoria = cambao_pecas_finalizadas[random_index]
                print("Escolher uma peça aleatória do cambão passado")
            else:
                peca_aleatoria = None

            if peca_aleatoria:
                print(f"Registrar teste com a peça: {peca_aleatoria.peca_ordem.id} - {peca_aleatoria.peca_ordem.ordem.cor} - {peca_aleatoria.cambao.tipo}")
            else:
                print("Nenhuma peça encontrada para registrar teste.")
            
            return peca_aleatoria
            
        
    elif tipo == 'PU':
        if 'manual' in cambao.nome.lower():
            print("Cambão é manual, não verificar cor.")
            return None
        
        # Pegando o nome do ultimo do cambão finalizado antes do atual (por ex: 7 aberto, 6 fechado)
        cambao_nome = str(int(cambao.nome) - 1)
        if cambao_nome == '0':
            cambao_nome = '8'
        qs = CambaoPecas.objects.filter(
            status='finalizada', 
            cambao__tipo=tipo,
        ).exclude(
            Q(cambao__nome__istartswith='manual') | Q(cambao__nome__istartswith='Único')
        ).exclude(
            cambao__id=cambao.id
        ).order_by('-data_fim')
        

        # Pega a data_fim mais recente
        primeira_peca_cambao_anterior = qs.first()

        print(f"cambao primeira peca {primeira_peca_cambao_anterior.peca_ordem.id} - {primeira_peca_cambao_anterior.peca_ordem.ordem.cor} e tipo {primeira_peca_cambao_anterior.cambao.tipo} e nome {primeira_peca_cambao_anterior.cambao.nome}")

        if primeira_peca_cambao_anterior.cambao.nome != cambao_nome:
            # último cambão finalizado não é o anterior ao atual (ex: 7 aberto, 5 fechado)
            print(f"Cambão anterior {cambao_nome} não encontrado, último encontrado foi {primeira_peca_cambao_anterior.cambao.nome}.")
            return None
        
        if primeira_peca_cambao_anterior.peca_ordem.ordem.cor == cor_antes_de_finalizar:
            print(f"Último cambão finalizado com cor {primeira_peca_cambao_anterior.peca_ordem.ordem.cor} e tipo {primeira_peca_cambao_anterior.cambao.tipo} é igual ao cambão atual.")
            return None
        else:
            # CASO 2:
            cor_primeira_peca = primeira_peca_cambao_anterior.peca_ordem.ordem.cor
            lista_pecas_selecao = []
            cambao_nome_inicial = int(cambao_nome)
            for cambao_peca in qs:
                if cambao_peca.peca_ordem.ordem.cor != cor_primeira_peca:
                    print(f"Encontrada peça com cor diferente da primeira finalizada antes do cambao atual: {cambao_peca.peca_ordem.id} - {cambao_peca.peca_ordem.ordem.cor} - {cambao_peca.cambao.tipo}")
                    # Registrar teste com essa peça
                    print(cambao_nome_inicial)
                    break

                lista_pecas_selecao.append(cambao_peca)

            
            print(f"Total de peças encontradas para seleção: {lista_pecas_selecao}")

            # Agrupa peças por cambao.id
            if len(lista_pecas_selecao) > 0:
                pecas_por_cambao = defaultdict(list)
                for p in lista_pecas_selecao:
                    pecas_por_cambao[p.cambao.nome].append(p)
                print(pecas_por_cambao)
                for chave, pecas in pecas_por_cambao.items():
                    print(f"{chave} - {[p.peca_ordem.id for p in pecas]}")

                peca_escolhida = random.choice(lista_pecas_selecao)

                # Sorteia 1 peça de todos os cambões
                print(f"{len(lista_pecas_selecao)} selecionadas para sorteio")
                print("Escolher uma peça aleatória de todos os cambãos anteriores com a mesma cor")

                # for peca in pecas_sorteadas:
                print(f"Registrar teste com a peça: {peca_escolhida.peca_ordem.id} - {peca_escolhida.peca_ordem.ordem.cor} - {peca_escolhida.cambao.tipo} - {peca_escolhida.cambao.nome}")

                return peca_escolhida
            else:
                print("Nenhuma peça encontrada para registrar teste.")
                return None
             
    # if request.method == 'POST':
    #     peca_ordem_id = request.POST.get('peca_ordem')
    #     polimerizacao = request.POST.get('polimerizacao',None)
        
    #     teste_funcional_pintura = TesteFuncional.objects.get(
    #             peca_ordem=peca_ordem_id
    #         )
        
    #     if teste_funcional_pintura:
    #         try:
    #             # teste_funcional_pintura.polimerizacao = 
    #         except Exception as e:
    #             print(e)


    #     peca_ordem = models.ForeignKey(PecasOrdem, on_delete=models.CASCADE, related_name='teste_funcional_peca_ordem_pintura')
    #     polimerizacao = models.BooleanField(null=True, blank=True) # apenas para PÓ
    #     aderencia = models.BooleanField(default=False)
    #     espessura_camada_1 = models.FloatField(null=True, blank=True)
    #     espessura_camada_2 = models.FloatField(null=True, blank=True)
    #     espessura_camada_3 = models.FloatField(null=True, blank=True)
    #     tonalidade = models.BooleanField(default=False)
    #     # status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pendente')
    #     observacao = models.TextField(null=True, blank=True)
    # pass