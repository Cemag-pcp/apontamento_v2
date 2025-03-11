from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.timezone import now
from django.db.models import Sum, F, ExpressionWrapper, FloatField, Value, Avg
from django.db import transaction, models, IntegrityError
from django.shortcuts import get_object_or_404
from django.db.models.functions import Coalesce
from django.shortcuts import render
from django.core.exceptions import ObjectDoesNotExist

import json
from datetime import datetime
import traceback

from .models import PecasOrdem
from core.models import SolicitacaoPeca, Ordem, OrdemProcesso, MaquinaParada, MotivoInterrupcao, MotivoMaquinaParada
from cadastro.models import Operador, Maquina, Pecas, Conjuntos

@csrf_exempt
def criar_ordem(request):
    """
    API para criar múltiplas ordens para o setor de montagem.
    Exemplo de carga JSON esperada:
    {
        "ordens": [
            {
                "grupo_maquina": "montagem",
                "setor_conjunto": "Içamento",
                "obs": "testes",
                "peca_nome": "123456",
                "qtd_planejada": 5,
                "data_carga": "2025-02-19"
            }
        ]
    }
    """


    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido!'}, status=405)
    try:
        data = json.loads(request.body)  # Tenta carregar o JSON
        ordens_data = data.get('ordens', [])
        atualizacao_ordem = data.get('atualizacao_ordem', None)

        if not ordens_data:
            return JsonResponse({'error': 'Nenhuma ordem fornecida!'}, status=400)

        # Coletar todas as datas únicas na requisição
        datas_requisicao = set()
        for ordem_info in ordens_data:
            data_carga_str = ordem_info.get('data_carga')
            if data_carga_str:
                try:
                    data_carga = datetime.strptime(data_carga_str, "%Y-%m-%d").date()
                    datas_requisicao.add(data_carga)
                except ValueError:
                    return JsonResponse({'error': 'Formato de data inválido! Use YYYY-MM-DD.'}, status=400)

        # Verifica se alguma das datas já tem carga alocada no banco
        datas_existentes = set(Ordem.objects.filter(data_carga__in=datas_requisicao, grupo_maquina='montagem').values_list('data_carga', flat=True))
        datas_bloqueadas = datas_existentes.intersection(datas_requisicao)

        if not atualizacao_ordem:
            if datas_bloqueadas:
                return JsonResponse({'error': f"Não é possível adicionar novas ordens. Datas já possuem carga alocada: {', '.join(map(str, datas_bloqueadas))}"}, status=400)
        
        # Coletar todas as máquinas na requisição
        maquinas_requisicao = set()
        for ordem_info in ordens_data:
            maquina_str = ordem_info.get('setor_conjunto')
            if maquina_str:  # Garante que não é None ou string vazia
                maquinas_requisicao.add(maquina_str)  # Corrigido para adicionar o nome correto da máquina

        # Verifica se todas as células já estão cadastradas no model de máquinas
        maquinas_existentes = set(Maquina.objects.filter(nome__in=maquinas_requisicao).values_list('nome', flat=True))

        # Identifica as máquinas que não estão cadastradas
        maquinas_faltantes = maquinas_requisicao - maquinas_existentes

        if maquinas_faltantes:
            return JsonResponse(
                {'error': f"Não é possível adicionar novas ordens. As máquinas a seguir não estão cadastradas: {', '.join(maquinas_faltantes)}"}, 
                status=400, safe=False
            )
        
        ordens_criadas = []

        with transaction.atomic():  # Garantir transação segura
            for ordem_info in ordens_data:
                grupo_maquina = ordem_info.get('grupo_maquina', 'montagem')
                setor_conjunto = ordem_info.get('setor_conjunto')
                obs = ordem_info.get('obs', '')
                nome_peca = ordem_info.get('peca_nome')
                qtd_planejada = ordem_info.get('qtd_planejada', 0)
                data_carga_str = ordem_info.get('data_carga')

                if not nome_peca:
                    return JsonResponse({'error': 'Nome da peça é obrigatório!'}, status=400)

                if not setor_conjunto:
                    return JsonResponse({'error': 'Setor de conjunto é obrigatório!'}, status=400)

                # Converter data_carga para datetime.date
                try:
                    data_carga = datetime.strptime(data_carga_str, "%Y-%m-%d").date()
                except ValueError:
                    return JsonResponse({'error': 'Data inválida. Use o formato YYYY-MM-DD.'}, status=400)

                # Buscar a máquina/setor correspondente
                try:
                    maquina = Maquina.objects.get(nome=setor_conjunto)
                except ObjectDoesNotExist:
                    return JsonResponse({'error': f"Setor '{setor_conjunto}' não encontrado!"}, status=404)

                # Criar objeto Ordem e salvar no banco
                nova_ordem = Ordem(
                    grupo_maquina=grupo_maquina,
                    status_atual='aguardando_iniciar',
                    obs=obs,
                    data_criacao=now(),
                    data_carga=data_carga,
                    maquina=maquina  # Associação com a máquina correta
                )

                nova_ordem.save()  # Salva a ordem no banco

                # Criar a peça associada à ordem
                nova_peca = PecasOrdem(
                    ordem=nova_ordem,
                    peca=nome_peca,
                    qtd_planejada=qtd_planejada,
                    qtd_boa=0,
                    qtd_morta=0
                )

                nova_peca.save()  # Salva a peça no banco

                # Adiciona ao JSON de retorno
                ordens_criadas.append({
                    'id': nova_ordem.id,
                    'setor_conjunto': setor_conjunto,
                    'data_carga': nova_ordem.data_carga.strftime('%Y-%m-%d')
                })

        return JsonResponse({
            'message': 'Ordens e peças criadas com sucesso!',
            'ordens': ordens_criadas
        }, safe=False)

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Erro ao processar JSON. Verifique o formato da requisição!'}, status=400)

    except IntegrityError:
        traceback.print_exc()  # Log detalhado do erro no console
        return JsonResponse({'error': 'Erro no banco de dados ao salvar a ordem!'}, status=500)

    except Exception as e:
        traceback.print_exc()  # Log detalhado do erro no console
        return JsonResponse({'error': f'Erro inesperado: {str(e)}'}, status=500)
    
