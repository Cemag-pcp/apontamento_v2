from django.shortcuts import render
from django.http import JsonResponse
from django.views import View
from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.core.paginator import Paginator, EmptyPage
from django.views.decorators.http import require_GET
from django.utils.timezone import now
from django.db.models import Q,Prefetch

from .models import Ordem,PecasOrdem
from core.models import OrdemProcesso
from cadastro.models import MotivoInterrupcao, Conjuntos, Operador, Setor, Pecas

import pandas as pd
import os
import tempfile
import re
import json

# Caminho para a pasta temporária dentro do projeto
TEMP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'temp')

# Certifique-se de que a pasta existe
os.makedirs(TEMP_DIR, exist_ok=True)

def extrair_numeracao(nome_arquivo):
    match = re.search(r"(?i)OP(\d+)", nome_arquivo)  # (?i) torna a busca case insensitive
    if match:
        return match.group(1)
    return None

def planejamento(request):

    motivos = MotivoInterrupcao.objects.filter(setor__nome='prod_esp')
    operadores = Operador.objects.filter(setor__nome='prod_esp')

    return render(request, 'apontamento_prod_esp/planejamento.html', {'motivos':motivos,'operadores':operadores})

def get_pecas_ordem(request, pk_ordem, name_maquina):
    try:
        # Busca a ordem com os relacionamentos necessários
        ordem = Ordem.objects.prefetch_related('ordem_pecas_prod_especiais').get(pk=pk_ordem, grupo_maquina=name_maquina)

        # Obtém a peça relacionada
        peca_ordem = ordem.ordem_pecas_prod_especiais.first()  # Obtém a primeira peça (ou única)

        if not peca_ordem:
            return JsonResponse({'error': 'Nenhuma peça encontrada para esta ordem.'}, status=404)

        # Monta o JSON com os dados da peça
        peca_data = {
            'peca': peca_ordem.conjunto.descricao,
            'quantidade': peca_ordem.qtd_planejada,
            'qtd_morta': peca_ordem.qtd_morta  # Se existir
        }

        return JsonResponse({'peca': peca_data})

    except Ordem.DoesNotExist:
        return JsonResponse({'error': 'Ordem não encontrada.'}, status=404)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def get_ordens_criadas(request):
    # Captura os parâmetros de filtro
    filtro_ordem = request.GET.get('ordem', '').strip()
    filtro_conjunto = request.GET.get('conjunto', '').strip()
    status_atual = request.GET.get('status', '').strip()

    page = int(request.GET.get('page', 1))
    limit = int(request.GET.get('limit', 10))

    # Filtra as ordens com base nos parâmetros
    ordens_queryset = Ordem.objects.prefetch_related('ordem_pecas_prod_especiais').filter(
        grupo_maquina='prod_esp'
    ).order_by('-status_prioridade')

    if filtro_ordem:
        ordens_queryset = ordens_queryset.filter(ordem=filtro_ordem)
    if filtro_conjunto:
        ordens_queryset = ordens_queryset.filter(ordem_pecas_prod_especiais__conjunto__codigo=filtro_conjunto)
    if status_atual:
        ordens_queryset = ordens_queryset.filter(status_atual=status_atual)

    # Paginação
    paginator = Paginator(ordens_queryset, limit)
    try:
        ordens_page = paginator.page(page)
    except EmptyPage:
        return JsonResponse({'ordens': []})  # Retorna vazio se a página não existir

    # Monta os dados para a resposta
    data = []
    for ordem in ordens_page:
        peca_info = ordem.ordem_pecas_prod_especiais.first()  # Assume que há apenas uma peça por ordem

        data.append({
            'id': ordem.pk,
            'ordem': ordem.ordem,
            'grupo_maquina': ordem.get_grupo_maquina_display(),
            'data_criacao': ordem.data_criacao.strftime('%d/%m/%Y %H:%M'),
            'obs': ordem.obs,
            'status_atual': ordem.status_atual,
            'peca': {
                'codigo': peca_info.conjunto.codigo if peca_info and peca_info.conjunto else None,
                'descricao': peca_info.conjunto.descricao if peca_info and peca_info.conjunto else None,
                'quantidade': peca_info.qtd_planejada if peca_info else 0,
            } if peca_info else None  # Retorna `None` se não houver peça
        })

    # Verifica se há próxima página
    has_next = ordens_page.has_next()

    return JsonResponse({
        'ordens': data,
        'has_next': has_next,  # Indica se há próxima página
    })

