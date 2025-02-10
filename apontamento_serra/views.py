from django.shortcuts import render
from django.http import JsonResponse
from django.db import transaction
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
from core.models import OrdemProcesso,PropriedadesOrdem,Ordem,MaquinaParada
from cadastro.models import MotivoExclusao, MotivoInterrupcao, Mp, Pecas, Operador, Setor, MotivoMaquinaParada

import os
import re
import json
import openpyxl

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
    motivos_maquina_parada = MotivoMaquinaParada.objects.filter(setor__nome='serra')
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
            ordem=pk_ordem,
            grupo_maquina=name_maquina
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
                'peca_id': peca.peca.id,
                'peca_codigo': peca.peca.codigo,
                'peca_nome': f"{peca.peca.codigo} - {peca.peca.descricao}",
                'quantidade': peca.qtd_planejada,
                'qtd_morta': peca.qtd_morta
            }
            for peca in ordem.ordem_pecas_serra.all()
        ]

        # Retorna as propriedades e as peças como JSON
        return JsonResponse({'pecas': pecas, 'propriedades': propriedades})

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
                grupo_maquina = body['grupo_maquina'].lower()
                pecas_geral = body.get('pecas_mortas', [])
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
                    data_fim=now() if status == 'finalizada' else None
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

                    # Verifica se ja existe alguma ordem iniciada nessa máquina
                    if processo_atual.status == 'iniciada':
                        return JsonResponse({'error': f'Ja existe uma ordem para essa máquina, finalize ou interrompa. Atualize a página'}, status=400)

                    ordem.status_prioridade = 1
                elif status == 'finalizada':
                    
                    tamanho_vara = body.get('tamanho_vara')
                    qtd_varas = body.get('qtd_vara')
                    operador_final = int(body.get('operador_final'))
                    obs_final = body.get('obs_finalizar')

                    ordem.operador_final=get_object_or_404(Operador, pk=operador_final)
                    ordem.obs_operador=obs_final

                    mp_final = body.get('mp_final')

                    if ordem.propriedade.mp_codigo.codigo != mp_final:
                        ordem.propriedade.nova_mp = get_object_or_404(Mp, codigo=mp_final)
                        ordem.propriedade.save()

                    ordem.propriedade.tamanho = tamanho_vara
                    ordem.propriedade.save()

                    # Verifica se a quantidade de chapas mudaram
                    if int(qtd_varas) != ordem.propriedade.quantidade:
                        ordem.propriedade.quantidade = int(qtd_varas)
                        ordem.propriedade.save()
                    
                    for peca in pecas_geral:
                        peca_id = peca.get('peca')
                        planejada = peca.get('planejadas')
                        mortas = peca.get('mortas', 0)

                        peca = PecasOrdem.objects.get(ordem=ordem, peca=peca_id)
                        peca.qtd_boa = planejada
                        peca.qtd_morta = mortas

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
def get_ordens_criadas(request):

    # Captura os parâmetros de filtro
    filtro_ordem = request.GET.get('ordem', '').strip()
    status_atual = request.GET.get('status', '').strip()
    filtro_mp = request.GET.get('mp', '').strip()
    filtro_peca = request.GET.get('peca', '').strip()

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
            'obs': ordem.obs,
            'status_atual': ordem.status_atual,
            'propriedade': {
                'descricao_mp': propriedade.mp_codigo.codigo +" - "+ propriedade.mp_codigo.descricao if propriedade else None,
                'quantidade': propriedade.quantidade if propriedade else None,
                'tipo_chapa': propriedade.get_tipo_chapa_display() if propriedade else None,
                'aproveitamento': propriedade.aproveitamento if propriedade else None,
                'retalho': 'Sim' if propriedade and propriedade.retalho else 'Não',
            } if propriedade else None,
            'pecas': [
                {
                    'peca_id': peca_ordem.peca.id,
                    'peca_codigo': peca_ordem.peca.codigo,
                    'peca_nome': peca_ordem.peca.descricao if peca_ordem.peca.descricao else 'Sem descrição',
                    'quantidade': peca_ordem.qtd_planejada,
                    'qtd_morta': peca_ordem.qtd_morta
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
            'ordem': ordem.ordem,
            'grupo_maquina': ordem.get_grupo_maquina_display(),
            'data_criacao': ordem.data_criacao.strftime('%d/%m/%Y %H:%M'),
            'obs': ordem.obs,
            'status_atual': ordem.status_atual,
            'maquina': ordem.get_maquina_display(),
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
        'ordens': data,
        'page': ordens_page.number,
        'total_pages': paginator.num_pages,
        'total_ordens': paginator.count
    })

@require_GET
def get_ordens_interrompidas(request):
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
            'ordem': ordem.ordem,
            'grupo_maquina': ordem.get_grupo_maquina_display(),
            'data_criacao': ordem.data_criacao.strftime('%d/%m/%Y %H:%M'),
            'obs': ordem.obs,
            'status_atual': ordem.status_atual,
            'maquina': ordem.get_maquina_display(),
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

def api_apontamentos_peca(request):
    ordens = (
        Ordem.objects.filter(status_atual='finalizada', grupo_maquina='serra', excluida=False)
        .exclude(Q(ordem_pecas_serra__peca__codigo='GRAU') | Q(ordem_pecas_serra__peca__codigo='RECORTE'))  # Exclui GRAU e RECORTE
        .select_related('operador_final')  # Para otimizar a relação com operador_final
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
                    "descricao_peca": apontamento.peca.descricao,
                    "qtd_boa": apontamento.qtd_boa,
                    "qtd_morta": apontamento.qtd_morta,
                    "qtd_planejada": apontamento.qtd_planejada,
                    "obs_plano": ordem.obs,
                    "maquina": ordem.get_maquina_display(),
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
