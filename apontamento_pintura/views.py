
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.timezone import now,localtime
from django.core.paginator import Paginator
from django.db.models import Sum, Q, Prefetch, Count, OuterRef, Subquery, F, Value, Avg, Value, CharField, Max, Min
from django.db.models.functions import Coalesce, Concat
from django.db import transaction, models
from django.shortcuts import get_object_or_404, render
from django.db import transaction, models, IntegrityError, connection

import json
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pytz import timezone
import random
from collections import defaultdict
from uuid import uuid4

from core.models import Profile
from apontamento_pintura.models import Retrabalho
from inspecao.models import Reinspecao, DadosExecucaoInspecao, Inspecao
from .models import PecasOrdem, CambaoPecas, Cambao, CambaoInterrupcao, TesteFuncional, Programa, Programacao, ControlePintura
from core.models import Ordem
from cadastro.models import Operador, Conjuntos
from inspecao.models import Inspecao
from core.utils import notificar_ordem

def planejamento(request):
    return render(request, "apontamento_pintura/planejamento.html")

def controle_pintura(request):
    registros = ControlePintura.objects.all()
    return render(request, "apontamento_pintura/controle_pintura.html", {"registros": registros})

def _controle_pintura_payload(registro):
    return {
        "id": registro.id,
        "data_iso": registro.data.strftime("%Y-%m-%d") if registro.data else "",
        "data": registro.data.strftime("%d/%m/%Y") if registro.data else "",
        "fornecedor": registro.fornecedor,
        "cor": registro.cor,
        "lote": registro.lote,
        "quantidade_tinta": registro.quantidade_tinta,
        "catalizador": registro.catalizador,
        "diluente": registro.diluente,
        "viscosidade": registro.viscosidade,
        "pintor": registro.pintor,
        "pistola": registro.pistola,
        "qnt_demaos": registro.qnt_demaos,
        "pressao_ar_1": registro.pressao_ar_1,
        "pressao_ar_2": registro.pressao_ar_2,
        "pressao_ar_3": registro.pressao_ar_3,
    }

def _campo_numerico_controle_pintura(data, campo, rotulo, inteiro=False):
    valor = (data.get(campo) or "").strip()
    if not valor:
        return "", None

    valor_normalizado = valor.replace(",", ".")
    try:
        numero = Decimal(valor_normalizado)
    except (InvalidOperation, ValueError):
        return None, JsonResponse({"error": f"{rotulo} deve ser numerico."}, status=400)

    if numero < 0:
        return None, JsonResponse({"error": f"{rotulo} deve ser maior ou igual a zero."}, status=400)
    if inteiro and numero != numero.to_integral_value():
        return None, JsonResponse({"error": f"{rotulo} deve ser um numero inteiro."}, status=400)

    if inteiro:
        return str(numero.quantize(Decimal("1"))), None
    return format(numero.normalize(), "f"), None

