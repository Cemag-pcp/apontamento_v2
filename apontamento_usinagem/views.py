from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.http import HttpResponse
from django.db.models import Q, Max,OuterRef,Subquery

from cadastro.models import Pecas, Operador, MotivoInterrupcao, Maquina
from apontamento.models import Apontamento, Planejamento, Interrupcao, PlanejamentoPeca
# from .forms import PlanejamentoForm

def lista_ordens(request):
    # Filtrar as ordens pelo status
    ordens_planejadas = Planejamento.objects.filter(status_andamento='aguardando_iniciar', setor='usinagem')

    ordens_em_processo = Apontamento.objects.filter(status='iniciado', planejamento__setor='usinagem')
    
    # Subquery para pegar a última interrupção (baseada na data de interrupção) para cada apontamento
    ultima_interrupcao = Interrupcao.objects.filter(
        apontamento=OuterRef('pk')
    ).order_by('-data_interrupcao').values('motivo__nome', 'data_interrupcao')[:1]

    # Consulta para obter os apontamentos interrompidos e suas últimas interrupções
    ordens_interrompidas = Apontamento.objects.filter(status='interrompido',planejamento__setor='usinagem').annotate(
        motivo_interrupcao=Subquery(ultima_interrupcao.values('motivo__nome')[:1]),
        data_interrupcao=Subquery(ultima_interrupcao.values('data_interrupcao')[:1])
    )

    operadores = Operador.objects.all()
    motivos = MotivoInterrupcao.objects.all()
    maquinas = Maquina.objects.filter(setor='usinagem')

    context = {
        'ordens_planejadas': ordens_planejadas,
        'ordens_em_processo': ordens_em_processo,
        'ordens_interrompidas': ordens_interrompidas,
        'operadores': operadores,
        'motivos': motivos,
        'maquinas': maquinas,
    }
    return render(request, 'apontamento_usinagem/lista_ordens.html', context)

def planejar(request):

    maquinas = Maquina.objects.filter(setor='usinagem')

    if request.method == 'POST':
        pecas = []
        for key in request.POST:
            if key.startswith('peca_'):
                index = key.split('_')[1]  # Extrai o índice da peça
                peca_id = request.POST.get(f'peca_{index}')
                quantidade = request.POST.get(f'quantidade_{index}')
                data_planejada = request.POST.get(f'data_planejada_{index}')
                maquina = request.POST.get(f'maquina_{index}', None)
                setor = 'usinagem'

                # Criar o planejamento para cada peça
                peca = Pecas.objects.get(id=peca_id)
                
                if maquina:
                    maquina = Maquina.objects.get(id=maquina)
                else:
                    maquina = None
                
                planejamento=Planejamento.objects.create(
                    data_planejada=data_planejada,
                    tipo_planejamento='planejamento',
                    setor=setor,
                    maquina=maquina
                    
                )
                
                PlanejamentoPeca.objects.create(
                    planejamento=planejamento,
                    peca=peca,
                    quantidade_planejada=quantidade,
                )
                
        return redirect('apontamento_usinagem:lista_ordens')  # Redireciona após o sucesso

    pecas = Pecas.objects.filter(setor='usinagem')
    context = {
        'pecas': pecas,
        'maquinas':maquinas
    }
    return render(request, 'apontamento_usinagem/planejar.html', context)

def finalizar_apontamento(request, apontamento_id):
    # Busca o apontamento
    apontamento = get_object_or_404(Apontamento, pk=apontamento_id)

    # Pega os dados enviados pelo formulário (POST)
    maquina_id = request.POST.get('maquina')
    quantidade_produzida = request.POST.get('quantidade_produzida')
    quantidade_morta = request.POST.get('quantidade_morta')
    proximo_processo = request.POST.get('proximo_processo')  # ID da próxima máquina, pode ser None

    # Finaliza o planejamento e apontamento atual
    maquina_atual = get_object_or_404(Maquina, pk=maquina_id)
    planejamento = apontamento.planejamento
    
    # Busca a única peça planejada associada ao planejamento
    peca_planejada = planejamento.pecas_planejadas.first()  # Como só há uma peça planejada
    
    # Atualiza a peça planejada com a quantidade produzida e morta
    if peca_planejada:
        peca_planejada.quantidade_produzida = int(quantidade_produzida)
        peca_planejada.save()

    # Atualiza o planejamento atual
    planejamento.maquina = maquina_atual
    planejamento.status_andamento = 'finalizado'  # Marca o planejamento como finalizado
    planejamento.save()

    # Finaliza o apontamento atual
    apontamento.finalizar()

    # Se há um próximo processo (ou seja, a peça vai para outra etapa)
    if proximo_processo:
        maquina_proxima = get_object_or_404(Maquina, pk=proximo_processo)
        peca = peca_planejada.peca  # Obtém a peça do planejamento atual

        # Cria um novo planejamento para o próximo processo
        planejamento_new = Planejamento.objects.create(
            data_planejada=planejamento.data_planejada,  # Mantém a data original ou pode alterar
            maquina=maquina_proxima,  # Atribui a nova máquina do próximo processo
            setor='usinagem',  # Ajusta o setor conforme a nova máquina
        )

        PlanejamentoPeca.objects.create(
            planejamento=planejamento_new,
            peca=peca,
            quantidade_planejada=peca_planejada.quantidade_produzida  # Usa a quantidade produzida no novo planejamento
        )

    # Redireciona para a lista de ordens
    return redirect('apontamento_usinagem:lista_ordens')

def editar_planejamento(request, planejamento_id):
    planejamento = get_object_or_404(Planejamento, id=planejamento_id)
    pecas = Pecas.objects.filter(setor='usinagem')
    maquinas = Maquina.objects.filter(setor='usinagem')

    if request.method == 'POST':
        # Limpa os antigos PlanejamentoPeca relacionados ao Planejamento
        PlanejamentoPeca.objects.filter(planejamento=planejamento).delete()

        # Itera sobre os campos do formulário dinâmico para salvar as novas peças planejadas
        peca_count = len([key for key in request.POST if key.startswith('peca_')])
        
        for i in range(peca_count):
            peca_id = request.POST.get(f'peca_{i}')
            quantidade_planejada = request.POST.get(f'quantidade_{i}')
            data_planejada = request.POST.get(f'data_planejada_{i}')
            maquina_id = request.POST.get(f'maquina_{i}')

            if peca_id and quantidade_planejada and data_planejada and maquina_id:
                peca = Pecas.objects.get(id=peca_id)
                maquina = Maquina.objects.get(id=maquina_id)
                
                # Cria um novo PlanejamentoPeca para cada peça
                PlanejamentoPeca.objects.create(
                    planejamento=planejamento,
                    peca=peca,
                    quantidade_planejada=quantidade_planejada
                )

        # Atualiza o planejamento principal
        planejamento.data_planejada = request.POST.get('data_planejada_0')  # Atualiza com base na primeira peça
        planejamento.maquina_id = request.POST.get('maquina_0')  # Atualiza com base na primeira peça
        planejamento.save()

        return redirect('apontamento_usinagem:lista_ordens')

    return render(request, 'apontamento_usinagem/editar_planejamento.html', {
        'planejamento': planejamento,
        'pecas': pecas,
        'maquinas': maquinas
    })