def atualizar_status_ordem(request):
    if request.method == 'PATCH':
        try:
            with transaction.atomic():
                # Parse do corpo da requisição
                body = json.loads(request.body)
                print(body)

                status = body['status']
                ordem_id = body['ordem_id']
                grupo_maquina = body['grupo_maquina'].lower()
                qt_produzida = body.get('qt_realizada')
                qt_mortas = body.get('qt_mortas')
                
                # Obtém a ordem
                ordem = Ordem.objects.get(pk=ordem_id)
                
                # Validações básicas
                if ordem.status_atual == status:
                    return JsonResponse({'error': f'Essa ordem ja está {status}. Atualize a página.'}, status=400)

                # Finaliza o processo atual (se existir)
                processo_atual = ordem.processos.filter(data_fim__isnull=True).first()
                if processo_atual:
                    processo_atual.finalizar_atual()

                # Cria o novo processo
                novo_processo = OrdemProcesso.objects.create(
                    ordem=ordem,
                    status=status,
                    data_inicio=now(),
                    data_fim=now() if status == 'finalizada' else None
                )

                # Atualiza o status da ordem para o novo status
                ordem.status_atual = status
                
                if status == 'iniciada':
                    ordem.status_prioridade = 1
                elif status == 'finalizada':
                    operador_final = int(body.get('operador_final'))
                    obs_final = body.get('obs_finalizar')

                    ordem.operador_final=get_object_or_404(Operador, pk=operador_final)
                    ordem.obs_operador=obs_final

                    peca = PecasOrdem.objects.get(ordem=ordem)
                    peca.qtd_boa = qt_produzida  
                    peca.qtd_morta = qt_mortas       

                    peca.save()

                    ordem.status_prioridade = 3
                elif status == 'interrompida':
                    novo_processo.motivo_interrupcao = MotivoInterrupcao.objects.get(nome=body['motivo'])
                    novo_processo.save()
                    ordem.status_prioridade = 2

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

    return JsonResponse({'error': 'Método não permitido.'}, status=405)

@require_GET
def get_ordens_iniciadas(request):
    # Filtra as ordens com base no status 'iniciada' e prefetch da peça relacionada
    ordens_queryset = Ordem.objects.prefetch_related(
        'ordem_pecas_prod_especiais__conjunto'
    ).filter(grupo_maquina='prod_esp', status_atual='iniciada')

    # Paginação
    page = int(request.GET.get('page', 1))  # Obtém o número da página
    limit = int(request.GET.get('limit', 10))  # Define o limite padrão por página
    paginator = Paginator(ordens_queryset, limit)  # Aplica a paginação
    try:
        ordens_page = paginator.page(page)  # Obtém a página atual
    except EmptyPage:
        return JsonResponse({'ordens': []})  # Retorna vazio se a página não existir

    # Monta os dados para retorno
    data = []
    for ordem in ordens_page:
        peca_info = ordem.ordem_pecas_prod_especiais.first()  # Obtém a primeira peça relacionada
        conjunto_info = peca_info.conjunto if peca_info else None  # Obtém o conjunto se houver uma peça

        data.append({
            'id': ordem.id,
            'ordem': ordem.ordem,
            'grupo_maquina': ordem.get_grupo_maquina_display(),
            'data_criacao': ordem.data_criacao.strftime('%d/%m/%Y %H:%M'),
            'obs': ordem.obs,
            'status_atual': ordem.status_atual,
            'ultima_atualizacao': ordem.ultima_atualizacao,
            'peca': {
                'codigo': conjunto_info.codigo if conjunto_info else 'Sem código',
                'descricao': conjunto_info.descricao if conjunto_info else 'Sem descrição',
                'quantidade': peca_info.qtd_planejada if peca_info else 0,
                'qtd_morta': peca_info.qtd_morta if peca_info else 0
            } if peca_info else None  # Retorna `None` se nenhuma peça estiver associada
        })

    # Retorna os dados paginados como JSON
    return JsonResponse({
        'ordens': data,
        'page': ordens_page.number,
        'total_pages': paginator.num_pages,
        'total_ordens': paginator.count
    })

