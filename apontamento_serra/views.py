from django.shortcuts import render
from django.http import JsonResponse
from django.db import transaction, connection
from django.shortcuts import get_object_or_404
from django.core.paginator import Paginator, EmptyPage
from django.views.decorators.http import require_GET
from django.utils.timezone import now
from django.views.decorators.csrf import csrf_exempt
from django.utils.timezone import localtime
from django.db.models import F, Value, Q, Prefetch, Count
from django.db.models.functions import Concat
from django.contrib.auth.decorators import login_required

from .models import PecasOrdem
from core.models import OrdemProcesso,PropriedadesOrdem,Ordem,MaquinaParada, Profile
from cadastro.models import MotivoExclusao, MotivoInterrupcao, Mp, Pecas, Operador, Setor, MotivoMaquinaParada, Maquina
from apontamento_usinagem.utils import criar_ordem_usinagem, verificar_se_existe_ordem
from .utils import hora_operacao_maquina, hora_parada_maquina, formatar_timedelta, ordem_por_maquina, producao_por_maquina
from core.utils import notificar_ordem

import os
import re
import json
import openpyxl
from datetime import datetime, timedelta
from collections import defaultdict

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

    motivos = MotivoInterrupcao.objects.filter(setor__nome='serra', visivel=True)
    operadores = Operador.objects.filter(setor__nome='serra')
    motivos_maquina_parada = MotivoMaquinaParada.objects.filter(setor__nome='serra').exclude(nome='Finalizada parcial')
    motivos_exclusao = MotivoExclusao.objects.filter(setor__nome='serra')

    return render(request, 'apontamento_serra/planejamento.html', {
                                                                    'motivos': motivos,
                                                                    'operadores':operadores,
                                                                    'motivos_maquina_parada':motivos_maquina_parada,
                                                                    'motivos_exclusao': motivos_exclusao})

