from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.http import HttpResponse
from django.db.models import Q, Max,OuterRef,Subquery
from django.http import JsonResponse

from cadastro.models import *
from apontamento.models import *
# from .forms import PlanejamentoForm

def lista_ordens(request):

    maquinas = Maquina.objects.filter(setor__nome='usinagem')

    context = {
        'maquinas': maquinas,
    }

    return render(request, 'apontamento_usinagem/lista_ordens.html', context)

def carregar_ordens_planejadas(request):
    
    ordens_planejadas = Planejamento.objects.filter(
        status_andamento='aguardando_iniciar', 
        setor__nome='usinagem'
    ).select_related('setor').prefetch_related('pecas_planejadas')
    operadores = Operador.objects.all()

    return render(request, 'apontamento_usinagem/partials/ordens_planejadas.html', {'ordens_planejadas': ordens_planejadas, 'operadores': operadores})

def carregar_ordens_em_processo(request):

    ordens_em_processo = Planejamento.objects.filter(
        setor__nome='usinagem',
        status_andamento='iniciada'
    ).prefetch_related('pecas_planejadas__peca')

    # Carregar máquinas e motivos de interrupção
    maquinas = Maquina.objects.filter(setor__nome='usinagem')
    motivos = MotivoInterrupcao.objects.all()

    return render(request, 'apontamento_usinagem/partials/ordens_em_processo.html', {
        'ordens_em_processo': ordens_em_processo,
        'maquinas': maquinas,
        'motivos': motivos
    })

def carregar_ordens_interrompidas(request):

    ultima_interrupcao = Interrupcao.objects.filter(
        apontamento=OuterRef('pk')
    ).order_by('-data_interrupcao')

    # Consulta para obter os apontamentos interrompidos e suas últimas interrupções
    ordens_interrompidas = Apontamento.objects.filter(
        status='interrompido', 
        planejamento__setor__nome='usinagem'
    ).annotate(
        motivo_interrupcao=Subquery(ultima_interrupcao.values('motivo__nome')[:1]),
        data_interrupcao=Subquery(ultima_interrupcao.values('data_interrupcao')[:1])
    ).select_related('planejamento')

    return render(request, 'apontamento_usinagem/partials/ordens_interrompidas.html', {'ordens_interrompidas': ordens_interrompidas})

def planejar(request):

    if request.method == 'POST':
        pecas = []
        for key in request.POST:
            if key.startswith('peca_'):
                index = key.split('_')[1]  # Extrai o índice da peça
                peca_id = request.POST.get(f'peca_{index}')
                quantidade = request.POST.get(f'quantidade_{index}')
                data_planejada = request.POST.get(f'data_planejada_{index}')
                setor = 'usinagem'

                # Criar o planejamento para cada peça
                peca = Pecas.objects.get(id=peca_id)
                
                planejamento=Planejamento.objects.create(
                    data_planejada=data_planejada,
                    tipo_planejamento='planejamento',
                    setor=get_object_or_404(Setor, nome=setor),
                )

                peca = get_object_or_404(Pecas, id=peca_id)

                peca_processo = PecaProcesso.objects.filter(peca=peca).first()  # Se há um processo associado
                
                PlanejamentoPeca.objects.create(
                    planejamento=planejamento,
                    peca=peca_processo,
                    quantidade_planejada=quantidade,
                )
                
        return redirect('apontamento_usinagem:lista_ordens')  # Redireciona após o sucesso

    pecas = PecaProcesso.objects.filter(processo__nome='usinagem', ordem=1).select_related('peca', 'processo')

    context = {
        'pecas': pecas,
    }
    return render(request, 'apontamento_usinagem/planejar.html', context)