def _dados_controle_pintura_request(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return None, JsonResponse({"error": "JSON inválido"}, status=400)

    data_registro = None
    data_informada = (data.get("data") or "").strip()
    if data_informada:
        try:
            data_registro = datetime.strptime(data_informada, "%Y-%m-%d").date()
        except ValueError:
            return None, JsonResponse({"error": "Data inválida. Use YYYY-MM-DD."}, status=400)

    campos_numericos = {
        "lote": ("Lote", True),
        "quantidade_tinta": ("Quantidade de tinta", False),
        "viscosidade": ("Viscosidade", False),
        "pressao_ar_1": ("Pressao do ar", False),
        "pressao_ar_2": ("Pressao da tinta", False),
        "pressao_ar_3": ("Pressao da pistola", False),
    }
    valores_numericos = {}
    for campo, (rotulo, inteiro) in campos_numericos.items():
        valor, erro = _campo_numerico_controle_pintura(data, campo, rotulo, inteiro=inteiro)
        if erro:
            return None, erro
        valores_numericos[campo] = valor

    return {
        "data": data_registro,
        "fornecedor": (data.get("fornecedor") or "").strip(),
        "cor": (data.get("cor") or "").strip(),
        "lote": valores_numericos["lote"],
        "quantidade_tinta": valores_numericos["quantidade_tinta"],
        "catalizador": (data.get("catalizador") or "").strip(),
        "diluente": (data.get("diluente") or "").strip(),
        "viscosidade": valores_numericos["viscosidade"],
        "pintor": (data.get("pintor") or "").strip(),
        "pistola": (data.get("pistola") or "").strip(),
        "qnt_demaos": (data.get("qnt_demaos") or "").strip(),
        "pressao_ar_1": valores_numericos["pressao_ar_1"],
        "pressao_ar_2": valores_numericos["pressao_ar_2"],
        "pressao_ar_3": valores_numericos["pressao_ar_3"],
    }, None

def criar_controle_pintura(request):
    if request.method != "POST":
        return JsonResponse({"error": "Método não permitido"}, status=405)

    dados, erro = _dados_controle_pintura_request(request)
    if erro:
        return erro

    registro = ControlePintura.objects.create(**dados)

    return JsonResponse({"success": True, "registro": _controle_pintura_payload(registro)})

def editar_controle_pintura(request, pk):
    if request.method != "POST":
        return JsonResponse({"error": "Método não permitido"}, status=405)

    dados, erro = _dados_controle_pintura_request(request)
    if erro:
        return erro

    registro = get_object_or_404(ControlePintura, pk=pk)
    for campo, valor in dados.items():
        setattr(registro, campo, valor)
    registro.save()

    return JsonResponse({"success": True, "registro": _controle_pintura_payload(registro)})

def listar_programas(request):
    """
    API para listar programas de pintura com suas programações
    """
    data_inicial = request.GET.get('data_inicial', None)
    data_final = request.GET.get('data_final', None)
    tipo_tinta = request.GET.get('tipo_tinta', '')
    cor = request.GET.get('cor', '')
    
    # Filtros base
    filtros = Q()
    
    if tipo_tinta:
        filtros &= Q(tipo_tinta=tipo_tinta)
    
    if cor:
        filtros &= Q(cor__icontains=cor)
    
    # Buscar programas com prefetch de programações
    programas = Programa.objects.filter(filtros, status='programada').prefetch_related(
        Prefetch('programacao_pintura', queryset=Programacao.objects.select_related('peca_ordem'))
    ).order_by('-data_planejada', '-num_programa')
    
    # Montar resposta
    dados = []
    for programa in programas:
        programacoes = programa.programacao_pintura.all()
        
        pecas = []
        total_programado = 0
        total_em_processo = 0
        total_finalizado = 0
        
        for prog in programacoes:
            pecas.append({
                'id': prog.id,
                'peca_codigo': prog.peca_ordem.peca if prog.peca_ordem else 'N/A',
                'quantidade': prog.qtd_programacao,
                'peca_ordem_id': prog.peca_ordem.id if prog.peca_ordem else None,
                'ordem_id': prog.peca_ordem.ordem.id if prog.peca_ordem else None,
                'ordem': prog.peca_ordem.ordem.ordem if (prog.peca_ordem and prog.peca_ordem.ordem) else '',
                'data_carga': prog.peca_ordem.ordem.data_carga.strftime('%d/%m/%Y') if (prog.peca_ordem and prog.peca_ordem.ordem and prog.peca_ordem.ordem.data_carga) else '',
            })
            
            total_programado += prog.qtd_programacao
        
        dados.append({
            'id': programa.id,
            'num_programa': programa.num_programa,
            'tipo_tinta': programa.tipo_tinta,
            'cor': programa.cor,
            'prioridade': programa.prioridade or 'médio',
            'data_planejada': programa.data_planejada.strftime('%d/%m/%Y') if programa.data_planejada else 'N/A',
            'data_criacao': (programa.data_created - timedelta(hours=3)).strftime('%d/%m/%Y %H:%M'),
            'pecas': pecas,
            'total_programado': total_programado,
            'total_em_processo': total_em_processo,
            'total_finalizado': total_finalizado,
            'percentual_concluido': round((total_finalizado / total_programado * 100), 2) if total_programado > 0 else 0
        })
    
    return JsonResponse({
        'sucesso': True,
        'programas': dados,
        'total': len(dados)
    })


def _saldo_disponivel_programacao(peca_ordem, programa_id_excluir=None):
    qtd_pendurada = (
        CambaoPecas.objects.filter(peca_ordem=peca_ordem).aggregate(
            total=Sum("quantidade_pendurada", output_field=models.FloatField())
        )["total"]
        or 0
    )

    programacoes = Programacao.objects.filter(peca_ordem=peca_ordem)
    if programa_id_excluir:
        programacoes = programacoes.exclude(programa_id=programa_id_excluir)

    qtd_programada = (
        programacoes.aggregate(
            total=Sum("qtd_programacao", output_field=models.FloatField())
        )["total"]
        or 0
    )

    return max(0, peca_ordem.qtd_planejada - qtd_pendurada - qtd_programada)


def _saldo_disponivel_cambao(peca_ordem, cambao_id_excluir=None):
    pecas_no_cambao = CambaoPecas.objects.filter(peca_ordem=peca_ordem)
    if cambao_id_excluir:
        pecas_no_cambao = pecas_no_cambao.exclude(cambao_id=cambao_id_excluir)

    qtd_pendurada = (
        pecas_no_cambao.aggregate(
            total=Sum("quantidade_pendurada", output_field=models.FloatField())
        )["total"]
        or 0
    )

    return max(0, peca_ordem.qtd_planejada - qtd_pendurada)

@csrf_exempt
def deletar_programa(request):
    """
    API para deletar um programa
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            programa_id = data.get('programa_id')
            
            if not programa_id:
                return JsonResponse({'error': 'ID do programa é obrigatório'}, status=400)
            
            programa = get_object_or_404(Programa, id=programa_id)
            
            # Deletar as programações associadas
            Programacao.objects.filter(programa=programa).delete()
            
            # Deletar o programa
            programa.delete()
            
            return JsonResponse({
                'success': True,
                'message': 'Programa deletado com sucesso',
                'programa_id': programa_id
            })
        
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Método não permitido'}, status=405)

def programar_producao(request):
    """
    Tela para programar produção do setor de pintura
    """
    # Buscar conjuntos para a seleção
    conjuntos = Conjuntos.objects.all()
    operadores = Operador.objects.all()
    
    context = {
        'conjuntos': conjuntos,
        'operadores': operadores
    }
    return render(request, "apontamento_pintura/programar_producao.html", context)

@csrf_exempt
def iniciar_programa(request):
    """
    API para iniciar um programa - atualiza o status para 'finalizada'
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            programa_id = data.get('programa_id')
            
            if not programa_id:
                return JsonResponse({'error': 'ID do programa é obrigatório'}, status=400)
            
            programa = get_object_or_404(Programa, id=programa_id)
            programa.status = 'finalizada'
            programa.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Programa iniciado com sucesso',
                'programa_id': programa.id
            })
        
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Método não permitido'}, status=405)

