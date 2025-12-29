from django.http import JsonResponse
from django.views import View
from django.conf import settings
from django.db import transaction, connection
from django.shortcuts import get_object_or_404, render
from django.core.paginator import Paginator, EmptyPage
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_exempt
from django.utils.timezone import now,localtime
from django.db.models import Q, Count, Sum, F, Max
from django.forms.models import model_to_dict
from django.contrib.auth.decorators import login_required

from .models import Ordem,PecasOrdem
from core.models import OrdemProcesso,PropriedadesOrdem,MaquinaParada, Profile
from cadastro.models import Maquina, MotivoInterrupcao, Operador, Espessura, MotivoMaquinaParada, MotivoExclusao
from .utils import *
from .utils_dashboard import *
from apontamento_serra.utils import formatar_timedelta
from core.utils import notificar_ordem

import pandas as pd
import os
import tempfile
import re
import json
import xml.etree.ElementTree as ET
from urllib.parse import unquote
from datetime import datetime, time, timedelta
from functools import reduce
from collections import defaultdict

from datetime import date
from functools import reduce
from urllib.parse import unquote
import re, json

# Caminho para a pasta temporária dentro do projeto
TEMP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'temp')

# Certifique-se de que a pasta existe
os.makedirs(TEMP_DIR, exist_ok=True)

def extrair_numeracao(nome_arquivo):
    match = re.search(r"(?i)OP\s*(\d+)", nome_arquivo)  # Permite espaços opcionais entre OP e o número
    if match:
        return match.group(1)
    return None

def planejamento(request):

    motivos = MotivoInterrupcao.objects.filter(setor__nome='corte', visivel=True)
    operadores = Operador.objects.filter(setor__nome='corte')
    espessuras = Espessura.objects.all()
    motivos_maquina_parada = MotivoMaquinaParada.objects.filter(setor__nome='serra').exclude(nome='Finalizada parcial')
    motivos_exclusao = MotivoExclusao.objects.filter(setor__nome='corte')

    return render(request, 'apontamento_corte/planejamento.html', {'motivos':motivos,'operadores':operadores,'espessuras':espessuras,'motivos_maquina_parada':motivos_maquina_parada,'motivos_exclusao':motivos_exclusao})

def get_pecas_ordem(request, pk_ordem):
    try:
        # Busca a ordem com os relacionamentos necessários
        ordem = Ordem.objects.prefetch_related('ordem_pecas_corte', 'propriedade').get(pk=pk_ordem)

        # Propriedades da ordem
        propriedades = {
            'descricao_mp': ordem.propriedade.descricao_mp if ordem.propriedade else None,
            'espessura': ordem.propriedade.espessura if ordem.propriedade else None,
            'quantidade': ordem.propriedade.quantidade if ordem.propriedade else None,
            'tipo_chapa': ordem.propriedade.get_tipo_chapa_display() if ordem.propriedade else None,
            'aproveitamento': ordem.propriedade.aproveitamento if ordem.propriedade else None,
        }

        # Peças relacionadas à ordem
        pecas = [
            {'peca': peca.peca, 'quantidade': peca.qtd_planejada if peca.qtd_boa == 0 else  peca.qtd_boa}
            for peca in ordem.ordem_pecas_corte.all()
        ]

        return JsonResponse({'pecas': pecas, 'propriedades': propriedades})

    except Ordem.DoesNotExist:
        return JsonResponse({'error': 'Ordem não encontrada.'}, status=404)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)    

def get_ordens_criadas(request):

    # Captura os parâmetros de filtro
    filtro_ordem = request.GET.get('ordem', '')
    filtro_maquina = request.GET.get('maquina', '').strip()
    filtro_status = request.GET.get('status', '')
    filtro_peca = request.GET.get('peca', '').strip()
    filtro_turno = request.GET.get('turno', '')
    filtro_data_programada = request.GET.get('data-programada', '').strip()

    page = int(request.GET.get('page', 1))
    limit = int(request.GET.get('limit', 10))

    # Filtra as ordens com base nos parâmetros
    ordens_queryset = Ordem.objects.prefetch_related('ordem_pecas_corte').select_related('propriedade').filter(grupo_maquina__in=['plasma', 'laser_1', 'laser_2', 'laser_3']).order_by('-ultima_atualizacao', '-status_prioridade')

    if filtro_ordem:
        if '.' in filtro_ordem or 'dup' in filtro_ordem:
            ordens_queryset = ordens_queryset.filter(ordem_duplicada__contains=filtro_ordem)
        else:
            ordens_queryset = ordens_queryset.filter(ordem=int(filtro_ordem))

    if filtro_maquina:
        ordens_queryset = ordens_queryset.filter(grupo_maquina__icontains=filtro_maquina)
    if filtro_status:
        ordens_queryset = ordens_queryset.filter(status_atual=filtro_status)
    if filtro_peca:
        ordens_queryset = ordens_queryset.filter(ordem_pecas_corte__peca__icontains=filtro_peca)
    if filtro_turno:
        if filtro_turno == 'turnoA':
            # Filtra entre 07:00 e 18:00
            ordens_queryset = ordens_queryset.filter(
                ultima_atualizacao__time__gte=time(7, 0),
                ultima_atualizacao__time__lte=time(18, 0),
            )
        elif filtro_turno == 'turnoB':
            # Filtra entre 21:00 e 07:00 do dia seguinte
            ordens_queryset = ordens_queryset.filter(
                Q(ultima_atualizacao__time__gte=time(21, 0)) |
                Q(ultima_atualizacao__time__lte=time(7, 0))
            )
    if filtro_data_programada:
        ordens_queryset = ordens_queryset.filter(data_programacao=filtro_data_programada)

    # Paginação
    paginator = Paginator(ordens_queryset, limit)
    try:
        ordens_page = paginator.page(page)
    except EmptyPage:
        return JsonResponse({'ordens': []})

    # Monta os dados
    data = [{
        'id':ordem.pk,  
        'ordem': ordem.ordem if ordem.ordem else ordem.ordem_duplicada,
        'grupo_maquina': ordem.get_grupo_maquina_display(),
        'data_criacao': localtime(ordem.data_criacao).strftime('%d/%m/%Y %H:%M'),
        'data_programacao': ordem.data_programacao.strftime('%d/%m/%Y'),
        'obs': ordem.obs,
        'status_atual': ordem.status_atual,
        'maquina': ordem.maquina.nome if ordem.maquina else None,
        'maquina_id': ordem.maquina.id if ordem.maquina else None,
        'sequenciada': ordem.sequenciada,
        'propriedade': {
            'descricao_mp': ordem.propriedade.descricao_mp if ordem.propriedade.descricao_mp else None,
            'quantidade': ordem.propriedade.quantidade if ordem.propriedade.quantidade else None,
            'tipo_chapa': ordem.propriedade.get_tipo_chapa_display() if ordem.propriedade.tipo_chapa else None,
            'aproveitamento': ordem.propriedade.aproveitamento if ordem.propriedade.aproveitamento else None,
            'retalho': 'Sim' if ordem.propriedade.retalho else None,
        },
        'ultima_atualizacao': localtime(ordem.ultima_atualizacao).strftime('%d/%m/%Y %H:%M') if ordem.status_atual == 'finalizada' else None,
        'tempo_estimado': ordem.tempo_estimado if ordem.tempo_estimado else 'Não foi possivel calcular',
    } for ordem in ordens_page]

    return JsonResponse({'ordens': data})

