from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.http import JsonResponse

from .models import Apontamento, Planejamento, PlanejamentoPeca
from cadastro.models import Operador, MotivoInterrupcao, Maquina

def iniciar_apontamento(request, planejamento_id):
    # Busca o planejamento e operador em uma única consulta cada
    planejamento = get_object_or_404(Planejamento, pk=planejamento_id)

    if request.method == 'POST':
        operador_id = request.POST.get('operador')
        operador = get_object_or_404(Operador, pk=operador_id)

        # Captura o namespace (ex: apontamento_usinagem ou apontamento_serra)
        namespace = request.resolver_match.namespace

        # Criar o apontamento e atualizar o status do planejamento em um único save
        Apontamento.objects.create(
            planejamento=planejamento,
            data_inicio=timezone.now(),
            status='iniciado',
            operador=operador
        )
        # Atualiza o status do planejamento em um único passo
        planejamento.status_andamento = 'iniciada'
        planejamento.save(update_fields=['status_andamento'])

        # Simplificação do redirecionamento baseado no namespace
        # return redirect(f'{namespace}:lista_ordens' if namespace in ['apontamento_usinagem', 'apontamento_serra'] else 'lista_ordens')
        namespace = f'{namespace}:lista_ordens' if namespace in ['apontamento_usinagem', 'apontamento_serra'] else 'lista_ordens'

        return JsonResponse({
            'status': 'success', 
            'message': 'Apontamento iniciado com sucesso.',
            'namespace': namespace  # Inclui o namespace na resposta, se necessário
        })
    
    # Se for um GET (não deveria ser neste fluxo), redireciona para a lista de ordens
    return redirect('lista_ordens')

def interromper_apontamento(request, planejamento_id):

    apontamento = get_object_or_404(Apontamento, planejamento=planejamento_id)

    if request.method == 'POST':
        motivo_id = request.POST.get('motivo_interrupcao')
        motivo_object = get_object_or_404(MotivoInterrupcao, pk=motivo_id)

        apontamento.motivo_interrupcao = motivo_object
        apontamento.save()
        apontamento.interromper(motivo_object)

        namespace = request.resolver_match.namespace     

        # Redirecionar para a lista de ordens correta, com base no namespace
        if namespace == 'apontamento_usinagem':
            return JsonResponse({
                'status': 'success', 
                'message': 'Apontamento interrompido com sucesso.',
            })
        elif namespace == 'apontamento_serra':
            return JsonResponse({
                'status': 'success', 
                'message': 'Apontamento interrompido com sucesso.',
            })
        else:
            return redirect('lista_ordens')  # Redireciona para o padrão se namespace não for detectado

def retornar_apontamento(request, planejamento_id):
    apontamento = get_object_or_404(Apontamento, pk=planejamento_id)
    apontamento.retornar()

    namespace = request.resolver_match.namespace        

    # Redirecionar para a lista de ordens correta, com base no namespace
    if namespace == 'apontamento_usinagem':
        return JsonResponse({
            'status': 'success', 
            'message': 'Apontamento retornado com sucesso.',
        })
    elif namespace == 'apontamento_serra':
        return JsonResponse({
            'status': 'success', 
            'message': 'Apontamento retornado com sucesso.',
        })
    else:
        return redirect('lista_ordens')  # Redireciona para o padrão se namespace não for detectado

def finalizar_parcial_apontamento(request, apontamento_id):
    apontamento = get_object_or_404(Apontamento, pk=apontamento_id)

    if request.method == 'POST':
        quantidade_produzida = int(request.POST.get('quantidade_produzida', 0))
        apontamento.finalizar_parcial(quantidade_produzida)
        
        namespace = request.resolver_match.namespace        

        # Redirecionar para a lista de ordens correta, com base no namespace
        if namespace == 'apontamento_usinagem':
            return redirect('apontamento_usinagem:lista_ordens')
        elif namespace == 'apontamento_serra':
            return redirect('apontamento_serra:lista_ordens')
        else:
            return redirect('lista_ordens')  # Redireciona para o padrão se namespace não for detectado

    return render(request, 'apontamento/finalizar_parcial.html', {'apontamento': apontamento})

def detalhe_apontamento(request, apontamento_id):
    apontamento = get_object_or_404(Apontamento, pk=apontamento_id)
    return render(request, 'apontamento/detalhe.html', {'apontamento': apontamento})