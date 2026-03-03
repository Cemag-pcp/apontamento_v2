from django.shortcuts import render
from django.http import JsonResponse
from django.views import View
from django.conf import settings
from django.db import transaction, connection
from django.shortcuts import get_object_or_404
from django.core.paginator import Paginator, EmptyPage
from django.views.decorators.http import require_GET
from django.views.decorators.http import require_POST
from django.utils.timezone import now,localtime
from django.utils.dateparse import parse_date
from django.db.models import Q,Prefetch,Count,OuterRef, Subquery, Exists
from django.contrib.auth.decorators import login_required

from .models import Ordem,PecasOrdem
from core.models import OrdemProcesso, MaquinaParada, Profile
from cadastro.models import MotivoInterrupcao, Pecas, Operador, Maquina, MotivoMaquinaParada, MotivoExclusao
from inspecao.models import Inspecao
from .utils import criar_ordem_usinagem

import pandas as pd
import os
import tempfile
import re
import json
import requests
from datetime import date

from core.utils import notificar_ordem

# Caminho para a pasta temporária dentro do projeto
TEMP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'temp')

# Certifique-se de que a pasta existe
os.makedirs(TEMP_DIR, exist_ok=True)

def _apontar_item_erp_usinagem_silencioso(item_id, user=None):
    """
    Tenta apontar no ERP sem interromper o fluxo do operador.
    Em caso de falha, registra o erro no item e retorna sem lançar exceção.
    """
    try:
        item = (
            PecasOrdem.objects
            .select_related('ordem', 'peca')
            .filter(pk=item_id, ordem__grupo_maquina='usinagem')
            .first()
        )
        if not item or item.apontado:
            return

        user_ref = user if getattr(user, 'is_authenticated', False) else None

        if (item.qtd_morta or 0) > 0:
            item.erro_apontamento = (
                'Apontamento via API bloqueado automaticamente: item com qtd_morta > 0. '
                'A funcionalidade de desvio precisa ser ajustada na API.'
            )
            item.tipo_apontamento = 'api'
            item.resp_apontamento = user_ref
            item.save(update_fields=['erro_apontamento', 'tipo_apontamento', 'resp_apontamento'])
            return

        payload_integracao = {
            "id": "Apontamento 1",
            "data": localtime(now()).strftime('%d/%m/%Y'),
            "pessoa": "4357",
            "recurso": str(item.peca.codigo if item.peca else ""),
            "processo": "S Usinagem",
            "produzido": item.qtd_boa,
            "observacao": str(item.ordem_id),
        }

        try:
            # se for dev não rodar esse bloco
            # DJANGO_ENV = dev
            if os.getenv("DJANGO_ENV") == "dev":
                return
            else:
                response_integracao = requests.post(
                    "https://cemag.innovaro.com.br/api/integracao/v1/producao/apontar",
                    json=payload_integracao,
                    auth=("luan araujo", "luanaraujo7"),
                    timeout=20,
                )
        except requests.RequestException as exc:
            item.erro_apontamento = str(exc)[:2000]
            item.tipo_apontamento = 'api'
            item.resp_apontamento = user_ref
            item.save(update_fields=['erro_apontamento', 'tipo_apontamento', 'resp_apontamento'])
            return

        try:
            resposta_api_json = response_integracao.json()
        except ValueError:
            resposta_api_json = None

        if not response_integracao.ok:
            descricao_erro = ''
            if isinstance(resposta_api_json, dict):
                descricao_erro = str(resposta_api_json.get('description') or '')
            item.erro_apontamento = (descricao_erro or (response_integracao.text or ''))[:2000]
            item.tipo_apontamento = 'api'
            item.resp_apontamento = user_ref
            item.save(update_fields=['erro_apontamento', 'tipo_apontamento', 'resp_apontamento'])
            return

        if not isinstance(resposta_api_json, dict):
            item.erro_apontamento = (response_integracao.text or '')[:2000]
            item.tipo_apontamento = 'api'
            item.resp_apontamento = user_ref
            item.save(update_fields=['erro_apontamento', 'tipo_apontamento', 'resp_apontamento'])
            return

        status_erp = str(resposta_api_json.get('status') or '').strip().lower()
        if status_erp != 'success':
            item.erro_apontamento = str(
                resposta_api_json.get('description') or resposta_api_json
            )[:2000]
            item.tipo_apontamento = 'api'
            item.resp_apontamento = user_ref
            item.save(update_fields=['erro_apontamento', 'tipo_apontamento', 'resp_apontamento'])
            return

        item.apontado = True
        item.data_apontamento = now()
        item.tipo_apontamento = 'api'
        item.resp_apontamento = user_ref
        item.chave_apontamento = str(resposta_api_json.get('chaveProducao') or '')
        item.erro_apontamento = None
        item.save(update_fields=[
            'apontado',
            'data_apontamento',
            'tipo_apontamento',
            'resp_apontamento',
            'chave_apontamento',
            'erro_apontamento',
        ])
    except Exception:
        # Fluxo silencioso por requisito: nunca interromper a finalização do operador.
        return

