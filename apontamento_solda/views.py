from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.timezone import now,localtime
from django.db.models import Sum, F, ExpressionWrapper, FloatField, Value, Avg, Q
from django.db import transaction, models, IntegrityError, connection
from django.shortcuts import get_object_or_404
from django.db.models.functions import Coalesce
from django.shortcuts import render
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.decorators import login_required

import json
from datetime import datetime, date, timedelta
import traceback

from .models import PecasOrdem, ConjuntosInspecionados
from core.models import SolicitacaoPeca, Ordem, OrdemProcesso, MaquinaParada, MotivoInterrupcao, MotivoMaquinaParada, Profile
from cadastro.models import Operador, Maquina, Pecas, Conjuntos
from inspecao.models import Inspecao
from core.utils import notificar_ordem

@csrf_exempt
def criar_ordem(request):
    """
    API para criar múltiplas ordens para o setor de solda.
    Exemplo de carga JSON esperada:
    {
        "ordens": [
            {
                "grupo_maquina": "solda",
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
        datas_existentes = set(Ordem.objects.filter(data_carga__in=datas_requisicao, grupo_maquina='solda').values_list('data_carga', flat=True))
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
                grupo_maquina = ordem_info.get('grupo_maquina', 'solda')
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
    
    if not request.user.is_authenticated:
        return JsonResponse(
            {"detail": "Usuário não autenticado"},
            status=401
        )
    
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
        grupo_maquina = 'solda'
        qt_produzida = body.get('qt_realizada', 0)
        continua = body.get('continua', 'false').lower() == 'true'

        if not ordem_id or not grupo_maquina or not status:
            return JsonResponse({'error': 'Campos obrigatórios não enviados.'}, status=400)

        # Obtém a ordem ANTES da transação, para evitar falha na atomicidade
        ordem = get_object_or_404(Ordem, pk=ordem_id)

        # Validações básicas
        if ordem.status_atual == status:
            
            if ordem.status_atual == 'iniciada':
                operador_inicio = body.get('operador_inicio', None)

                # verifica se a quantidade restante para a ordem é maior q eu 1
                # mas tem que coletar todas as ordems cuja ordem_pai seja a ordem atual
                ordens_filhas = Ordem.objects.filter(Q(ordem_pai=ordem) | Q(id=ordem.id))
                pecas_ordem = PecasOrdem.objects.filter(ordem__in=ordens_filhas)
                qtd_planejada_total = pecas_ordem.aggregate(total_planejada=Coalesce(Sum('qtd_planejada'), Value(0), output_field=FloatField()))['total_planejada']
                qtd_planejada_total = qtd_planejada_total / pecas_ordem.count()

                qtd_boa_total = pecas_ordem.aggregate(total_boa=Coalesce(Sum('qtd_boa'), Value(0), output_field=FloatField()))['total_boa']
                qtd_restante = qtd_planejada_total - qtd_boa_total
                if qtd_restante <= 1:
                    return JsonResponse({'error': f'Essa ordem já está iniciada e não possui quantidade restante suficiente para criar uma nova ordem. Atualize a página.'}, status=400)
            
                # criar nova ordem clone da ordem atual apenas alterando a coluna ordem e a coluna ordem_pai que será a referencia da própria ordem
                nova_ordem = Ordem.objects.create(
                    grupo_maquina=ordem.grupo_maquina,
                    status_atual='iniciada',
                    data_carga=ordem.data_carga,
                    data_programacao=ordem.data_programacao,
                    maquina=ordem.maquina,
                    ordem_pai=ordem,
                    obs=ordem.obs,
                )

                # Cria o novo processo
                novo_processo = OrdemProcesso.objects.create(
                    ordem=nova_ordem,
                    status='iniciada',
                    data_inicio=now(),
                )

                # cria um novo registro em "pecasordem" com a nova ordem e com a mesma peça da ordem original
                peca = PecasOrdem.objects.filter(ordem=ordem).first()
                nova_peca_ordem = PecasOrdem.objects.create(
                    ordem=nova_ordem,
                    peca=peca.peca,
                    qtd_planejada=qtd_planejada_total,
                    qtd_boa=0,
                    operador_inicio_id=operador_inicio,
                    processo_ordem=novo_processo
                )
                
                notificar_ordem(nova_ordem)

                return JsonResponse({
                    'message': 'Ordem iniciada com sucesso.',
                })

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

                operador_inicial = body.get('operador_inicio')
                operador_inicial = get_object_or_404(Operador, pk=int(operador_inicial)) 

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
                    operador_inicio=operador_inicial,
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
                ultimo_peca_ordem.operador_final=operador_final
                ultimo_peca_ordem.ordem=ordem.ordem_pai if ordem.ordem_pai else ordem
                ultimo_peca_ordem.save()

                if "-" in peca.peca:
                    codigo = peca.peca.split(" - ", maxsplit=1)[0]
                else:
                    codigo = peca.peca
                
                # verifica se ta na lista de itens a ser inspecionado pelo setor da solda
                conjuntos_inspecionados = ConjuntosInspecionados.objects.filter(codigo=codigo)
                if conjuntos_inspecionados:
                    Inspecao.objects.create(
                        pecas_ordem_solda=ultimo_peca_ordem,
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
                            operador_inicio=operador_final,
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

                ultimo_peca_ordem = PecasOrdem.objects.filter(ordem=ordem).last()
                ultimo_peca_ordem.processo_ordem=novo_processo
                
                ultimo_peca_ordem.save()

            ordem.save()
            notificar_ordem(ordem)
            

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
    
    O status_atual é calculado com base nas regras (ordem de prioridade):
        1. Se pelo menos uma ordem tiver status "iniciada" → "iniciada"
        2. Se qtd_planejada == qtd_boa → "finalizada"
        3. Se todas forem "retorno" → "retorno"
        4. Se todas forem "interrompida" → "interrompida"
        5. Se todas forem "aguardando_iniciar" → "aguardando_iniciar"
    
    Parâmetros esperados na URL (via GET):
      - data_carga: data da carga (default: hoje)
      - setor: nome da máquina (opcional)
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
        'grupo_maquina': 'solda',
        'ordem_pai__isnull': True,
        'excluida': False,
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

    # Máquinas a excluir da contagem
    maquinas_excluidas = [
        'PLAT. TANQUE. CAÇAM. 2',
        'QUALIDADE',
        'FORJARIA',
        'ESTAMPARIA',
        'Carpintaria',
        'FEIXE DE MOLAS',
        'SERRALHERIA',
        'TRANSBORDO',
        'ROÇADEIRA'
    ]

    maquinas = Ordem.objects.filter(id__in=ordem_ids).exclude(maquina__nome__in=maquinas_excluidas).values('maquina__nome','maquina__id').distinct()

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

    # if not request.user.is_authenticated:
    #     return JsonResponse({"detail": "Unauthorized"}, status=401)

    usuario_tipo = Profile.objects.filter(user=request.user).values_list('tipo_acesso', flat=True).first()

    maquina_param = request.GET.get('setor', '')

    ordem_id_montagem = request.GET.get('ordem_id', None)

    filtros_ordem = {
        'grupo_maquina': 'solda',
        'status_atual': 'iniciada',
        'excluida': False,
    }

    # Adicionar chave id caso exista o parametro ordem_id
    if ordem_id_montagem:
        # filtros_ordem['id'] = ordem_id_montagem # ordem id --> core_ordem --> montagem

        
        ordem = Ordem.objects.get(pk=ordem_id_montagem)
        print(ordem)

        data_carga_montagem = ordem.data_carga if ordem.data_carga else None
        ordem_peca_montagem = ordem.ordem_pecas_montagem.first() # É pra ter só uma peça por ordem
        peca_montagem = ordem_peca_montagem.peca if ordem_peca_montagem else None

        codigo_peca = peca_montagem.split("-", maxsplit=1)[0].strip() if peca_montagem else None
        
        ordem_solda = None


        print(peca_montagem, codigo_peca, data_carga_montagem)

        if peca_montagem is None or codigo_peca is None or data_carga_montagem is None:
            """
                Verificando se a ordem buscada(montagem) tem a peça e a data de carga preenchida.
                Se não tiver, não tem como buscar a ordem de solda relacionada.
            """
            return JsonResponse({
                'status': 'error', 
                'message': 'Não foram encontrados dados de montagem para esta ordem de montagem',
                'dados': None
            }, status=400)
        
        ordem_solda = Ordem.objects.filter(
            data_carga=data_carga_montagem,
            grupo_maquina='solda',
            ordem_pecas_solda__peca__istartswith=codigo_peca
        ).distinct()

        print(ordem_solda)
        filtros_ordem['id__in'] = [ordem.id for ordem in ordem_solda]
        print(filtros_ordem)
        # ordem_pecas_solda = []
        # for ordem in ordem_solda:
        #     for i in ordem.ordem_pecas_solda.all():
        #         ordem_pecas_solda.append(i)

        # print(ordem_pecas_solda)
        # for i in ordem_pecas_solda:
        #     print(i)

    if maquina_param:
        maquina = get_object_or_404(Maquina, pk=maquina_param)
        filtros_ordem['maquina'] = maquina

    # Filtra ordens com status 'iniciada' e grupo de máquina 'solda'
    ordens_filtradas = Ordem.objects.filter(**filtros_ordem).prefetch_related('ordem_pecas_solda', 'processos')

    resultado = []

    for ordem in ordens_filtradas:
        # Filtra apenas os processos que ainda não foram finalizados (data_fim nula)
        processos_ativos = ordem.processos.filter(data_fim__isnull=True)

        # pega o registro mais recente ainda em andamento, com operador_inicio preenchido
        registro_inicio = (
            ordem.ordem_pecas_solda
                .filter(operador_inicio__isnull=False, operador_final__isnull=True)
                .select_related('operador_inicio')
                .order_by('-id')  # ou '-data_inicio' se existir
                .first()
        )

        operador_inicio = registro_inicio.operador_inicio.matricula + " - " + registro_inicio.operador_inicio.nome.split(' ')[0] if registro_inicio else None

        # Obtém apenas os nomes das peças, eliminando duplicatas
        pecas_unicas = sorted(set(peca.peca for peca in ordem.ordem_pecas_solda.all()))

        # Calcula a soma total de qtd_planejada e qtd_boa para esta ordem
        # se a peça tiver a coluna "ordem_pai" preenchida, tem que somar todas as peças cuja ordem_pai seja a ordem atual
        ordem_atual = ordem
        if ordem.ordem_pai != None:
            ordem = ordem.ordem_pai
        
        ordens_para_somar = Ordem.objects.filter(
            Q(ordem_pai=ordem) | Q(id=ordem.id)
        )

        pecas_para_somar = PecasOrdem.objects.filter(ordem__in=ordens_para_somar)

        agregacoes = pecas_para_somar.aggregate(
            total_planejada=Sum('qtd_planejada', default=0.0, output_field=FloatField()),
            total_boa=Sum('qtd_boa', default=0.0, output_field=FloatField())
        )

        resultado.append({
            "ordem_id": ordem_atual.id,
            "ordem_numero": ordem_atual.ordem,
            "data_carga": ordem_atual.data_carga,
            "data_programacao": ordem_atual.data_programacao,
            "grupo_maquina": ordem_atual.grupo_maquina,
            "maquina": ordem_atual.maquina.nome if ordem_atual.maquina else None,
            "maquina_id": ordem_atual.maquina.id if ordem_atual.maquina else None,
            "status_atual": ordem_atual.status_atual,
            "ultima_atualizacao": ordem_atual.ultima_atualizacao,
            "pecas": pecas_unicas,  # Lista apenas os nomes das peças (sem repetições)
            "qtd_restante": (agregacoes['total_planejada'] / pecas_para_somar.count()) - agregacoes['total_boa'],  # Soma total de qtd_planejada
            "operador_inicio": operador_inicio,
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

    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Unauthorized"}, status=401)

    usuario_tipo = Profile.objects.filter(user=request.user).values_list('tipo_acesso', flat=True).first()

    maquina_param = request.GET.get('setor', '')

    filtros_ordem = {
        'grupo_maquina': 'solda',
        'status_atual': 'interrompida',
        'excluida': False,
    }

    if maquina_param:
        maquina = get_object_or_404(Maquina, pk=maquina_param)
        filtros_ordem['maquina'] = maquina

    ordens_filtradas = Ordem.objects.filter(**filtros_ordem).prefetch_related('ordem_pecas_solda', 'processos')

    resultado = []

    for ordem in ordens_filtradas:
        # Filtra apenas os processos que ainda não foram finalizados (data_fim nula)
        processos_ativos = ordem.processos.filter(data_fim__isnull=True)

        registro_inicio = (
            ordem.ordem_pecas_solda
                .filter(operador_inicio__isnull=False, operador_final__isnull=True)
                .select_related('operador_inicio')
                .order_by('-id')  # ou '-data_inicio' se existir
                .first()
        )

        operador_inicio = registro_inicio.operador_inicio.matricula + " - " + registro_inicio.operador_inicio.nome.split(' ')[0] if registro_inicio else None

        # Obtém apenas os nomes das peças, eliminando duplicatas
        pecas_unicas = sorted(set(peca.peca for peca in ordem.ordem_pecas_solda.all()))

        # Calcula a soma total de qtd_planejada e qtd_boa para esta ordem
        ordem_atual = ordem
        if ordem.ordem_pai != None:
            ordem = ordem.ordem_pai
        
        ordens_para_somar = Ordem.objects.filter(
            Q(ordem_pai=ordem) | Q(id=ordem.id)
        )

        pecas_para_somar = PecasOrdem.objects.filter(ordem__in=ordens_para_somar)

        agregacoes = pecas_para_somar.aggregate(
            total_planejada=Sum('qtd_planejada', default=0.0, output_field=FloatField()),
            total_boa=Sum('qtd_boa', default=0.0, output_field=FloatField())
        )

        resultado.append({
            "ordem_id": ordem_atual.id,
            "ordem_numero": ordem_atual.ordem,
            "data_carga": ordem_atual.data_carga,
            "data_programacao": ordem_atual.data_programacao,
            "grupo_maquina": ordem_atual.grupo_maquina,
            "maquina": ordem_atual.maquina.nome if ordem_atual.maquina else None,
            "status_atual": ordem_atual.status_atual,
            "ultima_atualizacao": ordem_atual.ultima_atualizacao,
            "pecas": pecas_unicas,  # Lista apenas os nomes das peças (sem repetições)
            "qtd_restante": (agregacoes['total_planejada'] / pecas_para_somar.count()) - agregacoes['total_boa'],  # Soma total de qtd_planejada
            "operador_inicio": operador_inicio,
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
    ordem = request.GET.get('ordem')

    processo = PecasOrdem.objects.filter(ordem_id=ordem).order_by('-data').first()
    operador_inicio_id = processo.operador_inicio.id if processo and processo.operador_inicio else None

    operadores = Operador.objects.filter(setor__nome='solda')

    if maquina_id:
        operadores_maquina = Operador.objects.filter(
            setor__nome='solda',
            maquinas__nome=maquina_id 
        ).distinct()
    else:
        operadores_maquina = Operador.objects.none()

    return JsonResponse({
        "operadores": list(operadores.values()),
        "operadores_maquina": list(operadores_maquina.values()),
        "operador_inicio_id": operador_inicio_id
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
        'TRANSBORDO',
        'ROÇADEIRA'
    ]

    maquinas_excluidas_ids = Maquina.objects.filter(nome__in=maquinas_excluidas).values_list('id', flat=True)

    # Total planejado sem duplicidade de peça e ordem, excluindo certas máquinas
    total_planejado = PecasOrdem.objects.filter(
        ordem__data_carga=data_carga,
        ordem__grupo_maquina='solda'
    ).exclude(ordem__maquina__id__in=maquinas_excluidas_ids) \
    .values('ordem', 'peca').distinct() \
    .aggregate(total_planejado=Coalesce(Sum('qtd_planejada', output_field=FloatField()), Value(0.0)))["total_planejado"]

    # Soma total da quantidade boa produzida
    total_finalizado = PecasOrdem.objects.filter(
        ordem__data_carga=data_carga,
        ordem__grupo_maquina='solda'
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
        'TRANSBORDO',
        'ROÇADEIRA'
    ]

    maquinas_excluidas_ids = Maquina.objects.filter(nome__in=maquinas_excluidas).values_list('id', flat=True)

    # Obtém as últimas 10 datas de carga disponíveis para pintura
    ultimas_cargas = Ordem.objects.filter(grupo_maquina='solda')\
        .order_by('-data_carga')\
        .values_list('data_carga', flat=True)\
        .distinct()[:10]

    andamento_cargas = []
    
    for data in ultimas_cargas:
        # Soma correta da quantidade planejada (evitando duplicações)
        total_planejado = PecasOrdem.objects.filter(
            ordem__data_carga=data,
            ordem__grupo_maquina='solda'
        ).exclude(ordem__maquina__id__in=maquinas_excluidas_ids) \
        .values('ordem', 'peca').distinct().aggregate(
            total_planejado=Coalesce(Sum('qtd_planejada', output_field=models.FloatField()), Value(0.0))
        )["total_planejado"]

        # Soma total da quantidade boa produzida
        total_finalizado = PecasOrdem.objects.filter(
            ordem__data_carga=data,
            ordem__grupo_maquina='solda'
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

    motivos = MotivoInterrupcao.objects.filter(setor__nome='solda', visivel=True)
    print(motivos)

    return JsonResponse({"motivos": list(motivos.values())})

def planejamento(request):

    motivos_maquina_parada = MotivoMaquinaParada.objects.filter(setor__nome='solda').exclude(nome='Finalizada parcial')

    return render(request, 'apontamento_solda/planejamento.html', {'motivos_maquina_parada': motivos_maquina_parada})

def buscar_maquinas(request):

    maquinas = Maquina.objects.filter(setor__nome='solda', tipo='maquina').values('id','nome')

    return JsonResponse({"maquinas":list(maquinas)})

def listar_conjuntos(request):
    """
    API para listar os conjuntos disponíveis para o setor de solda.
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

    conjunto = request.GET.get('conjunto')
    
    conjunto_object = get_object_or_404(Conjuntos, codigo=conjunto)

    pecas_disponiveis = Pecas.objects.filter(conjunto=conjunto_object)

    return JsonResponse({'pecas':list(pecas_disponiveis.values())})

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
        grupo_maquina='solda',
        ordem_pecas_solda__peca__contains=codigo_conjunto
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
            grupo_maquina='solda',
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
            INNER JOIN apontamento_v2.apontamento_solda_pecasordem po ON o.id = po.ordem_id
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
            LEFT JOIN apontamento_v2.apontamento_solda_pecasordem po ON po.processo_ordem_id = op.id
            LEFT JOIN apontamento_v2.cadastro_maquina m ON o.maquina_id = m.id
            WHERE o.grupo_maquina = 'solda' AND op.data_inicio IS NOT null and o.ordem_pai_id is null and qtd_planejada notnull 
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
    return render(request, 'apontamento_solda/apontamento_solda_qrcode.html')

