from django.http import JsonResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.utils.timezone import now,localtime
from django.db.models import Sum, F, ExpressionWrapper, FloatField, Value, Avg, Q, IntegerField, Max
from django.db import transaction, models, IntegrityError, connection
from django.shortcuts import get_object_or_404
from django.db.models.functions import Coalesce
from django.shortcuts import render
from django.core.exceptions import ObjectDoesNotExist

import json
from datetime import datetime, date, timedelta
import traceback

from .models import PecasOrdem, ConjuntosInspecionados
from core.utils import carregar_planilha_base_geral
from core.models import SolicitacaoPeca, Ordem, OrdemProcesso, MaquinaParada, MotivoInterrupcao, MotivoMaquinaParada, Profile, PecasFaltantes
from cadastro.models import Operador, Maquina, Pecas, Conjuntos, CarretasExplodidas
from inspecao.models import Inspecao

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
                    data_carga = datetime.strptime(data_carga_str, "%d/%m/%Y").date()
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

        with transaction.atomic():
            ordens_objs = []
            pecas_objs = []
            ordens_metadata = []

            for ordem_info in ordens_data:
                grupo_maquina = ordem_info.get('grupo_maquina', 'montagem')
                setor_conjunto = ordem_info.get('setor_conjunto')
                obs = ordem_info.get('obs', '')
                nome_peca = ordem_info.get('peca_nome')
                qtd_planejada = ordem_info.get('qtd_planejada', 0)
                data_carga = datetime.strptime(ordem_info['data_carga'], "%Y-%d-%m").date()

                maquina = Maquina.objects.get(nome=setor_conjunto)

                nova_ordem = Ordem(
                    grupo_maquina=grupo_maquina,
                    status_atual='aguardando_iniciar',
                    obs=obs,
                    data_criacao=now(),
                    data_carga=data_carga,
                    maquina=maquina
                )

                ordens_objs.append(nova_ordem)
                ordens_metadata.append({
                    "setor_conjunto": setor_conjunto,
                    "data_carga": data_carga,
                    "qtd_planejada": qtd_planejada,
                    "nome_peca": nome_peca
                })

            # Cria todas as ordens de uma vez
            Ordem.objects.bulk_create(ordens_objs)

            # Associa peças às ordens agora com IDs já definidos
            for ordem_obj, meta in zip(ordens_objs, ordens_metadata):
                pecas_objs.append(PecasOrdem(
                    ordem=ordem_obj,
                    peca=meta["nome_peca"],
                    qtd_planejada=meta["qtd_planejada"],
                    qtd_boa=0,
                    qtd_morta=0
                ))

            PecasOrdem.objects.bulk_create(pecas_objs)

            ordens_criadas = [{
                "id": ordem.id,
                "setor_conjunto": meta["setor_conjunto"],
                "data_carga": meta["data_carga"].strftime("%Y-%m-%d")
            } for ordem, meta in zip(ordens_objs, ordens_metadata)]

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
        continua = body.get('continua', 'false').lower() == 'true'

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

                peca = PecasOrdem.objects.filter(ordem=ordem).first()

                nova_peca_ordem = PecasOrdem.objects.create(
                    ordem=ordem,
                    peca=peca.peca,
                    qtd_planejada=peca.qtd_planejada,
                    qtd_boa=0,
                    operador=None,
                    processo_ordem=novo_processo
                )

                nova_peca_ordem.save()

            elif status == 'retorno':
                
                maquinas_paradas = MaquinaParada.objects.filter(maquina=ordem.maquina, data_fim__isnull=True)
                for parada in maquinas_paradas:
                    parada.data_fim = now()
                    parada.save()

                ordem.status_prioridade = 1

                # Atualiza o status da ordem
                ordem.status_atual = 'iniciada'

                ultimo_peca_ordem = PecasOrdem.objects.filter(ordem=ordem).last()
                ultimo_peca_ordem.processo_ordem=novo_processo
                
                ultimo_peca_ordem.save()

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
                
                if total_apontado <= 0:
                    return JsonResponse({'error': 'Quantidade produzida tem que ser maior que zero.'}, status=400)

                # Criando o novo registro de apontamento
                ultimo_peca_ordem = PecasOrdem.objects.filter(ordem=ordem).last()
                ultimo_peca_ordem.qtd_boa=int(qt_produzida)
                ultimo_peca_ordem.processo_ordem=novo_processo
                ultimo_peca_ordem.operador=operador_final
                ultimo_peca_ordem.save()

                if "-" in peca.peca:
                    codigo = peca.peca.split(" - ", maxsplit=1)[0]
                else:
                    codigo = peca.peca
                
                # verifica se ta na lista de itens a ser inspecionado pelo setor da montagem
                conjuntos_inspecionados = ConjuntosInspecionados.objects.filter(codigo=codigo)
                if conjuntos_inspecionados:
                    Inspecao.objects.create(
                        pecas_ordem_montagem=ultimo_peca_ordem,
                    )

                # verifica se a peça é da célula "serralheria", se sim cria inspeção
                maquina_nome = ordem.maquina.nome.strip().lower() if ordem.maquina and ordem.maquina.nome else ""
                if maquina_nome == "serralheria":
                    Inspecao.objects.create(
                        pecas_ordem_montagem=ultimo_peca_ordem,
                    )

                # Verificar novamente a quantidade finalizada após o novo registro
                sum_pecas_finalizadas = PecasOrdem.objects.filter(ordem=ordem).aggregate(Sum('qtd_boa'))['qtd_boa__sum']

                # Se a quantidade finalizada atingir a planejada, muda status para concluída
                if sum_pecas_finalizadas == peca.qtd_planejada:
                    ordem.status_atual = status
                    ordem.status_prioridade = 3
                    ordem.save()
                else:

                    # se o operador desejar continuar a ordem em aberto?
                    # continua = True
                    # mas e se o operador clicar sem querer?
                    # Como ele finaliza apenas sem computar a ordem?
                    if continua == True:
                        ordem.status_atual = 'iniciada'
                        ordem.status_prioridade = 1
                        ordem.save()

                        nova_peca_ordem = PecasOrdem.objects.create(
                            ordem=ordem,
                            peca=peca.peca,
                            qtd_planejada=peca.qtd_planejada,
                            qtd_boa=0,
                            operador=None,
                            processo_ordem=novo_processo
                        )

                        nova_peca_ordem.save()

                    else:
                        ordem.status_atual = 'aguardando_iniciar'
                        ordem.status_prioridade = 1
                        ordem.save()

            elif status == 'interrompida':
                novo_processo.motivo_interrupcao = get_object_or_404(MotivoInterrupcao, pk=body['motivo'])
                novo_processo.save()
                ordem.status_prioridade = 2

                if 'pecas_faltantes' in body and isinstance(body['pecas_faltantes'], list):
    
                    # 1. Encontrar o último número de interrupção para esta Ordem
                    ultimo_numero = PecasFaltantes.objects.filter(ordem=ordem).aggregate(
                        Max('numero_interrupcao')
                    )['numero_interrupcao__max']
                    
                    # 2. Definir o próximo número. Se for a primeira vez, será 1 (0+1);
                    #    caso contrário, será o máximo + 1.
                    proximo_numero_interrupcao = (ultimo_numero or 0) + 1
                    
                    pecas_a_criar = []
                    for peca_faltante in body['pecas_faltantes']:
                        nome = peca_faltante.get('nome')
                        quantidade = peca_faltante.get('quantidade')
                        
                        if nome and isinstance(quantidade, (int, float)) and quantidade > 0:
                            pecas_a_criar.append(
                                PecasFaltantes(
                                    ordem=ordem,
                                    # 3. Atribuir o número de interrupção calculado a todos
                                    #    os registros deste lote (interrupção)
                                    numero_interrupcao=proximo_numero_interrupcao,
                                    nome_peca=nome,
                                    quantidade=quantidade
                                )
                            )
                            
                    if pecas_a_criar:
                        PecasFaltantes.objects.bulk_create(pecas_a_criar)

                # Atualiza o status da ordem
                ordem.status_atual = status

            # Associa o processo à última PecasOrdem (mantido da sua lógica original)
            ultimo_peca_ordem = PecasOrdem.objects.filter(ordem=ordem).last()
            if ultimo_peca_ordem: # Adicionada verificação para evitar erro se não houver PecasOrdem
                ultimo_peca_ordem.processo_ordem=novo_processo
                ultimo_peca_ordem.save()

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
    data_programacao = request.GET.get("data-programada", '')

    if data_carga == '':
        data_carga = now().date()

    # Monta os filtros para a model Ordem
    filtros_ordem = {
        'data_carga': data_carga,
        'grupo_maquina': 'montagem',
        'excluida': False,
    }
    if maquina_param:
        maquina = get_object_or_404(Maquina, pk=maquina_param)
        filtros_ordem['maquina'] = maquina
    if status_param:
        filtros_ordem['status_atual'] = status_param
    if data_programacao:
        filtros_ordem['data_programacao'] = data_programacao

    # Máquinas a excluir da contagem / retorno
    maquinas_excluidas = [
        'PLAT. TANQUE. CAÇAM. 2',
        'QUALIDADE',
        'FORJARIA',
        'ESTAMPARIA',
        'Carpintaria',
        'FEIXE DE MOLAS',
        'ROÇADEIRA'
    ]

    # Recupera os IDs das ordens que atendem aos filtros (ainda sem excluir máquinas, pois o filtro de máquina pode vir por parâmetro)
    ordem_ids = Ordem.objects.filter(**filtros_ordem).values_list('id', flat=True)

    # Consulta em PecasOrdem filtrando pelas ordens e EXCLUINDO as máquinas definidas em maquinas_excluidas
    pecas_ordem_queryset = PecasOrdem.objects.filter(ordem_id__in=ordem_ids).exclude(
        ordem__maquina__nome__in=maquinas_excluidas
    )

    pecas_ordem_agg = pecas_ordem_queryset.values(
        'ordem',                    # id da ordem (chave para o agrupamento)
        'ordem__data_carga',        # data da carga da ordem
        'ordem__data_programacao',  # data da programação da ordem
        'ordem__maquina__nome',     # nome da máquina
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

    # Recalcula datas apenas com as ordens consideradas após exclusões
    datas_programacao = set(item['ordem__data_programacao'] for item in pecas_ordem_agg)
    data_programacao = next(iter(datas_programacao), None)
    data_formatada = data_programacao.strftime('%d/%m/%Y') if data_programacao else None

    datas_carga = set(item['ordem__data_carga'] for item in pecas_ordem_agg)
    data_carga = next(iter(datas_carga), None)
    data_formatada_carga = data_carga if data_carga else None

    # Lista de máquinas (apenas das ordens retornadas)
    maquinas = Ordem.objects.filter(id__in=ordem_ids).exclude(
        maquina__nome__in=maquinas_excluidas
    ).values('maquina__nome', 'maquina__id').distinct()

    return JsonResponse({
        "ordens": list(pecas_ordem_agg),
        "maquinas": list(maquinas),
        "data_programacao": data_formatada,
        "data_formatada_carga": data_formatada_carga
    })

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

    usuario_tipo = Profile.objects.filter(user=request.user).values_list('tipo_acesso', flat=True).first()

    maquina_param = request.GET.get('setor', '')

    ordem_id = request.GET.get('ordem_id', None)

    filtros_ordem = {
        'grupo_maquina': 'montagem',
        'status_atual': 'iniciada',
        'excluida': False,
    }

    # Adicionar chave id caso exista o parametro ordem_id
    if ordem_id:
        filtros_ordem['id'] = ordem_id # ordem id --> core_ordem

    if maquina_param:
        maquina = get_object_or_404(Maquina, pk=maquina_param)
        filtros_ordem['maquina'] = maquina

    # Filtra ordens com status 'iniciada' e grupo de máquina 'montagem'
    ordens_filtradas = Ordem.objects.filter(**filtros_ordem).prefetch_related('ordem_pecas_montagem', 'processos')

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

    return JsonResponse({"ordens": resultado,'usuario_tipo_acesso': usuario_tipo}, safe=False)

def ordens_interrompidas(request):
    """
    Retorna todas as ordens que estão com status "interrompida" e que ainda não foram finalizadas,
    trazendo informações da ordem, peças relacionadas (sem repetição), soma das quantidades planejadas/boas e processos em andamento.
    """

    usuario_tipo = Profile.objects.filter(user=request.user).values_list('tipo_acesso', flat=True).first()

    maquina_param = request.GET.get('setor', '')

    filtros_ordem = {
        'grupo_maquina': 'montagem',
        'status_atual': 'interrompida',
        'excluida': False,
    }

    if maquina_param:
        maquina = get_object_or_404(Maquina, pk=maquina_param)
        filtros_ordem['maquina'] = maquina

    ordens_filtradas = Ordem.objects.filter(**filtros_ordem).prefetch_related('ordem_pecas_montagem', 'processos')

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

        ultima_interrupcao_data = ordem.pecas_faltantes.aggregate(
            Max('numero_interrupcao')
        )
        ultima_interrupcao_num = ultima_interrupcao_data['numero_interrupcao__max']
        
        pecas_faltantes_list = []
        
        if ultima_interrupcao_num is not None:
            
            ultima_interrupcao_pecas = ordem.pecas_faltantes.filter(
                numero_interrupcao=ultima_interrupcao_num
            )
            
            pecas_faltantes_list = [
                {
                    "id": peca_faltante.id,
                    "nome_peca": peca_faltante.nome_peca,
                    "quantidade": peca_faltante.quantidade,
                    "data_registro": peca_faltante.data_registro,
                    "numero_interrupcao": peca_faltante.numero_interrupcao 
                }
                for peca_faltante in ultima_interrupcao_pecas
            ]

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
            "pecas_faltantes": pecas_faltantes_list,  # Lista de peças faltantes
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

    return JsonResponse({"ordens": resultado, 'usuario_tipo_acesso': usuario_tipo}, safe=False)

def listar_operadores(request):
    maquina_id = request.GET.get('maquina')
    
    # Operadores do setor de montagem
    operadores = Operador.objects.filter(setor__nome='montagem')
    
    # Operadores do setor de montagem que estão vinculados à máquina específica
    if maquina_id:
        operadores_maquina = Operador.objects.filter(
            setor__nome='montagem',
            maquinas__nome=maquina_id 
        ).distinct() 
    else:
        operadores_maquina = Operador.objects.none()
    
    return JsonResponse({
        "operadores": list(operadores.values()),
        "operadores_maquina": list(operadores_maquina.values())
    })

def percentual_concluido_carga(request):
    data_carga = request.GET.get('data_carga')  # Garantindo que seja apenas a data

    # Algumas máquinas que não precisam está na contagem
    maquinas_excluidas = [
        'PLAT. TANQUE. CAÇAM. 2',
        'QUALIDADE',
        'FORJARIA',
        'ESTAMPARIA',
        'Carpintaria',
        'FEIXE DE MOLAS',
        'SERRALHERIA',
        'ROÇADEIRA'
    ]

    maquinas_excluidas_ids = Maquina.objects.filter(nome__in=maquinas_excluidas).values_list('id', flat=True)

    # Total planejado sem duplicidade de peça e ordem, excluindo certas máquinas
    total_planejado = PecasOrdem.objects.filter(
        ordem__data_carga=data_carga,
        ordem__grupo_maquina='montagem'
    ).exclude(ordem__maquina__id__in=maquinas_excluidas_ids) \
    .values('ordem', 'peca').distinct() \
    .aggregate(total_planejado=Coalesce(Sum('qtd_planejada', output_field=FloatField()), Value(0.0)))["total_planejado"]

    # Soma total da quantidade boa produzida
    total_finalizado = PecasOrdem.objects.filter(
        ordem__data_carga=data_carga,
        ordem__grupo_maquina='montagem'
    ).exclude(ordem__maquina__id__in=maquinas_excluidas_ids) \
    .aggregate(
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

    # Máquinas a excluir da contagem
    maquinas_excluidas = [
        'PLAT. TANQUE. CAÇAM. 2',
        'QUALIDADE',
        'FORJARIA',
        'ESTAMPARIA',
        'Carpintaria',
        'FEIXE DE MOLAS',
        'SERRALHERIA',
        'ROÇADEIRA'
    ]

    maquinas_excluidas_ids = Maquina.objects.filter(nome__in=maquinas_excluidas).values_list('id', flat=True)

    # Obtém as últimas 10 datas de carga disponíveis para pintura
    ultimas_cargas = Ordem.objects.filter(grupo_maquina='montagem')\
        .order_by('-data_carga')\
        .values_list('data_carga', flat=True)\
        .distinct()[:10]

    andamento_cargas = []
    
    for data in ultimas_cargas:
        # Soma correta da quantidade planejada (evitando duplicações)
        total_planejado = PecasOrdem.objects.filter(
            ordem__data_carga=data,
            ordem__grupo_maquina='montagem'
        ).exclude(ordem__maquina__id__in=maquinas_excluidas_ids) \
        .values('ordem', 'peca').distinct().aggregate(
            total_planejado=Coalesce(Sum('qtd_planejada', output_field=models.FloatField()), Value(0.0))
        )["total_planejado"]

        # Soma total da quantidade boa produzida
        total_finalizado = PecasOrdem.objects.filter(
            ordem__data_carga=data,
            ordem__grupo_maquina='montagem'
        ).exclude(ordem__maquina__id__in=maquinas_excluidas_ids) \
        .aggregate(
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

def buscar_maquinas(request):

    maquinas = Maquina.objects.filter(setor__nome='montagem', tipo='maquina').values('id','nome')

    return JsonResponse({"maquinas":list(maquinas)})

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

def listar_pecas_disponiveis(request):
    """
    Retorna uma lista de peças disponíveis (Pecas) para um Conjunto específico, 
    usando a coluna de código puro.
    """
    
    conjunto_input = request.GET.get('conjunto')
    if not conjunto_input:
        return JsonResponse({'erro': 'Parâmetro "conjunto" é obrigatório.'}, status=400)

    try:
        codigo_conjunto_param = conjunto_input.split(' - ')[0].strip()
    except IndexError:
        return JsonResponse({'erro': 'Formato de "conjunto" inválido. Esperado: "CODIGO - NOME".'}, status=400)
    
    pecas = CarretasExplodidas.objects.filter(conjunto_peca__contains=codigo_conjunto_param).values('descricao_peca')

    if pecas is None:
        return JsonResponse({'erro': 'Dados da base não disponíveis.'}, status=503)

    return JsonResponse({'pecas': list(pecas), 'conjunto_filtrado': codigo_conjunto_param}, status=200)

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
    maquina = data.get('setor')
    data_carga = data.get('dataCarga')
    obs = data.get('observacao')

    ordens_existentes = Ordem.objects.filter(
        data_carga=data_carga,
        grupo_maquina='montagem',
        ordem_pecas_montagem__peca__contains=codigo_conjunto
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
        maquina = get_object_or_404(Maquina, pk=maquina)
        ordem = Ordem.objects.create(
            grupo_maquina='montagem',
            status_atual='aguardando_iniciar',
            data_carga=datetime.strptime(data_carga, '%Y-%m-%d').date(),
            maquina=maquina
        )  
        PecasOrdem.objects.create(
            ordem=ordem,
            peca=conjunto,
            qtd_planejada=quantidade_planejada,
            qtd_boa=0,
            qtd_morta=0
        )
        return JsonResponse({'message': 'Ordem criada com sucesso!'})

def api_ordens_finalizadas(request):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT 
                o.ordem,
                m.nome AS maquina,
                po.peca AS conjunto,
                po.qtd_boa AS total_produzido,
                o.data_carga,
                co.data_fim AS data_finalizacao,
                concat(op.matricula, ' - ', op.nome) AS operador,
                o.obs_operador AS obs
            FROM apontamento_v2.core_ordem o
            LEFT JOIN apontamento_v2.cadastro_maquina m ON m.id = o.maquina_id
            LEFT JOIN apontamento_v2.cadastro_operador op ON op.id = o.operador_final_id
            INNER JOIN apontamento_v2.apontamento_montagem_pecasordem po ON o.id = po.ordem_id
            INNER JOIN apontamento_v2.core_ordemprocesso co on co.id = po.processo_ordem_id 
            WHERE 
                co.data_fim >= '2025-04-08'
                AND po.qtd_boa > 0
            ORDER BY co.data_fim;
        """)
        columns = [col[0] for col in cursor.description]
        results_raw = [dict(zip(columns, row)) for row in cursor.fetchall()]

    def format_data(dt):
        if isinstance(dt, (datetime, date)):
            return dt.strftime("%d/%m/%Y")
        return ""

    def format_data_hora(dt):
        if isinstance(dt, (datetime, date)):
            data_final = dt - timedelta(hours=3) 
            return data_final.strftime("%d/%m/%Y %H:%M")
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
            'maquina': row.get('maquina'),
            'codigo': codigo,
            'descricao': descricao,
            'total_produzido': row.get('total_produzido'),
            'data_carga': format_data(row.get('data_carga')),
            'data_finalizacao': format_data_hora(row.get('data_finalizacao')),
            'operador': row.get('operador'),
            'obs': row.get('obs'),
        })

    return JsonResponse(final_results, safe=False)

def api_tempos(request):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT 
                o.id as id_ordem,
                o.ordem AS ordem,
                po.peca AS codigo,
                po.peca AS descricao,
                op.data_inicio,
                op.data_fim,
                o.data_carga,
                po.qtd_planejada AS qt_planejada,
                m.nome AS celula,
                op.status,
                po.qtd_boa AS qt_boa
            FROM apontamento_v2.core_ordem o
            LEFT JOIN apontamento_v2.core_ordemprocesso op ON op.ordem_id = o.id
            LEFT JOIN apontamento_v2.apontamento_montagem_pecasordem po ON po.processo_ordem_id = op.id
            LEFT JOIN apontamento_v2.cadastro_maquina m ON o.maquina_id = m.id
            WHERE o.grupo_maquina = 'montagem' AND op.data_inicio IS NOT NULL
            ORDER BY o.ordem, op.data_inicio
        """)
        columns = [col[0] for col in cursor.description]
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]

    # Reverso: de baixo pra cima
    last_by_ordem = {}

    for i in reversed(range(len(results))):
        row = results[i]
        ordem_id = row['id_ordem']

        if ordem_id not in last_by_ordem:
            # Armazena os últimos dados conhecidos (mais abaixo na lista)
            last_by_ordem[ordem_id] = {
                'codigo': row['codigo'],
                'descricao': row['descricao'],
                'qt_planejada': row['qt_planejada'],
                'qt_boa': row['qt_boa'],
            }
        else:
            # Preenche se estiver nulo
            for field in ['codigo', 'descricao', 'qt_planejada', 'qt_boa']:
                if row[field] in (None, ''):
                    row[field] = last_by_ordem[ordem_id][field]
                else:
                    # Atualiza valor "mais recente"
                    last_by_ordem[ordem_id][field] = row[field]

    return JsonResponse(results, safe=False)

def retornar_processo(request):
    if request.method != 'POST':
        return JsonResponse(
            {'status': 'error', 'message': 'Método não permitido'}, 
            status=405
        )

    try:
        data = json.loads(request.body)
        ordem_id = data.get('ordemId')
        
        if not ordem_id:
            return JsonResponse(
                {'status': 'error', 'message': 'ordemId não fornecido'}, 
                status=400
            )

        with transaction.atomic():
            ordem_process = OrdemProcesso.objects.filter(ordem_id=ordem_id).last()

            ordem_process.delete()
            
            updated_count = Ordem.objects.filter(id=ordem_id).update(
                status_atual='aguardando_iniciar'
            )
            
            if updated_count == 0:
                raise Ordem.DoesNotExist(f"Ordem com id {ordem_id} não encontrada")

        return JsonResponse({
            'status': 'success', 
            'message': 'Processo retornado com sucesso'
        })

    except json.JSONDecodeError:
        return JsonResponse(
            {'status': 'error', 'message': 'JSON inválido'}, 
            status=400
        )
    except Ordem.DoesNotExist:
        return JsonResponse(
            {'status': 'error', 'message': 'Ordem não encontrada'}, 
            status=404
        )
    except Exception as e:
        return JsonResponse(
            {'status': 'error', 'message': str(e)}, 
            status=500
        )

def apontamento_qrcode(request):
    return render(request, 'apontamento_montagem/apontamento_qrcode.html')

def api_apontamento_qrcode(request):
    if request.method != 'GET':
        return JsonResponse(
            {'status': 'error', 'message': 'Método não permitido'}, 
            status=405
        )

    try:
        ordem_id = request.GET.get('ordem_id')

        ordem = Ordem.objects.get(pk=ordem_id)
        ordem_pecas = ordem.ordem_pecas_montagem.all() # Pega todas as ordem peças relacionadas à ordem
        total_feito = ordem_pecas.aggregate(
            total_feito=Coalesce(Sum('qtd_boa', output_field=IntegerField()), Value(0, output_field=IntegerField()))
        )['total_feito'] or 0 # Soma a quantidade boa feita, ou 0 se não houver

        ordem_peca = ordem_pecas.first()  # Pega a primeira peça da ordem
        

        dados = {
            'ordem': ordem.ordem if ordem else None,
            'maquina': ordem.maquina.nome if ordem and ordem.maquina else None,
            'status': ordem.status_atual if ordem else None,
            'peca': ordem_peca.peca if ordem else None,
            'qtd_planejada': ordem_peca.qtd_planejada if ordem else 0,
            'qtd_boa': total_feito if ordem else 0,
            'data_carga': ordem.data_carga.strftime('%d/%m/%Y') if ordem and ordem.data_carga else None,
        }
        

        return JsonResponse({
            'status': 'success', 
            'message': 'Dados recebidos com sucesso',
            'dados': dados,
        })
    except Ordem.DoesNotExist:
        return JsonResponse(
            {'status': 'error', 'message': 'Ordem não encontrada'}, 
            status=404
        )
    
    except Exception as e:
        return JsonResponse(
            {'status': 'error', 'message': str(e)}, 
            status=500
        )