@login_required
def get_pecas_ordem(request, pk_ordem, name_maquina):
    try:
        # Busca a ordem com os relacionamentos necessários
        ordem = Ordem.objects.select_related('propriedade').prefetch_related('ordem_pecas_serra__peca').get(
            pk=pk_ordem,
            # grupo_maquina=name_maquina
        )

        # Propriedades da ordem
        propriedade = ordem.propriedade
        propriedades = {
            'id_mp': propriedade.mp_codigo.codigo if propriedade else None,
            'descricao_mp': propriedade.mp_codigo.codigo + " - " + propriedade.mp_codigo.descricao if propriedade else None,
            'quantidade': propriedade.quantidade if propriedade else None,
            'tamanho': propriedade.tamanho if propriedade else None,
        }

        # Peças relacionadas à ordem
        pecas = [
            {
                'id_peca': peca.id,
                'peca_id': peca.peca.id,
                'peca_codigo': peca.peca.codigo,
                'peca_nome': f"{peca.peca.codigo} - {peca.peca.descricao}",
                'quantidade': peca.qtd_planejada,
                'qtd_morta': peca.qtd_morta
            }
            for peca in ordem.ordem_pecas_serra.all()
        ]

        # Retorna as propriedades e as peças como JSON
        return JsonResponse({'pecas': pecas, 'propriedades': propriedades, 'ordem_status': ordem.status_atual})

    except Ordem.DoesNotExist:
        # Retorna erro caso a ordem não seja encontrada
        return JsonResponse({'error': 'Ordem não encontrada.'}, status=404)

    except Exception as e:
        # Captura erros genéricos
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def atualizar_status_ordem(request):
    if request.method == 'PATCH':
        try:
            with transaction.atomic():
                # Parse do corpo da requisição
                body = json.loads(request.body)

                status = body['status']
                ordem_id = body['ordem_id']
                # grupo_maquina = body['grupo_maquina'].lower()
                pecas_geral = body.get('pecas_mortas', [])
                maquina_request = body.get('maquina_nome')
                if maquina_request:
                    maquina_nome = get_object_or_404(Maquina, pk=int(maquina_request))

                # Obtém a ordem
                ordem = Ordem.objects.get(pk=int(ordem_id))

                # Validações básicas
                if ordem.status_atual == status:
                    return JsonResponse({'error': f'Essa ordem já está {status}. Atualize a página.'}, status=400)

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
                    data_fim=now() if status == 'finalizada' else None
                )

                # Atualiza o status da ordem
                ordem.status_atual = status

                if status == 'iniciada':
                    # Finaliza paradas da máquina se necessário
                    maquinas_paradas = MaquinaParada.objects.filter(maquina=maquina_nome, data_fim__isnull=True)
                    for parada in maquinas_paradas:
                        parada.data_fim = now()
                        parada.save()

                    ordem.maquina = maquina_nome
                    ordem.status_prioridade = 1

                elif status == 'finalizada':
                    tamanho_vara = body.get('tamanho_vara')
                    qtd_varas = body.get('qtd_vara')
                    operador_final = int(body.get('operador_final'))
                    obs_final = body.get('obs_finalizar')

                    ordem.operador_final = get_object_or_404(Operador, pk=operador_final)
                    ordem.obs_operador = obs_final

                    mp_final = body.get('mp_final')

                    if ordem.propriedade.mp_codigo.codigo != mp_final:
                        ordem.propriedade.nova_mp = get_object_or_404(Mp, codigo=mp_final)
                        ordem.propriedade.save()

                    ordem.propriedade.tamanho = tamanho_vara
                    ordem.propriedade.save()

                    # Verifica se a quantidade de chapas mudou
                    if int(qtd_varas) != ordem.propriedade.quantidade:
                        ordem.propriedade.quantidade = int(qtd_varas)
                        ordem.propriedade.save()

                    for peca in pecas_geral:
                        peca_id = peca.get('peca')
                        planejada = peca.get('planejadas')
                        mortas = peca.get('mortas', 0)

                        peca_obj = PecasOrdem.objects.get(ordem=ordem, peca=peca_id)
                        peca_obj.qtd_boa = planejada
                        peca_obj.qtd_morta = mortas
                        peca_obj.save()

                        # verifica se a peça tem passagem para usinagem
                        peca_object = Pecas.objects.get(pk=peca_id)
                        if peca_object.processo_1:

                            # verifica se ja existe alguma ordem no setor de usinagem aguardando_prox_proc com a mesma peça, 
                            # se existir apenas acrescenta a quantidade nova na que ja existe
                            
                            pecas_ordem_existente = verificar_se_existe_ordem(peca_object)

                            if pecas_ordem_existente:
                                pecas_ordem_existente.qtd_planejada += planejada

                                pecas_ordem_existente.save()
                            else:
                                dados_usinagem = {
                                    'observacoes': 'Gerado a partir da serra',
                                    'dataProgramacao': now().date(),
                                    'qtdPlanejada': planejada,
                                    'pecaSelect': peca_object.codigo,
                                    'maquina': peca_object.processo_1,
                                    'status_atual': 'agua_prox_proc'
                                }

                                nova_ordem = criar_ordem_usinagem(dados_usinagem)

                    ordem.status_prioridade = 3

                elif status == 'interrompida':
                    novo_processo.motivo_interrupcao = MotivoInterrupcao.objects.get(nome=body['motivo'])
                    novo_processo.save()
                    ordem.status_prioridade = 2
            
                ordem.save()
                notificar_ordem(ordem)

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
def get_ordens_criadas(request):

    # Captura os parâmetros de filtro
    filtro_ordem = request.GET.get('ordem', '').strip()
    status_atual = request.GET.get('status', '').strip()
    filtro_mp = request.GET.get('mp', '').strip()
    filtro_peca = request.GET.get('peca', '').strip()
    data_programada = request.GET.get('data-programada', '').strip()

    page = int(request.GET.get('page', 1))
    limit = int(request.GET.get('limit', 10))

    # Filtra as ordens com base nos parâmetros
    ordens_queryset = Ordem.objects.prefetch_related('ordem_pecas_serra', 'propriedade').filter(grupo_maquina='serra', excluida=False).order_by('status_prioridade','-data_criacao')

    if filtro_ordem:
        ordens_queryset = ordens_queryset.filter(ordem__icontains=filtro_ordem)
    if status_atual:
        ordens_queryset = ordens_queryset.filter(status_atual=status_atual)
    if filtro_mp:
        ordens_queryset = ordens_queryset.filter(propriedade__mp_codigo__codigo=filtro_mp)
    if filtro_peca:
        ordens_queryset = ordens_queryset.filter(ordem_pecas_serra__peca__codigo=filtro_peca)
    if data_programada:
        ordens_queryset = ordens_queryset.filter(data_programacao=data_programada)

    # Paginação
    paginator = Paginator(ordens_queryset, limit)
    try:
        ordens_page = paginator.page(page)
    except EmptyPage:
        return JsonResponse({'ordens': [], 'message': 'Nenhuma ordem encontrada para essa página.'})

    # Monta os dados para retorno
    data = []
    for ordem in ordens_page:
        # Obtém a propriedade associada de forma segura
        propriedade = getattr(ordem, 'propriedade', None)

        # Monta os dados para cada ordem
        data.append({
            'id': ordem.pk,
            'ordem': ordem.ordem,
            'grupo_maquina': ordem.get_grupo_maquina_display(),
            'data_criacao': localtime(ordem.data_criacao).strftime('%d/%m/%Y %H:%M'),
            'data_programacao': ordem.data_programacao.strftime('%d/%m/%Y'),
            'obs': ordem.obs,
            'status_atual': ordem.status_atual,
            'maquina':ordem.maquina.nome if ordem.maquina else None,
            'maquina_id': ordem.maquina.id if ordem.maquina else None,
            'ultima_atualizacao': localtime(ordem.ultima_atualizacao).strftime('%d/%m/%Y %H:%M'),
            'propriedade': {
                'descricao_mp': propriedade.mp_codigo.codigo +" - "+ propriedade.mp_codigo.descricao if propriedade else None,
                'mp_codigo': propriedade.mp_codigo.codigo if propriedade.mp_codigo else None,
                'quantidade': propriedade.quantidade if propriedade else None,
                'tamanho': propriedade.tamanho if propriedade else None,
                'aproveitamento': propriedade.aproveitamento if propriedade else None,
                'retalho': 'Sim' if propriedade and propriedade.retalho else 'Não',
                'nova_mp': propriedade.nova_mp.codigo +" - "+ propriedade.nova_mp.descricao if propriedade.nova_mp else None,
                'nova_mp_codigo': propriedade.nova_mp.codigo if propriedade.nova_mp else None,
            } if propriedade else None,
            'pecas': [
                {
                    'id': peca_ordem.id,
                    'peca_id': peca_ordem.peca.id,
                    'peca_codigo': peca_ordem.peca.codigo,
                    'peca_nome': peca_ordem.peca.descricao if peca_ordem.peca.descricao else 'Sem descrição',
                    'quantidade': peca_ordem.qtd_planejada,
                    'qtd_morta': peca_ordem.qtd_morta,
                    'qtd_boa': peca_ordem.qtd_boa
                }
                for peca_ordem in ordem.ordem_pecas_serra.all()
            ]  # Lista todas as peças associadas
        })

    has_next = ordens_page.has_next()

    # Retorna os dados paginados como JSON
    return JsonResponse({
        'ordens': data,
        'page': ordens_page.number,
        'total_pages': paginator.num_pages,
        'total_ordens': paginator.count,
        'has_next': has_next,  # Indica se há próxima página
    })