def api_apontamento_qrcode(request):
    """
    API para buscar dados de ordem de solda relacionada a uma ordem de montagem.
    
    O status é calculado com base nas regras (ordem de prioridade):
        1. Se pelo menos uma tiver status "iniciada" → "iniciada"
        2. Se qtd_planejada == qtd_boa (somando todas as qtd_boa) → "finalizada"
        3. Se todas forem "retorno" → "retorno"
        4. Se todas forem "interrompida" → "interrompida"
        5. Se todas forem "aguardando_iniciar" → "aguardando_iniciar"
    """
    if request.method != 'GET':
        return JsonResponse(
            {'status': 'error', 'message': 'Método não permitido'}, 
            status=405
        )

    try:
        ordem_id = request.GET.get('ordem_id')

        print(ordem_id)

        ordem = Ordem.objects.get(pk=ordem_id)
        print(ordem)
        data_carga_montagem = ordem.data_carga if ordem.data_carga else None
        ordem_peca_montagem = ordem.ordem_pecas_montagem.first() # É pra ter só uma peça por ordem
        peca_montagem = ordem_peca_montagem.peca if ordem_peca_montagem else None

        codigo_peca = peca_montagem.split("-", maxsplit=1)[0].strip() if peca_montagem else None
        
        ordem_solda = None

        print(peca_montagem, codigo_peca)

        if peca_montagem is None or codigo_peca is None or data_carga_montagem is None:
            """
                Verificando se a ordem buscada(montagem) tem a peça e a data de carga preenchida.
                Se não tiver, não tem como buscar a ordem de solda relacionada.
            """
            return JsonResponse({
                'status': 'error', 
                'message': 'Não foram encontrados dados de montagem para esta ordem de montagem',
                'dados': None
            }, status=400)
        
        ordem_solda = Ordem.objects.filter(
            data_carga=data_carga_montagem,
            grupo_maquina='solda',
            ordem_pecas_solda__peca__istartswith=codigo_peca
        ).first()

        if not ordem_solda:
            return JsonResponse({
                'status': 'error',
                'message': 'Ordem de solda não encontrada',
                'dados': None
            }, status=404)

        # Busca a ordem principal E todas as sub-ordens (filhas) relacionadas
        ordens_relacionadas = list(Ordem.objects.filter(
            Q(id=ordem_solda.id) | Q(ordem_pai=ordem_solda)
        ))

        print(f"Total de ordens relacionadas encontradas: {len(ordens_relacionadas)}")

        # Coleta todos os status das ordens relacionadas
        status_list = [
            ordem.status_atual.lower() if ordem.status_atual else ''
            for ordem in ordens_relacionadas
        ]

        print(f"Status coletados: {status_list}")

        # Busca todas as peças da ordem de solda principal
        todas_pecas_solda = ordem_solda.ordem_pecas_solda.all()
        ordem_pecas_solda = todas_pecas_solda.first()

        # Pega a qtd_planejada da ordem principal (não soma)
        qtd_planejada = ordem_pecas_solda.qtd_planejada if ordem_pecas_solda else 0

        # Calcula apenas o total de qtd_boa de TODAS as ordens relacionadas
        qtd_boa_total = 0

        for ordem_rel in ordens_relacionadas:
            pecas = ordem_rel.ordem_pecas_solda.all()
            for peca in pecas:
                qtd_boa_total += peca.qtd_boa if peca.qtd_boa else 0

        print(f"Qtd Planejada: {qtd_planejada}, Qtd Boa Total: {qtd_boa_total}")

        # Calcula o status baseado nas regras de negócio (analisando TODAS as ordens)
        
        # Regra 1: Se pelo menos uma for "iniciada" → "iniciada"
        if 'iniciada' in status_list:
            status_calculado = 'iniciada'
            print("Status calculado: iniciada (pelo menos uma iniciada)")
        # Regra 2: Se qtd_planejada == qtd_boa_total → "finalizada"
        elif qtd_planejada > 0 and qtd_planejada == qtd_boa_total:
            status_calculado = 'finalizada'
            print("Status calculado: finalizada (qtd planejada == qtd boa)")
        # Regra 3: Se todas forem "retorno" → "retorno"
        elif status_list and all(s == 'retorno' for s in status_list):
            status_calculado = 'retorno'
            print("Status calculado: retorno (todas retorno)")
        # Regra 4: Se todas forem "interrompida" → "interrompida"
        elif status_list and all(s == 'interrompida' for s in status_list):
            status_calculado = 'interrompida'
            print("Status calculado: interrompida (todas interrompidas)")
        # Regra 5: Padrão → "aguardando_iniciar"
        else:
            status_calculado = 'aguardando_iniciar'
            print("Status calculado: aguardando_iniciar (padrão)")

        dados = {
            'ordem': ordem_solda.id,
            'maquina': ordem_solda.maquina.nome if ordem_solda.maquina else None,
            'status': status_calculado,
            'peca': ordem_pecas_solda.peca if ordem_pecas_solda else None,
            'qtd_planejada': qtd_planejada,
            'qtd_boa': qtd_boa_total,
            'data_carga': ordem_solda.data_carga.strftime('%d/%m/%Y') if ordem_solda.data_carga else None,
            'total_ordens_relacionadas': len(ordens_relacionadas),  # Info adicional para debug
        }

        print(dados)
        
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