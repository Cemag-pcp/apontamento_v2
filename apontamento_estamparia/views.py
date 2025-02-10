from django.shortcuts import render
from django.http import JsonResponse
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.core.paginator import Paginator, EmptyPage
from django.views.decorators.http import require_GET
from django.utils.timezone import now,localtime
from django.db.models import Q
from django.contrib.auth.decorators import login_required

from .models import Ordem,PecasOrdem
from core.models import OrdemProcesso,MaquinaParada
from cadastro.models import MotivoInterrupcao, Pecas, Operador, MotivoMaquinaParada, MotivoExclusao

import os
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

@login_required
def planejamento(request):

    motivos = MotivoInterrupcao.objects.filter(setor__nome='estamparia', visivel=True)
    operadores = Operador.objects.filter(setor__nome='estamparia')
    motivos_maquina_parada = MotivoMaquinaParada.objects.filter(setor__nome='estamparia')
    motivos_exclusao = MotivoExclusao.objects.filter(setor__nome='estamparia')

    return render(request, 'apontamento_estamparia/planejamento.html', {
                                                                    'motivos': motivos,
                                                                    'operadores':operadores,
                                                                    'motivos_maquina_parada':motivos_maquina_parada,
                                                                    'motivos_exclusao': motivos_exclusao})