def atualizar_status_ordem(request):
    if request.method == 'PATCH':
        try:
            with transaction.atomic():
                # Parse do corpo da requisição
                body = json.loads(request.body)
                print(body)

                status = body['status']
                ordem_id = body['ordem_id']
                comentario_extra = body['comentario_extra'] if 'comentario_extra' in body else ''
                # grupo_maquina = body['grupo_maquina'].lower()
                pecas_geral = body.get('pecas_mortas', [])
                qtd_chapas = body.get('qtdChapas', None)
                maquina_request = body.get('maquina')
                tipo_chapa = body.get('tipoChapa')
                finalizar_parcial = bool(body.get('finalizar_parcial', False))

                if maquina_request:
                    maquina_nome = get_object_or_404(Maquina, pk=int(maquina_request))

                # Obtém a ordem
                ordem = Ordem.objects.get(pk=ordem_id)#, grupo_maquina=grupo_maquina)
                
                # Validações básicas
                if ordem.status_atual == status:
                    return JsonResponse({'error': f'Essa ordem ja está {status}. Atualize a página.'}, status=400)

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
                    # Finaliza paradas da máquina se necessário
                    maquinas_paradas = MaquinaParada.objects.filter(maquina=maquina_nome, data_fim__isnull=True)
                    for parada in maquinas_paradas:
                        parada.data_fim = now()
                        parada.save()

                    ordem.maquina = maquina_nome
                    ordem.status_prioridade = 1
                elif status == 'finalizada':
                    propriedade_atual = ordem.propriedade
                    quantidade_chapas_original = propriedade_atual.quantidade if propriedade_atual else 0
                    tipo_chapa_original = propriedade_atual.tipo_chapa if propriedade_atual else None

                    # Verifica se a quantidade de chapas mudaram
                    if int(qtd_chapas) != ordem.propriedade.quantidade:
                        ordem.propriedade.quantidade = int(qtd_chapas)
                        ordem.propriedade.save()
                    if tipo_chapa is not None and tipo_chapa != ordem.propriedade.tipo_chapa:
                        ordem.propriedade.tipo_chapa = tipo_chapa
                        ordem.propriedade.save()

                    pecas_restantes = []
                    for peca in pecas_geral:
                        peca_id = peca.get('peca')
                        planejada = peca.get('planejadas')
                        mortas = peca.get('mortas', 0)

                        peca = PecasOrdem.objects.get(ordem=ordem, peca=peca_id)
                        qtd_planejada_original = peca.qtd_planejada
                        peca.qtd_boa = planejada - mortas
                        peca.qtd_morta = mortas

                        peca.save()

                        if finalizar_parcial:
                            restante = max(qtd_planejada_original - planejada, 0)
                            if restante > 0:
                                pecas_restantes.append({"peca": peca.peca, "quantidade": restante})

                    ordem.status_prioridade = 3
                    ordem.operador_final = get_object_or_404(Operador, pk=body.get('operadorFinal'))
                    ordem.obs_operador = body.get('obsFinal')

                    nova_ordem = None
                    if finalizar_parcial and pecas_restantes:
                        quantidade_chapas_usada = float(qtd_chapas) if qtd_chapas is not None else 0
                        quantidade_chapas_restante = max(quantidade_chapas_original - quantidade_chapas_usada, 0)

                        ordem_base = ordem.ordem or ordem.ordem_duplicada
                        if ordem_base:
                            ordem_base = re.sub(r'^continuacao#', '', str(ordem_base))
                            ordem_base = re.sub(r'\.\d+$', '', ordem_base)
                        continuacao_prefixo = f"continuacao#{ordem_base}"
                        continuacoes_existentes = Ordem.objects.filter(
                            ordem_duplicada__startswith=f"{continuacao_prefixo}."
                        ).count()
                        nova_ordem = Ordem.objects.create(
                            ordem=None,
                            ordem_duplicada=f"{continuacao_prefixo}.{continuacoes_existentes + 1}",
                            obs=f"Saldo da ordem #{ordem_base}",
                            grupo_maquina=ordem.grupo_maquina,
                            data_programacao=now().date(),
                            status_atual='aguardando_iniciar',
                            maquina=ordem.maquina,
                            tempo_estimado=ordem.tempo_estimado,
                        )

                        PropriedadesOrdem.objects.create(
                            ordem=nova_ordem,
                            descricao_mp=propriedade_atual.descricao_mp if propriedade_atual else None,
                            tamanho=propriedade_atual.tamanho if propriedade_atual else None,
                            espessura=propriedade_atual.espessura if propriedade_atual else None,
                            quantidade=quantidade_chapas_restante,
                            aproveitamento=propriedade_atual.aproveitamento if propriedade_atual else None,
                            tipo_chapa=tipo_chapa if tipo_chapa is not None else tipo_chapa_original,
                            retalho=propriedade_atual.retalho if propriedade_atual else False,
                        )

                        for peca_restante in pecas_restantes:
                            PecasOrdem.objects.create(
                                ordem=nova_ordem,
                                peca=peca_restante["peca"],
                                qtd_planejada=peca_restante["quantidade"],
                            )
                elif status == 'interrompida':
                    novo_processo.motivo_interrupcao = MotivoInterrupcao.objects.get(nome=body['motivo'])
                    novo_processo.comentario_extra = comentario_extra
                    novo_processo.save()
                    ordem.status_prioridade = 2

                ordem.save()
                notificar_ordem(ordem)

                response_payload = {
                    'message': 'Status atualizado com sucesso.',
                    'ordem_id': ordem.id,
                    'status': novo_processo.status,
                    'data_inicio': novo_processo.data_inicio,
                    'maquina_id': ordem.maquina.id if ordem.maquina else None,
                }
                if status == 'finalizada' and 'nova_ordem' in locals() and nova_ordem:
                    response_payload['nova_ordem_id'] = nova_ordem.id
                    response_payload['nova_ordem_numero'] = nova_ordem.ordem or nova_ordem.ordem_duplicada

                return JsonResponse(response_payload)

        except Ordem.DoesNotExist:
            return JsonResponse({'error': 'Ordem não encontrada.'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Método não permitido.'}, status=405)

@require_GET
def get_ordens_iniciadas(request):
    usuario_tipo = Profile.objects.filter(user=request.user).values_list('tipo_acesso', flat=True).first()

    # Filtra as ordens com base no status 'iniciada'
    ordens_queryset = Ordem.objects.prefetch_related('ordem_pecas_corte').select_related('propriedade') \
        .filter(status_atual='iniciada', grupo_maquina__in=['plasma','laser_1','laser_2', 'laser_3'])

    # Paginação (opcional)
    page = request.GET.get('page', 1)  # Obtém o número da página
    limit = request.GET.get('limit', 10)  # Define o limite padrão por página
    paginator = Paginator(ordens_queryset, limit)  # Aplica a paginação
    ordens_page = paginator.get_page(page)  # Obtém a página atual

    # Monta os dados para retorno
    data = [{
        'id': ordem.id,
        'ordem': ordem.ordem if ordem.ordem else ordem.ordem_duplicada,
        'grupo_maquina': ordem.get_grupo_maquina_display(),
        'data_criacao': ordem.data_criacao.strftime('%d/%m/%Y %H:%M'),
        'obs': ordem.obs,
        'status_atual': ordem.status_atual,
        'maquina': ordem.maquina.nome if ordem.maquina else None,
        'maquina_id': ordem.maquina.id if ordem.maquina else None,
        'ultima_atualizacao': ordem.ultima_atualizacao,
        'propriedade': {
            'descricao_mp': ordem.propriedade.descricao_mp if ordem.propriedade else None,
            'espessura': ordem.propriedade.espessura if ordem.propriedade else None,
            'quantidade': ordem.propriedade.quantidade if ordem.propriedade else None,
            'tipo_chapa': ordem.propriedade.get_tipo_chapa_display() if ordem.propriedade else None,
            'aproveitamento': ordem.propriedade.aproveitamento if ordem.propriedade else None,
        }
    } for ordem in ordens_page]

    # Retorna os dados paginados como JSON
    return JsonResponse({
        'usuario_tipo_acesso':usuario_tipo,
        'ordens': data,
        'page': ordens_page.number,
        'total_pages': paginator.num_pages,
        'total_ordens': paginator.count
    })

@require_GET
def get_ordens_interrompidas(request):

    usuario_tipo = Profile.objects.filter(user=request.user).values_list('tipo_acesso', flat=True).first()

    # Filtra as ordens com base no status 'interrompida'
    ordens_queryset = Ordem.objects.prefetch_related('processos', 'ordem_pecas_corte').select_related('propriedade') \
        .filter(status_atual='interrompida', grupo_maquina__in=['plasma','laser_1','laser_2','laser_3'])

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

        data.append({
            'id': ordem.id,
            'ordem': ordem.ordem if ordem.ordem else ordem.ordem_duplicada,
            'grupo_maquina': ordem.get_grupo_maquina_display(),
            'data_criacao': ordem.data_criacao.strftime('%d/%m/%Y %H:%M'),
            'obs': ordem.obs,
            'status_atual': ordem.status_atual,
            'maquina': ordem.maquina.nome if ordem.maquina else None,
            'maquina_id': ordem.maquina.id if ordem.maquina else None,
            'motivo_interrupcao': ultimo_processo_interrompido.motivo_interrupcao.nome if ultimo_processo_interrompido and ultimo_processo_interrompido.motivo_interrupcao else None,
            'comentario_extra': ultimo_processo_interrompido.comentario_extra if ultimo_processo_interrompido else None,
            'ultima_atualizacao': ordem.ultima_atualizacao,
            'propriedade': {
                'descricao_mp': ordem.propriedade.descricao_mp if ordem.propriedade else None,
                'espessura': ordem.propriedade.espessura if ordem.propriedade else None,
                'quantidade': ordem.propriedade.quantidade if ordem.propriedade else None,
                'tipo_chapa': ordem.propriedade.get_tipo_chapa_display() if ordem.propriedade else None,
                'aproveitamento': ordem.propriedade.aproveitamento if ordem.propriedade else None,
            }
        })

    # Retorna os dados paginados como JSON
    return JsonResponse({
        'usuario_tipo_acesso':usuario_tipo,
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
    pecas_query = PecasOrdem.objects.values_list('peca', flat=True).distinct()  # Apenas o campo `peca`, eliminando duplicatas
    if search:
        pecas_query = pecas_query.filter(peca__icontains=search).order_by('peca')

    # Paginação
    paginator = Paginator(pecas_query, per_page)
    pecas_page = paginator.get_page(page)

    # Monta os resultados paginados no formato esperado pelo Select2
    data = {
        'results': [
            {'id': peca, 'text': peca} for peca in pecas_page  # Usa a string como `id` e `text`
        ],
        'pagination': {
            'more': pecas_page.has_next()  # Se há mais páginas
        },
    }

    return JsonResponse(data)

def filtrar_ordens(request):
    pecas_ids = request.GET.getlist("pecas")  # Lista de IDs das peças selecionadas
    maquina = request.GET.get("maquina", "")  # Máquina filtrada (se existir)

    # Filtra as ordens com base nas peças selecionadas
    ordens = PecasOrdem.objects.all()

    if maquina:
        ordens = ordens.filter(ordem__maquina=maquina)
    if pecas_ids:
        ordens = ordens.filter(peca__in=pecas_ids)

    # Monta os resultados com os dados relevantes
    resultados = [
        {
            "id": ordem.id,
            "mp": ordem.ordem.propriedade.descricao_mp if ordem.ordem.propriedade else "Sem MP",  # Acessa a propriedade corretamente
            "peca": ordem.peca.codigo,
            "quantidade": ordem.qtd_planejada,
        }
        for ordem in ordens
    ]

    return JsonResponse({"ordens": resultados})

def get_ordens_criadas_duplicar_ordem(request):
    #  Captura os parâmetros da requisição
    pecas = request.GET.get('pecas', '')
    pecas = [unquote(p) for p in pecas.split('|')] if pecas else []
    pecas = [re.match(r'\d+', p).group() for p in pecas if re.match(r'\d+', p)]

    maquina = unquote(request.GET.get('maquina', ''))
    ordem = unquote(request.GET.get('ordem', ''))

    codigos = [re.match(r'\d+', p).group() for p in pecas if re.match(r'\d+', p)]
    codigos_unicos = list(set(pecas))

    dataCriacao = request.GET.get('dataCriacao','')

    page = int(request.GET.get('page', 1))
    limit = int(request.GET.get('limit', 10))
    draw = int(request.GET.get('draw', 1))

    # NOVOS PARÂMETROS (acréscimo)
    modo = request.GET.get('modo', 'all')  # 'all' | 'prioritize' | 'qty'
    priorizar_raw = unquote(request.GET.get('priorizar', '')).strip()
    priorizar = re.match(r'\d+', priorizar_raw).group() if re.match(r'\d+', priorizar_raw) else ''

    qtymap_str = request.GET.get('qtymap', '')
    try:
        qtymap = json.loads(unquote(qtymap_str)) if qtymap_str else {}
    except Exception:
        qtymap = {}
    # normaliza chaves de qtymap para manter só dígitos
    qtymap = {
        (re.match(r'\d+', k).group() if re.match(r'\d+', k) else k): v
        for k, v in qtymap.items()
        if (isinstance(v, (int, float)) and v >= 0)
    }

    #  Define a Query Base
    ordens_queryset = (
        Ordem.objects.filter(grupo_maquina__in=['plasma', 'laser_1', 'laser_2','laser_3'], duplicada=False, excluida=False)
        .prefetch_related('ordem_pecas_corte')  # Evita queries repetidas para peças
        .select_related('propriedade')          # Carrega a propriedade diretamente
        .order_by('-propriedade__aproveitamento')
    )

    # otimização do Filtro de Peças (comportamento existente)
    if codigos_unicos:
        filtros = reduce(
            lambda acc, c: acc | Q(ordem_pecas_corte__peca__startswith=c),
            codigos_unicos[1:],
            Q(ordem_pecas_corte__peca__startswith=codigos_unicos[0])
        )

        ordens_queryset = ordens_queryset.filter(filtros).annotate(
            pecas_encontradas=Count(
                'ordem_pecas_corte__peca',
                filter=Q(ordem_pecas_corte__qtd_planejada__gt=0) & filtros,
                distinct=True
            )
        ).filter(
            pecas_encontradas=len(codigos_unicos)
        )

    # Filtra Máquina e Ordem se necessário (existente)
    if maquina:
        ordens_queryset = ordens_queryset.filter(grupo_maquina=maquina)
    if ordem:
        ordens_queryset = ordens_queryset.filter(ordem=ordem)

    # Filtra Data Criação (existente)
    if dataCriacao:
        ordens_queryset = ordens_queryset.filter(data_criacao__date=date.fromisoformat(dataCriacao))

    # ========= ACRÉSCIMOS DE LÓGICA (sem desfazer o que existe) =========

    # Para priorização e qty precisamos de anotações de quantidade por peça
    # Monta o conjunto de "códigos de interesse" conforme o modo
    codigos_interesse = set(codigos_unicos)
    if modo == 'qty' and qtymap:
        codigos_interesse |= set(qtymap.keys())
    if modo == 'prioritize' and priorizar:
        codigos_interesse |= {priorizar}

    # Cria anotações dinâmicas por peça (Sum filtrado por prefixo do código da peça)
    # Ex.: q_12345 = SUM(qtd_planejada WHERE peca startswith '12345')
    if codigos_interesse:
        annotations = {}
        for c in codigos_interesse:
            key = f"q_{c}"
            annotations[key] = Sum(
                'ordem_pecas_corte__qtd_planejada',
                filter=Q(ordem_pecas_corte__peca__startswith=c)
            )
        ordens_queryset = ordens_queryset.annotate(**annotations)

    # (1) modo PRIORITIZE: priorizar peça -> a peça priorizada deve ter a MAIOR quantidade
    #    Estratégia: exigir q_priorizar >= q_outros para cada outro código relevante.
    if modo == 'prioritize' and priorizar:
        prio_key = f"q_{priorizar}"
        # Garante que existe a anotação da priorizada
        if codigos_interesse and prio_key in ordens_queryset.query.annotations:
            for c in codigos_interesse:
                if c == priorizar:
                    continue
                other_key = f"q_{c}"
                # só compara se a outra anotação também existe
                if other_key in ordens_queryset.query.annotations:
                    ordens_queryset = ordens_queryset.filter(
                        Q(**{f"{prio_key}__gte": F(other_key)}) | Q(**{other_key: None})
                    )
            # também assegura que a priorizada exista (>0) para fazer sentido
            ordens_queryset = ordens_queryset.filter(**{f"{prio_key}__gt": 0})

    # (2) modo QTY: qtymap = { 'CODPECA': quantidade_minima } -> exigir q_cod >= quantidade
    if modo == 'qty' and qtymap:
        for c, req in qtymap.items():
            key = f"q_{c}"
            # se a anotação não existir, ainda assim o filtro abaixo retornará vazio
            ordens_queryset = ordens_queryset.filter(**{f"{key}__gte": req})

    # =====================================================================

    # Contagem de Registros para Paginação (existente)
    records_filtered = ordens_queryset.count()

    # Paginação eficiente (existente)
    paginator = Paginator(ordens_queryset, limit)
    try:
        ordens_page = paginator.page(page)
    except EmptyPage:
        return JsonResponse({'draw': draw, 'recordsTotal': records_filtered, 'recordsFiltered': records_filtered, 'data': []})

    # Otimização da Serialização dos Dados (existente)
    data = [
        {
            'id': ordem.pk,
            'ordem': ordem.ordem,
            'grupo_maquina': ordem.get_grupo_maquina_display(),
            'data_criacao': localtime(ordem.data_criacao).strftime('%d/%m/%Y %H:%M'),
            'obs': ordem.obs,
            'status_atual': ordem.status_atual,
            'aproveitamento': round(ordem.propriedade.aproveitamento, 5) if ordem.propriedade else None,
            'propriedade': {
                'descricao_mp': ordem.propriedade.descricao_mp if ordem.propriedade else None,
                'quantidade': ordem.propriedade.quantidade if ordem.propriedade else None,
                'tipo_chapa': ordem.propriedade.get_tipo_chapa_display() if ordem.propriedade else None,
                'aproveitamento': round(ordem.propriedade.aproveitamento, 5) if ordem.propriedade else None,
                'retalho': 'Sim' if ordem.propriedade and ordem.propriedade.retalho else None,
            }
        } for ordem in ordens_page
    ]

    #  Ordena os dados com base no aproveitamento corrigido (existente)
    data.sort(key=lambda x: x['aproveitamento'], reverse=True)

    return JsonResponse({
        'draw': draw,
        'recordsTotal': records_filtered,
        'recordsFiltered': records_filtered,
        'data': data
    })

def get_pecas_ordem_duplicar_ordem(request, pk_ordem):
    try:
        # Busca a ordem com os relacionamentos necessários
        ordem = Ordem.objects.prefetch_related('ordem_pecas_corte').select_related('propriedade').get(pk=pk_ordem)

        espessuras_distintas = PropriedadesOrdem.objects.exclude(
            espessura__isnull=True
        ).exclude(
            espessura__exact=''
        ).values_list(
            'espessura', flat=True
        ).distinct().order_by('espessura')
        
        valores_remover = {'nan', 'Selecione', ''}
        espessuras = [
            esp for esp in espessuras_distintas 
            if str(esp) not in valores_remover and esp is not None
        ]

        tipos_chapas = [tipo[1] for tipo in PropriedadesOrdem.TIPO_CHAPA_CHOICES]

        # Propriedades da ordem
        propriedades = {
            'descricao_mp': ordem.propriedade.descricao_mp if ordem.propriedade else None,
            'espessura': ordem.propriedade.espessura if ordem.propriedade else None,
            'quantidade': ordem.propriedade.quantidade if ordem.propriedade else None,
            'tipo_chapa': ordem.propriedade.get_tipo_chapa_display() if ordem.propriedade else None,
            'aproveitamento': ordem.propriedade.aproveitamento if ordem.propriedade else None,
            'maquina': ordem.grupo_maquina,
            'ordem': ordem.ordem,
        }

        # Peças relacionadas à ordem
        pecas = [
            {'peca': peca.peca, 'quantidade': peca.qtd_planejada}
            for peca in ordem.ordem_pecas_corte.all()
            if peca.qtd_planejada > 0
        ]

        return JsonResponse({'pecas': pecas, 'propriedades': propriedades, 
                             'espessuras': espessuras, 'tipos_chapas':tipos_chapas})

    except Ordem.DoesNotExist:
        return JsonResponse({'error': 'Ordem não encontrada.'}, status=404)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)    

def excluir_op_padrao(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)
    
    try:
        # Parse do JSON do corpo da requisição
        data = json.loads(request.body)
        ordem_id = data.get('ordem_id')
        
        if not ordem_id:
            return JsonResponse({'error': 'ordem_id não fornecido'}, status=400)
        
        # Busca a ordem no banco de dados
        try:
            ordem = Ordem.objects.get(pk=ordem_id)
        except Ordem.DoesNotExist:
            return JsonResponse({'error': 'Ordem não encontrada'}, status=404)
        
        # Marca como excluída e salva
        ordem.excluida = True

        ordem.save(update_fields=['excluida'])  # NÃO atualiza `ultima_atualizacao`
        
        return JsonResponse({'success': True, 'message': f'Ordem {ordem_id} marcada como excluída'})
    
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def excluir_op_lote(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)

    try:
        data = json.loads(request.body)
        ordem_ids = data.get('ordem_ids', [])

        if not isinstance(ordem_ids, list) or not ordem_ids:
            return JsonResponse({'error': 'ordem_ids deve ser uma lista não vazia'}, status=400)

        # Garante inteiros
        try:
            ordem_ids = [int(i) for i in ordem_ids]
        except Exception:
            return JsonResponse({'error': 'ordem_ids contém valores inválidos'}, status=400)

        updated = Ordem.objects.filter(pk__in=ordem_ids).update(excluida=True)
        return JsonResponse({'success': True, 'atualizadas': updated})
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def gerar_op_duplicada(request, pk_ordem):

    """
    Duplicar uma ordem existente com suas propriedades e criar uma nova entrada na base.
    """
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)

    # Carrega os dados do JSON
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    # Valida os campos necessários
    obs_duplicar = data.get('obs_duplicar')
    data_programacao = data.get('dataProgramacao')
    qtd_chapa = data.get('qtdChapa')
    tipo_chapa = data.get('tipoChapa')
    espessura = data.get('espessura')
    maquina = data.get('maquina', None)
    pecas = data.get('pecas', [])

    if not qtd_chapa or not pecas:
        return JsonResponse({'error': 'Campos obrigatórios ausentes (qtdChapa ou pecas)'}, status=400)

    try:
        qtd_chapa = float(qtd_chapa)  # Converte qtdChapa para float
    except ValueError:
        return JsonResponse({'error': 'Quantidade de chapas inválida'}, status=400)

    try:
        # Busca a ordem original
        ordem_original = Ordem.objects.get(pk=pk_ordem)

        if maquina:
            maquina_ordem = get_object_or_404(Maquina, pk=maquina)
        else:
            maquina_ordem = ordem_original.maquina.nome if ordem_original.maquina.nome in ['laser_1', 'laser_2','laser_3'] else None

        with transaction.atomic():
            # Cria a nova ordem como duplicada
            nova_ordem = Ordem.objects.create(
                ordem_pai=ordem_original,
                duplicada=True,
                grupo_maquina=ordem_original.grupo_maquina,
                maquina=maquina_ordem,
                obs=obs_duplicar,
                status_atual='aguardando_iniciar',
                data_programacao=data_programacao,
                tempo_estimado=ordem_original.tempo_estimado,
            )

            # Duplica as propriedades associadas
            if hasattr(ordem_original, 'propriedade'):
                propriedade_original = ordem_original.propriedade

                if espessura == None:
                    espessura = propriedade_original.espessura

                if tipo_chapa == None:
                    tipo_chapa = propriedade_original.tipo_chapa

                PropriedadesOrdem.objects.create(
                    ordem=nova_ordem,  # Associa a nova ordem
                    descricao_mp=propriedade_original.descricao_mp,
                    tamanho=propriedade_original.tamanho,
                    espessura=espessura,
                    quantidade=qtd_chapa,
                    aproveitamento=propriedade_original.aproveitamento,
                    tipo_chapa=tipo_chapa,
                    retalho=propriedade_original.retalho,
                )

            # Criar peças para ordem duplicada
            for peca in pecas:
                PecasOrdem.objects.create(
                    ordem=nova_ordem,
                    peca=peca['peca'],
                    qtd_planejada=peca['qtd_planejada']
                )

        return JsonResponse({'message': 'Ordem duplicada com sucesso', 'nova_ordem_id': nova_ordem.pk, 'nova_ordem': nova_ordem.ordem_duplicada}, status=201)

    except Ordem.DoesNotExist:
        return JsonResponse({'error': 'Ordem original não encontrada'}, status=404)
    except Exception as e:
        return JsonResponse({'error': f'Erro ao duplicar ordem: {str(e)}'}, status=500)

def duplicar_op(request):

    return render(request, 'apontamento_corte/duplicar-op.html')

def get_ordens_sequenciadas(request):
    """
    Função para buscar ordens já sequenciadas não finalizadas
    """

    # Máquina do laser ou plasma
    tipo_maquina = request.GET.get('maquina')
    ordem = request.GET.get('ordem', '')
    filtro_grupo_maquina = {
        'grupo_maquina': tipo_maquina
    }

    # if tipo_maquina == 'laser':
    #     filtro_grupo_maquina = {
    #         'grupo_maquina__in': ['laser_1', 'laser_2', 'Laser 2 (JFY)','laser_3']
    #     }
    # else:
    #     filtro_grupo_maquina = {
    #         'grupo_maquina': 'plasma'
    #     }

    filtros = {
        'sequenciada': True,
        **filtro_grupo_maquina
    }

    if ordem:
        # Verifica se é uma ordem duplicada; ajuste a condição para funcionar corretamente
        if '.' in ordem or 'dup' in ordem:
            filtros['ordem_duplicada__contains'] = ordem
        else:
            filtros['ordem'] = int(ordem)

    ordens_sequenciadas = Ordem.objects.filter(~Q(status_atual='finalizada'), **filtros).order_by('ordem_prioridade').select_related('propriedade')
    
    # Converte cada objeto para dicionário e adiciona o display do grupo_maquina
    data = []
    for ordem_obj in ordens_sequenciadas:
        ordem_dict = model_to_dict(ordem_obj, exclude=['qrcode'])  # << aqui
        ordem_dict['grupo_maquina_display'] = ordem_obj.get_grupo_maquina_display()

        propriedade = getattr(ordem_obj, 'propriedade', None)
        if propriedade:
            ordem_dict['descricao_mp'] = propriedade.descricao_mp if propriedade.descricao_mp else None
            ordem_dict['quantidade'] = propriedade.quantidade
            ordem_dict['tipo_chapa'] = propriedade.get_tipo_chapa_display() if hasattr(propriedade, 'tipo_chapa') else None
        else:
            ordem_dict['descricao_mp'] = None
            ordem_dict['quantidade'] = None
            ordem_dict['tipo_chapa'] = None

        data.append(ordem_dict)

    return JsonResponse({'ordens_sequenciadas': data})

def resequenciar_ordem(request):

    # Verifica se o usuário tem o tipo de acesso "pcp"
    if not hasattr(request.user, 'profile') or request.user.profile.tipo_acesso not in ['pcp','supervisor']:
        return JsonResponse({'error': 'Acesso negado: você não tem permissão para excluir ordens.'}, status=403)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            ordem_id = data['ordem_id']

            ordem = get_object_or_404(Ordem, pk=ordem_id)

            if ordem.sequenciada:
                return JsonResponse({'error':'Essa ordem já está sequenciada.'}, status=400)

            if ordem.status_atual != 'aguardando_iniciar':
                return JsonResponse({'error':'Essa ordem precisa está com status "Aguardando iniciar".'}, status=400)

            ordem.sequenciada = True
            ordem.save()

            return JsonResponse({'message': 'Ordem sequenciada com sucesso.'}, status=201)

        except Exception as e:
            return JsonResponse({'error': 'Erro interno no servidor.'}, status=500)

    return JsonResponse({'error': 'Método não permitido.'}, status=405)

def api_ordens_finalizadas(request):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT 
                COALESCE(o.ordem::TEXT, o.ordem_duplicada) AS ordem,
                poc.peca,
                poc.qtd_planejada,
                
                -- tamanho_chapa: prioridade para tamanho, senão extrai da descricao_mp
                CASE 
                    WHEN p.tamanho IS NOT NULL THEN p.tamanho
                    WHEN p.descricao_mp IS NOT NULL THEN SPLIT_PART(p.descricao_mp, ' - ', 2)
                    ELSE NULL
                END AS tamanho_chapa,

                p.quantidade AS qt_chapa,
                p.aproveitamento,

                -- espessura_final = espessura + sigla tipo_chapa
                TRIM(
                    TRIM(COALESCE(p.espessura, '')) || 
                    CASE p.tipo_chapa
                        WHEN 'inox' THEN ' Inox'
                        WHEN 'anti_derrapante' THEN ' A.D'
                        WHEN 'alta_resistencia' THEN ' A.R'
                        ELSE ''
                    END
                ) AS espessura,

                poc.qtd_morta,
                CONCAT(op.matricula, ' - ', op.nome) AS operador,
                TO_CHAR(o.ultima_atualizacao - interval '3 hours', 'DD/MM/YYYY HH24:MI') AS data_finalizacao,
                poc.qtd_boa AS total_produzido,
                p.retalho 
            FROM apontamento_v2.core_ordem o
            INNER JOIN apontamento_v2.apontamento_corte_pecasordem poc ON poc.ordem_id = o.id
            LEFT JOIN apontamento_v2.core_propriedadesordem p ON o.id = p.ordem_id
            LEFT JOIN apontamento_v2.cadastro_operador op ON op.id = o.operador_final_id
            WHERE 
                o.status_atual = 'finalizada'
                AND o.ultima_atualizacao >= '2025-04-08'
                AND poc.qtd_boa > 0
            ORDER BY o.ultima_atualizacao, peca;
        """)
        columns = [col[0] for col in cursor.description]
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]

    return JsonResponse(results, safe=False)

def api_ordens_finalizadas_mp(request):
    with connection.cursor() as cursor:
        cursor.execute("""
        SELECT 
            COALESCE(o.ordem::TEXT, o.ordem_duplicada) AS ordem,
            TO_CHAR(o.ultima_atualizacao - interval '3 hours', 'DD/MM/YYYY HH24:MI') AS data_finalizacao,

            -- tamanho_chapa: usa 'tamanho', senão usa split da descricao_mp
            CASE 
                WHEN p.tamanho IS NOT NULL THEN p.tamanho
                WHEN p.descricao_mp IS NOT NULL THEN SPLIT_PART(p.descricao_mp, ' - ', 2)
                ELSE NULL
            END AS tamanho_chapa,

            p.quantidade AS qt_chapa,
            p.aproveitamento,
            p.descricao_mp AS descricao_chapa,
            TRIM(p.espessura) AS espessura,
            m.nome AS maquina,
            CASE p.tipo_chapa
                WHEN 'inox' THEN ' Inox'
                WHEN 'anti_derrapante' THEN ' A.D'
                WHEN 'alta_resistencia' THEN ' A.R'
                ELSE ''
            END
            AS tipo_chapa,
            CASE 
                WHEN p.retalho THEN 'Sim'
                ELSE 'Não'
                END AS retalho

            FROM apontamento_v2.core_ordem o
            LEFT JOIN apontamento_v2.core_propriedadesordem p ON o.id = p.ordem_id
            LEFT JOIN apontamento_v2.cadastro_maquina m ON o.maquina_id = m.id
        WHERE 
            o.status_atual = 'finalizada'
        AND o.grupo_maquina IN ('laser_1', 'laser_2', 'plasma','laser_3')
        AND o.ultima_atualizacao >= '2025-04-08'
        ORDER BY o.ultima_atualizacao;
        """)

        columns = [col[0] for col in cursor.description]
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]

    return JsonResponse(results, safe=False)

def api_ordens_criadas(request):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT 
                TO_CHAR(o.data_criacao - interval '3 hours', 'DD/MM/YYYY HH24:MI') AS data_criacao,
                COALESCE(o.ordem::TEXT, o.ordem_duplicada) AS ordem,
                poc.peca,
                poc.qtd_planejada,
                o.status_atual,
                m.nome AS maquina
            FROM apontamento_v2.core_ordem o
            INNER JOIN apontamento_v2.apontamento_corte_pecasordem poc ON poc.ordem_id = o.id
            LEFT JOIN apontamento_v2.cadastro_maquina m ON m.id = o.maquina_id
            WHERE o.ultima_atualizacao >= '2025-04-08'
            ORDER BY o.ultima_atualizacao;
        """)
        columns = [col[0] for col in cursor.description]
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]

    return JsonResponse(results, safe=False)