@require_GET
def get_ordens_iniciadas(request):

    usuario_tipo = Profile.objects.filter(user=request.user).values_list('tipo_acesso', flat=True).first()

    # Filtra as ordens com base no status 'iniciada'
    ordens_queryset = Ordem.objects.prefetch_related('ordem_pecas_serra', 'propriedade') \
        .filter(grupo_maquina='serra',status_atual='iniciada')

    # Paginação
    page = int(request.GET.get('page', 1))  # Obtém o número da página
    limit = int(request.GET.get('limit', 10))  # Define o limite padrão por página

    filtro_ordem = request.GET.get('ordem', '').strip()
    filtro_mp = request.GET.get('mp', '').strip()
    filtro_peca = request.GET.get('peca', '').strip()

    if filtro_ordem:
        ordens_queryset = ordens_queryset.filter(ordem__icontains=filtro_ordem)
    if filtro_mp:
        ordens_queryset = ordens_queryset.filter(propriedade__mp_codigo__codigo=filtro_mp)
    if filtro_peca:
        ordens_queryset = ordens_queryset.filter(ordem_pecas_serra__peca__codigo=filtro_peca)

    paginator = Paginator(ordens_queryset, limit)  # Aplica a paginação

    try:
        ordens_page = paginator.page(page)  # Obtém a página atual
    except EmptyPage:
        return JsonResponse({
            'ordens': [],
            'message': 'Nenhuma ordem encontrada para essa página.'
        })

    # Monta os dados para retorno
    data = []
    for ordem in ordens_page:
        # Obtém a propriedade associada de forma segura
        propriedade = getattr(ordem, 'propriedade', None)

        # Obtém as peças associadas
        pecas_data = [
            {
                'peca_id': peca_ordem.peca.id,
                'peca_codigo': peca_ordem.peca.codigo,
                'peca_nome': peca_ordem.peca.descricao if peca_ordem.peca.descricao else 'Sem descrição',
                'quantidade': peca_ordem.qtd_planejada,
                'qtd_morta': peca_ordem.qtd_morta
            }
            for peca_ordem in ordem.ordem_pecas_serra.all()
        ]

        # Adiciona os dados da ordem
        data.append({
            'id': ordem.id,
            'ordem': ordem.ordem,
            'grupo_maquina': ordem.get_grupo_maquina_display(),
            'data_criacao': ordem.data_criacao.strftime('%d/%m/%Y %H:%M'),
            'obs': ordem.obs,
            'status_atual': ordem.status_atual,
            'maquina': ordem.maquina.nome,
            'ultima_atualizacao': ordem.ultima_atualizacao,
            'propriedade': {
                'descricao_mp': propriedade.mp_codigo.codigo + " - " + propriedade.mp_codigo.descricao if propriedade else None,
                'quantidade': propriedade.quantidade if propriedade else None,
                'retalho': 'Sim' if propriedade and propriedade.retalho else 'Não',
            } if propriedade else None,
            'pecas': pecas_data  # Inclui as peças associadas
        })

    # Retorna os dados paginados como JSON
    return JsonResponse({
        'usuario_tipo_acesso': usuario_tipo,
        'ordens': data,
        'page': ordens_page.number,
        'total_pages': paginator.num_pages,
        'total_ordens': paginator.count
    })