def ordens_criadas(request):
    filtros = {}
    filtros_peca = {}

    data_carga = request.GET.get("data_carga", None)
    type_template = request.GET.get("type_template")

    if data_carga:
        try:
            if data_carga and data_carga.strip():
                data_carga = datetime.strptime(data_carga, "%Y-%m-%d").date()
                filtros["data_carga"] = data_carga
            else:
                data_carga = now().date()
                filtros["data_carga"] = data_carga
        except ValueError:
            data_carga = now().date()
            filtros["data_carga"] = data_carga

    cor = request.GET.get("cor", "")
    conjunto = request.GET.get("conjunto", "")
    data_programacao = request.GET.get("data-programada", "")

    if cor:
        filtros["cor"] = cor
    if data_programacao:
        filtros["data_programacao"] = data_programacao
    if conjunto:
        filtros_peca["peca__contains"] = conjunto

    primeira_peca = PecasOrdem.objects.filter(
        ordem=OuterRef("pk"), **filtros_peca
    ).order_by("id")

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

    # soma do que já foi programado (Programacao)
    soma_qtd_programada = (
        Programacao.objects.filter(peca_ordem__ordem=OuterRef("pk"))
        .values("peca_ordem__ordem")
        .annotate(
            total_qtd_programada=Sum(
                "qtd_programacao", output_field=models.FloatField()
            )
        )
        .values("total_qtd_programada")
    )

    qt_planejada = primeira_peca.values("qtd_planejada")[:1]

    ordens_queryset = (
        Ordem.objects.filter(grupo_maquina="pintura", excluida=False, **filtros)
        .annotate(
            peca_ordem_id=Subquery(primeira_peca.values("id")[:1]),
            peca_codigo=Subquery(primeira_peca.values("peca")[:1]),
            peca_qt_planejada=Subquery(
                qt_planejada, output_field=models.FloatField()
            ),
            soma_qtd_pendurada=Coalesce(
                Subquery(soma_qtd_pendurada, output_field=models.FloatField()),
                Value(0.0),
                output_field=models.FloatField(),
            ),
            soma_qtd_programada=Coalesce(
                Subquery(soma_qtd_programada, output_field=models.FloatField()),
                Value(0.0),
                output_field=models.FloatField(),
            ),
        )
    )

    # 🔧 diferença de lógica apenas para programação
    if type_template == "programacao":
        ordens_queryset = ordens_queryset.annotate(
            qt_restante=F("peca_qt_planejada")
            - F("soma_qtd_pendurada")
            - F("soma_qtd_programada")
        )
    else:
        ordens_queryset = ordens_queryset.annotate(
            qt_restante=F("peca_qt_planejada") - F("soma_qtd_pendurada")
        )

    ordens_queryset = (
        ordens_queryset.filter(qt_restante__gt=0)
        .order_by("-status_prioridade", "data_programacao")
    )

    primeira_data = (
        ordens_queryset.first().data_programacao
        if ordens_queryset.exists()
        else None
    )
    data_programacao_formatada = (
        primeira_data.strftime("%d/%m/%Y") if primeira_data else None
    )

    primeira_data_carga = (
        ordens_queryset.first().data_carga
        if ordens_queryset.exists()
        else None
    )
    data_programacao_formatada_carga = (
        primeira_data_carga if primeira_data_carga else None
    )

    return JsonResponse(
        {
            "ordens": list(ordens_queryset.values()),
            "data_programacao": data_programacao_formatada,
            "data_carga": data_programacao_formatada_carga,
        }
    )



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
                
                lote_em_andamento = (
                    CambaoPecas.objects
                    .filter(
                        cambao=cambao,
                        status__in=["pendurada", "programada"],
                        data_fim__isnull=True,
                    )
                    .values_list("identificador_lote", flat=True)
                    .first()
                )

                # Criar as associações no cambão
                identificador_lote = lote_em_andamento or uuid4()
                operador_obj = get_object_or_404(Operador, pk=operador_inicial)
                for peca_ordem, quantidade in pecas_selecionadas:
                    CambaoPecas.objects.update_or_create(
                        cambao=cambao,
                        peca_ordem=peca_ordem,
                        status="pendurada",
                        defaults={
                            "identificador_lote": identificador_lote,
                            "quantidade_pendurada": quantidade,
                            "data_pendura": now(),
                            "operador_inicio": operador_obj,
                        },
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
def adicionar_pecas_programacao(request):
    """
    Cria uma programação de peças para pintura.
    {
        "peca_ordens": [12, 15],
        "quantidade": [1, 1],
        "cor": "Azul"  # cor do cambão
        "tipo":"PU"
    }
    """

    if request.method == "POST":
        try:
            data = json.loads(request.body)

            peca_ordens = data.get("peca_ordens", [])  # Lista de IDs de PecasOrdem
            quantidades = data.get(
                "quantidade", []
            )  # Lista de quantidades correspondentes
            cor = data.get("cor")
            tipo_tinta = data.get("tipo")
            data_planejamento = data.get("data_planejamento")

            if len(peca_ordens) != len(quantidades):
                return JsonResponse(
                    {"error": "A quantidade de peças e de IDs deve ser a mesma!"},
                    status=400,
                )

            # cria o programa
            maior_valor_programa = Programa.objects.aggregate(
                max_num=models.Max('num_programa')
            )['max_num'] or 0

            with transaction.atomic():
                programa = Programa.objects.create(
                    num_programa=maior_valor_programa + 1,  # deve ser o maior valor do num_programa +1
                    cor=cor,
                    tipo_tinta=tipo_tinta,
                    data_planejada=data_planejamento
                )

                # cria programacao atrelada ao programa
                pecas_selecionadas = []

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

                    # Verificar quantidade disponível para programar
                    qtd_programacao = (
                        CambaoPecas.objects.filter(peca_ordem=peca_ordem).aggregate(
                            Sum("quantidade_pendurada")
                        )["quantidade_pendurada__sum"]
                        or 0
                    )

                    qtd_disponivel = peca_ordem.qtd_planejada - qtd_programacao
                    if quantidade > qtd_disponivel:
                        return JsonResponse(
                            {
                                "error": f"A peça {peca_ordem.peca} só pode ter mais {qtd_disponivel} unidades penduradas!"
                            },
                            status=400,
                        )

                    pecas_selecionadas.append((peca_ordem, quantidade))

                for peca_ordem, quantidade in pecas_selecionadas:
                    Programacao.objects.create(
                        programa=programa,
                        peca_ordem=peca_ordem,
                        qtd_programacao=quantidade,
                    )

                # Notifica o websocket
                notificar_ordem(peca_ordem.ordem)

                return JsonResponse(
                    {"success": True, "message": "Peças programadas com sucesso!"}
                )

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Método não permitido!"}, status=405)

@csrf_exempt
def editar_programa(request):
    """
    Edita um programa de pintura em lote.
    Espera:
    {
        "programa_id": 1,
        "itens": [
            {"id": 10, "peca_ordem_id": 25, "quantidade": 4},
            {"peca_ordem_id": 30, "quantidade": 2}
        ]
    }
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'MÃ©todo nÃ£o permitido'}, status=405)

    try:
        data = json.loads(request.body)
        programa_id = data.get('programa_id')
        itens = data.get('itens', [])

        if not programa_id:
            return JsonResponse({'error': 'ID do programa Ã© obrigatÃ³rio'}, status=400)

        if not itens:
            return JsonResponse({'error': 'Informe ao menos um item para o programa'}, status=400)

        programa = get_object_or_404(Programa, id=programa_id)
        programacoes_atuais = {
            programacao.id: programacao
            for programacao in Programacao.objects.filter(programa=programa)
        }

        quantidades_por_peca = defaultdict(float)
        itens_normalizados = []

        for item in itens:
            programacao_id = item.get('id')
            peca_ordem_id = item.get('peca_ordem_id')
            quantidade = item.get('quantidade')

            if not peca_ordem_id:
                return JsonResponse({'error': 'Toda linha precisa ter um conjunto selecionado'}, status=400)

            try:
                quantidade = float(quantidade)
            except (TypeError, ValueError):
                return JsonResponse({'error': 'Quantidade invÃ¡lida informada'}, status=400)

            if quantidade <= 0:
                return JsonResponse({'error': 'A quantidade deve ser maior que zero'}, status=400)

            peca_ordem = get_object_or_404(
                PecasOrdem.objects.select_related('ordem'),
                id=peca_ordem_id,
            )

            if peca_ordem.ordem.cor != programa.cor:
                return JsonResponse(
                    {'error': f'A peÃ§a {peca_ordem.peca} nÃ£o pertence Ã  cor do programa.'},
                    status=400
                )

            quantidades_por_peca[peca_ordem.id] += quantidade
            itens_normalizados.append({
                'id': int(programacao_id) if programacao_id else None,
                'peca_ordem': peca_ordem,
                'quantidade': quantidade,
            })

        for peca_ordem_id, quantidade_total in quantidades_por_peca.items():
            peca_ordem = next(
                item['peca_ordem'] for item in itens_normalizados if item['peca_ordem'].id == peca_ordem_id
            )
            qtd_disponivel = _saldo_disponivel_programacao(peca_ordem, programa_id_excluir=programa.id)

            if quantidade_total > qtd_disponivel:
                return JsonResponse(
                    {
                        'error': (
                            f'A peça {peca_ordem.peca} só possui '
                            f'{qtd_disponivel} unidades disponíveis para planejamento.'
                        )
                    },
                    status=400
                )

        with transaction.atomic():
            ids_recebidos = set()

            for item in itens_normalizados:
                programacao_id = item['id']
                peca_ordem = item['peca_ordem']
                quantidade = item['quantidade']

                if programacao_id:
                    programacao = programacoes_atuais.get(programacao_id)
                    if not programacao:
                        return JsonResponse(
                            {'error': 'Uma das linhas enviadas nÃ£o pertence ao programa informado'},
                            status=400
                        )

                    programacao.peca_ordem = peca_ordem
                    programacao.qtd_programacao = quantidade
                    programacao.save(update_fields=['peca_ordem', 'qtd_programacao'])
                    ids_recebidos.add(programacao.id)
                else:
                    nova_programacao = Programacao.objects.create(
                        programa=programa,
                        peca_ordem=peca_ordem,
                        qtd_programacao=quantidade,
                    )
                    ids_recebidos.add(nova_programacao.id)

            Programacao.objects.filter(programa=programa).exclude(id__in=ids_recebidos).delete()

        return JsonResponse({'success': True, 'message': 'Programa atualizado com sucesso'})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def remover_peca_programa(request):
    """
    API para remover uma peça (Programacao) de um programa
    Espera: {"programacao_id": 123}
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            programacao_id = data.get('programacao_id')
            if not programacao_id:
                return JsonResponse({'error': 'ID da programação é obrigatório'}, status=400)
            programacao = get_object_or_404(Programacao, id=programacao_id)
            programacao.delete()
            return JsonResponse({'success': True, 'message': 'Peça removida com sucesso', 'programacao_id': programacao_id})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Método não permitido'}, status=405)

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

            operador = get_object_or_404(Operador, id=operador_id)

            with transaction.atomic():
                cambao = get_object_or_404(Cambao.objects.select_for_update(), id=cambao_id)

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

                # Pré-validação de todas as peças dentro da transação (evita race condition)
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
                        quantidade_pendurada = f"{item.quantidade_pendurada:g}"
                        quantidade_restante = f"{qtd_restante:g}"
                        quantidade_planejada = f"{peca_ordem_original.qtd_planejada:g}"
                        quantidade_ja_finalizada = f"{qtd_finalizadas:g}"

                        return JsonResponse(
                            {
                                "error": (
                                    f"Não foi possível finalizar o cambão porque a peça "
                                    f"'{peca_ordem_original.peca}' da ordem "
                                    f"'{peca_ordem_original.ordem.ordem}' não tem saldo disponível. "
                                    f"Tentativa de finalizar: {quantidade_pendurada}. "
                                    f"Saldo restante: {quantidade_restante}. "
                                    f"Planejado da peça: {quantidade_planejada}. "
                                    f"Já finalizado anteriormente: {quantidade_ja_finalizada}. "
                                    f"Verifique se essa peça já foi concluída ou se o planejamento precisa ser ajustado."
                                )
                            },
                            status=400,
                        )

                # Só verificar a cor do cambao caso na finalização se o tipo da cor for PÓ
                if tipo_po:
                    # Verificar cor e sortear uma peca
                    peca_sorteada = verificar_cor_cambao(cambao.cor, cambao.nome)
                    if peca_sorteada:
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
                cambao.cor = ''
                cambao.data_fim = now()
                cambao.save()
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

@csrf_exempt
def interromper_cambao(request):
    """
    Interrompe um cambão em uso, registrando o motivo e alterando o status.
    """
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            
            cambao_id = data.get("cambao_id")
            motivo = data.get("motivo")

            if not cambao_id:
                return JsonResponse(
                    {"error": "ID do cambão é obrigatório!"}, status=400
                )

            if not motivo or not motivo.strip():
                return JsonResponse(
                    {"error": "O motivo da interrupção é obrigatório!"}, status=400
                )

            cambao = get_object_or_404(Cambao, id=cambao_id)

            if cambao.status != "em uso":
                return JsonResponse(
                    {"error": "Apenas cambões em uso podem ser interrompidos!"}, status=400
                )

            # Altera o status do cambão para interrompido
            cambao.status = "interrompido"
            cambao.save()

            # Cria o registro da interrupção
            interrupcao = CambaoInterrupcao.objects.create(
                cambao=cambao,
                motivo=motivo
            )

            return JsonResponse(
                {
                    "success": True,
                    "message": f"Cambão {cambao.nome} interrompido com sucesso!",
                    "interrupcao_id": interrupcao.id
                }
            )

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Método não permitido!"}, status=405)

@csrf_exempt
def retornar_cambao(request):
    """
    Retorna um cambão interrompido para o status 'em uso'.
    """
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            
            cambao_id = data.get("cambao_id")

            if not cambao_id:
                return JsonResponse(
                    {"error": "ID do cambão é obrigatório!"}, status=400
                )

            cambao = get_object_or_404(Cambao, id=cambao_id)

            if cambao.status != "interrompido":
                return JsonResponse(
                    {"error": "Apenas cambões interrompidos podem retornar!"}, status=400
                )

            # Busca a última interrupção ativa (sem data_fim)
            interrupcao_ativa = CambaoInterrupcao.objects.filter(
                cambao=cambao,
                data_fim__isnull=True
            ).order_by('-data_inicio').first()

            if interrupcao_ativa:
                # Finaliza a interrupção
                interrupcao_ativa.data_fim = now()
                interrupcao_ativa.save()

            # Altera o status do cambão de volta para em uso
            cambao.status = "em uso"
            cambao.save()

            return JsonResponse(
                {
                    "success": True,
                    "message": f"Cambão {cambao.nome} retornou ao processo com sucesso!",
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
    Retorna os cambões que estão em processo ou interrompidos, agrupando suas peças corretamente.

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
                "cambao_status": "em uso",
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
        pecas_qs = cambao.pecas_no_cambao.all()  # usa prefetch cache (status="pendurada")
        pecas = [
            {
                "id": peca.id,
                "peca_ordem_id": peca.peca_ordem.id,
                "ordem_id": peca.peca_ordem.ordem.id,
                "ordem": peca.peca_ordem.ordem.ordem,
                "peca": peca.peca_ordem.peca,
                "quantidade_pendurada": peca.quantidade_pendurada,
                "data_carga": peca.peca_ordem.ordem.data_carga,
            }
            for peca in pecas_qs
        ]
        primeira_peca = pecas_qs.first()  # permanece no prefetch cache; evita nova query ao DB

        resultado.append({
            "id": cambao.id,
            "cor": cambao.cor,
            "pecas": pecas,
            "data_pendura": primeira_peca.data_pendura if primeira_peca else None,
            "status": "pendurada",
            "cambao_status": cambao.status,  # Adiciona o status do cambão (em uso, interrompido, etc)
            "tipo": cambao.tipo,
            "nome": cambao.nome,
            # "data_fim": cambao.data_fim
        })

    return JsonResponse({"cambao_em_processo": resultado})


def itens_disponiveis_cambao(request):
    cambao_id = request.GET.get("cambao_id")
    termo = (request.GET.get("q") or "").strip()

    if not cambao_id:
        return JsonResponse({"error": "ID do cambão é obrigatório"}, status=400)

    cambao = get_object_or_404(Cambao, id=cambao_id)
    data_carga = request.GET.get("data_carga")

    if not termo or len(termo.strip()) < 2:
        return JsonResponse({"itens": []})

    filtros = {
        "grupo_maquina": "pintura",
        "excluida": False,
        "cor": cambao.cor,
    }
    if data_carga:
        filtros["data_carga"] = data_carga

    filtros_peca = {"peca__contains": termo}

    primeira_peca = PecasOrdem.objects.filter(
        ordem=OuterRef("pk"), **filtros_peca
    ).order_by("id")

    soma_qtd_pendurada = (
        CambaoPecas.objects.filter(peca_ordem__ordem=OuterRef("pk"))
        .exclude(cambao_id=cambao.id)
        .values("peca_ordem__ordem")
        .annotate(
            total_quantidade_pendurada=Sum(
                "quantidade_pendurada", output_field=models.FloatField()
            )
        )
        .values("total_quantidade_pendurada")
    )

    qt_planejada = primeira_peca.values("qtd_planejada")[:1]

    ordens_queryset = (
        Ordem.objects.filter(**filtros)
        .annotate(
            peca_ordem_id=Subquery(primeira_peca.values("id")[:1]),
            peca_codigo=Subquery(primeira_peca.values("peca")[:1]),
            peca_qt_planejada=Subquery(
                qt_planejada, output_field=models.FloatField()
            ),
            soma_qtd_pendurada=Coalesce(
                Subquery(soma_qtd_pendurada, output_field=models.FloatField()),
                Value(0.0),
                output_field=models.FloatField(),
            ),
        )
        .annotate(
            qt_restante=F("peca_qt_planejada") - F("soma_qtd_pendurada")
        )
        .filter(
            peca_ordem_id__isnull=False,
            qt_restante__gt=0,
        )
        .order_by("-status_prioridade", "data_programacao")[:50]
    )

    itens = [
        {
            "peca_ordem_id": item["peca_ordem_id"],
            "ordem_id": item["id"],
            "ordem": item["ordem"],
            "peca": item["peca_codigo"],
            "saldo_disponivel": item["qt_restante"],
            "qtd_planejada": item["peca_qt_planejada"],
            "data_carga": item["data_carga"].strftime("%d/%m/%Y")
            if item["data_carga"]
            else "",
        }
        for item in ordens_queryset.values(
            "id",
            "ordem",
            "peca_ordem_id",
            "peca_codigo",
            "peca_qt_planejada",
            "qt_restante",
            "data_carga",
        )
    ]

    return JsonResponse({"itens": itens})


@csrf_exempt
def editar_cambao(request):
    """
    Edita as peças penduradas em um cambão.
    Espera:
    {
        "cambao_id": 1,
        "itens": [
            {"id": 10, "peca_ordem_id": 25, "quantidade": 4},
            {"peca_ordem_id": 30, "quantidade": 2}
        ]
    }
    """
    if request.method != "POST":
        return JsonResponse({"error": "Método não permitido"}, status=405)

    try:
        data = json.loads(request.body)
        cambao_id = data.get("cambao_id")
        itens = data.get("itens", [])

        if not cambao_id:
            return JsonResponse({"error": "ID do cambão é obrigatório"}, status=400)

        cambao = get_object_or_404(Cambao, id=cambao_id)
        registros_atuais = {
            registro.id: registro
            for registro in CambaoPecas.objects.filter(cambao=cambao, status="pendurada")
        }
        ordens_ids_anteriores = {
            registro.peca_ordem.ordem_id
            for registro in registros_atuais.values()
            if registro.peca_ordem_id
        }

        if not itens:
            with transaction.atomic():
                CambaoPecas.objects.filter(cambao=cambao, status="pendurada").delete()
                cambao.status = "livre"
                cambao.cor = ""
                cambao.save(update_fields=["status", "cor"])
            for ordem in Ordem.objects.filter(id__in=ordens_ids_anteriores):
                notificar_ordem(ordem)
            return JsonResponse({"success": True, "message": "Cambão atualizado com sucesso"})

        quantidades_por_peca = defaultdict(float)
        itens_normalizados = []

        for item in itens:
            registro_id = item.get("id")
            peca_ordem_id = item.get("peca_ordem_id")
            quantidade = item.get("quantidade")

            if not peca_ordem_id:
                return JsonResponse(
                    {"error": "Toda linha precisa ter uma peça selecionada"},
                    status=400,
                )

            try:
                quantidade = float(quantidade)
            except (TypeError, ValueError):
                return JsonResponse({"error": "Quantidade inválida informada"}, status=400)

            if quantidade <= 0:
                return JsonResponse(
                    {"error": "A quantidade deve ser maior que zero"},
                    status=400,
                )

            peca_ordem = get_object_or_404(
                PecasOrdem.objects.select_related("ordem"),
                id=peca_ordem_id,
            )
            registro_existente = registros_atuais.get(int(registro_id)) if registro_id else None
            mantendo_peca_original = (
                registro_existente is not None
                and registro_existente.peca_ordem_id == peca_ordem.id
            )

            if not mantendo_peca_original and peca_ordem.ordem.cor != cambao.cor:
                return JsonResponse(
                    {"error": f"A peça {peca_ordem.peca} não pertence à cor do cambão."},
                    status=400,
                )

            if False and not mantendo_peca_original and peca_ordem.tipo != cambao.tipo:
                return JsonResponse(
                    {"error": f"A peça {peca_ordem.peca} não pertence ao tipo do cambão."},
                    status=400,
                )

            quantidades_por_peca[peca_ordem.id] += quantidade
            itens_normalizados.append(
                {
                    "id": int(registro_id) if registro_id else None,
                    "peca_ordem": peca_ordem,
                    "quantidade": quantidade,
                }
            )

        for peca_ordem_id, quantidade_total in quantidades_por_peca.items():
            peca_ordem = next(
                item["peca_ordem"]
                for item in itens_normalizados
                if item["peca_ordem"].id == peca_ordem_id
            )
            saldo_disponivel = _saldo_disponivel_cambao(
                peca_ordem,
                cambao_id_excluir=cambao.id,
            )

            if quantidade_total > saldo_disponivel:
                return JsonResponse(
                    {
                        "error": (
                            f"A peça {peca_ordem.peca} só possui "
                            f"{saldo_disponivel:g} unidades disponíveis para este cambão."
                        )
                    },
                    status=400,
                )

        with transaction.atomic():
            ordens_ids = set(ordens_ids_anteriores)
            lote_atual = (
                CambaoPecas.objects.filter(cambao=cambao, status="pendurada")
                .values_list("identificador_lote", flat=True)
                .first()
            ) or uuid4()

            ids_recebidos = set()

            for item in itens_normalizados:
                registro_id = item["id"]
                peca_ordem = item["peca_ordem"]
                quantidade = item["quantidade"]

                if registro_id:
                    registro = registros_atuais.get(registro_id)
                    if not registro:
                        return JsonResponse(
                            {"error": "Uma das linhas enviadas não pertence ao cambão informado"},
                            status=400,
                        )

                    registro.peca_ordem = peca_ordem
                    registro.quantidade_pendurada = quantidade
                    registro.identificador_lote = lote_atual
                    registro.save(
                        update_fields=[
                            "peca_ordem",
                            "quantidade_pendurada",
                            "identificador_lote",
                        ]
                    )
                    ids_recebidos.add(registro.id)
                else:
                    novo_registro = CambaoPecas.objects.create(
                        identificador_lote=lote_atual,
                        cambao=cambao,
                        peca_ordem=peca_ordem,
                        quantidade_pendurada=quantidade,
                        data_pendura=now(),
                        status="pendurada",
                    )
                    ids_recebidos.add(novo_registro.id)

            CambaoPecas.objects.filter(cambao=cambao, status="pendurada").exclude(
                id__in=ids_recebidos
            ).delete()

            cambao.status = "em uso"
            cambao.save(update_fields=["status"])

            ordens_ids.update(
                item["peca_ordem"].ordem.id
                for item in itens_normalizados
            )
            for ordem in Ordem.objects.filter(id__in=ordens_ids):
                notificar_ordem(ordem)

        return JsonResponse({"success": True, "message": "Cambão atualizado com sucesso"})

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

def listar_operadores(request):

    operadores = Operador.objects.filter(setor__nome="pintura")

    return JsonResponse({"operadores": list(operadores.values())})

def listar_cores_carga(request):
    data_carga_str = (request.GET.get("data_carga") or "").strip()

    try:
        from datetime import datetime as _dt
        data_carga = _dt.strptime(data_carga_str, "%Y-%m-%d").date() if data_carga_str else now().date()
    except ValueError:
        return JsonResponse({"error": "Formato de data inválido. Use YYYY-MM-DD."}, status=400)

    cores = sorted(
        cor for cor in (
            Ordem.objects.filter(data_carga=data_carga, grupo_maquina="pintura")
            .values_list("cor", flat=True)
            .distinct()
        )
        if cor is not None and str(cor).strip() != ""
    )

    return JsonResponse({"cores": cores})

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
        'cinza escuro': 'CE',
    }

    brasil_tz = timezone("America/Sao_Paulo")
    hoje = now().astimezone(brasil_tz).date()

    data_inicio_str = request.GET.get('data_inicio')
    data_fim_str = request.GET.get('data_fim')

    try:
        data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date() if data_inicio_str else hoje - timedelta(days=1)
        data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date() if data_fim_str else hoje
    except ValueError:
        return JsonResponse({'erro': 'Formato de data inválido. Use YYYY-MM-DD.'}, status=400)

    inicio_utc = brasil_tz.localize(datetime(data_inicio.year, data_inicio.month, data_inicio.day, 0, 0, 0))
    fim_utc = brasil_tz.localize(datetime(data_fim.year, data_fim.month, data_fim.day, 23, 59, 59))

    dados = (
        PecasOrdem.objects
        .filter(
            qtd_boa__gt=0,
            operador_fim__isnull=False,
            data__gte=inicio_utc,
            data__lte=fim_utc,
        )
        .annotate(
            ordem_numero=F('ordem__ordem'),
            cor=F('ordem__cor'),
            data_carga=F('ordem__data_carga'),
            data_apontamento=F('data'),
            operador_nome=Concat(
                F('operador_fim__matricula'),
                Value(' - '),
                F('operador_fim__nome'),
                output_field=CharField()
            ),
        )
        .values(
            'ordem_numero',
            'peca',
            'qtd_planejada',
            'cor',
            'qtd_boa',
            'tipo',
            'data_carga',
            'data_apontamento',
            'operador_nome',
        )
        .order_by('data_apontamento')
        .iterator(chunk_size=1000)
    )

    resultado = []
    for d in dados:
        peca = d['peca'] or ''
        parte_direita = peca.partition(" - ")[2]

        resultado.append({
            'ordem': d['ordem_numero'],
            'codigo': peca.split(" - ")[0] if peca else '',
            'descricao': parte_direita,
            'qtd_planejada': d['qtd_planejada'],
            'cor': mapa_cor.get(d['cor'], d['cor']),
            'qtd_boa': d['qtd_boa'],
            'col5': '',
            'tipo': d['tipo'],
            'data_carga': d['data_carga'],
            'data_apontamento': (d['data_apontamento'] - timedelta(hours=3)).date() if d['data_apontamento'] else None,
            'col1': '',
            'col2': '',
            'col3': '',
            'col4': '',
            'operador': d['operador_nome'] or '',
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

    brasil_tz = timezone("America/Sao_Paulo")
    hoje = now().astimezone(brasil_tz).date()

    data_inicio_str = request.GET.get('data_inicio')
    data_fim_str = request.GET.get('data_fim')

    try:
        data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date() if data_inicio_str else hoje
        data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date() if data_fim_str else hoje
    except ValueError:
        return JsonResponse({'erro': 'Formato de data inválido. Use YYYY-MM-DD.'}, status=400)

    cursor = connection.cursor()
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
            WHERE (cp.data_pendura AT TIME ZONE 'America/Sao_Paulo')::date BETWEEN %s AND %s
            ORDER BY o.ordem, cp.data_pendura;
        """, [data_inicio, data_fim])

    # Trata os dados para saída final
    def format_data(dt):
        if isinstance(dt, (datetime, date)):
            return dt.strftime("%d/%m/%Y")
        return ""

    final_results = []
    for row in cursor:
        (
            ordem,
            conjunto,
            qt_planejada,
            cor,
            quantidade_pendurada,
            cambao,
            tipo,
            data_carga,
            data_fim,
            operador_inicio,
            operador_fim,
            data_pendura,
        ) = row

        conjunto = conjunto or ''
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
            'ordem': ordem,
            'codigo': codigo,
            'descricao': descricao,
            'qt_planejada': qt_planejada,
            'cor': cor,
            'quantidade_pendurada': quantidade_pendurada,
            'cambao': cambao,
            'tipo': tipo,
            'data_carga': format_data(data_carga),
            'data_fim': format_data(data_fim),
            'col1': '',
            'col2': '',
            'col3': '',
            'col4': '',
            'operador_inicio': operador_inicio or '',
            'operador_fim': operador_fim or '',
            'col5': '',
            'data_pendura': format_data(data_pendura),
        })

    cursor.close()
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


def historico_pintura(request):
    brasil_tz = timezone("America/Sao_Paulo")
    operadores = Operador.objects.order_by("nome")
    camboes = Cambao.objects.filter(ativo=True).order_by("nome")
    return render(
        request,
        "apontamento_pintura/historico.html",
        {"operadores": operadores, "camboes": camboes},
    )


def api_historico_pintura(request):
    if request.method != "GET":
        return JsonResponse({"error": "Método não permitido"}, status=405)

    brasil_tz = timezone("America/Sao_Paulo")

    data_inicio_str = request.GET.get("data_inicio", "")
    data_fim_str = request.GET.get("data_fim", "")
    tipo = request.GET.get("tipo", "").strip()
    operador_id = request.GET.get("operador", "").strip()
    cambao_id = request.GET.get("cambao", "").strip()
    status_filtro = request.GET.get("status", "").strip()
    pesquisar = request.GET.get("pesquisar", "").strip()
    pagina = int(request.GET.get("pagina", 1))
    por_pagina = int(request.GET.get("por_pagina", 25))

    qs = (
        CambaoPecas.objects
        .select_related(
            "cambao",
            "peca_ordem",
            "peca_ordem__ordem",
            "operador_inicio",
            "peca_ordem__operador_fim",
        )
        .exclude(peca_ordem__isnull=True)
    )

    if data_inicio_str:
        try:
            di = datetime.strptime(data_inicio_str, "%Y-%m-%d").date()
            qs = qs.filter(data_pendura__date__gte=di)
        except ValueError:
            pass

    if data_fim_str:
        try:
            df = datetime.strptime(data_fim_str, "%Y-%m-%d").date()
            qs = qs.filter(data_pendura__date__lte=df)
        except ValueError:
            pass

    if tipo:
        qs = qs.filter(peca_ordem__tipo=tipo)

    if operador_id:
        qs = qs.filter(
            Q(operador_inicio_id=operador_id) | Q(peca_ordem__operador_fim_id=operador_id)
        )

    if cambao_id:
        qs = qs.filter(cambao_id=cambao_id)

    if status_filtro:
        qs = qs.filter(status=status_filtro)

    if pesquisar:
        qs = qs.filter(
            Q(peca_ordem__peca__icontains=pesquisar)
            | Q(peca_ordem__ordem__id__icontains=pesquisar)
            | Q(cambao__cor__icontains=pesquisar)
        )

    qs = qs.order_by("-data_pendura")

    total = qs.count()
    paginator = Paginator(qs, por_pagina)
    page_obj = paginator.get_page(pagina)

    def fmt_dt(dt):
        if dt is None:
            return None
        return localtime(dt).strftime("%d/%m/%Y %H:%M")

    def duracao_minutos(inicio, fim):
        if inicio and fim:
            delta = fim - inicio
            mins = int(delta.total_seconds() // 60)
            h, m = divmod(mins, 60)
            return f"{h}h {m:02d}min"
        return None

    registros = []
    for cp in page_obj:
        po = cp.peca_ordem
        ordem = po.ordem

        peca_parts = po.peca.split(" - ", maxsplit=1)
        codigo = peca_parts[0].strip()
        descricao = peca_parts[1].strip() if len(peca_parts) == 2 else ""

        registros.append({
            "id": cp.id,
            "data_pendura": fmt_dt(cp.data_pendura),
            "data_fim": fmt_dt(cp.data_fim),
            "duracao": duracao_minutos(cp.data_pendura, cp.data_fim),
            "cambao": cp.cambao.nome,
            "cambao_cor": cp.cambao.cor,
            "tipo": po.tipo,
            "codigo": codigo,
            "descricao": descricao,
            "ordem_id": ordem.id,
            "data_carga": ordem.data_carga.strftime("%d/%m/%Y") if ordem.data_carga else None,
            "quantidade_pendurada": cp.quantidade_pendurada,
            "qtd_planejada": po.qtd_planejada,
            "qtd_boa": po.qtd_boa,
            "qtd_morta": po.qtd_morta,
            "operador_inicio": cp.operador_inicio.nome if cp.operador_inicio else None,
            "operador_fim": po.operador_fim.nome if po.operador_fim else None,
            "status": cp.status,
            "identificador_lote": cp.identificador_lote,
        })

    return JsonResponse({
        "registros": registros,
        "total": total,
        "pagina_atual": page_obj.number,
        "total_paginas": paginator.num_pages,
        "por_pagina": por_pagina,
    })