def extrair_numeracao(nome_arquivo):
    match = re.search(r"(?i)OP(\d+)", nome_arquivo)  # (?i) torna a busca case insensitive
    if match:
        return match.group(1)
    return None

def planejamento(request):

    motivos = MotivoInterrupcao.objects.filter(setor__nome='usinagem', visivel=True)
    operadores = Operador.objects.filter(setor__nome='usinagem')
    motivos_maquina_parada = MotivoMaquinaParada.objects.filter(setor__nome='usinagem').exclude(nome='Finalizada parcial')
    motivos_exclusao = MotivoExclusao.objects.filter(setor__nome='usinagem')
    processos = Maquina.objects.filter(setor__nome='usinagem', tipo='processo')

    return render(request, 'apontamento_usinagem/planejamento.html', {'motivos':motivos,
                                                                      'operadores':operadores,
                                                                      'motivos_maquina_parada':motivos_maquina_parada,
                                                                      'motivos_exclusao': motivos_exclusao,
                                                                      'processos': processos})

def processos(request):

    motivos = MotivoInterrupcao.objects.filter(setor__nome='usinagem', visivel=True)
    operadores = Operador.objects.filter(setor__nome='usinagem')
    motivos_maquina_parada = MotivoMaquinaParada.objects.filter(setor__nome='estamparia').exclude(nome='Finalizada parcial')

    return render(request, 'apontamento_usinagem/processos.html', {'motivos':motivos,'operadores':operadores,'motivos_maquina_parada':motivos_maquina_parada,})

def get_pecas_ordem(request, pk_ordem):
    try:
        # Busca a ordem com os relacionamentos necessários
        ordem = Ordem.objects.prefetch_related('ordem_pecas_usinagem').get(pk=pk_ordem)

        # Obtém a peça relacionada
        peca_ordem = ordem.ordem_pecas_usinagem.first()  # Obtém a primeira peça (ou única)

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
    filtro_ordem = request.GET.get('ordem', '').strip()
    filtro_peca = request.GET.get('peca', '').strip()
    status_atual = request.GET.get('status', '').strip()
    data_programada = request.GET.get('data-programada', '').strip()
    
    page = int(request.GET.get('page', 1))
    limit = int(request.GET.get('limit', 10))

    usuario_tipo = Profile.objects.filter(user=request.user).values_list('tipo_acesso', flat=True).first()

    # obter a primeira peça associada à ordem
    primeira_peca = PecasOrdem.objects.filter(
        ordem=OuterRef('pk')
    ).order_by('id')[:1]

    # Query principal das ordens
    ordens_queryset = Ordem.objects.filter(
        grupo_maquina='usinagem',
        excluida=False
    ).annotate(
        peca_codigo=Subquery(primeira_peca.values('peca__codigo')),
        peca_descricao=Subquery(primeira_peca.values('peca__descricao')),
        peca_quantidade=Subquery(primeira_peca.values('qtd_planejada')),
        peca_quantidade_boa=Subquery(primeira_peca.values('qtd_boa'))
    ).order_by('-data_criacao')#.exclude(status_atual='finalizada')

    if filtro_ordem:
        ordens_queryset = ordens_queryset.filter(ordem=filtro_ordem)
    if filtro_peca:
        ordens_queryset = ordens_queryset.filter(peca_codigo=filtro_peca)
    if status_atual:
        ordens_queryset = ordens_queryset.filter(status_atual=status_atual)
    if data_programada:
        ordens_queryset = ordens_queryset.filter(data_programacao=data_programada)

    # Paginação
    paginator = Paginator(ordens_queryset, limit)
    try:
        ordens_page = paginator.page(page)
    except EmptyPage:
        return JsonResponse({'ordens': []})

    # Monta os dados para a resposta
    data = []
    for ordem in ordens_page:
        data.append({
            'id': ordem.pk,
            'ordem': ordem.ordem,
            'grupo_maquina': ordem.get_grupo_maquina_display(),
            'data_criacao': localtime(ordem.data_criacao).strftime('%d/%m/%Y %H:%M'),
            'data_programacao': ordem.data_programacao.strftime('%d/%m/%Y'),
            'obs': ordem.obs,
            'status_atual': ordem.status_atual,
            'maquina_id': ordem.maquina.id if ordem.maquina else None,
            'ultima_atualizacao': localtime(ordem.ultima_atualizacao).strftime('%d/%m/%Y %H:%M'),
            'peca': {
                'codigo': ordem.peca_codigo,
                'descricao': ordem.peca_descricao,
                'quantidade': ordem.peca_quantidade,
                'quantidade_boa': ordem.peca_quantidade_boa,
            } if ordem.peca_codigo else None
        })

    return JsonResponse({
        'usuario_tipo_acesso': usuario_tipo,
        'ordens': data,
        'has_next': ordens_page.has_next(),
    })

