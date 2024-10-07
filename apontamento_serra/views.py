from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import OuterRef,Subquery
from django.utils.dateparse import parse_date  # Import para formatar a data corretamente

from cadastro.models import *
from apontamento.models import *
# from .forms import PlanejamentoForm

def lista_ordens(request):
    # Filtrar os processos relacionados ao setor "Serra"
    peca_processos_serra = PecaProcesso.objects.filter(processo__nome='serra')
    peca_processos_serra_ids = peca_processos_serra.values_list('id', flat=True)

    # Filtrar os planejamentos pendentes associados às peças que estão no processo "Serra"
    ordens_planejadas = Planejamento.objects.filter(
        pecas_planejadas__peca__in=peca_processos_serra_ids,
        status_andamento='aguardando_iniciar'
    ).distinct().prefetch_related('pecas_planejadas')

    # Filtrar os apontamentos que estão em processo no setor "Serra"
    ordens_em_processo = Apontamento.objects.filter(
        planejamento__pecas_planejadas__peca__in=peca_processos_serra_ids,
        status='iniciado'
    ).distinct().select_related('planejamento')

    # Subquery para pegar a última interrupção para cada apontamento
    ultima_interrupcao = Interrupcao.objects.filter(
        apontamento=OuterRef('pk')
    ).order_by('-data_interrupcao')

    # Filtrar os apontamentos interrompidos e adicionar o motivo da interrupção e a data
    ordens_interrompidas = Apontamento.objects.filter(
        planejamento__pecas_planejadas__peca__in=peca_processos_serra_ids,
        status='interrompido'
    ).distinct().annotate(
        motivo_interrupcao=Subquery(ultima_interrupcao.values('motivo__nome')[:1]),
        data_interrupcao=Subquery(ultima_interrupcao.values('data_interrupcao')[:1])
    ).select_related('planejamento')

    # Obter todos os operadores, motivos de interrupção e máquinas do setor de serra
    operadores = Operador.objects.all()
    motivos = MotivoInterrupcao.objects.all()
    maquinas = Maquina.objects.filter(setor__nome='serra')

    ordens_padrao = OrdemPadrao.objects.all()

    context = {
        'ordens_planejadas': ordens_planejadas,
        'ordens_em_processo': ordens_em_processo,
        'ordens_interrompidas': ordens_interrompidas,
        'operadores': operadores,
        'motivos': motivos,
        'maquinas': maquinas,
        'ordens_padrao': ordens_padrao,
        'pecas':peca_processos_serra.filter(ordem=1).distinct()
    }

    return render(request, 'apontamento_serra/lista_ordens.html', context)

def finalizar_apontamento(request, apontamento_id):
    # Busca o apontamento
    apontamento = get_object_or_404(Apontamento, pk=apontamento_id)

    # Busca as peças relacionadas ao planejamento do apontamento
    planejamento_pecas = PlanejamentoPeca.objects.filter(planejamento=apontamento.planejamento)

    if planejamento_pecas.exists():
        # Iterar sobre todas as peças do planejamento
        for planejamento_peca in planejamento_pecas:

            # Verifica se a peça possui um próximo processo
            proximo_processo = PecaProcesso.objects.filter(
                peca=planejamento_peca.peca.peca,  # Acessa o modelo 'Pecas' através de 'PecaProcesso'
                ordem__gt=planejamento_peca.ordem  # Verifica o próximo na ordem
            ).order_by('ordem').first()

            # Se houver próximo processo, abrir um novo planejamento e incrementar a ordem
            if proximo_processo:
                nova_ordem = planejamento_peca.ordem + 1

                # Criar um novo planejamento para o próximo processo
                planejamento_novo = Planejamento.objects.create(
                    data_planejada=timezone.now(),
                    setor=proximo_processo.processo
                )

                # Criar PlanejamentoPeca com a nova ordem
                PlanejamentoPeca.objects.create(
                    planejamento=planejamento_novo,
                    peca=proximo_processo,
                    quantidade_planejada=planejamento_peca.quantidade_planejada,
                    ordem=nova_ordem  # Incrementa a ordem
                )

    # Se for uma requisição POST, atualizar os detalhes do apontamento
    if request.method == 'POST':
        # Pega o ID da máquina e outras informações do POST
        maquina_id = request.POST.get('maquina')
        tamanho_vara = request.POST.get('tamanho_vara')
        quantidade_vara = request.POST.get('quantidade_vara')

        maquina_object = get_object_or_404(Maquina, pk=maquina_id)

        # Obtém o planejamento associado ao apontamento
        planejamento = apontamento.planejamento

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

                # Atualiza o objeto PlanejamentoPeca com os valores produzidos e mortos
                peca_planejada.quantidade_produzida = quantidade_produzida
                peca_planejada.quantidade_morta = quantidade_morta
                peca_planejada.save()

                # Verifica se a peça foi finalizada
                # Se houver um próximo processo, criar novo planejamento
                if proximo_processo:
                    planejamento_novo = Planejamento.objects.create(
                        data_planejada=timezone.now(),
                        setor=proximo_processo.processo
                    )
                    # Criar PlanejamentoPeca com a nova ordem
                    PlanejamentoPeca.objects.create(
                        planejamento=planejamento_novo,
                        peca=proximo_processo,
                        quantidade_planejada=quantidade_produzida,
                        ordem=nova_ordem  # Incrementa a ordem
                    )

    # Finaliza o apontamento (atualiza o status e data de finalização)
    apontamento.status = 'finalizado'
    apontamento.data_finalizacao = timezone.now()
    apontamento.save()

    # Redireciona para a lista de ordens
    return redirect('apontamento_serra:lista_ordens')