def excluir_ordem(request):
    """
    API para excluir ordens apenas do corte.
    """

    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)

    try:
        data = json.loads(request.body)
        ordem_id = data.get('ordem_id')
        motivo_id = data.get('motivo')

        print(ordem_id)
        print(motivo_id)
        
        ordem = get_object_or_404(Ordem, pk=ordem_id)
        motivo = get_object_or_404(MotivoExclusao, pk=int(motivo_id))

        # Atualiza os campos da ordem
        ordem.sequenciada = None
        ordem.status_atual = 'aguardando_iniciar'
        ordem.motivo_retirar_sequenciada = motivo
        
        ordem.save()

        # Apaga os processos associados a essa ordem
        OrdemProcesso.objects.filter(ordem=ordem).delete()

        return JsonResponse({'success': 'Ordem excluída com sucesso.'}, status=201)

    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
def definir_prioridade(request):
    """
    Define a prioridade de uma ordem de corte.
    
    - Se já existir uma ordem com a prioridade escolhida, ela terá a prioridade removida.
    - A nova ordem recebe a prioridade definida.
    """

    try:
        data = json.loads(request.body)
        ordem_id = data.get('ordemId')
        prioridade = data.get('prioridade')

        if not ordem_id or not prioridade:
            return JsonResponse({'error': 'Parâmetros ordemId e prioridade são obrigatórios.'}, status=400)

        ordem = get_object_or_404(Ordem, pk=ordem_id)

        with transaction.atomic():
            # Remove a prioridade de outras ordens, se já atribuída
            Ordem.objects.filter(ordem_prioridade=prioridade, grupo_maquina=ordem.grupo_maquina).exclude(pk=ordem_id).update(ordem_prioridade=None)

            # Atualiza a ordem solicitada com a nova prioridade
            ordem.ordem_prioridade = prioridade
            ordem.save()

        return JsonResponse({'success': 'Prioridade definida com sucesso.'}, status=201)

    except Ordem.DoesNotExist:
        return JsonResponse({'error': 'Ordem não encontrada.'}, status=404)

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Formato JSON inválido.'}, status=400)

    except Exception as e:
        return JsonResponse({'error': f'Ocorreu um erro inesperado: {str(e)}'}, status=500)
    
