from django.shortcuts import render
from django.http import JsonResponse
from django.db import transaction, connection
from django.shortcuts import get_object_or_404
from django.core.paginator import Paginator, EmptyPage
from django.views.decorators.http import require_GET
from django.utils.timezone import now,localtime
from django.db.models import Q,Prefetch,Count,OuterRef, Subquery
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt

from .models import Ordem,PecasOrdem
from core.models import OrdemProcesso,MaquinaParada
from cadastro.models import MotivoInterrupcao, Pecas, Operador, MotivoMaquinaParada, MotivoExclusao, Maquina
from inspecao.models import Inspecao, DadosExecucaoInspecao

from datetime import datetime, timedelta
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
    motivos_maquina_parada = MotivoMaquinaParada.objects.filter(setor__nome='estamparia').exclude(nome='Finalizada parcial')
    motivos_exclusao = MotivoExclusao.objects.filter(setor__nome='estamparia')

    return render(request, 'apontamento_estamparia/planejamento.html', {
                                                                    'motivos': motivos,
                                                                    'operadores':operadores,
                                                                    'motivos_maquina_parada':motivos_maquina_parada,
                                                                    'motivos_exclusao': motivos_exclusao})

def get_pecas_ordem(request, pk_ordem, name_maquina):
    try:
        # Busca a ordem com os relacionamentos necessários
        ordem = Ordem.objects.prefetch_related('ordem_pecas_estamparia').get(pk=pk_ordem)

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

    # Criamos uma subquery para obter a primeira peça associada à ordem
    primeira_peca = PecasOrdem.objects.filter(
        ordem=OuterRef('pk')
    ).order_by('id')[:1]

    # Query principal das ordens
    ordens_queryset = Ordem.objects.filter(
        grupo_maquina='estamparia',
        excluida=False,
    ).annotate(
        peca_codigo=Subquery(primeira_peca.values('peca__codigo')),
        peca_descricao=Subquery(primeira_peca.values('peca__descricao')),
        peca_quantidade=Subquery(primeira_peca.values('qtd_planejada'))
    ).order_by('status_prioridade').exclude(status_atual='finalizada')

    if filtro_ordem:
        ordens_queryset = ordens_queryset.filter(ordem=filtro_ordem)
    if filtro_peca:
        ordens_queryset = ordens_queryset.filter(peca_codigo=filtro_peca)
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
        data.append({
            'id': ordem.pk,
            'ordem': ordem.ordem,
            'grupo_maquina': ordem.get_grupo_maquina_display(),
            'data_criacao': localtime(ordem.data_criacao).strftime('%d/%m/%Y %H:%M'),
            'obs': ordem.obs,
            'status_atual': ordem.status_atual,
            'peca': {
                'codigo': ordem.peca_codigo,
                'descricao': ordem.peca_descricao,
                'quantidade': ordem.peca_quantidade,
            } if ordem.peca_codigo else None,
            'info_pecas': [
                {
                    'ordem_id':ordem.pk,
                    'ordem': ordem.ordem,
                    'data_criacao': ordem.data_criacao,
                    'maquina': ordem.maquina.nome,
                    'id': peca_ordem.id,
                    'peca_id': peca_ordem.peca.id,
                    'peca_codigo': peca_ordem.peca.codigo,
                    'peca_nome': peca_ordem.peca.descricao if peca_ordem.peca.descricao else 'Sem descrição',
                    'quantidade': peca_ordem.qtd_planejada,
                    'qtd_morta': peca_ordem.qtd_morta,
                    'qtd_boa': peca_ordem.qtd_boa
                }
                for peca_ordem in ordem.ordem_pecas_estamparia.all() if peca_ordem.qtd_boa > 0
            ]  # Lista todas as peças associadas

        })

    return JsonResponse({
        'ordens': data,
        'total_ordens': paginator.count,  # Envia total de ordens
        'has_next': ordens_page.has_next(),  # Envia se há próxima página
    })

