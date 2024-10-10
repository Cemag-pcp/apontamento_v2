from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import OuterRef,Subquery,Q
from django.utils.dateparse import parse_date  # Import para formatar a data corretamente
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.urls import reverse

from cadastro.models import *
from apontamento.models import *

def lista_ordens(request):

    pecas = PecaProcesso.objects.filter(processo__nome='serra', ordem=1).select_related('peca', 'processo')

    return render(request, 'apontamento_serra/lista_ordens.html', {'pecas': pecas})

def datatable_ordens(request):
    # Filtros e parâmetros de DataTables
    start = int(request.GET.get('start', 0))
    length = int(request.GET.get('length', 10))
    search_value = request.GET.get('search[value]', '').strip()
    order_column = request.GET.get('order[0][column]', '0')
    order_dir = request.GET.get('order[0][dir]', 'asc')
    
    # Mapeamento das colunas para ordenar
    order_column_map = {
        '0': 'numero_ordem',
        '1': 'pecas__peca__codigo',
    }
    order_column = order_column_map.get(order_column, 'numero_ordem')
    
    if order_dir == 'desc':
        order_column = f'-{order_column}'

    # Filtrando por múltiplas peças, se os IDs forem fornecidos
    peca_ids = request.GET.getlist('pecaOrdemPadrao[]')
    ordens = OrdemPadrao.objects.all()

    if peca_ids:
        ordens = ordens.filter(pecas__id__in=peca_ids).distinct()

    # Filtro de pesquisa global
    if search_value:
        ordens = ordens.filter(
            Q(numero_ordem__icontains=search_value) |
            Q(pecas__peca__codigo__icontains=search_value) |
            Q(pecas__peca__descricao__icontains=search_value)
        ).distinct()

    # Ordenação e paginação
    ordens = ordens.order_by(order_column)
    paginator = Paginator(ordens, length)
    page = paginator.get_page(start // length + 1)

    # Dados para retornar
    data = []
    for ordem in page:
        data.append({
            'numero_ordem': ordem.numero_ordem,
            'pecas': '<br>'.join([f"{peca.peca.codigo} - {peca.peca.descricao}" for peca in ordem.pecas.all()]),
            'planejar': f'<a href="{reverse("apontamento_serra:escolher_ordem_padrao", args=[ordem.pk])}">Escolher</a>'
        })

    # Retorno em formato JSON para o DataTables
    return JsonResponse({
        'draw': int(request.GET.get('draw', 0)),
        'recordsTotal': OrdemPadrao.objects.count(),
        'recordsFiltered': paginator.count,
        'data': data,
    })

def carregar_ordens_planejadas(request):

    ordens_planejadas = Planejamento.objects.filter(
        setor__nome='serra',
        status_andamento='aguardando_iniciar'
    ).distinct().prefetch_related('pecas_planejadas__peca')

    operadores = Operador.objects.filter(setor__nome='serra')

    return render(request, 'apontamento_serra/partials/ordens_planejadas.html', {'ordens_planejadas': ordens_planejadas, 'operadores': operadores})

def carregar_ordens_em_processo(request):

    ordens_em_processo = Planejamento.objects.filter(
        setor__nome='serra',
        status_andamento='iniciada'
    ).prefetch_related('pecas_planejadas__peca')

    # Carregar máquinas e motivos de interrupção
    maquinas = Maquina.objects.filter(setor__nome='serra')
    motivos = MotivoInterrupcao.objects.all()

    return render(request, 'apontamento_serra/partials/ordens_em_processo.html', {
        'ordens_em_processo': ordens_em_processo,
        'maquinas': maquinas,
        'motivos': motivos
    })

def carregar_ordens_interrompidas(request):
    # peca_processos_serra = PecaProcesso.objects.filter(
    #     processo__nome='serra'
    # ).select_related('peca', 'processo', 'maquina').distinct()

    # peca_ids_serra = list(peca_processos_serra.values_list('peca__id', flat=True))

    ultima_interrupcao = Interrupcao.objects.filter(
        apontamento=OuterRef('pk')
    ).order_by('-data_interrupcao')

    ordens_interrompidas = Apontamento.objects.filter(
        planejamento__setor__nome='serra',
        status='interrompido'
    ).distinct().annotate(
        motivo_interrupcao=Subquery(ultima_interrupcao.values('motivo__nome')[:1]),
        data_interrupcao=Subquery(ultima_interrupcao.values('data_interrupcao')[:1])
    ).select_related('planejamento')

    return render(request, 'apontamento_serra/partials/ordens_interrompidas.html', {'ordens_interrompidas': ordens_interrompidas})

def finalizar_apontamento(request, planejamento_id):
    # Busca o apontamento
    apontamento = get_object_or_404(Apontamento, planejamento=planejamento_id)

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
                # if proximo_processo:
                #     planejamento_novo = Planejamento.objects.create(
                #         data_planejada=timezone.now(),
                #         setor=proximo_processo.processo
                #     )
                #     # Criar PlanejamentoPeca com a nova ordem
                #     PlanejamentoPeca.objects.create(
                #         planejamento=planejamento_novo,
                #         peca=proximo_processo,
                #         quantidade_planejada=quantidade_produzida,
                #         ordem=nova_ordem  # Incrementa a ordem
                #     )

    # Finaliza o apontamento (atualiza o status e data de finalização)
    apontamento.finalizar()

    return JsonResponse({'status': 'success', 'message': 'Apontamento finalizado com sucesso.'})

def planejar(request):
    # Otimização de query com select_related para melhorar o desempenho da busca de peças
    pecas = PecaProcesso.objects.filter(processo__nome='serra', ordem=1).select_related('peca', 'processo')

    # Certifique-se de que distinct está realmente necessário, se a tabela é grande pode ser custoso
    mp = Pecas.objects.values('materia_prima').distinct()

    if request.method == 'POST':
        # Extrair dados do POST
        tamanho_planejado_vara = request.POST.get('tamanho_planejado_vara')
        qt_planejada_vara = request.POST.get('qt_planejada_vara')
        data_planejada = parse_date(request.POST.get('data_planejada'))
        mp_usada = request.POST.get('mp_usada_peca_0')
        setor = 'serra'

        # Obter o objeto Setor diretamente
        try:
            setor_obj = Setor.objects.get(nome=setor)
        except Setor.DoesNotExist:
            # Trate o erro conforme necessário
            setor_obj = None  # Ou crie um novo setor, dependendo da lógica do seu aplicativo

        # Criar o planejamento
        planejamento = Planejamento.objects.create(
            data_planejada=data_planejada,
            setor=setor_obj,
            tamanho_vara=tamanho_planejado_vara,
            quantidade_vara=qt_planejada_vara,
            mp_usada=mp_usada,
        )

        # Recuperar os índices das peças a partir do campo oculto
        peca_indices = request.POST.getlist('peca_index[]')

        # Coletar dados das peças
        peca_data_list = []
        for index in peca_indices:
            peca_id = request.POST.get(f'peca_{index}')
            quantidade = request.POST.get(f'quantidade_{index}')
            if peca_id and quantidade:
                peca_data_list.append({'peca_id': peca_id, 'quantidade': quantidade})

        # Obter todos os IDs de peças únicos
        peca_ids = [data['peca_id'] for data in peca_data_list]

        # Buscar todas as peças de uma vez
        pecas = Pecas.objects.filter(id__in=peca_ids)

        # Buscar todos os PecaProcesso correspondentes
        peca_processos = PecaProcesso.objects.filter(peca__in=pecas).select_related('peca', 'processo')
        peca_processo_dict = {str(pp.peca.id): pp for pp in peca_processos}

        # Preparar objetos PlanejamentoPeca para criação em lote
        planejamento_pecas = []
        for data in peca_data_list:
            peca_id = data['peca_id']
            quantidade = data['quantidade']
            peca_processo = peca_processo_dict.get(peca_id)
            if peca_processo:
                planejamento_pecas.append(PlanejamentoPeca(
                    planejamento=planejamento,
                    peca=peca_processo,
                    quantidade_planejada=quantidade
                ))

        # Criar PlanejamentoPeca em lote
        PlanejamentoPeca.objects.bulk_create(planejamento_pecas)

        return redirect('apontamento_serra:lista_ordens')

    return render(request, 'apontamento_serra/planejar.html', {'pecas': pecas, 'mps': mp})

def editar_planejamento(request, planejamento_id):
    # Otimização: Usar select_related para pré-carregar relações
    planejamento = get_object_or_404(Planejamento.objects.select_related('setor'), id=planejamento_id)
    
    # Otimização: Usar select_related para carregar a peça e o processo numa única consulta
    pecas = PecaProcesso.objects.filter(processo__nome='serra', ordem=1).select_related('peca', 'processo')
    
    # Filtrar máquinas do setor "serra"
    maquinas = Maquina.objects.filter(setor__nome='serra')
    
    # Buscar matérias-primas de maneira eficiente
    mp = Pecas.objects.values('materia_prima').distinct()

    if request.method == 'POST':
        # Atualiza os dados do planejamento
        planejamento.data_planejada = request.POST.get('data_planejada')
        planejamento.tamanho_vara = request.POST.get('tamanho_vara')
        planejamento.mp_usada = request.POST.get('mp_usada_peca_0')
        planejamento.quantidade_vara = request.POST.get('qt_planejada_vara')
        planejamento.save()

        pecaCount = int(request.POST.get('pecaCount'))

        # Otimização: Em vez de deletar todas as peças, pode-se verificar as peças removidas e apenas deletá-las
        # No entanto, se for certo que todas mudam, essa operação pode ser mantida
        PlanejamentoPeca.objects.filter(planejamento=planejamento).delete()

        # Otimização: Buscar todas as peças de uma vez para evitar consultas dentro do loop
        pecas_ids = [request.POST.get(f'peca_{i}') for i in range(pecaCount)]
        pecas_obj = Pecas.objects.filter(id__in=pecas_ids)

        pecas_por_id = {str(peca.id): peca for peca in pecas_obj}

        # Itera sobre as novas peças adicionadas no formulário
        for i in range(pecaCount):
            peca_id = request.POST.get(f'peca_{i}')
            quantidade_planejada = request.POST.get(f'quantidade_{i}')

            if peca_id and quantidade_planejada:
                # Busca a peça previamente recuperada do banco
                peca = pecas_por_id.get(peca_id)

                if peca:
                    # Busca o PecaProcesso correspondente à peça
                    peca_processo = PecaProcesso.objects.filter(peca=peca).first()

                    if peca_processo:
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
        'mps': mp,
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
