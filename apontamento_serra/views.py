from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q, Max,OuterRef,Subquery

from cadastro.models import *
from apontamento.models import *
# from .forms import PlanejamentoForm

def lista_ordens(request):
    # Filtrar as peças que têm o processo "Serra"
    peca_processos_serra = PecaProcesso.objects.filter(processo__nome='Serra')

    # Filtrar os planejamentos associados às peças que estão no processo "Serra"
    ordens_planejadas = Planejamento.objects.filter(
        pecas_planejadas__peca__in=[pp.peca for pp in peca_processos_serra],
        status_andamento='aguardando_iniciar'
    ).distinct().prefetch_related('pecas_planejadas')

    # Filtrar os apontamentos que estão em processo no setor "Serra"
    ordens_em_processo = Apontamento.objects.filter(
        planejamento__pecas_planejadas__peca__in=[pp.peca for pp in peca_processos_serra],
        status='iniciado'
    ).distinct().select_related('planejamento')

    # Subquery para pegar a última interrupção para cada apontamento
    ultima_interrupcao = Interrupcao.objects.filter(
        apontamento=OuterRef('pk')
    ).order_by('-data_interrupcao')

    # Filtrar os apontamentos interrompidos e adicionar o motivo da interrupção e a data
    ordens_interrompidas = Apontamento.objects.filter(
        planejamento__pecas_planejadas__peca__in=[pp.peca for pp in peca_processos_serra],
        status='interrompido'
    ).distinct().annotate(
        motivo_interrupcao=Subquery(ultima_interrupcao.values('motivo__nome')[:1]),
        data_interrupcao=Subquery(ultima_interrupcao.values('data_interrupcao')[:1])
    ).select_related('planejamento')

    # Obter todos os operadores, motivos de interrupção e máquinas do setor de serra
    operadores = Operador.objects.all()
    motivos = MotivoInterrupcao.objects.all()
    maquinas = Maquina.objects.filter(setor='serra')

    context = {
        'ordens_planejadas': ordens_planejadas,
        'ordens_em_processo': ordens_em_processo,
        'ordens_interrompidas': ordens_interrompidas,
        'operadores': operadores,
        'motivos': motivos,
        'maquinas': maquinas,
    }
    return render(request, 'apontamento_serra/lista_ordens.html', context)

def finalizar_apontamento(request, apontamento_id):
    # Busca o apontamento
    apontamento = get_object_or_404(Apontamento, pk=apontamento_id)

    if request.method == 'POST':
        # Pega o ID da máquina e outras informações do POST
        maquina_id = request.POST.get('maquina')
        tamanho_vara = request.POST.get('tamanho_vara')
        quantidade_vara = request.POST.get('quantidade_vara')

        maquina_object = get_object_or_404(Maquina, pk=maquina_id)

        # Obtém o planejamento associado ao apontamento
        planejamento = apontamento.planejamento  # Instância do Planejamento associada

        # Atualiza o campo máquina e outros detalhes no planejamento
        planejamento.maquina = maquina_object
        planejamento.tamanho_vara = tamanho_vara
        planejamento.quantidade_vara = quantidade_vara
        planejamento.save()

        # Iterar sobre as peças planejadas e obter as quantidades produzidas e mortas
        for peca_planejada in planejamento.pecas_planejadas.all():
            # Recupera a quantidade produzida e morta submetida no formulário
            quantidade_produzida = request.POST.get(f'quantidade_produzida_{peca_planejada.id}')
            quantidade_morta = request.POST.get(f'quantidade_morta_{peca_planejada.id}')

            # Verifica se os valores foram fornecidos e converte para inteiros
            if quantidade_produzida is not None and quantidade_morta is not None:
                quantidade_produzida = int(quantidade_produzida)
                quantidade_morta = int(quantidade_morta)

                # Atualiza o objeto PlanejamentoPeca com os valores produzidos e mortas
                peca_planejada.quantidade_produzida = quantidade_produzida
                peca_planejada.quantidade_morta = quantidade_morta
                peca_planejada.save()

            # Planeja o próximo processo para o apontamento
            planejar_proximo_processo(peca_planejada)

        # Finaliza o apontamento (atualiza o status e data de finalização)
        apontamento.finalizar()

        # Redireciona para a lista de ordens
        return redirect('apontamento_serra:lista_ordens')

    # Se não for um POST, redireciona para a lista de ordens
    return redirect('apontamento_serra:lista_ordens')