class ProcessarArquivoView(View):
    def post(self, request):
        
        """
        Faz o upload do arquivo, processa os dados e retorna como JSON.
        """

        # Verifica se o arquivo foi enviado
        uploaded_file = request.FILES.get('file')
        tipo_maquina = request.POST.get('tipoMaquina')
        print(tipo_maquina)
        print(uploaded_file)
        
        if not uploaded_file:
            return JsonResponse({'error': 'Nenhum arquivo enviado.'}, status=400)

        # Extrai a numeração do nome do arquivo
        numeracao = extrair_numeracao(uploaded_file.name)
        # deverá ser tratado de forma diferente dos laser
            
        if numeracao:
            # Verifica se a numeração já existe no banco de dados
            if Ordem.objects.filter(ordem=int(numeracao),grupo_maquina=tipo_maquina).exists():
                return JsonResponse({
                    'error': f"A ordem {numeracao} já foi gerada.",
                    'exists': True,
                }, status=400)
        else:
            return JsonResponse({'error': 'Numeração não encontrada no nome do arquivo.'}, status=400)

        try:
            # Ler o arquivo Excel enviado
            if tipo_maquina == 'laser_3':
                ordem_producao_excel = ET.parse(uploaded_file)
            else:
                ordem_producao_excel = pd.read_excel(uploaded_file)

            # Realizar o tratamento da planilha
            if tipo_maquina=='plasma':
                excel_tratado,propriedades = tratamento_planilha_plasma(ordem_producao_excel)
            elif tipo_maquina == 'laser_2':
                try:
                    # Tenta carregar a aba em inglês
                    ordem_producao_excel_2 = pd.read_excel(uploaded_file, sheet_name='AllPartsList')
                    ordem_producao_excel_3 = pd.read_excel(uploaded_file, sheet_name='Cost List')
                except ValueError:
                    try:
                        # Se não achar, tenta a aba em português
                        ordem_producao_excel_2 = pd.read_excel(uploaded_file, sheet_name='Lista de Todas as Peças')
                        ordem_producao_excel_3 = pd.read_excel(uploaded_file, sheet_name='Lista de custos')
                    except ValueError:
                        # Se nenhuma das duas existir, levanta erro claro
                        raise ValueError("Nenhuma das abas 'AllPartsList' ou 'Lista de Todas as Peças' foi encontrada na planilha.")
                
                excel_tratado,propriedades = tratamento_planilha_laser2(ordem_producao_excel,ordem_producao_excel_2,ordem_producao_excel_3)
            elif tipo_maquina == 'laser_3':
                excel_tratado,propriedades = tratamento_planilha_laser3(ordem_producao_excel)

            # Converter para uma lista de dicionários
            relevant_data = excel_tratado.to_dict(orient='records')

            # Retornar os dados processados como JSON
            return JsonResponse({'data': relevant_data})
        except Exception as e:
            # Lidar com possíveis erros durante o processamento
            return JsonResponse({'error': f"Erro ao processar o arquivo: {str(e)}"}, status=500)