@require_GET
def get_ordens_interrompidas(request):

    usuario_tipo = Profile.objects.filter(user=request.user).values_list('tipo_acesso', flat=True).first()

    # Filtra as ordens com base no status 'interrompida'
    ordens_queryset = Ordem.objects.prefetch_related('processos', 'ordem_pecas_serra', 'propriedade') \
        .filter(grupo_maquina='serra',status_atual='interrompida')

    # Paginação (opcional)
    page = request.GET.get('page', 1)  # Obtém o número da página
    limit = request.GET.get('limit', 10)  # Define o limite padrão por página

    filtro_ordem = request.GET.get('ordem', '').strip()
    filtro_mp = request.GET.get('mp', '').strip()
    filtro_peca = request.GET.get('peca', '').strip()

    if filtro_ordem:
        ordens_queryset = ordens_queryset.filter(ordem__icontains=filtro_ordem)
    if filtro_mp:
        ordens_queryset = ordens_queryset.filter(propriedade__mp_codigo__codigo=filtro_mp)
    if filtro_peca:
        ordens_queryset = ordens_queryset.filter(ordem_pecas_serra__peca__codigo=filtro_peca)

    paginator = Paginator(ordens_queryset, limit)  # Aplica a paginação
    ordens_page = paginator.get_page(page)  # Obtém a página atual

    # Monta os dados para retorno
    data = []
    for ordem in ordens_page:
        # Obtém o último processo interrompido (caso tenha mais de um)
        ultimo_processo_interrompido = ordem.processos.filter(status='interrompida').order_by('-data_inicio').first()

        # Obtém a propriedade da ordem (se existir)
        propriedade = getattr(ordem, 'propriedade', None)

        # Obtém todas as peças associadas à ordem
        pecas_data = []
        for peca_ordem in ordem.ordem_pecas_serra.all():
            pecas_data.append({
                'peca_id': peca_ordem.peca.id,
                'peca_codigo': peca_ordem.peca.codigo,
                'peca_nome': peca_ordem.peca.descricao if peca_ordem.peca.descricao else 'Sem descrição',
                'quantidade': peca_ordem.qtd_planejada,
                'qtd_morta': peca_ordem.qtd_morta,
            })

        # Adiciona os dados da ordem
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
            'propriedade': {
                'descricao_mp': propriedade.mp_codigo.codigo + " - " + propriedade.mp_codigo.descricao if propriedade else None,
                'quantidade': propriedade.quantidade if propriedade else None,
            } if propriedade else None,
            'pecas': pecas_data,  # Inclui as peças associadas
        })

    # Retorna os dados paginados como JSON
    return JsonResponse({
        'usuario_tipo_acesso': usuario_tipo,
        'ordens': data,
        'page': ordens_page.number,
        'total_pages': paginator.num_pages,
        'total_ordens': paginator.count
    })

def get_mp(request):
    """
    Retorna uma lista paginada de mp, com suporte a busca por código ou descrição.
    """
    # Obtém os parâmetros da requisição
    search = request.GET.get('search', '').strip()  # Termo de busca
    page = int(request.GET.get('page', 1))  # Página atual (padrão é 1)
    per_page = int(request.GET.get('per_page', 10))  # Itens por página (padrão é 10)

    # Filtra as peças com base no termo de busca (opcional)
    mps_query = Mp.objects.all()
    if search:
        mps_query = mps_query.filter(
            Q(codigo__icontains=search) | Q(descricao__icontains=search)
        ).order_by('codigo')

    # Paginação
    paginator = Paginator(mps_query, per_page)
    mp_page = paginator.get_page(page)

    # Monta os resultados paginados no formato esperado pelo Select2
    data = {
        'results': [
            {'id': mp.codigo, 'text': f"{mp.codigo} - {mp.descricao}"} for mp in mp_page
        ],
        'pagination': {
            'more': mp_page.has_next()  # Se há mais páginas
        },
    }

    return JsonResponse(data)

def get_peca(request):
    
    """
    Retorna uma lista paginada de peca, com suporte a busca por código ou descrição.
    """

    # Obtém os parâmetros da requisição
    search = request.GET.get('search', '').strip()  # Termo de busca
    page = int(request.GET.get('page', 1))  # Página atual (padrão é 1)
    per_page = int(request.GET.get('per_page', 10))  # Itens por página (padrão é 10)

    # Filtra as peças com base no termo de busca (opcional)
    peca_query = Pecas.objects.all()
    if search:
        peca_query = peca_query.filter(
            Q(codigo__icontains=search) | Q(descricao__icontains=search)
        ).order_by('codigo')

    # Paginação
    paginator = Paginator(peca_query, per_page)
    peca_page = paginator.get_page(page)

    # Monta os resultados paginados no formato esperado pelo Select2
    data = {
        'results': [
            {'id': peca.codigo, 'text': f"{peca.codigo} - {peca.descricao}"} for peca in peca_page
        ],
        'pagination': {
            'more': peca_page.has_next()  # Se há mais páginas
        },
    }

    return JsonResponse(data)