def atualizar_status_ordem(request):
    if request.method != 'PATCH':
        return JsonResponse({'error': 'Método não permitido.'}, status=405)

    try:
        # Parse do corpo da requisição
        body = json.loads(request.body)

        status = body.get('status')
        ordem_id = body.get('ordem_id')
        grupo_maquina = body.get('grupo_maquina', '').lower()
        qt_produzida = body.get('qt_realizada', 0)
        qt_mortas = body.get('qt_mortas', 0)
        maquina_nome = body.get('maquina_nome')

        if not ordem_id or not grupo_maquina or not status:
            return JsonResponse({'error': 'Campos obrigatórios não enviados.'}, status=400)

        # Obtém a ordem ANTES da transação, para evitar falha na atomicidade
        ordem = get_object_or_404(Ordem, pk=ordem_id)

        if maquina_nome:
            maquina_nome = get_object_or_404(Maquina, pk=int(maquina_nome))

        # Validações básicas
        if ordem.status_atual == status:
            return JsonResponse({'error': f'Essa ordem já está {status}. Atualize a página.'}, status=400)

        with transaction.atomic():  # Entra na transação somente após garantir que todos os objetos existem
            ###NÃO VERIFICA MAIS SE A MÁQUINA JA ESTÁ SENDO UTILIZADA, USUARIO PODE INICIAR OUTRA PEÇA NA MESMA MÁQUINA###
            # Verifica se já existe uma ordem iniciada na mesma máquina
            # if status == 'iniciada' and maquina_nome:
            #     ordem_em_andamento = Ordem.objects.filter(
            #         maquina=maquina_nome, status_atual='iniciada'
            #     ).exclude(id=ordem.id).exists()

            #     if ordem_em_andamento:
            #         return JsonResponse({
            #             'error': f'Já existe uma ordem iniciada para essa máquina ({maquina_nome}).'
            #         }, status=400)

            # Finaliza o processo atual (se existir)
            processo_atual = ordem.processos.filter(data_fim__isnull=True).first()
            if processo_atual:
                processo_atual.finalizar_atual()

            # Cria o novo processo
            novo_processo = OrdemProcesso.objects.create(
                ordem=ordem,
                status=status,
                data_inicio=now(),
                data_fim=now() if status == 'finalizada' else None,
            )

            # Atualiza o status da ordem
            ordem.status_atual = status

            if status == 'iniciada':
                # Finaliza a parada da máquina se necessário
                maquinas_paradas = MaquinaParada.objects.filter(maquina=maquina_nome, data_fim__isnull=True)
                for parada in maquinas_paradas:
                    parada.data_fim = now()
                    parada.save()

                ordem.maquina = maquina_nome
                ordem.status_prioridade = 1

            elif status == 'finalizada':
                operador_final = get_object_or_404(Operador, pk=int(body.get('operador_final')))
                obs_final = body.get('obs_finalizar')

                ordem.operador_final = operador_final
                ordem.obs_operador = obs_final

                peca = PecasOrdem.objects.filter(ordem=ordem).first()

                nova_peca_ordem = PecasOrdem.objects.create(
                    ordem=ordem,
                    peca=peca.peca,
                    qtd_planejada=peca.qtd_planejada,
                    qtd_boa=int(qt_produzida),
                    qtd_morta=int(qt_mortas),
                    operador=operador_final
                )

                Inspecao.objects.create(
                    pecas_ordem_estamparia=nova_peca_ordem
                )

                ordem.status_prioridade = 3

            elif status == 'interrompida':
                novo_processo.motivo_interrupcao = get_object_or_404(MotivoInterrupcao, nome=body['motivo'])
                novo_processo.save()
                ordem.status_prioridade = 2

            elif status == 'agua_prox_proc':
                ordem.maquina = maquina_nome
                novo_processo.maquina = maquina_nome

                peca = PecasOrdem.objects.filter(ordem=ordem).first()
                peca.qtd_planejada = int(body['qtd_prox_processo'])
                peca.save()
                novo_processo.save()

                ordem.status_prioridade = 4

            elif status == 'finalizada_parcial':

                peca = PecasOrdem.objects.filter(ordem=ordem).first()

                operador_final = get_object_or_404(Operador, pk=int(body.get('operador_final')))
                ordem.status_atual = 'interrompida'

                novo_processo.motivo_interrupcao = get_object_or_404(MotivoInterrupcao, nome='Finalizada parcial')
                novo_processo.save()
                ordem.status_prioridade = 2

                nova_peca_ordem_parcial = PecasOrdem.objects.create(
                    ordem=ordem,
                    peca=peca.peca,
                    qtd_planejada=peca.qtd_planejada,
                    qtd_boa=int(qt_produzida),
                    qtd_morta=int(qt_mortas),
                    operador=operador_final
                )

                Inspecao.objects.create(
                    pecas_ordem_estamparia=nova_peca_ordem_parcial
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
    
@require_GET
def get_ordens_iniciadas(request):
    # Filtra as ordens baseadas no status e no grupo da máquina
    ordens_queryset = Ordem.objects.filter(
        grupo_maquina='estamparia',
        status_atual='iniciada'
    )

    page = int(request.GET.get('page', 1))
    limit = int(request.GET.get('limit', 10))
    filtro_ordem = request.GET.get('ordem', '').strip()
    filtro_peca = request.GET.get('peca', '').strip()

    if filtro_ordem:
        ordens_queryset = ordens_queryset.filter(ordem=filtro_ordem)
    if filtro_peca:
        ordens_queryset = ordens_queryset.filter(
            ordem_pecas_estamparia__peca__codigo=filtro_peca
        )

    # Paginação
    paginator = Paginator(ordens_queryset, limit)
    try:
        ordens_page = paginator.page(page)
    except EmptyPage:
        return JsonResponse({'ordens': []})

    # Criamos um dicionário para armazenar as peças agrupadas por ordem
    ordens_dict = {}

    # Iteramos pelas ordens da página
    for ordem in ordens_page:
        if ordem.id not in ordens_dict:
            ordens_dict[ordem.id] = {
                'id': ordem.id,
                'ordem': ordem.ordem,
                'grupo_maquina': ordem.get_grupo_maquina_display(),
                'data_criacao': ordem.data_criacao.strftime('%d/%m/%Y %H:%M'),
                'obs': ordem.obs,
                'status_atual': ordem.status_atual,
                'maquina': ordem.maquina.nome if ordem.maquina else None,
                'ultima_atualizacao': ordem.ultima_atualizacao,
                'pecas': []  # Criamos uma lista para armazenar as peças da ordem
            }

        # Iteramos pelas peças associadas à ordem
        for peca_ordem in ordem.ordem_pecas_estamparia.all():
            # Verifica se já existe uma entrada para essa peça
            peca_existente = next(
                (item for item in ordens_dict[ordem.id]['pecas'] if item['codigo'] == peca_ordem.peca.codigo),
                None
            )

            if peca_existente:
                # Soma a quantidade de boas à peça existente
                peca_existente['qtd_boa'] += peca_ordem.qtd_boa
            else:
                # Adiciona uma nova entrada para a peça
                ordens_dict[ordem.id]['pecas'].append({
                    'codigo': peca_ordem.peca.codigo,
                    'descricao': peca_ordem.peca.descricao,
                    'qtd_boa': peca_ordem.qtd_boa,
                    'qtd_planejada': peca_ordem.qtd_planejada,
                    'qtd_morta': peca_ordem.qtd_morta,
                })

    return JsonResponse({
        'ordens': list(ordens_dict.values()),  # Retorna apenas valores únicos
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
            'id': ordem.id,
            'ordem': ordem.ordem,
            'grupo_maquina': ordem.get_grupo_maquina_display(),
            'data_criacao': ordem.data_criacao.strftime('%d/%m/%Y %H:%M'),
            'obs': ordem.obs,
            'status_atual': ordem.status_atual,
            'maquina': ordem.maquina.nome if ordem.maquina else None,
            'maquina_id': ordem.maquina.id if ordem.maquina else None,
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
            'id': ordem.id,
            'ordem': ordem.ordem,
            'grupo_maquina': ordem.get_grupo_maquina_display(),
            'data_criacao': ordem.data_criacao.strftime('%d/%m/%Y %H:%M'),
            'obs': ordem.obs,
            'status_atual': ordem.status_atual,
            'maquina': ordem.maquina.nome if ordem.maquina else None,
            'maquina_id': ordem.maquina.id if ordem.maquina else None,
            'ultima_atualizacao': ordem.ultima_atualizacao,
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
            'ordem_id': nova_ordem.pk
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
            "maquina": apontamento.ordem.maquina.nome,
            'maquina_id': apontamento.ordem.maquina.id,
            "obs_operador": apontamento.ordem.obs_operador or "Sem observações",
            "operador": f"{apontamento.operador.matricula} - {apontamento.operador.nome}",
            "data": localtime(apontamento.data).strftime('%d/%m/%Y %H:%M'),
        })

    return JsonResponse(resultado, safe=False)

def historico(request):

    return render(request, "apontamento_estamparia/historico.html")

@csrf_exempt
def atualizar_pecas_ordem(request):

    data = json.loads(request.body)

    if request.method == 'POST':

        edit_info_apontamento = get_object_or_404(PecasOrdem, pk=int(data['ordemId']))
        edit_info_apontamento.qtd_boa = int(data['novaQtBoa'])
        edit_info_apontamento.qtd_morta = int(data['novaQtMorta'])

        edit_info_apontamento.save()

    return JsonResponse({'status':'success'})

def api_ordens_finalizadas(request):
    
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT 
                o.ordem AS ordem,
                m.nome AS maquina,
                p.codigo AS peca,
                p.descricao AS descricao,
                ope.qtd_boa AS total_produzido,
                TO_CHAR(o.data_programacao, 'DD/MM/YYYY HH24:MI') AS data_programacao,
                TO_CHAR(o.ultima_atualizacao AT TIME ZONE 'America/Sao_Paulo', 'DD/MM/YYYY HH24:MI') AS data_finalizacao,
                CONCAT(f.matricula, ' - ', f.nome) AS operador,
                o.obs_operador AS obs
            FROM apontamento_v2.core_ordem o
            JOIN apontamento_v2.apontamento_estamparia_pecasordem ope ON ope.ordem_id = o.id
            JOIN apontamento_v2.cadastro_pecas p ON ope.peca_id = p.id
            LEFT JOIN apontamento_v2.cadastro_maquina m ON o.maquina_id = m.id
            LEFT JOIN apontamento_v2.cadastro_operador f ON o.operador_final_id = f.id
            WHERE 
                o.status_atual = 'finalizada'
                AND o.ultima_atualizacao >= '2025-04-08'
                AND ope.qtd_boa > 0
            ORDER BY o.ultima_atualizacao;
        """)
        columns = [col[0] for col in cursor.description]
        results_raw = [dict(zip(columns, row)) for row in cursor.fetchall()]


    return JsonResponse(results_raw, safe=False)