@require_GET
def get_ordens_interrompidas(request):
    # Filtra as ordens com base no status 'interrompida'
    ordens_queryset = Ordem.objects.prefetch_related('processos', 'ordem_pecas_prod_especiais').filter(status_atual='interrompida', grupo_maquina='prod_esp')

    # Paginação (opcional)
    page = request.GET.get('page', 1)  # Obtém o número da página
    limit = request.GET.get('limit', 10)  # Define o limite padrão por página
    paginator = Paginator(ordens_queryset, limit)  # Aplica a paginação
    ordens_page = paginator.get_page(page)  # Obtém a página atual

    # Monta os dados para retorno
    data = []
    for ordem in ordens_page:
        # Obtém o último processo interrompido (caso tenha mais de um)
        ultimo_processo_interrompido = ordem.processos.filter(status='interrompida').order_by('-data_inicio').first()

        # Obtém as peças associadas à ordem
        pecas_data = []
        for peca_ordem in ordem.ordem_pecas_prod_especiais.all():
            pecas_data.append({
                'codigo': peca_ordem.conjunto.codigo,  # Supondo que o campo `peca` é um FK para o modelo `Peca`
                'descricao': peca_ordem.conjunto.descricao,  # Ajuste para refletir o campo correto no modelo
                'quantidade': peca_ordem.qtd_planejada,
                'qtd_morta': peca_ordem.qtd_morta,
            })

        data.append({
            'id': ordem.id,
            'ordem': ordem.ordem,
            'grupo_maquina': ordem.get_grupo_maquina_display(),
            'data_criacao': ordem.data_criacao.strftime('%d/%m/%Y %H:%M'),
            'obs': ordem.obs,
            'status_atual': ordem.status_atual,
            'ultima_atualizacao': ordem.ultima_atualizacao,
            'motivo_interrupcao': ultimo_processo_interrompido.motivo_interrupcao.nome if ultimo_processo_interrompido and ultimo_processo_interrompido.motivo_interrupcao else None,
            'pecas': pecas_data,  # Adiciona informações das peças
        })

    # Retorna os dados paginados como JSON
    return JsonResponse({
        'ordens': data,
        'page': ordens_page.number,
        'total_pages': paginator.num_pages,
        'total_ordens': paginator.count
    })

def get_pecas(request):
    """
    Retorna uma lista paginada de peças do setor `prod_esp`, com suporte a busca por código ou descrição.
    """

    # Obtém os parâmetros da requisição
    search = request.GET.get('search', '').strip()  # Termo de busca
    page = int(request.GET.get('page', 1))  # Página atual (padrão é 1)
    per_page = int(request.GET.get('per_page', 10))  # Itens por página (padrão é 10)

    # Busca o setor `prod_esp`
    try:
        setor_prod_esp = Setor.objects.get(nome='prod_esp')
    except Setor.DoesNotExist:
        return JsonResponse({'results': [], 'pagination': {'more': False}})

    # Filtra as peças que pertencem ao setor `prod_esp`
    pecas_query = Conjuntos.objects.filter()

    # Aplica o filtro de busca, se fornecido
    if search:
        pecas_query = pecas_query.filter(
            Q(codigo__icontains=search) | Q(descricao__icontains=search)
        ).order_by('codigo')

    # Paginação
    paginator = Paginator(pecas_query, per_page)
    pecas_page = paginator.get_page(page)

    # Monta os resultados paginados no formato esperado pelo Select2
    data = {
        'results': [
            {'id': peca.codigo, 'text': f"{peca.codigo} - {peca.descricao}"} for peca in pecas_page
        ],
        'pagination': {
            'more': pecas_page.has_next()  # Se há mais páginas
        },
    }

    return JsonResponse(data)

def planejar_ordem_prod_esp(request):

    if request.method == 'POST':

        with transaction.atomic():

            nova_ordem = Ordem.objects.create(
                obs=request.POST.get('observacoes'),
                grupo_maquina='prod_esp',
                data_programacao=request.POST.get("dataProgramacao")
            )

            PecasOrdem.objects.create(
                qtd_planejada=request.POST.get('qtdPlanejada'),
                ordem=nova_ordem,
                conjunto=get_object_or_404(Conjuntos, codigo=request.POST.get('pecaSelect')),
            )

        return JsonResponse({
            'message': 'Status atualizado com sucesso.',
            'ordem_id': nova_ordem.pk
        })