def criar_ordem(request):
    if request.method == "POST":
        try:
            # Carrega o JSON enviado no corpo da requisição
            data = json.loads(request.body)
            
            with transaction.atomic():

                # Criação da nova ordem
                nova_ordem = Ordem.objects.create(
                    obs=data.get('descricao', ''),  # Usa o valor de 'descricao' ou string vazia caso não exista
                    grupo_maquina='serra',
                    data_programacao=data.get('dataProgramacao')
                )

                # Criação das propriedades da ordem
                PropriedadesOrdem.objects.create(
                    ordem=nova_ordem,
                    mp_codigo=get_object_or_404(Mp, codigo=data.get('mp')),
                    tamanho=data.get('tamanhoVara', 0),  # Usa valor padrão caso 'tamanho' não exista
                    quantidade=0 if data.get('quantidade') == '' else data.get('quantidade'),  # Usa valor padrão caso 'qtd' não exista
                    retalho=(data.get('retalho') == 'on')  # Converte "on" para True e ausente para False
                )

                # Iteração para criar peças associadas à ordem
                for peca in data.get('pecas', []):  # Garante que 'pecas' seja uma lista, mesmo se não existir
                    PecasOrdem.objects.create(
                        ordem=nova_ordem,
                        peca=get_object_or_404(Pecas, codigo=peca.get('peca')),
                        qtd_planejada=peca.get('quantidade', 0),  # Usa valor padrão caso 'quantidade' não exista
                    )

                # Retorna sucesso se tudo foi processado
                return JsonResponse({'status': 'success', 'message': 'Ordem criada com sucesso!'})

        except json.JSONDecodeError as e:
            # Captura erro ao decodificar JSON
            return JsonResponse({'status': 'error', 'message': 'Erro ao processar JSON', 'details': str(e)}, status=400)

        except Exception as e:
            # Captura erros genéricos
            return JsonResponse({'status': 'error', 'message': 'Erro ao criar a ordem', 'details': str(e)}, status=500)

def adicionar_pecas_ordem(request):

    if request.method == 'POST':

        data = json.loads(request.body)

        ordem = Ordem.objects.filter(id=data.get('ordem_id')).first()

        print(data)

        nova_peca = PecasOrdem.objects.create(
            ordem=ordem,
            peca=get_object_or_404(Pecas, codigo=data.get('peca')),
            qtd_planejada=data.get('quantidade', 1),
        )

        peca = {
            'id_peca': nova_peca.id,
            'peca_id': nova_peca.peca.id,
            'peca_codigo': nova_peca.peca.codigo,
            'peca_nome': f"{nova_peca.peca.codigo} - {nova_peca.peca.descricao}",
            'quantidade': nova_peca.qtd_planejada,
            'qtd_morta': nova_peca.qtd_morta
        }

        return JsonResponse({'success': True, 'peca': peca})

@csrf_exempt
def importar_ordens_serra(request):
    if request.method == "POST":
        arquivo = request.FILES.get('arquivoOrdens')  # Captura o arquivo enviado
        
        if not arquivo:
            return JsonResponse({'status': 'error', 'message': 'Nenhum arquivo foi enviado.'}, status=400)

        try:
            with transaction.atomic():

                # Verifica se o arquivo é um Excel
                if not arquivo.name.endswith('.xlsx'):
                    return JsonResponse({'status': 'error', 'message': 'O arquivo enviado não é um Excel (.xlsx).'}, status=400)

                # Carrega o arquivo Excel
                workbook = openpyxl.load_workbook(arquivo)
                sheet = workbook.active  # Considera a primeira aba do Excel

                # Dicionário para agrupar as peças por ordem
                ordens = {}

                # Lê as linhas do Excel (assumindo que a primeira linha contém cabeçalhos)
                for row in sheet.iter_rows(min_row=2, values_only=True):  # Ignora a linha de cabeçalho
                    os = row[0]
                    codigo = row[1]
                    # quantidade = row[2]
                    comprimento = row[3]
                    conjunto = row[4]
                    qtd_planejada = row[5]
                    perca = row[6]
                    qt_varas = row[7]

                    mp = row[8]  # MP é única por ordem
                    if isinstance(mp, tuple):
                        mp = ', '.join(mp)  # Converte para string se for uma tupla

                    # Agrupa as peças pela ordem (OS)
                    if os not in ordens:
                        ordens[os] = {
                            'conjunto': conjunto,
                            'mp': mp,
                            'qt_varas': qt_varas,
                            'pecas': []
                        }

                    ordens[os]['pecas'].append({
                        'codigo': codigo,
                        'quantidade': qtd_planejada,
                        'comprimento': comprimento,
                        'perca': perca
                    })

                # Processa as ordens e peças
                for os, data in ordens.items():
                    # Cria a ordem
                    ordem = Ordem.objects.create(
                        obs=data['conjunto'],
                        grupo_maquina="serra",
                    )

                    # Cria a propriedade da ordem (MP única)
                    mp_codigo = data['mp'].split(' - ')[0].replace("('","")  # Extrai o código MP
                    mp_descricao = data['mp'].split(' - ')[1].replace("',)","")

                    mp_existente = Mp.objects.filter(codigo=mp_codigo).exists()

                    if not mp_existente:
                        mp = Mp.objects.create(
                            codigo=mp_codigo,
                            descricao=mp_descricao,
                            setor=get_object_or_404(Setor, nome='serra')  # Busca o setor "serra"
                        )
                    else:
                        # Recupera a MP existente
                        mp = Mp.objects.get(codigo=mp_codigo)

                    # Cria a propriedade da ordem, associando a MP existente ou recém-criada
                    propriedade = PropriedadesOrdem.objects.create(
                        ordem=ordem,
                        mp_codigo=mp,  # Associa a MP (existente ou nova)
                        quantidade=data['qt_varas'],  # Quantidade de varas da MP
                    )
                        
                    # Cria as peças associadas à ordem
                    for peca in data['pecas']:
                        # Extrai os dados da peça
                        peca_codigo = peca['codigo']
                        peca_quantidade = peca['quantidade']

                        # Verifica se a peça já existe no banco de dados
                        peca_existente = Pecas.objects.filter(codigo=peca_codigo).exists()

                        if not peca_existente:
                            # Cria a peça caso ela não exista
                            nova_peca = Pecas.objects.create(
                                codigo=peca_codigo,
                                comprimento=peca['comprimento']
                            )
                        else:
                            # Recupera a peça existente
                            nova_peca = Pecas.objects.get(codigo=peca_codigo)

                        # Cria a associação da peça à ordem
                        PecasOrdem.objects.create(
                            ordem=ordem,
                            peca=nova_peca,  # Associa à peça existente ou recém-criada
                            qtd_planejada=peca_quantidade,
                        )

                return JsonResponse({'status': 'success', 'message': 'Arquivo Excel processado com sucesso!'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f'Erro ao processar o arquivo: {str(e)}'}, status=500)

    return JsonResponse({'status': 'error', 'message': 'Método não permitido.'}, status=405)