class SalvarArquivoView(View):

    @staticmethod
    def corrigir_aproveitamento(valor):
        """
        Corrige valores de aproveitamento que foram inseridos de forma incorreta.
        Exemplo:
        - 9855 -> 0.9855
        - 006 -> 0.6
        - 49.85 -> 0.4985
        """
        valor = str(valor)
        valor = valor.replace("%","").replace(",",".")

        if valor is None:
            return 0  # Garante que valores nulos não quebrem a ordenação

        try:
            valor = float(valor)

            # Se for maior que 1, assumimos que foi multiplicado por 10^n e ajustamos
            if valor > 1:
                num_digitos = len(str(int(valor)))  # Conta os dígitos inteiros
                valor = valor / (10 ** num_digitos)  # Ajusta dividindo por 10^n

            # Se for menor que 0.01, assume erro de casas decimais e ajusta
            elif valor < 0.001:
                valor = valor * 1000  # Multiplica por 10 e arredonda para 1 casa decimal
            elif valor < 0.01:
                valor = valor * 100  # Multiplica por 10 e arredonda para 1 casa decimal
            
            return valor

        except ValueError:
            return 0  # Se não for possível converter, assume 0

    def post(self, request):

        """
        Recebe o caminho do arquivo e os dados confirmados pelo usuário.
        Salva as informações no banco de dados.
        """

        uploaded_file = request.FILES.get('file')
        descricao = request.POST.get('descricao')
        tipo_chapa = request.POST.get('tipo_chapa')
        retalho = request.POST.get('retalho') == 'true'  # Converte 'true' para True e 'false' para False
        tipo_maquina = request.POST.get('maquina')
        data_programacao = request.POST.get('dataProgramacao')

        if not uploaded_file:
            return JsonResponse({'error': 'Nenhum arquivo enviado.'}, status=400)

        numeracao_op = extrair_numeracao(uploaded_file.name)

        # Ler o arquivo Excel enviado
        if tipo_maquina == 'laser_3':
            ordem_producao_excel = ET.parse(uploaded_file)
        else:
            ordem_producao_excel = pd.read_excel(uploaded_file)

        tipo_maquina_tratada = tipo_maquina.replace("_"," ").title()

        tipo_maquina_object = get_object_or_404(Maquina, nome__contains=tipo_maquina_tratada) if tipo_maquina in ['laser_1','laser_2','laser_3'] else None

        if tipo_maquina =='plasma':
            excel_tratado,propriedades = tratamento_planilha_plasma(ordem_producao_excel)
        elif tipo_maquina_object.nome=='Laser 2 (JFY)':

            # apenas para o laser2
            try:
                # Tenta carregar a aba em inglês
                ordem_producao_excel_2 = pd.read_excel(uploaded_file, sheet_name='AllPartsList')
                ordem_producao_excel_3 = pd.read_excel(uploaded_file, sheet_name='Cost List')
            except ValueError:
                try:
                    # Se não achar, tenta a aba em português
                    ordem_producao_excel_2 = pd.read_excel(uploaded_file, sheet_name='Lista de Todas as Peças')
                    ordem_producao_excel_3 = pd.read_excel(uploaded_file, sheet_name='Lista de custos')
                except ValueError:
                    # Se nenhuma das duas existir, levanta erro claro
                    raise ValueError("Nenhuma das abas 'AllPartsList' ou 'Lista de Todas as Peças' foi encontrada na planilha.")

            excel_tratado,propriedades = tratamento_planilha_laser2(ordem_producao_excel,ordem_producao_excel_2,ordem_producao_excel_3)
        elif tipo_maquina_object.nome=='Laser 1':

            comprimento = request.POST.get('comprimento')
            largura=request.POST.get('largura')

            espessura=get_object_or_404(Espessura, pk=request.POST.get('espessura'))
            
            # apenas para o laser1
            ordem_producao_excel_2 = pd.read_excel(uploaded_file, sheet_name='Nestings_Cost', dtype={'Unnamed: 3': str})
            excel_tratado,propriedades = tratamento_planilha_laser1(ordem_producao_excel,ordem_producao_excel_2,comprimento,largura,espessura.nome)
        elif tipo_maquina_object.nome == 'Laser 3 Trumpf':
            excel_tratado,propriedades = tratamento_planilha_laser3(ordem_producao_excel)

        pecas = excel_tratado.to_dict(orient='records')  # Converter para uma lista de dicionários

        with transaction.atomic():

            # buscar tempo estimado
            for prop in propriedades:
                tempo_estimado = prop['tempo_estimado_total']

            # criar ordem
            nova_ordem = Ordem.objects.create(
                ordem=int(numeracao_op),
                obs=descricao,
                grupo_maquina=tipo_maquina,
                data_programacao=data_programacao,
                maquina=tipo_maquina_object,
                tempo_estimado=tempo_estimado
            )
            
            # salvar propriedades
            for prop in propriedades:

                PropriedadesOrdem.objects.create(
                    ordem=nova_ordem,
                    descricao_mp=prop['descricao_mp'],
                    espessura=str(prop['espessura']).rstrip(),
                    quantidade=prop['quantidade'],
                    aproveitamento=SalvarArquivoView.corrigir_aproveitamento(prop['aproveitamento']),
                    tipo_chapa=tipo_chapa,
                    retalho=retalho,
                )
            
            # salvar peças
            for peca in pecas:
                print(peca['qtd_planejada'])
                if peca['qtd_planejada'] == 0:
                    continue

                PecasOrdem.objects.create(
                    ordem=nova_ordem,
                    peca=peca['peca'],
                    qtd_planejada=peca['qtd_planejada']
                )

        return JsonResponse({'message': 'Dados salvos com sucesso!'})
    
#### dashboard

def dashboard(request):

    return render(request, 'dashboard/dashboard-corte.html')

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