def planejar(request):

    pecas = PecaProcesso.objects.filter(processo__nome='serra', ordem=1)
    mp = Pecas.objects.values('materia_prima').distinct()

    if request.method == 'POST':
        # Criar o planejamento
        tamanho_planejado_vara = request.POST.get('tamanho_planejado_vara')
        qt_planejada_vara = request.POST.get('qt_planejada_vara')
        data_planejada = parse_date(request.POST.get('data_planejada'))
        mp_usada = request.POST.get('mp_usada_peca_0')
        setor = 'serra'

        planejamento = Planejamento.objects.create(
            data_planejada=data_planejada,
            setor=get_object_or_404(Setor, nome=setor),
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
                # Busca a peça no modelo Pecas
                peca = get_object_or_404(Pecas, id=peca_id)
                print(peca)

                # Busca o PecaProcesso correspondente à peça
                peca_processo = PecaProcesso.objects.filter(peca=peca).first()  # Se há um processo associado

                if peca_processo:
                    PlanejamentoPeca.objects.create(
                        planejamento=planejamento,
                        peca=peca_processo,
                        quantidade_planejada=quantidade
                    )

        return redirect('apontamento_serra:lista_ordens')

    return render(request, 'apontamento_serra/planejar.html', {'pecas': pecas,
                                                                'mps': mp, })

def editar_planejamento(request, planejamento_id):
    planejamento = get_object_or_404(Planejamento, id=planejamento_id)
    # pecas = Pecas.objects.filter(setor__nome='serra')
    pecas = PecaProcesso.objects.filter(processo__nome='serra', ordem=1)

    maquinas = Maquina.objects.filter(setor__nome='serra')
    mp = Pecas.objects.values('materia_prima').distinct()

    if request.method == 'POST':
        # Atualiza os dados do planejamento
        planejamento.data_planejada = request.POST.get('data_planejada')
        planejamento.tamanho_vara = request.POST.get('tamanho_vara')
        planejamento.mp_usada = request.POST.get('mp_usada_peca_0')
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

                # Busca a peça no modelo Pecas
                peca = get_object_or_404(Pecas, id=peca_id)

                # Busca o PecaProcesso correspondente à peça
                peca_processo = PecaProcesso.objects.filter(peca=peca).first()  # Se há um processo associado

                PlanejamentoPeca.objects.create(
                    planejamento=planejamento,
                    peca=peca_processo,
                    quantidade_planejada=quantidade_planejada,
                )

        return redirect('apontamento_serra:lista_ordens')

    return render(request, 'apontamento_serra/editar_planejamento.html', {
        'planejamento': planejamento,
        'pecas': pecas,
        'maquinas': maquinas,
        'mps':mp
    })

def escolher_ordem_padrao(request, pk):
    planejamento = get_object_or_404(OrdemPadrao, id=pk)
    pecas = Pecas.objects.filter(setor__nome='serra')
    maquinas = Maquina.objects.filter(setor__nome='serra')
    mp = Pecas.objects.values('materia_prima').distinct()

    if request.method == 'POST':
        
        planejamento = Planejamento.objects.create(
            data_planejada=request.POST.get('data_planejada'),
            setor=get_object_or_404(Setor, nome='serra'),
            tamanho_vara=request.POST.get('tamanho_vara'),
            quantidade_vara=request.POST.get('qt_planejada_vara'),
            mp_usada=request.POST.get('mp_usada_peca_0'),
        )

        pecaCount = int(request.POST.get('pecaCount'))

        # Remove peças antigas relacionadas ao planejamento
        PlanejamentoPeca.objects.filter(planejamento=planejamento).delete()

        # Itera sobre as novas peças adicionadas no formulário
        for i in range(pecaCount):  # Usar o número de peças dinamicamente gerado
            peca_id = request.POST.get(f'peca_{i}')
            quantidade_planejada = request.POST.get(f'quantidade_{i}')

            if peca_id and quantidade_planejada:

                # Busca a peça no modelo Pecas
                peca = get_object_or_404(Pecas, id=peca_id)

                # Busca o PecaProcesso correspondente à peça
                peca_processo = PecaProcesso.objects.filter(peca=peca).first()  # Se há um processo associado

                PlanejamentoPeca.objects.create(
                    planejamento=planejamento,
                    peca=peca_processo,
                    quantidade_planejada=quantidade_planejada,
                )

        return redirect('apontamento_serra:lista_ordens')

    return render(request, 'apontamento_serra/editar_planejamento.html', {
        'planejamento': planejamento,
        'pecas': pecas,
        'maquinas': maquinas,
        'mps':mp,
        'ordem_padrao':True
    })

def planejar_ordem_padrao(request):
    # Obtém todas as peças para preencher o dropdown no template
    pecas = PecaProcesso.objects.all()

    # Inicialmente, traz todas as ordens padrão
    ordens_padrao = OrdemPadrao.objects.all()

    # Verificar se há um filtro de peça no request (vários IDs)
    pecas_selecionadas = request.GET.getlist('pecaOrdemPadrao')  # Obtém uma lista de peças do GET
    if pecas_selecionadas:
        # Se uma ou mais peças foram selecionadas, filtrar as ordens padrão que possuem essas peças
        ordens_padrao = ordens_padrao.filter(pecas__id__in=pecas_selecionadas).distinct()

    # Renderiza o template passando as peças e as ordens filtradas
    return render(request, 'apontamento_serra/lista_ordens.html', {
        'pecas': pecas,
        'ordens_padrao': ordens_padrao,
    })