def verificar_mp_pecas_na_ordem(request):
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Método não permitido"}, status=405)

    try:
        data = json.loads(request.body)
        mp_codigo = data.get("mp")
        pecas_codigos = data.get("pecas", [])
        
        if not mp_codigo or not pecas_codigos:
            return JsonResponse({
                "status": "warning",
                "message": "Código de MP e lista de peças são obrigatórios."
            }, status=400)

        # Converte para set para operações mais eficientes
        pecas_filter = set(pecas_codigos)
        
        # Otimização: Filtra por status e usa prefetch_related com Prefetch
        ordens_com_mp = Ordem.objects.filter(
            propriedade__mp_codigo__codigo=mp_codigo,
            status_atual='aguardando_iniciar'  # Filtro adicional por status
        ).prefetch_related(
            Prefetch(
                'ordem_pecas_serra',
                queryset=PecasOrdem.objects.filter(peca__codigo__in=pecas_filter),
                to_attr='pecas_relevantes'
            )
        )

        if not ordens_com_mp.exists():
            return JsonResponse({
                "status": "warning",
                "message": "Matéria-prima não encontrada em ordens aguardando iniciar."
            }, status=404)

        # Verifica cada ordem de forma otimizada
        for ordem in ordens_com_mp:
            pecas_da_ordem = {p.peca.codigo for p in ordem.pecas_relevantes}
            if pecas_filter.issubset(pecas_da_ordem):
                return JsonResponse({
                    "status": "success",
                    "ordem": ordem.ordem,
                    "id_ordem": ordem.id,
                    "grupo_maquina": ordem.grupo_maquina,
                    "mp": mp_codigo,
                    "pecas": pecas_codigos
                })

        return JsonResponse({
            "status": "warning", 
            "message": "MP e peças não estão associadas à mesma ordem com status 'aguardando_iniciar'."
        }, status=404)

    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "JSON inválido"}, status=400)
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)
    
def api_apontamentos_peca(request):
    ordens = (
        Ordem.objects.filter(status_atual='finalizada', grupo_maquina='serra', excluida=False)
        .exclude(Q(ordem_pecas_serra__peca__codigo='GRAU') | Q(ordem_pecas_serra__peca__codigo='RECORTE'))  # Exclui GRAU e RECORTE
        .select_related('operador_final', 'maquina')  # Para otimizar a relação com operador_final
        .prefetch_related('ordem_pecas_serra__peca')  # Ajustado para usar o related_name correto
        .distinct()  # Evitar duplicatas
    )

    # Constrói o resultado manualmente
    resultado = []
    vistos = set()  # Rastreamos os itens já processados
    for ordem in ordens:
        for apontamento in ordem.ordem_pecas_serra.all():
            chave_unica = (ordem.id, apontamento.peca.id)  # Identificador único
            if chave_unica not in vistos:
                vistos.add(chave_unica)  # Marca como visto
                data_final = localtime(apontamento.data) if apontamento.data else None

                resultado.append({
                    "ordem": ordem.ordem,
                    "codigo_peca": apontamento.peca.codigo,
                    "descricao_peca": apontamento.peca.descricao if apontamento.peca.descricao else 'Cadastrar descrição',
                    "qtd_boa": apontamento.qtd_boa,
                    "qtd_morta": apontamento.qtd_morta,
                    "qtd_planejada": apontamento.qtd_planejada,
                    "obs_plano": ordem.obs,
                    "maquina": ordem.maquina.nome,
                    "obs_operador": ordem.obs_operador,
                    "operador": f"{ordem.operador_final.matricula} - {ordem.operador_final.nome}" if ordem.operador_final else None,
                    "data_final": data_final  # Mantemos o objeto datetime para ordenação
                })
    
    resultado.sort(key=lambda x: x['data_final'])

    # Converte a data para o formato desejado após ordenar
    for item in resultado:
        if item['data_final']:
            item['data_final'] = item['data_final'].strftime('%d/%m/%Y %H:%M')

    return JsonResponse(resultado, safe=False)