def planejar_proximo_processo(peca_planejada):
    """
    Função para planejar o próximo processo de uma peça planejada de acordo com a ordem dos processos.
    """

    # Obter todos os processos associados à peça, ordenados pela ordem
    peca_processos = PecaProcesso.objects.filter(peca=peca_planejada.peca).order_by('ordem')

    # Verificar se existem processos para essa peça
    if not peca_processos.exists():
        print(f"Não há processos definidos para a peça {peca_planejada.peca.codigo}")
        return

    # Identificar o processo atual: o último processo finalizado no planejamento atual
    processo_atual = peca_processos.filter(ordem=peca_planejada.planejamento.apontamento_planejamento.last().planejamento.ordem).first()

    if not processo_atual:
        print(f"Nenhum processo atual encontrado para a peça {peca_planejada.peca.codigo}")
        return

    # Agora que temos o processo atual, vamos procurar o próximo na sequência
    proximo_processo = peca_processos.filter(ordem__gt=processo_atual.ordem).first()

    if proximo_processo:
        # Criar um novo planejamento para o próximo processo
        Planejamento.objects.create(
            data_planejada=timezone.now(),
            tipo_planejamento='planejamento',
            status_andamento='aguardando_iniciar'
        )
        print(f"Planejado próximo processo: {proximo_processo.processo.nome} para a peça {peca_planejada.peca.codigo}.")
    else:
        print(f"Não há próximo processo disponível para a peça {peca_planejada.peca.codigo}.")


def planejar(request):

    pecas = Pecas.objects.filter(setor='serra')
    mp = Pecas.objects.values('materia_prima').distinct()

    if request.method == 'POST':
        # Criar o planejamento
        tamanho_planejado_vara = request.POST.get('tamanho_planejado_vara')
        qt_planejada_vara = request.POST.get('qt_planejada_vara')
        data_planejada = request.POST.get('data_planejada')
        mp_usada = request.POST.get('mp_usada')
        setor = 'serra'

        planejamento = Planejamento.objects.create(
            data_planejada=data_planejada,
            setor=setor,
            tamanho_vara=tamanho_planejado_vara,
            quantidade_vara=qt_planejada_vara,
            mp_usada=mp_usada,
        )

        # Recuperar os índices das peças a partir do campo oculto
        peca_indices = request.POST.getlist('peca_index[]')

        # Adicionar as peças associadas
        for index in peca_indices:
            peca_id = request.POST.get(f'peca_{index}')
            quantidade = request.POST.get(f'quantidade_{index}')
            if peca_id and quantidade:
                peca = Pecas.objects.get(id=peca_id)
                PlanejamentoPeca.objects.create(
                    planejamento=planejamento,
                    peca=peca,
                    quantidade_planejada=quantidade
                )

        return redirect('apontamento_serra:lista_ordens')

    return render(request, 'apontamento_serra/planejar.html', {'pecas': pecas, 'mps': mp, })

def editar_planejamento(request, planejamento_id):
    planejamento = get_object_or_404(Planejamento, id=planejamento_id)
    pecas = Pecas.objects.filter(setor='serra')
    maquinas = Maquina.objects.filter(setor='serra')
    mp = Pecas.objects.values('materia_prima').distinct()

    if request.method == 'POST':
        # Atualiza os dados do planejamento
        mp_usada = request.POST.get('mp_usada')

        planejamento.data_planejada = request.POST.get('data_planejada')
        planejamento.tamanho_vara = request.POST.get('tamanho_vara')
        planejamento.mp_usada = request.POST.get('mp_usada')
        planejamento.quantidade_vara = request.POST.get('qt_planejada_vara')
        planejamento.save()

        pecaCount = int(request.POST.get('pecaCount'))

        # Remove peças antigas relacionadas ao planejamento
        PlanejamentoPeca.objects.filter(planejamento=planejamento).delete()

        # Itera sobre as novas peças adicionadas no formulário
        for i in range(pecaCount):  # Usar o número de peças dinamicamente gerado
            peca_id = request.POST.get(f'peca_{i}')
            quantidade_planejada = request.POST.get(f'quantidade_{i}')

            if peca_id and quantidade_planejada:
                peca = Pecas.objects.get(id=peca_id)
                PlanejamentoPeca.objects.create(
                    planejamento=planejamento,
                    peca=peca,
                    quantidade_planejada=quantidade_planejada,
                )

        return redirect('apontamento_serra:lista_ordens')

    return render(request, 'apontamento_serra/editar_planejamento.html', {
        'planejamento': planejamento,
        'pecas': pecas,
        'maquinas': maquinas,
        'mps':mp
    })