@csrf_exempt
def atualizar_status_ordem(request):

    """
    Para iniciar uma ordem:

    {
        "status": "iniciada",
        "ordem_id": 21101,
    }

    Para interromper uma ordem:

    {
        "status": "interrompida",
        "ordem_id": 21101,
        "motivo": 2
    }

    Para finalizar uma ordem:

    {
        "status": "finalizada",
        "ordem_id": 21103,
        "operador_final": 2,
        "obs_finalizar": "teste",
        "qt_realizada": 2,
        "qt_mortas": 0
    }
    """

    try:
        # Parse do corpo da requisição
        body = json.loads(request.body)

        status = body.get('status')
        ordem_id = body.get('ordem_id')
        grupo_maquina = 'montagem'
        qt_produzida = body.get('qt_realizada', 0)

        if not ordem_id or not grupo_maquina or not status:
            return JsonResponse({'error': 'Campos obrigatórios não enviados.'}, status=400)

        # Obtém a ordem ANTES da transação, para evitar falha na atomicidade
        ordem = get_object_or_404(Ordem, pk=ordem_id)

        # Validações básicas
        if ordem.status_atual == status:
            return JsonResponse({'error': f'Essa ordem já está {status}. Atualize a página.'}, status=400)

        if status == 'retorno' and ordem.status_atual == 'iniciada':
            return JsonResponse({'error': f'Essa ordem já está iniciada. Atualize a página.'}, status=400)

        with transaction.atomic():  # Entra na transação somente após garantir que todos os objetos existem

            # Finaliza o processo atual (se existir)
            processo_atual = ordem.processos.filter(data_fim__isnull=True).first()
            if processo_atual:
                processo_atual.finalizar_atual()

            # Cria o novo processo
            novo_processo = OrdemProcesso.objects.create(
                ordem=ordem,
                status='iniciada' if status == 'retorno' else status,
                data_inicio=now(),
                data_fim=now() if status in ['finalizada'] else None,
            )

            if status == 'iniciada':

                # Validações básicas
                if ordem.status_atual == 'interrompida':
                    return JsonResponse({'error': f'Essa ordem está interrompida, retorne ela.'}, status=400)

                maquinas_paradas = MaquinaParada.objects.filter(maquina=ordem.maquina, data_fim__isnull=True)
                for parada in maquinas_paradas:
                    parada.data_fim = now()
                    parada.save()

                ordem.status_prioridade = 1

                # Atualiza o status da ordem
                ordem.status_atual = status

            elif status == 'retorno':
                
                maquinas_paradas = MaquinaParada.objects.filter(maquina=ordem.maquina, data_fim__isnull=True)
                for parada in maquinas_paradas:
                    parada.data_fim = now()
                    parada.save()

                ordem.status_prioridade = 1

                # Atualiza o status da ordem
                ordem.status_atual = 'iniciada'

            elif status == 'finalizada':
                operador_final = get_object_or_404(Operador, pk=int(body.get('operador_final')))
                obs_final = body.get('obs_finalizar')

                ordem.operador_final = operador_final
                ordem.obs_operador = obs_final

                peca = PecasOrdem.objects.filter(ordem=ordem).first()

                if not peca:
                    return JsonResponse({'error': 'Nenhuma peça encontrada para essa ordem.'}, status=400)

                # Verificar a quantidade já apontada antes de criar um novo registro
                sum_pecas_finalizadas = PecasOrdem.objects.filter(ordem=ordem).aggregate(Sum('qtd_boa'))['qtd_boa__sum'] or 0
                total_apontado = sum_pecas_finalizadas + int(qt_produzida)  # Soma a nova produção

                # Se a nova quantidade ultrapassar a planejada, retorna erro
                if total_apontado > peca.qtd_planejada:
                    return JsonResponse({'error': 'Quantidade produzida maior que a quantidade planejada.'}, status=400)

                # Criando o novo registro de apontamento
                PecasOrdem.objects.create(
                    ordem=ordem,
                    peca=peca.peca,
                    qtd_planejada=peca.qtd_planejada,
                    qtd_boa=int(qt_produzida),
                    operador=operador_final,
                    processo_ordem=novo_processo
                )

                # Verificar novamente a quantidade finalizada após o novo registro
                sum_pecas_finalizadas = PecasOrdem.objects.filter(ordem=ordem).aggregate(Sum('qtd_boa'))['qtd_boa__sum']

                # Se a quantidade finalizada atingir a planejada, muda status para concluída
                if sum_pecas_finalizadas == peca.qtd_planejada:
                    ordem.status_atual = status
                else:
                    ordem.status_atual = 'aguardando_iniciar'

                ordem.status_prioridade = 3
                ordem.save()

            elif status == 'interrompida':
                novo_processo.motivo_interrupcao = get_object_or_404(MotivoInterrupcao, pk=body['motivo'])
                novo_processo.save()
                ordem.status_prioridade = 2

                peca_falta = body.get('peca_falta')
                maquina_id = body.get('maquina_id')
                data_carga = body.get('data_carga')

                if peca_falta:
                    solicitacao_peca=SolicitacaoPeca.objects.create(
                        peca=get_object_or_404(Pecas, pk=peca_falta),
                        localizacao_solicitante=get_object_or_404(Maquina, pk=maquina_id),
                        data_carga=datetime.strptime(data_carga, "%Y-%m-%d").date()
                    )

                # Atualiza o status da ordem
                ordem.status_atual = status

            ordem.save()

            return JsonResponse({
                'message': 'Status atualizado com sucesso.',
                'ordem_id': ordem.id,
                'status': novo_processo.status,
                'data_inicio': novo_processo.data_inicio,
            })

    except Ordem.DoesNotExist:
        return JsonResponse({'error': 'Ordem não encontrada.'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
def ordens_criadas(request):
    """
    View que agrega os dados de PecasOrdem (por ordem) e junta com a model Ordem,
    trazendo algumas colunas da Ordem e calculando o saldo:
        saldo = soma(qtd_planejada) - soma(qtd_boa)
    
    Parâmetros esperados na URL (via GET):
      - data_carga: data da carga (default: hoje)
      - maquina: nome da máquina (opcional)
      - status: status da ordem (opcional)
    """
    data_carga = request.GET.get('data_carga')
    maquina_param = request.GET.get('setor', '')
    status_param = request.GET.get('status', '')

    if data_carga == '':
        data_carga = now().date()

    # Monta os filtros para a model Ordem
    filtros_ordem = {
        'data_carga': data_carga,
        'grupo_maquina': 'montagem'
    }
    if maquina_param:
        maquina = get_object_or_404(Maquina, pk=maquina_param)
        filtros_ordem['maquina'] = maquina
    if status_param:
        filtros_ordem['status_atual'] = status_param

    # Recupera os IDs das ordens que atendem aos filtros
    ordem_ids = Ordem.objects.filter(**filtros_ordem).values_list('id', flat=True)

    # Consulta na PecasOrdem filtrando pelas ordens identificadas,
    # trazendo alguns campos da Ordem (usando a notação "ordem__<campo>"),
    # e agrupando para calcular as somas e o saldo.
    pecas_ordem_agg = PecasOrdem.objects.filter(ordem_id__in=ordem_ids).values(
        'ordem',                    # id da ordem (chave para o agrupamento)
        'ordem__data_carga',        # data da carga da ordem
        'ordem__data_programacao',  # data da programação da ordem
        'ordem__maquina__nome',     # nome da máquina (ajuste se necessário)
        'ordem__status_atual',      # status atual da ordem
        'peca',                     # nome da peça
    ).annotate(
        total_planejada=Coalesce(
            Avg('qtd_planejada'), Value(0.0, output_field=FloatField())
        ),
        total_boa=Coalesce(
            Sum('qtd_boa'), Value(0.0, output_field=FloatField())
        )
    ).annotate(
        restante=ExpressionWrapper(
            F('total_planejada') - F('total_boa'), output_field=FloatField()
        )
    )

    maquinas = Ordem.objects.filter(id__in=ordem_ids).values('maquina__nome','maquina__id').distinct()

    return JsonResponse({"ordens": list(pecas_ordem_agg),
                         "maquinas":list(maquinas)})

def verificar_qt_restante(request):

    ordem_id = request.GET.get('ordem_id')

    ordem_ids = Ordem.objects.filter(pk=ordem_id).values_list('id', flat=True)

    # Consulta na PecasOrdem filtrando pelas ordens identificadas,
    # trazendo alguns campos da Ordem (usando a notação "ordem__<campo>"),
    # e agrupando para calcular as somas e o saldo.
    pecas_ordem_agg = PecasOrdem.objects.filter(ordem_id__in=ordem_ids).values(
        'ordem',                    # id da ordem (chave para o agrupamento)
        'ordem__data_carga',        # data da carga da ordem
        'ordem__data_programacao',  # data da programação da ordem
        'ordem__maquina__nome',     # nome da máquina (ajuste se necessário)
        'ordem__status_atual',      # status atual da ordem
        'peca',                     # nome da peça
    ).annotate(
        total_planejada=Coalesce(
            Avg('qtd_planejada'), Value(0.0, output_field=FloatField())
        ),
        total_boa=Coalesce(
            Sum('qtd_boa'), Value(0.0, output_field=FloatField())
        )
    ).annotate(
        restante=ExpressionWrapper(
            F('total_planejada') - F('total_boa'), output_field=FloatField()
        )
    )

    return JsonResponse({"ordens": list(pecas_ordem_agg)})

def ordens_iniciadas(request):
    """
    Retorna todas as ordens que estão com status "iniciada" e que ainda não foram finalizadas,
    trazendo informações da ordem, peças relacionadas (sem repetição), soma das quantidades planejadas/boas e processos em andamento.
    """
    # Filtra ordens com status 'iniciada' e grupo de máquina 'montagem'
    ordens_filtradas = Ordem.objects.filter(
        status_atual='iniciada',
        grupo_maquina='montagem'
    ).prefetch_related('ordem_pecas_montagem', 'processos')

    resultado = []

    for ordem in ordens_filtradas:
        # Filtra apenas os processos que ainda não foram finalizados (data_fim nula)
        processos_ativos = ordem.processos.filter(data_fim__isnull=True)

        # Obtém apenas os nomes das peças, eliminando duplicatas
        pecas_unicas = sorted(set(peca.peca for peca in ordem.ordem_pecas_montagem.all()))

        # Calcula a soma total de qtd_planejada e qtd_boa para esta ordem
        agregacoes = ordem.ordem_pecas_montagem.aggregate(
            total_planejada=Avg('qtd_planejada', default=0.0),
            total_boa=Sum('qtd_boa', default=0.0)
        )

        resultado.append({
            "ordem_id": ordem.id,
            "ordem_numero": ordem.ordem,
            "data_carga": ordem.data_carga,
            "data_programacao": ordem.data_programacao,
            "grupo_maquina": ordem.grupo_maquina,
            "maquina": ordem.maquina.nome if ordem.maquina else None,
            "maquina_id": ordem.maquina.id if ordem.maquina else None,
            "status_atual": ordem.status_atual,
            "ultima_atualizacao": ordem.ultima_atualizacao,
            "pecas": pecas_unicas,  # Lista apenas os nomes das peças (sem repetições)
            "qtd_restante": agregacoes['total_planejada'] - agregacoes['total_boa'],  # Soma total de qtd_planejada
            "processos": [
                {
                    "processo_id": processo.id,
                    "status": processo.status,
                    "data_inicio": processo.data_inicio,
                    "data_fim": processo.data_fim,
                    "motivo_interrupcao": processo.motivo_interrupcao.nome if processo.motivo_interrupcao else None,
                    "maquina": processo.maquina.nome if processo.maquina else None
                }
                for processo in processos_ativos
            ]
        })

    return JsonResponse({"ordens": resultado}, safe=False)

def ordens_interrompidas(request):
    """
    Retorna todas as ordens que estão com status "interrompida" e que ainda não foram finalizadas,
    trazendo informações da ordem, peças relacionadas (sem repetição), soma das quantidades planejadas/boas e processos em andamento.
    """
    # Filtra ordens com status 'iniciada' e grupo de máquina 'montagem'
    ordens_filtradas = Ordem.objects.filter(
        status_atual='interrompida',
        grupo_maquina='montagem'
    ).prefetch_related('ordem_pecas_montagem', 'processos')

    resultado = []

    for ordem in ordens_filtradas:
        # Filtra apenas os processos que ainda não foram finalizados (data_fim nula)
        processos_ativos = ordem.processos.filter(data_fim__isnull=True)

        # Obtém apenas os nomes das peças, eliminando duplicatas
        pecas_unicas = sorted(set(peca.peca for peca in ordem.ordem_pecas_montagem.all()))

        # Calcula a soma total de qtd_planejada e qtd_boa para esta ordem
        agregacoes = ordem.ordem_pecas_montagem.aggregate(
            total_planejada=Avg('qtd_planejada', default=0.0),
            total_boa=Sum('qtd_boa', default=0.0)
        )

        resultado.append({
            "ordem_id": ordem.id,
            "ordem_numero": ordem.ordem,
            "data_carga": ordem.data_carga,
            "data_programacao": ordem.data_programacao,
            "grupo_maquina": ordem.grupo_maquina,
            "maquina": ordem.maquina.nome if ordem.maquina else None,
            "status_atual": ordem.status_atual,
            "ultima_atualizacao": ordem.ultima_atualizacao,
            "pecas": pecas_unicas,  # Lista apenas os nomes das peças (sem repetições)
            "qtd_restante": agregacoes['total_planejada'] - agregacoes['total_boa'],  # Soma total de qtd_planejada
            "processos": [
                {
                    "processo_id": processo.id,
                    "status": processo.status,
                    "data_inicio": processo.data_inicio,
                    "data_fim": processo.data_fim,
                    "motivo_interrupcao": processo.motivo_interrupcao.nome if processo.motivo_interrupcao else None,
                    "maquina": processo.maquina.nome if processo.maquina else None
                }
                for processo in processos_ativos
            ]
        })

    return JsonResponse({"ordens": resultado}, safe=False)

def listar_operadores(request):

    operadores = Operador.objects.filter(setor__nome='montagem')

    return JsonResponse({"operadores": list(operadores.values())})

def percentual_concluido_carga(request):
    data_carga = request.GET.get('data_carga', now().date())  # Garantindo que seja apenas a data

    # Soma correta da quantidade planejada por peça e ordem (evitando duplicação)
    total_planejado = PecasOrdem.objects.filter(
        ordem__data_carga=data_carga,
        ordem__grupo_maquina='montagem'
    ).values('ordem', 'peca').distinct().aggregate(
        total_planejado=Coalesce(Sum('qtd_planejada', output_field=FloatField()), Value(0.0))
    )["total_planejado"]

    # Soma total da quantidade boa produzida
    total_finalizado = PecasOrdem.objects.filter(
        ordem__data_carga=data_carga,
        ordem__grupo_maquina='montagem'
    ).aggregate(
        total_finalizado=Coalesce(Sum('qtd_boa', output_field=FloatField()), Value(0.0))
    )["total_finalizado"]

    # Evitar divisão por zero
    percentual_concluido = (total_finalizado / total_planejado * 100) if total_planejado > 0 else 0.0

    return JsonResponse({
        "percentual_concluido": round(percentual_concluido, 2),  # Arredonda para 2 casas decimais
        "total_planejado": total_planejado,
        "total_finalizado": total_finalizado
    })

def andamento_ultimas_cargas(request):
    # Obtém as últimas 5 datas de carga disponíveis para pintura
    ultimas_cargas = Ordem.objects.filter(grupo_maquina='montagem')\
        .order_by('-data_carga')\
        .values_list('data_carga', flat=True)\
        .distinct()[:5]

    andamento_cargas = []
    
    for data in ultimas_cargas:
        # Soma correta da quantidade planejada (evitando duplicações)
        total_planejado = PecasOrdem.objects.filter(
            ordem__data_carga=data,
            ordem__grupo_maquina='montagem'
        ).values('ordem', 'peca').distinct().aggregate(
            total_planejado=Coalesce(Sum('qtd_planejada', output_field=models.FloatField()), Value(0.0))
        )["total_planejado"]

        # Soma total da quantidade boa produzida
        total_finalizado = PecasOrdem.objects.filter(
            ordem__data_carga=data,
            ordem__grupo_maquina='montagem'
        ).aggregate(
            total_finalizado=Coalesce(Sum('qtd_boa', output_field=models.FloatField()), Value(0.0))
        )["total_finalizado"]

        # Evita divisão por zero e calcula o percentual corretamente
        percentual_concluido = (total_finalizado / total_planejado * 100) if total_planejado > 0 else 0.0

        andamento_cargas.append({
            "data_carga": data.strftime("%d/%m/%Y"),
            "percentual_concluido": round(percentual_concluido, 2),
            "total_planejado": total_planejado,
            "total_finalizado": total_finalizado
        })

    return JsonResponse({"andamento_cargas": andamento_cargas})

def listar_motivos_interrupcao(request):

    motivos = MotivoInterrupcao.objects.filter(setor__nome='montagem', visivel=True)

    return JsonResponse({"motivos": list(motivos.values())})

def planejamento(request):

    motivos_maquina_parada = MotivoMaquinaParada.objects.filter(setor__nome='montagem').exclude(nome='Finalizada parcial')

    return render(request, 'apontamento_montagem/planejamento.html', {'motivos_maquina_parada': motivos_maquina_parada})

def listar_pecas_disponiveis(request):

    conjunto = request.GET.get('conjunto')
    
    conjunto_object = get_object_or_404(Conjuntos, codigo=conjunto)

    pecas_disponiveis = Pecas.objects.filter(conjunto=conjunto_object)

    return JsonResponse({'pecas':list(pecas_disponiveis.values())})