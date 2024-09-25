from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.http import HttpResponse
from django.db.models import Q, Max,OuterRef,Subquery

from cadastro.models import Operador, MotivoInterrupcao, Maquina, Pecas
from apontamento.models import Apontamento, Planejamento, Interrupcao, PlanejamentoPeca
# from .forms import PlanejamentoForm

def lista_ordens(request):
    # Filtrar as ordens pelo status
    ordens_planejadas = Planejamento.objects.filter(~Q(status_andamento='iniciada'))
    ordens_planejadas = ordens_planejadas.filter(setor='serra')

    # Use 'planejamento_peca' para se referir corretamente ao campo ForeignKey no Apontamento
    ordens_em_processo = Apontamento.objects.filter(
        status='iniciado',
        planejamento__setor='serra'
    )
    
    # Subquery para pegar a última interrupção (baseada na data de interrupção) para cada apontamento
    ultima_interrupcao = Interrupcao.objects.filter(
        apontamento=OuterRef('pk')  # Usando OuterRef para pegar a última interrupção de cada apontamento
    ).order_by('-data_interrupcao')  # Ordena pelas mais recentes
     
    # Consulta para obter os apontamentos interrompidos e suas últimas interrupções
    ordens_interrompidas = Apontamento.objects.filter(
        status='interrompido',
        planejamento__setor='serra'  # Referência ao setor dentro do planejamento
    ).annotate(
        motivo_interrupcao=Subquery(ultima_interrupcao.values('motivo__nome')[:1]),  # Pega o nome do motivo
        data_interrupcao=Subquery(ultima_interrupcao.values('data_interrupcao')[:1])  # Pega a data da interrupção
    )

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
        # Pega o ID da máquina do POST
        maquina_id = request.POST.get('maquina')
        tamanho_vara = request.POST.get('tamanho_vara')
        quantidade_vara = request.POST.get('quantidade_vara')

        maquina_object = get_object_or_404(Maquina, pk=maquina_id)

        # Obtém o planejamento associado ao apontamento
        planejamento = apontamento.planejamento  # Instância do Planejamento associada

        # Atualiza o campo máquina e tamanho da vara no planejamento
        planejamento.maquina = maquina_object
        planejamento.tamanho_vara = tamanho_vara
        planejamento.quantidade_vara = quantidade_vara
        planejamento.save()

        # Iterar sobre as peças planejadas e obter as quantidades produzidas e mortas
        for peca_planejada in planejamento.pecas_planejadas.all():
            # Recupera a quantidade produzida e morta submetida no formulário
            quantidade_produzida = request.POST.get(f'quantidade_produzida_{peca_planejada.id}')
            quantidade_morta = request.POST.get(f'quantidade_morta_{peca_planejada.id}')

            # Verifica se os valores foram fornecidos
            if quantidade_produzida is not None and quantidade_morta is not None:
                quantidade_produzida = int(quantidade_produzida)
                quantidade_morta = int(quantidade_morta)

                # Atualiza o objeto PlanejamentoPeca (adapte para o seu modelo)
                peca_planejada.quantidade_produzida = quantidade_produzida
                peca_planejada.quantidade_morta = quantidade_morta  # Certifique-se de ter este campo no modelo PlanejamentoPeca
                peca_planejada.save()

        # Finaliza o apontamento (atualiza o status e salva o registro)
        apontamento.finalizar()

        # Redireciona para a lista de ordens
        return redirect('apontamento_serra:lista_ordens')

    # Se não for um POST, redireciona
    return redirect('apontamento_serra:lista_ordens')

def planejar(request):

    pecas = Pecas.objects.all()
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
    pecas = Pecas.objects.all()
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
