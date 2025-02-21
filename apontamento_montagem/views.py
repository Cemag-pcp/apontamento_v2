from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.timezone import now
from django.db.models import Sum
from django.db import transaction
from django.shortcuts import get_object_or_404

import json
from datetime import datetime

from .models import PecasOrdem
from core.models import Ordem, OrdemProcesso, MaquinaParada, MotivoInterrupcao, MotivoMaquinaParada
from cadastro.models import Operador, Maquina

@csrf_exempt
def criar_ordem(request):

    """
    Maneira de chamar a API:
    {
        "obs": "testes",
        "peca_nome": "123456",
        "qtd_planejada": 5
        "data_carga": "2025-02-19"
        "setor_conjunto": "Içamento",
    }   
    """

    if request.method == 'POST':
        try:
            data = json.loads(request.body)

            # Capturar dados da ordem
            grupo_maquina = data.get('grupo_maquina', 'montagem')  # Define 'pintura' como padrão
            obs = data.get('obs', '')
            nome_peca = data.get('peca_nome')
            qtd_planejada = data.get('qtd_planejada', 0)
            data_carga = data.get('data_carga', now())
            setor_conjunto = data.get('setor_conjunto')

            if not nome_peca:
                return JsonResponse({'error': 'Nome da peça é obrigatório!'}, status=400)

            if not setor_conjunto:
                return JsonResponse({'error': 'Setor de conjunto é obrigatório!'}, status=400)

            with transaction.atomic():

                ordem = Ordem.objects.create(
                    grupo_maquina=grupo_maquina,
                    status_atual='aguardando_iniciar',
                    obs=obs,
                    data_criacao=now(),
                    data_carga=datetime.strptime(data_carga, "%Y-%m-%d").date(),
                    maquina=get_object_or_404(Maquina, nome=setor_conjunto)
                )

                # Criar a única peça associada à ordem
                peca = PecasOrdem.objects.create(
                    ordem=ordem,
                    peca=nome_peca,
                    qtd_planejada=qtd_planejada,
                    qtd_boa=0,  # Inicialmente 0
                    qtd_morta=0
                )

                return JsonResponse({
                    'message': 'Ordem e peça criadas com sucesso!',
                    'ordem_id': ordem.id,
                    'peca': {'id': peca.id, 'nome': peca.peca, 'qtd_planejada': peca.qtd_planejada}
                })

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Método não permitido!'}, status=405)

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
        qt_mortas = body.get('qt_mortas', 0)

        if not ordem_id or not grupo_maquina or not status:
            return JsonResponse({'error': 'Campos obrigatórios não enviados.'}, status=400)

        # Obtém a ordem ANTES da transação, para evitar falha na atomicidade
        ordem = get_object_or_404(Ordem, pk=ordem_id)

        # Validações básicas
        if ordem.status_atual == status:
            return JsonResponse({'error': f'Essa ordem já está {status}. Atualize a página.'}, status=400)

        with transaction.atomic():  # Entra na transação somente após garantir que todos os objetos existem

            # Finaliza o processo atual (se existir)
            processo_atual = ordem.processos.filter(data_fim__isnull=True).first()
            if processo_atual:
                processo_atual.finalizar_atual()

            # Cria o novo processo
            novo_processo = OrdemProcesso.objects.create(
                ordem=ordem,
                status=status,
                data_inicio=now(),
                data_fim=now() if status in ['finalizada'] else None,
            )

            if status == 'iniciada':
                # Finaliza a parada da máquina se necessário
                
                maquinas_paradas = MaquinaParada.objects.filter(maquina=ordem.maquina, data_fim__isnull=True)
                for parada in maquinas_paradas:
                    parada.data_fim = now()
                    parada.save()

                ordem.status_prioridade = 1

                # Atualiza o status da ordem
                ordem.status_atual = status

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
                    qtd_morta=int(qt_mortas),
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
    