def api_apontamentos_mp(request):
    propriedades_ordens = (
        PropriedadesOrdem.objects.filter(ordem__status_atual='finalizada', ordem__grupo_maquina='serra', ordem__excluida=False)
        .exclude(Q(mp_codigo__codigo='GRAU') | Q(mp_codigo__codigo='RECORTE'))  # Exclui GRAU e RECORTE
        .select_related('ordem', 'mp_codigo', 'nova_mp')  # Otimiza consultas relacionadas
        # .order_by('ordem__ordem_pecas_serra__data')  # Ordena pelo campo `data` da tabela `Ordem`
        .annotate(
            descricao_original=Concat(  # Concatena código e descrição originais
                F('mp_codigo__codigo'),
                Value(' - '),
                F('mp_codigo__descricao')
            ),
            descricao_nova=Concat(  # Concatena código e descrição da nova matéria-prima, se houver
                F('nova_mp__codigo'),
                Value(' - '),
                F('nova_mp__descricao')
            ),
            data_formatada=F('ordem__ordem_pecas_serra__data')  # Adiciona o campo bruto para ser formatado posteriormente
        )
        .distinct('ordem__ordem')  # Garante linhas únicas por ordem
        # .order_by('ordem__ordem', '-ordem__ordem_pecas_serra__data')  # Ordena primeiro por ordem, depois por data decrescente
        .values(
            'ordem__ordem',  # Campo `ordem` da tabela `Ordem`
            'tamanho',  # Campo `tamanho` da tabela `PropriedadesOrdem`
            'quantidade',  # Campo `quantidade` da tabela `PropriedadesOrdem`
            'descricao_original',  # Concatenação do código e descrição original
            'descricao_nova',  # Concatenação do código e descrição da nova matéria-prima
            'data_formatada',  # Inclui o campo data sem formatação para ser processado
        )
    )

    propriedades_ordens = sorted(propriedades_ordens, key=lambda x: x['data_formatada'] or '')

    # Formata o campo `data_formatada` para o formato desejado
    propriedades_ordens = [
        {
            **item,
            'data_formatada': localtime(item['data_formatada']).strftime('%d/%m/%Y %H:%M') if item['data_formatada'] else None
        }
        for item in propriedades_ordens
    ]

    return JsonResponse(propriedades_ordens, safe=False)

def historico(request):

    return render(request, "apontamento_serra/historico.html")

@csrf_exempt
def atualizar_propriedades_ordem(request):

    if request.method == 'POST':
        data = json.loads(request.body)

        print(data)

        ordem_id = data.get('ordemId')
        tamanho = data.get('novoTamanho')
        quantidade = data.get('novaQuantidade')
        codigo_mp=data.get('novaMateriaPrimaId')

        ordem = get_object_or_404(Ordem, pk=ordem_id)
        edit_propriedade = get_object_or_404(PropriedadesOrdem, ordem=ordem)
        edit_propriedade.tamanho = tamanho
        edit_propriedade.quantidade = quantidade
        edit_propriedade.nova_mp = get_object_or_404(Mp, codigo=codigo_mp)
        edit_propriedade.save()

    return JsonResponse({'status': 'success'})

@csrf_exempt
def atualizar_pecas_ordem(request):

    data = json.loads(request.body)

    if request.method == 'POST':

        for peca in data['pecas']:
            edit_info_apontamento = get_object_or_404(PecasOrdem, pk=peca['peca_id'])
            edit_info_apontamento.qtd_boa = peca['qtd_boa']
            edit_info_apontamento.qtd_morta = peca['qtd_morta']
    
            edit_info_apontamento.save()

    return JsonResponse({'status':'success'})