def get_pecas_ordem(request, pk_ordem, name_maquina):
    try:
        # Busca a ordem com os relacionamentos necessários
        ordem = Ordem.objects.prefetch_related('ordem_pecas_estamparia').get(ordem=pk_ordem, grupo_maquina=name_maquina)

        # Obtém a peça relacionada
        peca_ordem = ordem.ordem_pecas_estamparia.first()  # Obtém a primeira peça (ou única)

        if not peca_ordem:
            return JsonResponse({'error': 'Nenhuma peça encontrada para esta ordem.'}, status=404)

        # Monta o JSON com os dados da peça
        peca_data = {
            'peca': peca_ordem.peca.descricao,  # Substitua 'descricao' pelo campo correto do modelo `Pecas`
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
    filtro_peca = request.GET.get('peca', '').strip()
    status_atual = request.GET.get('status', '').strip()

    page = int(request.GET.get('page', 1))
    limit = int(request.GET.get('limit', 10))

    # Filtra as ordens com base nos parâmetros
    ordens_queryset = Ordem.objects.prefetch_related('ordem_pecas_estamparia', 'propriedade').filter(grupo_maquina='estamparia', excluida=False).order_by('status_prioridade','-data_criacao')

    if filtro_ordem:
        ordens_queryset = ordens_queryset.filter(ordem=filtro_ordem)
    if filtro_peca:
        ordens_queryset = ordens_queryset.filter(ordem_pecas_estamparia__peca__codigo=filtro_peca)
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
        peca_info = ordem.ordem_pecas_estamparia.first()  # Assume que há apenas uma peça por ordem

        data.append({
            'id': ordem.pk,
            'ordem': ordem.ordem,
            'grupo_maquina': ordem.get_grupo_maquina_display(),
            'data_criacao': localtime(ordem.data_criacao).strftime('%d/%m/%Y %H:%M'),
            'obs': ordem.obs,
            'status_atual': ordem.status_atual,
            'maquina': ordem.maquina,
            'peca': {
                'codigo': peca_info.peca.codigo if peca_info and peca_info.peca else None,
                'descricao': peca_info.peca.descricao if peca_info and peca_info.peca else None,
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

                status = body['status']
                ordem_id = body['ordem_id']
                grupo_maquina = body['grupo_maquina'].lower()
                qt_produzida = body.get('qt_realizada')
                qt_mortas = body.get('qt_mortas')
                maquina_nome = body.get('maquina_nome')

                # Obtém a ordem
                ordem = Ordem.objects.get(ordem=ordem_id, grupo_maquina=grupo_maquina)
                
                # Validações básicas
                if ordem.status_atual == status:
                    return JsonResponse({'error': f'Essa ordem ja está {status}. Atualize a página.'}, status=400)

                if not ordem_id or not grupo_maquina or not status:
                    return JsonResponse({'error': 'Campos obrigatórios não enviados.'}, status=400)

                # Verifica se já existe uma ordem iniciada na mesma máquina
                if status == 'iniciada' and maquina_nome:
                    ordem_em_andamento = Ordem.objects.filter(
                        maquina=maquina_nome, status_atual='iniciada'
                    ).exclude(id=ordem.id).exists()

                    if ordem_em_andamento:
                        return JsonResponse({'error': f'Já existe uma ordem iniciada para essa máquina ({maquina_nome}). Finalize ou interrompa antes de iniciar outra.'}, status=400)

                # Finaliza o processo atual (se existir)
                processo_atual = ordem.processos.filter(data_fim__isnull=True).first()
                if processo_atual:
                    processo_atual.finalizar_atual()

                # Cria o novo processo
                novo_processo = OrdemProcesso.objects.create(
                    ordem=ordem,
                    status=status,
                    data_inicio=now(),
                    data_fim=now() if status == 'finalizada' or status == 'agua_prox_proc' else None,
                )

                # Atualiza o status da ordem para o novo status
                ordem.status_atual = status
                
                if status == 'iniciada':
                    # Verifica e finaliza a parada da máquina se necessário
                    maquinas_paradas = MaquinaParada.objects.filter(maquina=maquina_nome, data_fim__isnull=True)
                    for parada in maquinas_paradas:
                        parada.data_fim = now()
                        parada.save()
                    
                    if maquina_nome:
                        ordem.maquina = maquina_nome

                    ordem.status_prioridade = 1
                elif status == 'finalizada':
                    operador_final = int(body.get('operador_final'))
                    obs_final = body.get('obs_finalizar')
                    operador_final_object = get_object_or_404(Operador, pk=operador_final)

                    ordem.operador_final=operador_final_object
                    ordem.obs_operador=obs_final

                    peca = PecasOrdem.objects.filter(ordem=ordem).first()
                    # peca.qtd_boa = qt_produzida  
                    # peca.qtd_morta = qt_mortas 

                    PecasOrdem.objects.create(
                        ordem=ordem,
                        peca=peca.peca,
                        qtd_planejada=peca.qtd_planejada,
                        qtd_boa=int(qt_produzida),
                        qtd_morta=int(qt_mortas),
                        operador=operador_final_object
                    )      

                    peca.save()

                    ordem.status_prioridade = 3
                elif status == 'interrompida':
                    novo_processo.motivo_interrupcao = MotivoInterrupcao.objects.get(nome=body['motivo'])
                    novo_processo.save()
                    ordem.status_prioridade = 2
                elif status == 'agua_prox_proc':
                    try:
                        ordem.maquina = body['maquina_nome']
                        novo_processo.maquina=body['maquina_nome']

                        peca = PecasOrdem.objects.filter(ordem=ordem).first()
                        peca.qtd_planejada = int(body['qtd_prox_processo'])
                        
                        peca.save()
                        novo_processo.save()
                    except:
                        pass
                    ordem.status_prioridade = 4
                elif status == 'finalizada_parcial':

                    peca = PecasOrdem.objects.filter(ordem=ordem).first()
                    operador_final = int(body.get('operador_final'))
                    ordem.status_atual = 'interrompida'

                    novo_processo.motivo_interrupcao = MotivoInterrupcao.objects.get(nome='Finalizada parcial')
                    novo_processo.save()

                    ordem.status_prioridade = 2

                    PecasOrdem.objects.create(
                        ordem=ordem,
                        peca=peca.peca,
                        qtd_planejada=peca.qtd_planejada,
                        qtd_boa=int(qt_produzida),
                        qtd_morta=int(qt_mortas),
                        operador=get_object_or_404(Operador, pk=operador_final)
                    )

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
        'ordem_pecas_estamparia'
    ).filter(grupo_maquina='estamparia', status_atual='iniciada')

    # Paginação
    page = int(request.GET.get('page', 1))  # Obtém o número da página
    limit = int(request.GET.get('limit', 10))  # Define o limite padrão por página
    filtro_ordem = request.GET.get('ordem', '').strip()
    filtro_peca = request.GET.get('peca', '').strip()
 
    if filtro_ordem:
        ordens_queryset = ordens_queryset.filter(ordem=filtro_ordem)
    if filtro_peca:
        ordens_queryset = ordens_queryset.filter(ordem_pecas_estamparia__peca__codigo=filtro_peca)

    paginator = Paginator(ordens_queryset, limit)  # Aplica a paginação

    try:
        ordens_page = paginator.page(page)  # Obtém a página atual
    except EmptyPage:
        return JsonResponse({'ordens': []})  # Retorna vazio se a página não existir

    # Monta os dados para retorno
    data = []
    for ordem in ordens_page:
        pecas_data = []
        for peca_ordem in ordem.ordem_pecas_estamparia.all():
            # Verifica se já existe uma entrada para essa peça
            peca_existente = next((item for item in pecas_data if item['codigo'] == peca_ordem.peca.codigo), None)

            if peca_existente:
                # Soma a quantidade de boas à peça existente
                peca_existente['qtd_boa'] += peca_ordem.qtd_boa
            else:
                # Adiciona uma nova entrada para a peça
                pecas_data.append({
                    'codigo': peca_ordem.peca.codigo,
                    'descricao': peca_ordem.peca.descricao,
                    'qtd_boa': peca_ordem.qtd_boa,
                    'qtd_planejada': peca_ordem.qtd_planejada,
                    'qtd_morta': peca_ordem.qtd_morta,
                })

        data.append({
            'ordem': ordem.ordem,
            'grupo_maquina': ordem.get_grupo_maquina_display(),
            'data_criacao': ordem.data_criacao.strftime('%d/%m/%Y %H:%M'),
            'obs': ordem.obs,
            'status_atual': ordem.status_atual,
            'maquina': ordem.get_maquina_display(),
            'pecas': pecas_data,  # Lista consolidada de peças
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
    ordens_queryset = Ordem.objects.prefetch_related('processos', 'ordem_pecas_estamparia').filter(status_atual='interrompida', grupo_maquina='estamparia')

    # Paginação (opcional)
    page = request.GET.get('page', 1)  # Obtém o número da página
    limit = request.GET.get('limit', 10)  # Define o limite padrão por página
    paginator = Paginator(ordens_queryset, limit)  # Aplica a paginação
    ordens_page = paginator.get_page(page)  # Obtém a página atual

    # Monta os dados para retorno
    data = []
    for ordem in ordens_page:
        # Obtém o último processo interrompido (caso tenha mais de um)
        ultimo_processo_interrompido = ordem.processos.filter(motivo_interrupcao__isnull=False).order_by('-data_inicio').first()

        # Obtém as peças associadas à ordem
        pecas_data = []
        for peca_ordem in ordem.ordem_pecas_estamparia.all():
            # Verifica se já existe uma entrada para essa peça
            peca_existente = next((item for item in pecas_data if item['codigo'] == peca_ordem.peca.codigo), None)

            if peca_existente:
                # Soma a quantidade de boas à peça existente
                peca_existente['qtd_boa'] += peca_ordem.qtd_boa
            else:
                # Adiciona uma nova entrada para a peça
                pecas_data.append({
                    'codigo': peca_ordem.peca.codigo,
                    'descricao': peca_ordem.peca.descricao,
                    'qtd_boa': peca_ordem.qtd_boa,
                    'qtd_planejada': peca_ordem.qtd_planejada,
                    'qtd_morta': peca_ordem.qtd_morta,
                })

        data.append({
            'ordem': ordem.ordem,
            'grupo_maquina': ordem.get_grupo_maquina_display(),
            'data_criacao': ordem.data_criacao.strftime('%d/%m/%Y %H:%M'),
            'obs': ordem.obs,
            'status_atual': ordem.status_atual,
            'maquina': ordem.get_maquina_display(),
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

@require_GET
def get_ordens_ag_prox_proc(request):
    # Filtra as ordens com base no status 'agua_prox_proc' e prefetch da peça relacionada
    ordens_queryset = Ordem.objects.prefetch_related(
        'ordem_pecas_estamparia'
    ).filter(grupo_maquina='estamparia', status_atual='agua_prox_proc')

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
        pecas_data = []
        total_qtd_boa = 0
        total_qtd_planejada = 0
        total_qtd_morta = 0

        # Itera sobre todas as peças relacionadas
        for peca_ordem in ordem.ordem_pecas_estamparia.all():
            # Soma os totais
            total_qtd_boa += peca_ordem.qtd_boa
            total_qtd_planejada += peca_ordem.qtd_planejada
            total_qtd_morta += peca_ordem.qtd_morta

            pecas_data.append({
                'codigo': peca_ordem.peca.codigo,
                'descricao': peca_ordem.peca.descricao,
                'qtd_boa': peca_ordem.qtd_boa,
                'qtd_planejada': peca_ordem.qtd_planejada,
                'qtd_morta': peca_ordem.qtd_morta,
            })

        data.append({
            'ordem': ordem.ordem,
            'grupo_maquina': ordem.get_grupo_maquina_display(),
            'data_criacao': ordem.data_criacao.strftime('%d/%m/%Y %H:%M'),
            'obs': ordem.obs,
            'status_atual': ordem.status_atual,
            'maquina': ordem.get_maquina_display(),
            'totais': {
                'qtd_boa': total_qtd_boa,
                'qtd_planejada': total_qtd_planejada,
                'qtd_morta': total_qtd_morta
            },
            'pecas': pecas_data,  # Lista consolidada de peças
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
    Retorna uma lista paginada de peças, com suporte a busca por código ou descrição.
    """
    # Obtém os parâmetros da requisição
    search = request.GET.get('search', '').strip()  # Termo de busca
    page = int(request.GET.get('page', 1))  # Página atual (padrão é 1)
    per_page = int(request.GET.get('per_page', 10))  # Itens por página (padrão é 10)

    # Filtra as peças com base no termo de busca (opcional)
    pecas_query = Pecas.objects.all()
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

def planejar_ordem_estamparia(request):

    if request.method == 'POST':

        with transaction.atomic():

            nova_ordem = Ordem.objects.create(
                obs=request.POST.get('observacoes'),
                grupo_maquina='estamparia',
                data_programacao=request.POST.get("dataProgramacao")
            )

            PecasOrdem.objects.create(
                qtd_planejada=request.POST.get('qtdPlanejada'),
                ordem=nova_ordem,
                peca=get_object_or_404(Pecas, codigo=request.POST.get('pecaSelect')),
            )

        return JsonResponse({
            'message': 'Status atualizado com sucesso.',
            'ordem_id': nova_ordem.ordem
        })

def api_apontamentos_peca(request):

    pecas_ordenadas = (
        PecasOrdem.objects.filter(operador__isnull=False, ordem__grupo_maquina='estamparia')
        .select_related('ordem', 'peca', 'operador')  # Carrega os relacionamentos necessários
        .order_by('-data')  # Ordena por data decrescente
    )

    resultado = []
    for apontamento in pecas_ordenadas:
        resultado.append({
            "ordem": apontamento.ordem.ordem,
            "codigo_peca": apontamento.peca.codigo,
            "descricao_peca": apontamento.peca.descricao or "Sem descrição",
            "qtd_boa": apontamento.qtd_boa,
            "qtd_morta": apontamento.qtd_morta,
            "qtd_planejada": apontamento.qtd_planejada,
            "obs_plano": apontamento.ordem.obs or "Sem observações",
            "maquina": apontamento.ordem.get_maquina_display(),
            "obs_operador": apontamento.ordem.obs_operador or "Sem observações",
            "operador": f"{apontamento.operador.matricula} - {apontamento.operador.nome}",
            "data": localtime(apontamento.data).strftime('%d/%m/%Y %H:%M'),
        })

    return JsonResponse(resultado, safe=False)