def atualizar_status_ordem(request):
    if request.method == 'PATCH':
        try:
            with transaction.atomic():
                # Parse do corpo da requisição
                body = json.loads(request.body)

                status = body['status']
                ordem_id = body['ordem_id']
                # grupo_maquina = body['grupo_maquina'].lower()
                qt_produzida = body.get('qt_realizada')
                qt_mortas = body.get('qt_mortas')
                maquina_nome = body.get('maquina_nome')

                if maquina_nome:
                    maquina_nome = get_object_or_404(Maquina, pk=int(maquina_nome))

                # Obtém a ordem
                ordem = Ordem.objects.get(pk=ordem_id)

                if status == 'iniciada' and maquina_nome:
                    ordem_em_andamento = Ordem.objects.filter(
                        maquina=maquina_nome, status_atual='iniciada'
                    ).exclude(id=ordem.id).exists()

                    if ordem_em_andamento:
                        return JsonResponse({
                            'error': f'Já existe uma ordem iniciada para essa máquina ({maquina_nome}).'
                        }, status=400)

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
                    data_fim=now() if status == 'finalizada' else None,
                )

                # Atualiza o status da ordem para o novo status
                ordem.status_atual = status
                
                if status == 'iniciada':

                    # Pode ser que a ordem tenha sido reestarada, então não precisao atualizar a máquina
                    maquinas_paradas = MaquinaParada.objects.filter(maquina=maquina_nome, data_fim__isnull=True)
                    for parada in maquinas_paradas:
                        parada.data_fim = now()
                        parada.save()

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

                    peca_obj = PecasOrdem.objects.create(
                        ordem=ordem,
                        peca=peca.peca,
                        qtd_planejada=peca.qtd_planejada,
                        qtd_boa=int(qt_produzida),
                        qtd_morta=int(qt_mortas),
                        operador=operador_final_object
                    )      

                    peca.save()
                    
                    Inspecao.objects.create(    
                        pecas_ordem_usinagem=peca_obj
                    )

                    # Envio silencioso ao ERP após confirmar a transação de finalização.
                    transaction.on_commit(
                        lambda peca_obj_id=peca_obj.id, user=request.user: _apontar_item_erp_usinagem_silencioso(peca_obj_id, user)
                    )

                    ordem.status_prioridade = 3
                elif status == 'interrompida':
                    novo_processo.motivo_interrupcao = MotivoInterrupcao.objects.get(nome=body['motivo'])
                    novo_processo.save()
                    ordem.status_prioridade = 2
                elif status == 'agua_prox_proc':
                    try:
                        ordem.maquina = get_object_or_404(Maquina, pk=int(body['maquina_nome']))
                        novo_processo.maquina=get_object_or_404(Maquina, pk=int(body['maquina_nome']))

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
                notificar_ordem(ordem)  # dispara o websocket

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
    # Filtra as ordens baseadas no status e no grupo da máquina
    ordens_queryset = Ordem.objects.filter(
        grupo_maquina='usinagem',
        status_atual='iniciada'
    )

    page = int(request.GET.get('page', 1))
    limit = int(request.GET.get('limit', 10))
    filtro_ordem = request.GET.get('ordem', '').strip()
    filtro_peca = request.GET.get('peca', '').strip()

    if filtro_ordem:
        ordens_queryset = ordens_queryset.filter(ordem=filtro_ordem, grupo_maquina='usinagem')
    if filtro_peca:
        ordens_queryset = ordens_queryset.filter(
            Q(ordem_pecas_usinagem__peca__codigo=filtro_peca) |
            Q(ordem_pecas_usinagem__peca__descricao__icontains=filtro_peca)
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
        for peca_ordem in ordem.ordem_pecas_usinagem.all():
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
    ordens_queryset = Ordem.objects.prefetch_related('processos', 'ordem_pecas_usinagem').filter(status_atual='interrompida', grupo_maquina='usinagem', excluida=False)

    usuario_tipo = Profile.objects.filter(user=request.user).values_list('tipo_acesso', flat=True).first()
    # Paginação (opcional)
    page = request.GET.get('page', 1)  # Obtém o número da página
    limit = request.GET.get('limit', 10)  # Define o limite padrão por página
    filtro_ordem = request.GET.get('ordem', '').strip()
    filtro_peca = request.GET.get('peca', '').strip()

    if filtro_ordem:
        ordens_queryset = ordens_queryset.filter(ordem=filtro_ordem, grupo_maquina='usinagem')
    if filtro_peca:
        ordens_queryset = ordens_queryset.filter(
            Q(ordem_pecas_usinagem__peca__codigo=filtro_peca) |
            Q(ordem_pecas_usinagem__peca__descricao__icontains=filtro_peca)
        )

    paginator = Paginator(ordens_queryset, limit)  # Aplica a paginação
    ordens_page = paginator.get_page(page)  # Obtém a página atual

    # Monta os dados para retorno
    data = []
    for ordem in ordens_page:
        # Obtém o último processo interrompido (caso tenha mais de um)
        ultimo_processo_interrompido = ordem.processos.filter(motivo_interrupcao__isnull=False).order_by('-data_inicio').first()

        # Obtém as peças associadas à ordem
        pecas_data = []
        for peca_ordem in ordem.ordem_pecas_usinagem.all():
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
            'motivo_interrupcao': ultimo_processo_interrompido.motivo_interrupcao.nome if ultimo_processo_interrompido and ultimo_processo_interrompido.motivo_interrupcao else None,
            'ultima_atualizacao': ordem.ultima_atualizacao,
            'pecas': pecas_data,  # Adiciona informações das peças
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
def get_ordens_ag_prox_proc(request):
    # Filtra as ordens com base no status 'agua_prox_proc' e prefetch da peça relacionada
    ordens_queryset = Ordem.objects.prefetch_related(
        'ordem_pecas_usinagem','processos'
    ).filter(grupo_maquina='usinagem', status_atual='agua_prox_proc', excluida=False)

    usuario_tipo = Profile.objects.filter(user=request.user).values_list('tipo_acesso', flat=True).first()
    # Paginação
    page = int(request.GET.get('page', 1))  # Obtém o número da página
    limit = int(request.GET.get('limit', 10))  # Define o limite padrão por página
    filtro_ordem = request.GET.get('ordem', '').strip()
    filtro_peca = request.GET.get('peca', '').strip()
    filtro_processo = request.GET.get('processo', '').strip()

    if filtro_ordem:
        ordens_queryset = ordens_queryset.filter(ordem=filtro_ordem, grupo_maquina='usinagem')
    if filtro_peca:
        ordens_queryset = ordens_queryset.filter(
            Q(ordem_pecas_usinagem__peca__codigo=filtro_peca) |
            Q(ordem_pecas_usinagem__peca__descricao__icontains=filtro_peca)
        )
    if filtro_processo:
        ordens_queryset = ordens_queryset.filter(
            maquina_id=filtro_processo
        )

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

        # Conta quantas vezes a ordem já teve 'agua_prox_proc'
        qtd_processo_atual = ordem.processos.filter(status='agua_prox_proc').count() + 1

        # Itera sobre todas as peças relacionadas
        for peca_ordem in ordem.ordem_pecas_usinagem.all():
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
            'maquina': ordem.maquina.nome,
            'maquina_id': ordem.maquina.id if ordem.maquina else None,
            'ultima_atualizacao': ordem.ultima_atualizacao,
            'processo_atual': qtd_processo_atual, 
            'totais': {
                'qtd_boa': total_qtd_boa,
                'qtd_planejada': total_qtd_planejada,
                'qtd_morta': total_qtd_morta
            },
            'pecas': pecas_data,  # Lista consolidada de peças
        })
    # Retorna os dados paginados como JSON
    return JsonResponse({
        'usuario_tipo_acesso': usuario_tipo,
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

def planejar_ordem_usinagem(request):

    if request.method == 'POST':
        criar_ordem_usinagem(request.POST)
        return JsonResponse({'message': 'Status atualizado com sucesso.'})

def api_apontamentos_peca(request):

    pecas_ordenadas = (
        PecasOrdem.objects.filter(operador__isnull=False, ordem__grupo_maquina='usinagem')
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
            "obs_operador": apontamento.ordem.obs_operador or "Sem observações",
            "operador": f"{apontamento.operador.matricula} - {apontamento.operador.nome}",
            "data": localtime(apontamento.data).strftime('%d/%m/%Y %H:%M'),
        })

    return JsonResponse(resultado, safe=False)


@login_required
def erp_apontamentos_usinagem(request):
    return render(request, "apontamento_usinagem/erp_apontamentos_usinagem.html")


@login_required
@require_GET
def api_erp_apontamentos_usinagem(request):
    page = max(int(request.GET.get('page', 1) or 1), 1)
    limit = int(request.GET.get('limit', 50) or 50)
    limit = min(max(limit, 10), 200)

    filtros = {
        'ordem': request.GET.get('ordem', '').strip(),
        'peca': request.GET.get('peca', '').strip(),
        'chave_apontamento': request.GET.get('chave_apontamento', '').strip(),
        'apontado': request.GET.get('apontado', '').strip().lower(),
        'resp_apontamento': request.GET.get('resp_apontamento', '').strip(),
        'data_apontamento_inicio': request.GET.get('data_apontamento_inicio', '').strip(),
        'data_apontamento_fim': request.GET.get('data_apontamento_fim', '').strip(),
        'data_producao_inicio': request.GET.get('data_producao_inicio', '').strip(),
        'data_producao_fim': request.GET.get('data_producao_fim', '').strip(),
    }

    subquery_ordem_apontada = (
        PecasOrdem.objects
        .filter(ordem_id=OuterRef('ordem_id'), apontado=True)
        .order_by('-data_apontamento', '-id')
    )

    queryset = (
        PecasOrdem.objects
        .filter(
            qtd_boa__gt=0,
            ordem__grupo_maquina='usinagem',
            data__date__gte=date(2026, 2, 23),
        )
        .select_related('ordem', 'ordem__maquina', 'peca', 'operador', 'resp_apontamento')
        .annotate(
            ordem_ja_apontada=Exists(subquery_ordem_apontada),
            ordem_item_apontado_id=Subquery(subquery_ordem_apontada.values('id')[:1]),
            ordem_tipo_apontamento=Subquery(subquery_ordem_apontada.values('tipo_apontamento')[:1]),
            ordem_data_apontamento_ref=Subquery(subquery_ordem_apontada.values('data_apontamento')[:1]),
            ordem_chave_apontamento_ref=Subquery(subquery_ordem_apontada.values('chave_apontamento')[:1]),
            ordem_resp_username_ref=Subquery(subquery_ordem_apontada.values('resp_apontamento__username')[:1]),
        )
        .order_by('-data_apontamento', '-id')
    )

    if filtros['ordem']:
        queryset = queryset.filter(ordem__ordem__icontains=filtros['ordem'])

    if filtros['peca']:
        queryset = queryset.filter(
            Q(peca__codigo__icontains=filtros['peca']) |
            Q(peca__descricao__icontains=filtros['peca'])
        )

    if filtros['chave_apontamento']:
        queryset = queryset.filter(chave_apontamento__icontains=filtros['chave_apontamento'])

    if filtros['resp_apontamento']:
        queryset = queryset.filter(
            Q(resp_apontamento__username__icontains=filtros['resp_apontamento']) |
            Q(resp_apontamento__first_name__icontains=filtros['resp_apontamento']) |
            Q(resp_apontamento__last_name__icontains=filtros['resp_apontamento'])
        )

    if filtros['apontado'] == 'true':
        queryset = queryset.filter(apontado=True)
    elif filtros['apontado'] == 'false':
        queryset = queryset.filter(apontado=False)

    data_apontamento_inicio = parse_date(filtros['data_apontamento_inicio']) if filtros['data_apontamento_inicio'] else None
    data_apontamento_fim = parse_date(filtros['data_apontamento_fim']) if filtros['data_apontamento_fim'] else None
    data_producao_inicio = parse_date(filtros['data_producao_inicio']) if filtros['data_producao_inicio'] else None
    data_producao_fim = parse_date(filtros['data_producao_fim']) if filtros['data_producao_fim'] else None

    if data_apontamento_inicio:
        queryset = queryset.filter(data_apontamento__date__gte=data_apontamento_inicio)
    if data_apontamento_fim:
        queryset = queryset.filter(data_apontamento__date__lte=data_apontamento_fim)
    if data_producao_inicio:
        queryset = queryset.filter(data__date__gte=data_producao_inicio)
    if data_producao_fim:
        queryset = queryset.filter(data__date__lte=data_producao_fim)

    paginator = Paginator(queryset, limit)
    pagina = paginator.get_page(page)

    itens = []
    for item in pagina.object_list:
        resp = item.resp_apontamento
        nome_resp = ''
        if resp:
            nome_resp = (resp.get_full_name() or resp.username).strip()

        itens.append({
            'id': item.id,
            'ordem_id': item.ordem_id,
            'ordem': item.ordem.ordem if item.ordem else '',
            'peca_codigo': item.peca.codigo if item.peca else '',
            'peca_descricao': item.peca.descricao if item.peca else '',
            'qtd_boa': item.qtd_boa,
            'qtd_morta': item.qtd_morta,
            'qtd_planejada': item.qtd_planejada,
            'maquina': item.ordem.maquina.nome if item.ordem and item.ordem.maquina else '',
            'operador': f"{item.operador.matricula} - {item.operador.nome}" if item.operador else '',
            'apontado': item.apontado,
            'tipo_apontamento': item.tipo_apontamento or '',
            'chave_apontamento': item.chave_apontamento or '',
            'erro_apontamento': item.erro_apontamento or '',
            'resp_apontamento': nome_resp,
            'resp_apontamento_username': resp.username if resp else '',
            'data_producao': localtime(item.data).strftime('%d/%m/%Y %H:%M') if item.data else '',
            'data_apontamento': localtime(item.data_apontamento).strftime('%d/%m/%Y %H:%M') if item.data_apontamento else '',
            'ordem_ja_apontada': bool(getattr(item, 'ordem_ja_apontada', False)),
            'ordem_item_apontado_id': getattr(item, 'ordem_item_apontado_id', None),
            'ordem_tipo_apontamento': getattr(item, 'ordem_tipo_apontamento', '') or '',
            'ordem_chave_apontamento': getattr(item, 'ordem_chave_apontamento_ref', '') or '',
            'ordem_resp_apontamento_username': getattr(item, 'ordem_resp_username_ref', '') or '',
            'ordem_data_apontamento': (
                localtime(item.ordem_data_apontamento_ref).strftime('%d/%m/%Y %H:%M')
                if getattr(item, 'ordem_data_apontamento_ref', None)
                else ''
            ),
        })

    return JsonResponse({
        'results': itens,
        'pagination': {
            'page': pagina.number,
            'page_size': limit,
            'total_items': paginator.count,
            'total_pages': paginator.num_pages,
            'has_next': pagina.has_next(),
            'has_previous': pagina.has_previous(),
        }
    })


@login_required
@require_POST
def api_erp_apontar_item_usinagem(request, pk):
    try:
        body = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        body = {}

    tipo_apontamento = (body.get('tipo_apontamento') or 'manual').strip().lower()
    if tipo_apontamento not in ('manual', 'api'):
        return JsonResponse({'status': 'error', 'message': 'tipo_apontamento inválido.'}, status=400)

    item = get_object_or_404(
        PecasOrdem.objects.select_related('ordem', 'peca'),
        pk=pk,
        ordem__grupo_maquina='usinagem'
    )

    item_ja_apontado_ordem = (
        PecasOrdem.objects
        .filter(ordem_id=item.ordem_id, apontado=True)
        .exclude(pk=item.pk)
        .select_related('resp_apontamento')
        .order_by('-data_apontamento', '-id')
        .first()
    )

    if item.apontado or item_ja_apontado_ordem:
        item_referencia = item if item.apontado else item_ja_apontado_ordem
        resp_ref = getattr(item_referencia, 'resp_apontamento', None)
        return JsonResponse(
            {
                'status': 'error',
                'message': 'Esta ordem já foi apontada e não pode ser apontada novamente.',
                'already_apontado': True,
                'detalhes': {
                    'item_id': item_referencia.id,
                    'ordem_id': item_referencia.ordem_id,
                    'tipo_apontamento': item_referencia.tipo_apontamento or '',
                    'data_apontamento': localtime(item_referencia.data_apontamento).strftime('%d/%m/%Y %H:%M') if item_referencia.data_apontamento else '',
                    'resp_apontamento': (resp_ref.get_full_name() or resp_ref.username) if resp_ref else '',
                    'chave_apontamento': item_referencia.chave_apontamento or '',
                }
            },
            status=409
        )

    if tipo_apontamento == 'api' and (item.qtd_morta or 0) > 0:
        msg_qtd_morta = (
            'Apontamento via API bloqueado automaticamente: item com qtd_morta > 0. '
            'A funcionalidade de desvio precisa ser ajustada na API.'
        )
        item.erro_apontamento = msg_qtd_morta
        item.tipo_apontamento = 'api'
        item.resp_apontamento = request.user
        item.save(update_fields=['erro_apontamento', 'tipo_apontamento', 'resp_apontamento'])
        return JsonResponse(
            {
                'status': 'error',
                'message': 'Apontamento via API bloqueado para item com qtd_morta.',
                'description': msg_qtd_morta,
            },
            status=422
        )

    payload_integracao = None
    if tipo_apontamento == 'api':
        payload_integracao = {
            "id": "Apontamento 1",
            "data": localtime(now()).strftime('%d/%m/%Y'),
            "pessoa": "4357",
            "recurso": str(item.peca.codigo if item.peca else ""),
            "processo": "S Usinagem",
            "produzido": item.qtd_boa,
            "observacao": str(item.ordem_id),
        }

        try:
            if os.getenv("DJANGO_ENV") == "dev":
                return
            else:
                response_integracao = requests.post(
                    "https://cemag.innovaro.com.br/api/integracao/v1/producao/apontar",
                    json=payload_integracao,
                    auth=("luan araujo", "luanaraujo7"),
                    timeout=20,
                )
        except requests.RequestException as exc:
            return JsonResponse(
                {
                    'status': 'error',
                    'message': f'Falha de comunicação com API ERP: {exc}',
                    'payload_enviado': payload_integracao,
                },
                status=502
            )

        resposta_api_json = None
        try:
            resposta_api_json = response_integracao.json()
        except ValueError:
            resposta_api_json = None

        if not response_integracao.ok:
            descricao_erro = ''
            if isinstance(resposta_api_json, dict):
                descricao_erro = str(resposta_api_json.get('description') or '')

            retorno_texto = ''
            try:
                retorno_texto = response_integracao.text[:500]
            except Exception:
                retorno_texto = 'Sem detalhes'

            item.erro_apontamento = descricao_erro or retorno_texto
            item.tipo_apontamento = 'api'
            item.resp_apontamento = request.user
            item.save(update_fields=['erro_apontamento', 'tipo_apontamento', 'resp_apontamento'])

            return JsonResponse(
                {
                    'status': 'error',
                    'message': f'API ERP retornou status {response_integracao.status_code}.',
                    'payload_enviado': payload_integracao,
                    'description': descricao_erro,
                    'retorno_api': retorno_texto,
                },
                status=502
            )

        if isinstance(resposta_api_json, dict):
            status_erp = str(resposta_api_json.get('status') or '').strip()

            if status_erp.lower() == 'error':
                descricao_erro = str(resposta_api_json.get('description') or 'Erro retornado pela API ERP.')
                item.erro_apontamento = descricao_erro
                item.tipo_apontamento = 'api'
                item.resp_apontamento = request.user
                item.save(update_fields=['erro_apontamento', 'tipo_apontamento', 'resp_apontamento'])

                return JsonResponse(
                    {
                        'status': 'error',
                        'message': 'API ERP retornou erro de negócio.',
                        'description': descricao_erro,
                        'payload_enviado': payload_integracao,
                        'retorno_api': resposta_api_json,
                    },
                    status=422
                )

            if status_erp.lower() == 'success':
                item.chave_apontamento = str(resposta_api_json.get('chaveProducao') or '')
                item.erro_apontamento = None
            else:
                item.erro_apontamento = str(resposta_api_json)
                item.tipo_apontamento = 'api'
                item.resp_apontamento = request.user
                item.save(update_fields=['erro_apontamento', 'tipo_apontamento', 'resp_apontamento'])
                return JsonResponse(
                    {
                        'status': 'error',
                        'message': 'Resposta da API ERP em formato inesperado.',
                        'payload_enviado': payload_integracao,
                        'retorno_api': resposta_api_json,
                    },
                    status=502
                )
        else:
            item.erro_apontamento = (response_integracao.text or '')[:2000]
            item.tipo_apontamento = 'api'
            item.resp_apontamento = request.user
            item.save(update_fields=['erro_apontamento', 'tipo_apontamento', 'resp_apontamento'])
            return JsonResponse(
                {
                    'status': 'error',
                    'message': 'API ERP não retornou JSON válido.',
                    'payload_enviado': payload_integracao,
                    'retorno_api': (response_integracao.text or '')[:500],
                },
                status=502
            )

    item.apontado = True
    item.data_apontamento = now()
    item.tipo_apontamento = tipo_apontamento
    item.resp_apontamento = request.user
    update_fields = ['apontado', 'data_apontamento', 'tipo_apontamento', 'resp_apontamento']
    if tipo_apontamento == 'api':
        update_fields.extend(['chave_apontamento', 'erro_apontamento'])
    item.save(update_fields=update_fields)

    return JsonResponse({
        'status': 'success',
        'message': 'Apontamento confirmado com sucesso.',
        'item_id': item.id,
        'apontado': item.apontado,
        'tipo_apontamento': item.tipo_apontamento,
        'data_apontamento': localtime(item.data_apontamento).strftime('%d/%m/%Y %H:%M'),
        'resp_apontamento': request.user.get_full_name() or request.user.username,
        'chave_apontamento': item.chave_apontamento or '',
        'erro_apontamento': item.erro_apontamento or '',
        'payload_enviado': payload_integracao if tipo_apontamento == 'api' else None,
    })

def buscar_processos(request):

    processos = Maquina.objects.filter(setor__nome='usinagem', tipo='processo').values('id','nome')

    return JsonResponse({"processos":list(processos)})

def api_ordens_finalizadas(request):
    
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT 
                o.ordem AS ordem,
                m.nome AS maquina,
                p.codigo AS peca,
                p.descricao AS descricao,
                ope.qtd_planejada AS total_planejada,
                ope.qtd_boa - ope.qtd_morta as total_produzido,
                TO_CHAR(o.data_programacao, 'DD/MM/YYYY HH24:MI') AS data_programacao,
                TO_CHAR(o.ultima_atualizacao AT TIME ZONE 'America/Sao_Paulo', 'DD/MM/YYYY HH24:MI') AS data_finalizacao,
                CONCAT(f.matricula, ' - ', f.nome) AS operador,
                o.obs_operador AS obs,
                ope.qtd_morta AS total_morta
            FROM apontamento_v2.core_ordem o
            JOIN apontamento_v2.apontamento_usinagem_pecasordem ope ON ope.ordem_id = o.id
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

def retornar_processo(request):
    if request.method != 'POST':
        return JsonResponse(
            {'status': 'error', 'message': 'Método não permitido'}, 
            status=405
        )

    try:
        data = json.loads(request.body)
        ordem_id = data.get('ordemId')
        
        if not ordem_id:
            return JsonResponse(
                {'status': 'error', 'message': 'ordemId não fornecido'}, 
                status=400
            )

        with transaction.atomic():
            ordem_process = OrdemProcesso.objects.filter(ordem_id=ordem_id)

            ordem_process.delete()
            
            updated_count = Ordem.objects.filter(id=ordem_id).update(
                maquina=None,
                status_atual='aguardando_iniciar'
            )
            
            if updated_count == 0:
                raise Ordem.DoesNotExist(f"Ordem com id {ordem_id} não encontrada")

        return JsonResponse({
            'status': 'success', 
            'message': 'Processo retornado com sucesso'
        })

    except json.JSONDecodeError:
        return JsonResponse(
            {'status': 'error', 'message': 'JSON inválido'}, 
            status=400
        )
    except Ordem.DoesNotExist:
        return JsonResponse(
            {'status': 'error', 'message': 'Ordem não encontrada'}, 
            status=404
        )
    except Exception as e:
        return JsonResponse(
            {'status': 'error', 'message': str(e)}, 
            status=500
        )