@csrf_exempt
def duplicar_ordem(request):
    """
    API para duplicar uma ordem existente.
    """

    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Método não permitido. Use POST!"}, status=405)

    # Verifica se o usuário é do tipo "operador" e bloqueia o acesso
    if not hasattr(request.user, 'profile') or request.user.profile.tipo_acesso != 'pcp':
        return JsonResponse({'error': 'Acesso negado: você não tem permissão para duplicar ordens.'}, status=403)


    try:
        # Carrega o JSON enviado no corpo da requisição
        data = json.loads(request.body)
        ordem_id = data.get("ordem_id")

        if not ordem_id:
            return JsonResponse({"status": "error", "message": "O campo 'ordem_id' é obrigatório!"}, status=400)

        # Obtém a ordem original
        ordem_original = get_object_or_404(Ordem, pk=ordem_id)

        # Garante que a ordem pode ser duplicada
        # if ordem_original.status_atual == "finalizada":
        #     return JsonResponse({"status": "error", "message": "Não é possível duplicar uma ordem já finalizada!"}, status=400)

        with transaction.atomic():
            # Criando a nova ordem duplicada
            nova_ordem = Ordem.objects.create(
                obs=f"Ordem duplicada #{ordem_original.ordem}",
                grupo_maquina=ordem_original.grupo_maquina,
                data_programacao=now().date(),  # Agora será sempre o dia atual
                status_atual="aguardando_iniciar",
            )

            # Criando as propriedades da nova ordem
            propriedade_original = PropriedadesOrdem.objects.filter(ordem=ordem_original).first()
            if propriedade_original:
                PropriedadesOrdem.objects.create(
                    ordem=nova_ordem,
                    mp_codigo=propriedade_original.mp_codigo,
                    tamanho=propriedade_original.tamanho,
                    quantidade=propriedade_original.quantidade,
                    retalho=propriedade_original.retalho
                )

            # Duplicando as peças associadas
            for peca in PecasOrdem.objects.filter(ordem=ordem_original):
                PecasOrdem.objects.create(
                    ordem=nova_ordem,
                    peca=peca.peca,
                    qtd_planejada=peca.qtd_planejada
                )

        return JsonResponse({
            "status": "success",
            "message": "Ordem duplicada com sucesso!",
            "nova_ordem_id": nova_ordem.pk
        }, status=201)

    except json.JSONDecodeError as e:
        return JsonResponse({"status": "error", "message": "Erro ao processar JSON", "details": str(e)}, status=400)

    except Ordem.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Ordem original não encontrada."}, status=404)

    except Exception as e:
        return JsonResponse({"status": "error", "message": "Erro ao duplicar a ordem", "details": str(e)}, status=500)

@csrf_exempt
def excluir_peca_ordem(request):
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Método não permitido. Use POST."}, status=405)

    if not hasattr(request.user, 'profile') or request.user.profile.tipo_acesso != 'pcp':
        return JsonResponse({"status": "error", "message": 'Acesso negado: você não tem permissão para excluir peças da ordem.'}, status=403)

    try:
        # Carrega os dados enviados na requisição
        data = json.loads(request.body)
        ordem_id = data.get("ordem_id")
        index = data.get("index")

        ordem = Ordem.objects.get(pk=ordem_id)

        if ordem.status_atual == 'finalizada':
            return JsonResponse({"status":"error", "message":"Ordem finalizada, não é possível alterar."})    

        if not ordem_id or index is None:
            return JsonResponse({"status": "error", "message": "Os campos 'ordem_id' e 'index' são obrigatórios."}, status=400)

        pecas = PecasOrdem.objects.filter(ordem=ordem)

        # Verifica se há pelo menos uma peça restante antes de excluir
        if pecas.count() <= 1:
            return JsonResponse({"status": "error", "message": "A ordem deve ter pelo menos uma peça."}, status=400)

        # Obtém a peça específica e exclui
        peca = get_object_or_404(PecasOrdem, pk=index)
        peca.delete()

        return JsonResponse({"status": "success", "message": "Peça excluída com sucesso."})

    except Ordem.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Ordem não encontrada."}, status=404)

    except PecasOrdem.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Peça não encontrada."}, status=404)

    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)

#### dashboard

def dashboard(request):

    return render(request, 'dashboard/dashboard.html')

def parse_tempo(hora_str):
    h, m, s = map(float, hora_str.split(':'))
    return timedelta(hours=h, minutes=m, seconds=s)

def merge_metricas(horas_producao, horas_parada):
    resultado = defaultdict(dict)

    # Produção
    for item in horas_producao:
        key = (item['maquina'], item['dia'])
        resultado[key]['maquina'] = item['maquina']
        resultado[key]['dia'] = item['dia']
        resultado[key]['producao_total'] = item.get('total_dia', '00:00:00')

    # Parada
    for item in horas_parada:
        key = (item['maquina'], item['dia'])
        resultado[key].setdefault('maquina', item['maquina'])
        resultado[key].setdefault('dia', item['dia'])
        resultado[key]['parada_total'] = item.get('total_dia', '00:00:00')

    # Calcular tempo ocioso
    for key, val in resultado.items():
        prod = parse_tempo(val.get('producao_total', '00:00:00'))
        parada = parse_tempo(val.get('parada_total', '00:00:00'))
        usado = prod + parada

        ocioso = timedelta(hours=20) - usado
        ocioso = max(ocioso, timedelta(seconds=0))  # nunca negativo
        val['tempo_ocioso'] = formatar_timedelta(ocioso)

    return sorted(resultado.values(), key=lambda x: (x['dia'], x['maquina']))

@login_required
def indicador_hora_operacao_maquina(request):
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    maquina_param = request.GET.get('maquina')

    horas_producao = hora_operacao_maquina(maquina_param, data_inicio, data_fim)
    horas_parada = hora_parada_maquina(maquina_param, data_inicio, data_fim)

    resultado_unificado = merge_metricas(horas_producao, horas_parada)

    return JsonResponse(resultado_unificado, safe=False)

@login_required
def indicador_ordem_finalizada_maquina(request):
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')

    resultado = ordem_por_maquina(data_inicio, data_fim)

    return JsonResponse(resultado)

@login_required
def indicador_peca_produzida_maquina(request):
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')

    resultado = producao_por_maquina(data_inicio, data_fim)

    return JsonResponse(resultado)