def finalizar_apontamento(request, planejamento_id):
    # Busca o apontamento
    apontamento = get_object_or_404(Apontamento, planejamento=planejamento_id)

    # Pega os dados enviados pelo formulário (POST)
    quantidade_produzida = request.POST.get('quantidade_produzida')
    quantidade_morta = request.POST.get('quantidade_morta',0)

    # Finaliza o planejamento e apontamento atual
    planejamento = apontamento.planejamento
    
    # Busca a única peça planejada associada ao planejamento
    peca_planejada = planejamento.pecas_planejadas.first()  # Como só há uma peça planejada
    
    # Atualiza a peça planejada com a quantidade produzida
    if peca_planejada:
        peca_planejada.quantidade_produzida = int(quantidade_produzida)
        peca_planejada.quantidade_morta = int(quantidade_morta)
        peca_planejada.save()

    planejamento.status_andamento = 'finalizado'  # Marca o planejamento como finalizado
    planejamento.save()

    # Finaliza o apontamento atual
    apontamento.finalizar()

    # Verificar automaticamente se há um próximo processo para a peça
    peca_processo_atual = peca_planejada.peca
    proximo_processo = PecaProcesso.objects.filter(
        peca=peca_processo_atual.peca,
        ordem__gt=peca_processo_atual.ordem  # Verifica o próximo na ordem de processos
    ).order_by('ordem').first()

    # Se há um próximo processo (ou seja, a peça vai para outra etapa)
    if proximo_processo:
        # Obter a próxima máquina ou setor do próximo processo, conforme necessário
        peca = peca_planejada.peca  # Obtém a peça do planejamento atual

        # Cria um novo planejamento para o próximo processo
        planejamento_new = Planejamento.objects.create(
            data_planejada=timezone.now(),  # Pode ser ajustada conforme a necessidade
            setor=proximo_processo.processo  # Ajusta o setor conforme o próximo processo
        )

        # Cria um novo PlanejamentoPeca com a ordem incrementada e a quantidade produzida
        PlanejamentoPeca.objects.create(
            planejamento=planejamento_new,
            peca=proximo_processo,
            quantidade_planejada=peca_planejada.quantidade_produzida,  # Usa a quantidade produzida no novo planejamento
            ordem=peca_planejada.ordem + 1  # Incrementa a ordem
        )

    # Redireciona para a lista de ordens
    return JsonResponse({'status': 'success', 'message': 'Apontamento finalizado com sucesso.'})

def editar_planejamento(request, planejamento_id):
    planejamento = get_object_or_404(Planejamento, id=planejamento_id)
    # pecas = Pecas.objects.filter(setor__nome='usinagem')
    pecas = PecaProcesso.objects.filter(processo__nome='usinagem', ordem=1)

    if request.method == 'POST':
        # Limpa os antigos PlanejamentoPeca relacionados ao Planejamento
        PlanejamentoPeca.objects.filter(planejamento=planejamento).delete()

        # Itera sobre os campos do formulário dinâmico para salvar as novas peças planejadas
        peca_count = len([key for key in request.POST if key.startswith('peca_')])
        
        for i in range(peca_count):
            peca_id = request.POST.get(f'peca_{i}')
            quantidade_planejada = request.POST.get(f'quantidade_{i}')
            data_planejada = request.POST.get(f'data_planejada_{i}')

            if peca_id and quantidade_planejada and data_planejada:
                peca = get_object_or_404(Pecas, id=peca_id)

                peca_processo = PecaProcesso.objects.filter(peca=peca).first()  # Se há um processo associado

                # Cria um novo PlanejamentoPeca para cada peça
                PlanejamentoPeca.objects.create(
                    planejamento=planejamento,
                    peca=peca_processo,
                    quantidade_planejada=quantidade_planejada
                )

        # Atualiza o planejamento principal
        planejamento.data_planejada = request.POST.get('data_planejada_0')  # Atualiza com base na primeira peça
        planejamento.save()

        return redirect('apontamento_usinagem:lista_ordens')

    return render(request, 'apontamento_usinagem/editar_planejamento.html', {
        'planejamento': planejamento,
        'pecas': pecas,
    })