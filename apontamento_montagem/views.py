from django.conf import settings
from django.http import JsonResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.utils.timezone import now,localtime
from django.utils.dateparse import parse_date
from django.db.models import Sum, F, ExpressionWrapper, FloatField, Value, Avg, Q, IntegerField, Max, OuterRef, Subquery, Count, Exists
from django.db import transaction, models, IntegrityError, connection
from django.shortcuts import get_object_or_404
from django.db.models.functions import Coalesce, TruncDate
from django.shortcuts import render
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator
from django.views.decorators.http import require_GET, require_POST

import json
import os
import requests
from datetime import datetime, date, timedelta
import logging
import traceback

from .models import PecasOrdem, ConjuntosInspecionados, TaktCelulaExcluida
from core.utils import carregar_planilha_base_geral
from core.models import SolicitacaoPeca, Ordem, OrdemProcesso, MaquinaParada, MotivoInterrupcao, MotivoMaquinaParada, Profile, PecasFaltantes
from cadastro.models import Operador, Maquina, Pecas, Conjuntos, CarretasExplodidas
from inspecao.models import Inspecao


logger = logging.getLogger(__name__)


def _normalizar_codigo_inspecao(valor):
    codigo = str(valor or "").strip().replace(" ", "")
    if codigo.endswith(".0"):
        codigo = codigo[:-2]
    return codigo.upper()


def _chave_codigo_inspecao(valor):
    return _normalizar_codigo_inspecao(valor).lstrip("0")


def _extrair_codigo_peca(peca_nome):
    texto = str(peca_nome or "").strip()
    if " - " in texto:
        return texto.split(" - ", maxsplit=1)[0].strip()
    if "-" in texto:
        return texto.split("-", maxsplit=1)[0].strip()
    return texto


def _extrair_descricao_peca(peca_nome):
    texto = str(peca_nome or "").strip()
    if " - " in texto:
        return texto.split(" - ", maxsplit=1)[1].strip()
    if "-" in texto:
        return texto.split("-", maxsplit=1)[1].strip()
    return ""


def _extrair_chave_retorno_erp_montagem(retorno):
    if not isinstance(retorno, dict):
        return ''

    for campo in ('chaveProducao', 'chave', 'productionKey'):
        valor = retorno.get(campo)
        if valor not in (None, ''):
            return str(valor).strip()

    for valor in retorno.values():
        if isinstance(valor, dict):
            chave = _extrair_chave_retorno_erp_montagem(valor)
            if chave:
                return chave

    return ''


def _normalizar_chave_apontamento_erp_montagem(retorno_api, payload_integracao):
    chave = _extrair_chave_retorno_erp_montagem(retorno_api)
    if chave:
        return chave, None

    retorno_serializado = json.dumps(retorno_api, ensure_ascii=False, default=str)[:1200]
    chave_fallback = f"sem-chave:{payload_integracao.get('id')}"
    aviso = (
        'ERP confirmou o apontamento, mas nao retornou chave explicita. '
        f'Retorno bruto: {retorno_serializado}'
    )
    return chave_fallback, aviso


def _nome_responsavel_apontamento(user):
    if not user:
        return ''
    return (user.get_full_name() or user.username).strip()


def _data_finalizacao_item_montagem(item):
    """
    Data em que o item foi de fato finalizado/produzido (nao a data em que o
    registro PecasOrdem foi criado, que reflete quando a ordem foi iniciada).
    """
    data_finalizacao = item.processo_ordem.data_inicio if item.processo_ordem_id else None
    return data_finalizacao or item.data_apontamento or item.data or now()


def _payload_apontamento_erp_montagem(item):
    data_producao = localtime(_data_finalizacao_item_montagem(item))
    return {
        "id": f"montagem-item-{item.id}",
        "data": data_producao.strftime('%d/%m/%Y'),
        "pessoa": "4357",
        "recurso": _extrair_codigo_peca(item.peca),
        "processo": "S Mont Conjuntos Carretas",
        "produzido": item.qtd_boa,
        "observacao": str(item.ordem_id),
    }


def _apontar_item_via_api_erp_montagem(item, user):
    """
    Tenta apontar o item no ERP. Falhas de qualquer natureza (rede, HTTP,
    erro de negocio do ERP, etc.) nunca bloqueiam a finalizacao da ordem:
    o erro e apenas registrado em item.erro_apontamento para conferencia
    posterior em /montagem/erp-apontamentos/.
    """
    payload_integracao = _payload_apontamento_erp_montagem(item)

    if settings.DEBUG:
        print(
            "[MONTAGEM][INNOVARO][PAYLOAD]",
            json.dumps(payload_integracao, ensure_ascii=False, indent=2)
        )

    def _registrar_erro(mensagem, retorno_api=None):
        item.erro_apontamento = mensagem
        item.tipo_apontamento = 'api'
        item.resp_apontamento = user if getattr(user, 'is_authenticated', False) else None
        item.save(update_fields=['erro_apontamento', 'tipo_apontamento', 'resp_apontamento'])
        return {
            'payload_enviado': payload_integracao,
            'retorno_api': retorno_api,
            'chave_apontamento': '',
            'erro_apontamento': mensagem,
        }

    if (item.qtd_morta or 0) > 0:
        return _registrar_erro(
            'Apontamento via API bloqueado automaticamente: item com qtd_morta > 0. '
            'A funcionalidade de desvio precisa ser ajustada na API.'
        )

    if os.getenv("DISABLE_ERP_APONTAMENTO") == "true":
        return _registrar_erro("ERP desabilitado temporariamente.")

    try:
        if os.getenv("DJANGO_ENV") == "dev":
            response_integracao = requests.post(
                "https://hcemag.innovaro.com.br/api/integracao/v1/producao/apontar",
                json=payload_integracao,
                auth=("luan araujo", "luanaraujo7"),
                timeout=(10, 60),
            )
        else:
            response_integracao = requests.post(
                "https://cemag.innovaro.com.br/api/integracao/v1/producao/apontar",
                json=payload_integracao,
                auth=("luan araujo", "luanaraujo7"),
                timeout=(10, 60),
            )
    except requests.RequestException as exc:
        return _registrar_erro(f'Falha de comunicacao com API ERP: {exc}')

    try:
        resposta_api_json = response_integracao.json()
    except ValueError:
        resposta_api_json = None

    if not response_integracao.ok:
        descricao_erro = ''
        if isinstance(resposta_api_json, dict):
            descricao_erro = str(resposta_api_json.get('description') or '')

        if not descricao_erro:
            try:
                descricao_erro = response_integracao.text[:500]
            except Exception:
                descricao_erro = 'Sem detalhes'

        return _registrar_erro(
            f'API ERP retornou status {response_integracao.status_code}: {descricao_erro}',
            retorno_api=resposta_api_json,
        )

    if not isinstance(resposta_api_json, dict):
        retorno_texto = (response_integracao.text or '')[:500]
        return _registrar_erro('API ERP nao retornou JSON valido. ' + retorno_texto)

    status_erp = str(resposta_api_json.get('status') or '').strip().lower()
    if status_erp == 'error':
        descricao_erro = str(resposta_api_json.get('description') or 'Erro retornado pela API ERP.')
        return _registrar_erro(descricao_erro, retorno_api=resposta_api_json)

    if status_erp != 'success':
        return _registrar_erro('Resposta da API ERP em formato inesperado: ' + str(resposta_api_json))

    item.chave_apontamento, aviso_chave = _normalizar_chave_apontamento_erp_montagem(
        resposta_api_json,
        payload_integracao,
    )
    item.erro_apontamento = aviso_chave
    item.apontado = True
    item.tipo_apontamento = 'api'
    item.resp_apontamento = user if getattr(user, 'is_authenticated', False) else None
    item.data_apontamento = now()
    item.save(update_fields=[
        'apontado',
        'tipo_apontamento',
        'resp_apontamento',
        'data_apontamento',
        'chave_apontamento',
        'erro_apontamento',
    ])

    return {
        'payload_enviado': payload_integracao,
        'retorno_api': resposta_api_json,
        'chave_apontamento': item.chave_apontamento or '',
        'erro_apontamento': item.erro_apontamento or '',
    }

@csrf_exempt
def criar_ordem(request):
    """
    API para criar múltiplas ordens para o setor de montagem.
    Exemplo de carga JSON esperada:
    {
        "ordens": [
            {
                "grupo_maquina": "montagem",
                "setor_conjunto": "Içamento",
                "obs": "testes",
                "peca_nome": "123456",
                "qtd_planejada": 5,
                "data_carga": "2025-02-19"
            }
        ]
    }
    """

    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido!'}, status=405)
    try:
        data = json.loads(request.body)  # Tenta carregar o JSON
        ordens_data = data.get('ordens', [])
        atualizacao_ordem = data.get('atualizacao_ordem', None)

        if not ordens_data:
            return JsonResponse({'error': 'Nenhuma ordem fornecida!'}, status=400)

        # Coletar todas as datas únicas na requisição
        datas_requisicao = set()

        for ordem_info in ordens_data:
            data_carga_str = ordem_info.get('data_carga')
            if data_carga_str:
                try:
                    data_carga = datetime.strptime(data_carga_str, "%d/%m/%Y").date()
                    datas_requisicao.add(data_carga)
                except ValueError:
                    return JsonResponse({'error': 'Formato de data inválido! Use YYYY-MM-DD.'}, status=400)

        # Verifica se alguma das datas já tem carga alocada no banco
        datas_existentes = set(Ordem.objects.filter(data_carga__in=datas_requisicao, grupo_maquina='montagem').values_list('data_carga', flat=True))
        datas_bloqueadas = datas_existentes.intersection(datas_requisicao)

        if not atualizacao_ordem:
            if datas_bloqueadas:
                return JsonResponse({'error': f"Não é possível adicionar novas ordens. Datas já possuem carga alocada: {', '.join(map(str, datas_bloqueadas))}"}, status=400)
        
        # Coletar todas as máquinas na requisição
        maquinas_requisicao = set()
        for ordem_info in ordens_data:
            maquina_str = ordem_info.get('setor_conjunto')
            if maquina_str:  # Garante que não é None ou string vazia
                maquinas_requisicao.add(maquina_str)  # Corrigido para adicionar o nome correto da máquina

        # Verifica se todas as células já estão cadastradas no model de máquinas
        maquinas_existentes = set(Maquina.objects.filter(nome__in=maquinas_requisicao).values_list('nome', flat=True))

        # Identifica as máquinas que não estão cadastradas
        maquinas_faltantes = maquinas_requisicao - maquinas_existentes

        if maquinas_faltantes:
            return JsonResponse(
                {'error': f"Não é possível adicionar novas ordens. As máquinas a seguir não estão cadastradas: {', '.join(maquinas_faltantes)}"}, 
                status=400, safe=False
            )
        
        ordens_criadas = []

        with transaction.atomic():
            ordens_objs = []
            pecas_objs = []
            ordens_metadata = []

            for ordem_info in ordens_data:
                grupo_maquina = ordem_info.get('grupo_maquina', 'montagem')
                setor_conjunto = ordem_info.get('setor_conjunto')
                obs = ordem_info.get('obs', '')
                nome_peca = ordem_info.get('peca_nome')
                qtd_planejada = ordem_info.get('qtd_planejada', 0)
                data_carga = datetime.strptime(ordem_info['data_carga'], "%Y-%d-%m").date()

                maquina = Maquina.objects.get(nome=setor_conjunto)

                nova_ordem = Ordem(
                    grupo_maquina=grupo_maquina,
                    status_atual='aguardando_iniciar',
                    obs=obs,
                    data_criacao=now(),
                    data_carga=data_carga,
                    maquina=maquina
                )

                ordens_objs.append(nova_ordem)
                ordens_metadata.append({
                    "setor_conjunto": setor_conjunto,
                    "data_carga": data_carga,
                    "qtd_planejada": qtd_planejada,
                    "nome_peca": nome_peca
                })

            # Cria todas as ordens de uma vez
            Ordem.objects.bulk_create(ordens_objs)

            # Associa peças às ordens agora com IDs já definidos
            for ordem_obj, meta in zip(ordens_objs, ordens_metadata):
                pecas_objs.append(PecasOrdem(
                    ordem=ordem_obj,
                    peca=meta["nome_peca"],
                    qtd_planejada=meta["qtd_planejada"],
                    qtd_boa=0,
                    qtd_morta=0
                ))

            PecasOrdem.objects.bulk_create(pecas_objs)

            ordens_criadas = [{
                "id": ordem.id,
                "setor_conjunto": meta["setor_conjunto"],
                "data_carga": meta["data_carga"].strftime("%Y-%m-%d")
            } for ordem, meta in zip(ordens_objs, ordens_metadata)]

        return JsonResponse({
            'message': 'Ordens e peças criadas com sucesso!',
            'ordens': ordens_criadas
        }, safe=False)

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Erro ao processar JSON. Verifique o formato da requisição!'}, status=400)

    except IntegrityError:
        traceback.print_exc()  # Log detalhado do erro no console
        return JsonResponse({'error': 'Erro no banco de dados ao salvar a ordem!'}, status=500)

    except Exception as e:
        traceback.print_exc()  # Log detalhado do erro no console
        return JsonResponse({'error': f'Erro inesperado: {str(e)}'}, status=500)
    
@csrf_exempt
def atualizar_status_ordem(request):

    """
    Para iniciar uma ordem:

    {
        "status": "iniciada",
        "ordem_id": 21101,
    }

    Para interromper uma ordem:

    {
        "status": "interrompida",
        "ordem_id": 21101,
        "motivo": 2
    }

    Para finalizar uma ordem:

    {
        "status": "finalizada",
        "ordem_id": 21103,
        "operador_final": 2,
        "obs_finalizar": "teste",
        "qt_realizada": 2,
        "qt_mortas": 0
    }
    """

    try:
        # Parse do corpo da requisição
        body = json.loads(request.body)

        status = body.get('status')
        ordem_id = body.get('ordem_id')
        grupo_maquina = 'montagem'
        qt_produzida = body.get('qt_realizada', 0)
        qt_mortas = body.get('qt_mortas', 0)
        continua = body.get('continua', 'false').lower() == 'true'
        apontamento_erp = None

        if not ordem_id or not grupo_maquina or not status:
            return JsonResponse({'error': 'Campos obrigatórios não enviados.'}, status=400)

        with transaction.atomic():  # Entra na transação somente após garantir que todos os objetos existem
            # select_for_update mantem o lock na ordem durante toda a checagem de status +
            # criacao do processo + apontamento ERP: uma segunda requisicao concorrente para
            # a mesma ordem (duplo clique, retry) fica bloqueada ate essa transacao terminar e
            # so entao ve o status_atual real, evitando duplicar o apontamento no Innovaro.
            ordem = get_object_or_404(Ordem.objects.select_for_update(of=('self',)), pk=ordem_id)

            if ordem.status_atual == status:
                return JsonResponse({'error': f'Essa ordem já está {status}. Atualize a página.'}, status=400)

            if status == 'retorno' and ordem.status_atual == 'iniciada':
                return JsonResponse({'error': f'Essa ordem já está iniciada. Atualize a página.'}, status=400)

            # Finaliza o processo atual (se existir)
            processo_atual = ordem.processos.filter(data_fim__isnull=True).first()
            if processo_atual:
                processo_atual.finalizar_atual()

            # Cria o novo processo
            novo_processo = OrdemProcesso.objects.create(
                ordem=ordem,
                status='iniciada' if status == 'retorno' else status,
                data_inicio=now(),
                data_fim=now() if status in ['finalizada'] else None,
            )

            if status == 'iniciada':

                # Validações básicas
                if ordem.status_atual == 'interrompida':
                    return JsonResponse({'error': f'Essa ordem está interrompida, retorne ela.'}, status=400)

                maquinas_paradas = MaquinaParada.objects.filter(maquina=ordem.maquina, data_fim__isnull=True)
                for parada in maquinas_paradas:
                    parada.data_fim = now()
                    parada.save()

                ordem.status_prioridade = 1

                # Atualiza o status da ordem
                ordem.status_atual = status

                peca = PecasOrdem.objects.filter(ordem=ordem).first()

                nova_peca_ordem = PecasOrdem.objects.create(
                    ordem=ordem,
                    peca=peca.peca,
                    qtd_planejada=peca.qtd_planejada,
                    qtd_boa=0,
                    operador=None,
                    processo_ordem=novo_processo
                )

                nova_peca_ordem.save()

            elif status == 'retorno':
                
                maquinas_paradas = MaquinaParada.objects.filter(maquina=ordem.maquina, data_fim__isnull=True)
                for parada in maquinas_paradas:
                    parada.data_fim = now()
                    parada.save()

                ordem.status_prioridade = 1

                # Atualiza o status da ordem
                ordem.status_atual = 'iniciada'

                ultimo_peca_ordem = PecasOrdem.objects.filter(ordem=ordem).last()
                ultimo_peca_ordem.processo_ordem=novo_processo
                
                ultimo_peca_ordem.save()

            elif status == 'finalizada':
                operador_final = get_object_or_404(Operador, pk=int(body.get('operador_final')))
                obs_final = body.get('obs_finalizar')

                ordem.operador_final = operador_final
                ordem.obs_operador = obs_final

                peca = PecasOrdem.objects.filter(ordem=ordem).first()

                if not peca:
                    return JsonResponse({'error': 'Nenhuma peça encontrada para essa ordem.'}, status=400)

                # Guarda anti-duplo-clique: a regra de negócio permite múltiplas finalizações
                # parciais legítimas na mesma ordem (status_atual volta para
                # 'aguardando_iniciar'/'iniciada' entre lotes), então não dá pra bloquear só
                # por status repetido como nos outros setores. O registro de PecasOrdem é
                # reaproveitado/atualizado entre finalizações (não recriado quando continua=False),
                # então usamos o OrdemProcesso 'finalizada' anterior (excluindo o que acabamos de
                # criar nesta própria requisição) para saber quando foi a última finalização real.
                processo_finalizada_anterior = (
                    OrdemProcesso.objects
                    .filter(ordem=ordem, status='finalizada')
                    .exclude(pk=novo_processo.pk)
                    .order_by('-data_inicio')
                    .first()
                )
                ultimo_lote = PecasOrdem.objects.filter(ordem=ordem).order_by('-id').first()
                if (
                    processo_finalizada_anterior
                    and (now() - processo_finalizada_anterior.data_inicio) < timedelta(seconds=5)
                    and ultimo_lote
                    and int(ultimo_lote.qtd_boa or 0) == int(qt_produzida)
                    and ultimo_lote.operador_id == operador_final.id
                ):
                    return JsonResponse(
                        {'error': 'Finalização duplicada detectada (mesma quantidade e operador há poucos segundos). Verifique antes de tentar novamente.'},
                        status=409,
                    )

                # Verificar a quantidade já apontada antes de criar um novo registro
                sum_pecas_finalizadas = PecasOrdem.objects.filter(ordem=ordem).aggregate(Sum('qtd_boa'))['qtd_boa__sum'] or 0
                total_apontado = sum_pecas_finalizadas + int(qt_produzida)  # Soma a nova produção

                # Se a nova quantidade ultrapassar a planejada, retorna erro
                if total_apontado > peca.qtd_planejada:
                    return JsonResponse({'error': 'Quantidade produzida maior que a quantidade planejada.'}, status=400)
                
                if total_apontado <= 0:
                    return JsonResponse({'error': 'Quantidade produzida tem que ser maior que zero.'}, status=400)

                # Criando o novo registro de apontamento
                ultimo_peca_ordem = PecasOrdem.objects.filter(ordem=ordem).last()
                ultimo_peca_ordem.qtd_boa=int(qt_produzida)
                ultimo_peca_ordem.qtd_morta=int(qt_mortas or 0)
                ultimo_peca_ordem.processo_ordem=novo_processo
                ultimo_peca_ordem.operador=operador_final
                ultimo_peca_ordem.save()

                apontamento_erp = _apontar_item_via_api_erp_montagem(
                    ultimo_peca_ordem,
                    request.user,
                )

                codigo = _extrair_codigo_peca(peca.peca)
                codigo_chave = _chave_codigo_inspecao(codigo)

                # verifica se tá na lista de itens a ser inspecionado (com fallback de normalização)
                conjunto_exato = ConjuntosInspecionados.objects.filter(codigo=codigo).exists()
                if conjunto_exato:
                    conjunto_inspecionado = True
                else:
                    codigos_cadastro = ConjuntosInspecionados.objects.values_list("codigo", flat=True)
                    codigos_chave = {_chave_codigo_inspecao(c) for c in codigos_cadastro}
                    conjunto_inspecionado = codigo_chave in codigos_chave

                # verifica se a peça é da célula "serralheria", se sim cria inspeção
                maquina_nome = ordem.maquina.nome.strip().lower() if ordem.maquina and ordem.maquina.nome else ""
                precisa_inspecao = conjunto_inspecionado or maquina_nome in {
                    "serralheria",
                    "transbordo",
                    "roçadeira",
                }

                if precisa_inspecao and not Inspecao.objects.filter(pecas_ordem_montagem=ultimo_peca_ordem).exists():
                    Inspecao.objects.create(
                        pecas_ordem_montagem=ultimo_peca_ordem,
                    )

                # Verificar novamente a quantidade finalizada após o novo registro
                sum_pecas_finalizadas = PecasOrdem.objects.filter(ordem=ordem).aggregate(Sum('qtd_boa'))['qtd_boa__sum']

                # Se a quantidade finalizada atingir a planejada, muda status para concluída
                if sum_pecas_finalizadas == peca.qtd_planejada:
                    ordem.status_atual = status
                    ordem.status_prioridade = 3
                    ordem.save()
                else:

                    # se o operador desejar continuar a ordem em aberto?
                    # continua = True
                    # mas e se o operador clicar sem querer?
                    # Como ele finaliza apenas sem computar a ordem?
                    if continua == True:
                        ordem.status_atual = 'iniciada'
                        ordem.status_prioridade = 1
                        ordem.save()

                        nova_peca_ordem = PecasOrdem.objects.create(
                            ordem=ordem,
                            peca=peca.peca,
                            qtd_planejada=peca.qtd_planejada,
                            qtd_boa=0,
                            operador=None,
                            processo_ordem=novo_processo
                        )

                        nova_peca_ordem.save()

                    else:
                        ordem.status_atual = 'aguardando_iniciar'
                        ordem.status_prioridade = 1
                        ordem.save()

            elif status == 'interrompida':
                novo_processo.motivo_interrupcao = get_object_or_404(MotivoInterrupcao, pk=body['motivo'])
                novo_processo.save()
                ordem.status_prioridade = 2

                if 'pecas_faltantes' in body and isinstance(body['pecas_faltantes'], list):
    
                    # 1. Encontrar o último número de interrupção para esta Ordem
                    ultimo_numero = PecasFaltantes.objects.filter(ordem=ordem).aggregate(
                        Max('numero_interrupcao')
                    )['numero_interrupcao__max']
                    
                    # 2. Definir o próximo número. Se for a primeira vez, será 1 (0+1);
                    #    caso contrário, será o máximo + 1.
                    proximo_numero_interrupcao = (ultimo_numero or 0) + 1
                    
                    pecas_a_criar = []
                    for peca_faltante in body['pecas_faltantes']:
                        nome = peca_faltante.get('nome')
                        quantidade = peca_faltante.get('quantidade')
                        
                        if nome and isinstance(quantidade, (int, float)) and quantidade > 0:
                            pecas_a_criar.append(
                                PecasFaltantes(
                                    ordem=ordem,
                                    # 3. Atribuir o número de interrupção calculado a todos
                                    #    os registros deste lote (interrupção)
                                    numero_interrupcao=proximo_numero_interrupcao,
                                    nome_peca=nome,
                                    quantidade=quantidade
                                )
                            )
                            
                    if pecas_a_criar:
                        PecasFaltantes.objects.bulk_create(pecas_a_criar)

                # Atualiza o status da ordem
                ordem.status_atual = status

            # Associa o processo à última PecasOrdem (mantido da sua lógica original)
            ultimo_peca_ordem = PecasOrdem.objects.filter(ordem=ordem).last()
            if ultimo_peca_ordem: # Adicionada verificação para evitar erro se não houver PecasOrdem
                ultimo_peca_ordem.processo_ordem=novo_processo
                ultimo_peca_ordem.save()

            ordem.save()

            response_payload = {
                'message': 'Status atualizado com sucesso.',
                'ordem_id': ordem.id,
                'status': novo_processo.status,
                'data_inicio': novo_processo.data_inicio,
            }
            if apontamento_erp:
                response_payload['apontamento_erp'] = apontamento_erp
                response_payload['chave_apontamento'] = apontamento_erp.get('chave_apontamento', '')

            return JsonResponse(response_payload)

    except Ordem.DoesNotExist:
        return JsonResponse({'error': 'Ordem não encontrada.'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
def ordens_criadas(request):
   
    """
    View que agrega os dados de PecasOrdem (por ordem) e junta com a model Ordem,
    trazendo algumas colunas da Ordem e calculando o saldo:
        saldo = soma(qtd_planejada) - soma(qtd_boa)
    
    Parâmetros esperados na URL (via GET):
      - data_carga: data da carga (default: hoje)
      - maquina: nome da máquina (opcional)
      - status: status da ordem (opcional)
    """

    data_carga = request.GET.get('data_carga')
    maquina_param = request.GET.get('setor', '')
    status_param = request.GET.get('status', '')
    data_programacao = request.GET.get("data-programada", '')

    if data_carga == '':
        data_carga = now().date()

    # Monta os filtros para a model Ordem
    filtros_ordem = {
        'data_carga': data_carga,
        'grupo_maquina': 'montagem',
        'excluida': False,
    }
    if maquina_param:
        maquina = get_object_or_404(Maquina, pk=maquina_param)
        filtros_ordem['maquina'] = maquina
    if status_param:
        filtros_ordem['status_atual'] = status_param
    if data_programacao:
        filtros_ordem['data_programacao'] = data_programacao

    # Máquinas a excluir da contagem / retorno
    maquinas_excluidas = [
        'PLAT. TANQUE. CAÇAM. 2',
        'QUALIDADE',
        'FORJARIA',
        'ESTAMPARIA',
        'Carpintaria',
        'FEIXE DE MOLAS',
    ]

    # Recupera os IDs das ordens que atendem aos filtros (ainda sem excluir máquinas, pois o filtro de máquina pode vir por parâmetro)
    ordem_ids = Ordem.objects.filter(**filtros_ordem).values_list('id', flat=True)

    # Consulta em PecasOrdem filtrando pelas ordens e EXCLUINDO as máquinas definidas em maquinas_excluidas
    pecas_ordem_queryset = PecasOrdem.objects.filter(ordem_id__in=ordem_ids).exclude(
        ordem__maquina__nome__in=maquinas_excluidas
    )

    pecas_ordem_agg = pecas_ordem_queryset.values(
        'ordem',                    # id da ordem (chave para o agrupamento)
        'ordem__data_carga',        # data da carga da ordem
        'ordem__data_programacao',  # data da programação da ordem
        'ordem__maquina__nome',     # nome da máquina
        'ordem__status_atual',      # status atual da ordem
        'peca',                     # nome da peça
    ).annotate(
        total_planejada=Coalesce(
            Avg('qtd_planejada'), Value(0.0, output_field=FloatField())
        ),
        total_boa=Coalesce(
            Sum('qtd_boa'), Value(0.0, output_field=FloatField())
        )
    ).annotate(
        restante=ExpressionWrapper(
            F('total_planejada') - F('total_boa'), output_field=FloatField()
        )
    )

    # Recalcula datas apenas com as ordens consideradas após exclusões
    datas_programacao = set(item['ordem__data_programacao'] for item in pecas_ordem_agg)
    data_programacao = next(iter(datas_programacao), None)
    data_formatada = data_programacao.strftime('%d/%m/%Y') if data_programacao else None

    datas_carga = set(item['ordem__data_carga'] for item in pecas_ordem_agg)
    data_carga = next(iter(datas_carga), None)
    data_formatada_carga = data_carga if data_carga else None

    # Lista de máquinas (apenas das ordens retornadas)
    maquinas = Ordem.objects.filter(id__in=ordem_ids).exclude(
        maquina__nome__in=maquinas_excluidas
    ).values('maquina__nome', 'maquina__id').distinct()

    return JsonResponse({
        "ordens": list(pecas_ordem_agg),
        "maquinas": list(maquinas),
        "data_programacao": data_formatada,
        "data_formatada_carga": data_formatada_carga
    })

def verificar_qt_restante(request):

    ordem_id = request.GET.get('ordem_id')

    ordem_ids = Ordem.objects.filter(pk=ordem_id).values_list('id', flat=True)

    # Consulta na PecasOrdem filtrando pelas ordens identificadas,
    # trazendo alguns campos da Ordem (usando a notação "ordem__<campo>"),
    # e agrupando para calcular as somas e o saldo.
    pecas_ordem_agg = PecasOrdem.objects.filter(ordem_id__in=ordem_ids).values(
        'ordem',                    # id da ordem (chave para o agrupamento)
        'ordem__data_carga',        # data da carga da ordem
        'ordem__data_programacao',  # data da programação da ordem
        'ordem__maquina__nome',     # nome da máquina (ajuste se necessário)
        'ordem__status_atual',      # status atual da ordem
        'peca',                     # nome da peça
    ).annotate(
        total_planejada=Coalesce(
            Avg('qtd_planejada'), Value(0.0, output_field=FloatField())
        ),
        total_boa=Coalesce(
            Sum('qtd_boa'), Value(0.0, output_field=FloatField())
        )
    ).annotate(
        restante=ExpressionWrapper(
            F('total_planejada') - F('total_boa'), output_field=FloatField()
        )
    )

    return JsonResponse({"ordens": list(pecas_ordem_agg)})

def ordens_iniciadas(request):
    """
    Retorna todas as ordens que estão com status "iniciada" e que ainda não foram finalizadas,
    trazendo informações da ordem, peças relacionadas (sem repetição), soma das quantidades planejadas/boas e processos em andamento.
    """

    usuario_tipo = Profile.objects.filter(user=request.user).values_list('tipo_acesso', flat=True).first()

    maquina_param = request.GET.get('setor', '')

    ordem_id = request.GET.get('ordem_id', None)

    filtros_ordem = {
        'grupo_maquina': 'montagem',
        'status_atual': 'iniciada',
        'excluida': False,
    }

    # Adicionar chave id caso exista o parametro ordem_id
    if ordem_id:
        filtros_ordem['id'] = ordem_id # ordem id --> core_ordem

    if maquina_param:
        maquina = get_object_or_404(Maquina, pk=maquina_param)
        filtros_ordem['maquina'] = maquina

    # Filtra ordens com status 'iniciada' e grupo de máquina 'montagem'
    ordens_filtradas = Ordem.objects.filter(**filtros_ordem).prefetch_related('ordem_pecas_montagem', 'processos')

    resultado = []

    for ordem in ordens_filtradas:
        # Filtra apenas os processos que ainda não foram finalizados (data_fim nula)
        processos_ativos = ordem.processos.filter(data_fim__isnull=True)

        # Obtém apenas os nomes das peças, eliminando duplicatas
        pecas_unicas = sorted(set(peca.peca for peca in ordem.ordem_pecas_montagem.all()))

        # Calcula a soma total de qtd_planejada e qtd_boa para esta ordem
        agregacoes = ordem.ordem_pecas_montagem.aggregate(
            total_planejada=Avg('qtd_planejada', default=0.0),
            total_boa=Sum('qtd_boa', default=0.0)
        )

        resultado.append({
            "ordem_id": ordem.id,
            "ordem_numero": ordem.ordem,
            "data_carga": ordem.data_carga,
            "data_programacao": ordem.data_programacao,
            "grupo_maquina": ordem.grupo_maquina,
            "maquina": ordem.maquina.nome if ordem.maquina else None,
            "maquina_id": ordem.maquina.id if ordem.maquina else None,
            "status_atual": ordem.status_atual,
            "ultima_atualizacao": ordem.ultima_atualizacao,
            "pecas": pecas_unicas,  # Lista apenas os nomes das peças (sem repetições)
            "qtd_restante": agregacoes['total_planejada'] - agregacoes['total_boa'],  # Soma total de qtd_planejada
            "processos": [
                {
                    "processo_id": processo.id,
                    "status": processo.status,
                    "data_inicio": processo.data_inicio,
                    "data_fim": processo.data_fim,
                    "motivo_interrupcao": processo.motivo_interrupcao.nome if processo.motivo_interrupcao else None,
                    "maquina": processo.maquina.nome if processo.maquina else None
                }
                for processo in processos_ativos
            ]
        })

    return JsonResponse({"ordens": resultado,'usuario_tipo_acesso': usuario_tipo}, safe=False)

def ordens_interrompidas(request):
    """
    Retorna todas as ordens que estão com status "interrompida" e que ainda não foram finalizadas,
    trazendo informações da ordem, peças relacionadas (sem repetição), soma das quantidades planejadas/boas e processos em andamento.
    """

    usuario_tipo = Profile.objects.filter(user=request.user).values_list('tipo_acesso', flat=True).first()

    maquina_param = request.GET.get('setor', '')

    filtros_ordem = {
        'grupo_maquina': 'montagem',
        'status_atual': 'interrompida',
        'excluida': False,
    }

    if maquina_param:
        maquina = get_object_or_404(Maquina, pk=maquina_param)
        filtros_ordem['maquina'] = maquina

    ordens_filtradas = Ordem.objects.filter(**filtros_ordem).prefetch_related('ordem_pecas_montagem', 'processos')

    resultado = []

    for ordem in ordens_filtradas:
        # Filtra apenas os processos que ainda não foram finalizados (data_fim nula)
        processos_ativos = ordem.processos.filter(data_fim__isnull=True)

        # Obtém apenas os nomes das peças, eliminando duplicatas
        pecas_unicas = sorted(set(peca.peca for peca in ordem.ordem_pecas_montagem.all()))

        # Calcula a soma total de qtd_planejada e qtd_boa para esta ordem
        agregacoes = ordem.ordem_pecas_montagem.aggregate(
            total_planejada=Avg('qtd_planejada', default=0.0),
            total_boa=Sum('qtd_boa', default=0.0)
        )

        ultima_interrupcao_data = ordem.pecas_faltantes.aggregate(
            Max('numero_interrupcao')
        )
        ultima_interrupcao_num = ultima_interrupcao_data['numero_interrupcao__max']
        
        pecas_faltantes_list = []
        
        if ultima_interrupcao_num is not None:
            
            ultima_interrupcao_pecas = ordem.pecas_faltantes.filter(
                numero_interrupcao=ultima_interrupcao_num
            )
            
            pecas_faltantes_list = [
                {
                    "id": peca_faltante.id,
                    "nome_peca": peca_faltante.nome_peca,
                    "quantidade": peca_faltante.quantidade,
                    "data_registro": peca_faltante.data_registro,
                    "numero_interrupcao": peca_faltante.numero_interrupcao 
                }
                for peca_faltante in ultima_interrupcao_pecas
            ]

        resultado.append({
            "ordem_id": ordem.id,
            "ordem_numero": ordem.ordem,
            "data_carga": ordem.data_carga,
            "data_programacao": ordem.data_programacao,
            "grupo_maquina": ordem.grupo_maquina,
            "maquina": ordem.maquina.nome if ordem.maquina else None,
            "status_atual": ordem.status_atual,
            "ultima_atualizacao": ordem.ultima_atualizacao,
            "pecas": pecas_unicas,  # Lista apenas os nomes das peças (sem repetições)
            "qtd_restante": agregacoes['total_planejada'] - agregacoes['total_boa'],  # Soma total de qtd_planejada
            "pecas_faltantes": pecas_faltantes_list,  # Lista de peças faltantes
            "processos": [
                {
                    "processo_id": processo.id,
                    "status": processo.status,
                    "data_inicio": processo.data_inicio,
                    "data_fim": processo.data_fim,
                    "motivo_interrupcao": processo.motivo_interrupcao.nome if processo.motivo_interrupcao else None,
                    "maquina": processo.maquina.nome if processo.maquina else None
                }
                for processo in processos_ativos
            ]
        })

    return JsonResponse({"ordens": resultado, 'usuario_tipo_acesso': usuario_tipo}, safe=False)

def listar_operadores(request):
    maquina_id = request.GET.get('maquina')
    
    # Operadores do setor de montagem
    operadores = Operador.objects.filter(setor__nome='montagem')
    
    # Operadores do setor de montagem que estão vinculados à máquina específica
    if maquina_id:
        operadores_maquina = Operador.objects.filter(
            setor__nome='montagem',
            maquinas__nome=maquina_id 
        ).distinct() 
    else:
        operadores_maquina = Operador.objects.none()
    
    return JsonResponse({
        "operadores": list(operadores.values()),
        "operadores_maquina": list(operadores_maquina.values())
    })

def percentual_concluido_carga(request):
    data_carga = request.GET.get('data_carga')  # Garantindo que seja apenas a data

    # Algumas máquinas que não precisam está na contagem
    maquinas_excluidas = [
        'PLAT. TANQUE. CAÇAM. 2',
        'QUALIDADE',
        'FORJARIA',
        'ESTAMPARIA',
        'Carpintaria',
        'FEIXE DE MOLAS',
        'SERRALHERIA',
    ]

    maquinas_excluidas_ids = Maquina.objects.filter(nome__in=maquinas_excluidas).values_list('id', flat=True)

    # Total planejado sem duplicidade de peça e ordem, excluindo certas máquinas
    total_planejado = PecasOrdem.objects.filter(
        ordem__data_carga=data_carga,
        ordem__grupo_maquina='montagem'
    ).exclude(ordem__maquina__id__in=maquinas_excluidas_ids) \
    .values('ordem', 'peca').distinct() \
    .aggregate(total_planejado=Coalesce(Sum('qtd_planejada', output_field=FloatField()), Value(0.0)))["total_planejado"]

    # Soma total da quantidade boa produzida
    total_finalizado = PecasOrdem.objects.filter(
        ordem__data_carga=data_carga,
        ordem__grupo_maquina='montagem'
    ).exclude(ordem__maquina__id__in=maquinas_excluidas_ids) \
    .aggregate(
        total_finalizado=Coalesce(Sum('qtd_boa', output_field=FloatField()), Value(0.0))
    )["total_finalizado"]

    # Evitar divisão por zero
    percentual_concluido = (total_finalizado / total_planejado * 100) if total_planejado > 0 else 0.0

    return JsonResponse({
        "percentual_concluido": round(percentual_concluido, 2),  # Arredonda para 2 casas decimais
        "total_planejado": total_planejado,
        "total_finalizado": total_finalizado
    })

def andamento_ultimas_cargas(request):

    # Máquinas a excluir da contagem
    maquinas_excluidas = [
        'PLAT. TANQUE. CAÇAM. 2',
        'QUALIDADE',
        'FORJARIA',
        'ESTAMPARIA',
        'Carpintaria',
        'FEIXE DE MOLAS',
        'SERRALHERIA',
    ]

    maquinas_excluidas_ids = Maquina.objects.filter(nome__in=maquinas_excluidas).values_list('id', flat=True)

    # Obtém as últimas 10 datas de carga disponíveis para pintura
    ultimas_cargas = Ordem.objects.filter(grupo_maquina='montagem')\
        .order_by('-data_carga')\
        .values_list('data_carga', flat=True)\
        .distinct()[:10]

    andamento_cargas = []
    
    for data in ultimas_cargas:
        # Soma correta da quantidade planejada (evitando duplicações)
        total_planejado = PecasOrdem.objects.filter(
            ordem__data_carga=data,
            ordem__grupo_maquina='montagem'
        ).exclude(ordem__maquina__id__in=maquinas_excluidas_ids) \
        .values('ordem', 'peca').distinct().aggregate(
            total_planejado=Coalesce(Sum('qtd_planejada', output_field=models.FloatField()), Value(0.0))
        )["total_planejado"]

        # Soma total da quantidade boa produzida
        total_finalizado = PecasOrdem.objects.filter(
            ordem__data_carga=data,
            ordem__grupo_maquina='montagem'
        ).exclude(ordem__maquina__id__in=maquinas_excluidas_ids) \
        .aggregate(
            total_finalizado=Coalesce(Sum('qtd_boa', output_field=models.FloatField()), Value(0.0))
        )["total_finalizado"]

        # Evita divisão por zero e calcula o percentual corretamente
        percentual_concluido = (total_finalizado / total_planejado * 100) if total_planejado > 0 else 0.0

        andamento_cargas.append({
            "data_carga": data.strftime("%d/%m/%Y"),
            "percentual_concluido": round(percentual_concluido, 2),
            "total_planejado": total_planejado,
            "total_finalizado": total_finalizado
        })

    return JsonResponse({"andamento_cargas": andamento_cargas})

def listar_motivos_interrupcao(request):

    motivos = MotivoInterrupcao.objects.filter(setor__nome='montagem', visivel=True)

    return JsonResponse({"motivos": list(motivos.values())})

def planejamento(request):

    motivos_maquina_parada = MotivoMaquinaParada.objects.filter(setor__nome='montagem').exclude(nome='Finalizada parcial')

    return render(request, 'apontamento_montagem/planejamento.html', {'motivos_maquina_parada': motivos_maquina_parada})


@login_required
def dashboard(request):
    maquinas = (
        Maquina.objects
        .filter(setor__nome='montagem', tipo='maquina')
        .order_by('nome')
        .values('id', 'nome')
    )
    return render(
        request,
        'dashboard/dashboard-montagem.html',
        {
            'maquinas': list(maquinas),
        }
    )


@login_required
def dashboard_data(request):
    hoje = localtime(now()).date()
    data_inicio = parse_date(request.GET.get('data_inicio') or '') or (hoje - timedelta(days=29))
    data_fim = parse_date(request.GET.get('data_fim') or '') or hoje
    maquina_id = (request.GET.get('maquina_id') or '').strip()

    if data_inicio > data_fim:
        return JsonResponse({'error': 'A data inicial nao pode ser maior que a data final.'}, status=400)

    ordens = Ordem.objects.filter(
        grupo_maquina='montagem',
        excluida=False,
        data_carga__isnull=False,
        data_carga__range=[data_inicio, data_fim],
    )

    if maquina_id:
        try:
            ordens = ordens.filter(maquina_id=int(maquina_id))
        except ValueError:
            return JsonResponse({'error': 'Maquina invalida.'}, status=400)

    pecas = PecasOrdem.objects.filter(ordem__in=ordens)
    processos = OrdemProcesso.objects.filter(
        ordem__in=ordens,
        data_inicio__date__range=[data_inicio, data_fim],
    )

    totais = pecas.aggregate(
        total_planejada=Coalesce(Sum('qtd_planejada', output_field=FloatField()), Value(0.0)),
        total_boa=Coalesce(Sum('qtd_boa', output_field=FloatField()), Value(0.0)),
        total_morta=Coalesce(Sum('qtd_morta', output_field=FloatField()), Value(0.0)),
    )

    total_planejada = float(totais['total_planejada'] or 0)
    total_boa = float(totais['total_boa'] or 0)
    total_morta = float(totais['total_morta'] or 0)
    eficiencia = round((total_boa / total_planejada) * 100, 1) if total_planejada > 0 else 0.0

    status_map = {
        'aguardando_iniciar': 'Aguardando',
        'iniciada': 'Iniciada',
        'interrompida': 'Interrompida',
        'finalizada': 'Finalizada',
        'agua_prox_proc': 'Aguardando prox.',
    }

    status_rows = (
        ordens.values('status_atual')
        .annotate(total=Count('id'))
        .order_by('status_atual')
    )
    status_chart = [
        {'label': status_map.get(row['status_atual'], row['status_atual']), 'value': row['total']}
        for row in status_rows
    ]

    # Agrupa por (maquina, ordem) para evitar multiplicar qtd_planejada
    # pelo número de aberturas da ordem
    maquina_rows = (
        pecas.values(
            nome=Coalesce(F('ordem__maquina__nome'), Value('Sem celula')),
            ordem_ref=F('ordem'),
        )
        .annotate(
            planejada=Coalesce(Avg('qtd_planejada', output_field=FloatField()), Value(0.0)),
            produzida=Coalesce(Sum('qtd_boa', output_field=FloatField()), Value(0.0)),
        )
    )

    _maquina_totals = {}
    for row in maquina_rows:
        nome = row['nome']
        if nome not in _maquina_totals:
            _maquina_totals[nome] = {'planejada': 0.0, 'produzida': 0.0}
        _maquina_totals[nome]['planejada'] += float(row['planejada'] or 0)
        _maquina_totals[nome]['produzida'] += float(row['produzida'] or 0)

    producao_por_maquina = sorted(
        [
            {'label': nome, 'planejada': v['planejada'], 'produzida': v['produzida']}
            for nome, v in _maquina_totals.items()
        ],
        key=lambda x: (-x['produzida'], -x['planejada'])
    )[:8]

    # Agrupa por (carga_data, ordem) para evitar multiplicar qtd_planejada
    # pelo número de aberturas da ordem (cada abertura cria um novo PecasOrdem)
    carga_rows = (
        pecas.values(carga_data=F('ordem__data_carga'), ordem_ref=F('ordem'))
        .annotate(
            planejada=Coalesce(Avg('qtd_planejada', output_field=FloatField()), Value(0.0)),
            produzida=Coalesce(Sum('qtd_boa', output_field=FloatField()), Value(0.0)),
        )
        .order_by('carga_data')
    )

    _carga_totals = {}
    for row in carga_rows:
        data = row['carga_data']
        if data not in _carga_totals:
            _carga_totals[data] = {'planejada': 0.0, 'produzida': 0.0}
        _carga_totals[data]['planejada'] += float(row['planejada'] or 0)
        _carga_totals[data]['produzida'] += float(row['produzida'] or 0)

    andamento_cargas = []
    for data in sorted(_carga_totals):
        planejada = _carga_totals[data]['planejada']
        produzida = _carga_totals[data]['produzida']
        percentual = round((produzida / planejada) * 100, 1) if planejada > 0 else 0.0
        andamento_cargas.append({
            'label': data.strftime('%d/%m') if data else '-',
            'planejada': planejada,
            'produzida': produzida,
            'percentual': percentual,
        })

    atividade_rows = (
        processos.annotate(dia=TruncDate('data_inicio'))
        .values('dia', 'status')
        .annotate(total=Count('id'))
        .order_by('dia', 'status')
    )
    atividade_lookup = {}
    for row in atividade_rows:
        atividade_lookup.setdefault(row['dia'], {})[row['status']] = row['total']

    atividade_diaria = []
    cursor = data_inicio
    while cursor <= data_fim:
        dia_data = atividade_lookup.get(cursor, {})
        atividade_diaria.append({
            'label': cursor.strftime('%d/%m'),
            'iniciada': dia_data.get('iniciada', 0),
            'interrompida': dia_data.get('interrompida', 0),
            'finalizada': dia_data.get('finalizada', 0),
        })
        cursor += timedelta(days=1)

    # Agrupa por (peca, ordem) para evitar multiplicar qtd_planejada pelo nº de aberturas da ordem
    per_order_rows = (
        pecas.values('peca', 'ordem')
        .annotate(
            produzida=Coalesce(Sum('qtd_boa', output_field=FloatField()), Value(0.0)),
            morta=Coalesce(Sum('qtd_morta', output_field=FloatField()), Value(0.0)),
            # Avg porque todos os registros de uma mesma ordem têm o mesmo qtd_planejada
            planejada=Coalesce(Avg('qtd_planejada', output_field=FloatField()), Value(0.0)),
        )
    )

    from collections import defaultdict
    _peca_totals = defaultdict(lambda: {'produzida': 0.0, 'morta': 0.0, 'planejada': 0.0})
    for row in per_order_rows:
        p = row['peca']
        _peca_totals[p]['produzida'] += float(row['produzida'] or 0)
        _peca_totals[p]['morta']     += float(row['morta'] or 0)
        _peca_totals[p]['planejada'] += float(row['planejada'] or 0)

    top_conjuntos = sorted(
        [
            {'nome': peca, 'produzida': v['produzida'], 'morta': v['morta'], 'planejada': v['planejada']}
            for peca, v in _peca_totals.items()
        ],
        key=lambda x: (-x['produzida'], -x['planejada'])
    )[:8]

    interruption_rows = (
        processos.filter(status='interrompida')
        .values('motivo_interrupcao__nome', 'ordem__maquina__nome')
        .annotate(
            total=Count('id'),
            ultima=Max('data_inicio'),
        )
        .order_by('-total', '-ultima')[:8]
    )
    interruption_ranking = [
        {
            'motivo': row['motivo_interrupcao__nome'] or 'Sem motivo',
            'maquina': row['ordem__maquina__nome'] or 'Sem celula',
            'total': row['total'],
            'ultima': localtime(row['ultima']).strftime('%d/%m %H:%M') if row['ultima'] else '-',
        }
        for row in interruption_rows
    ]

    falta_peca_queryset = PecasFaltantes.objects.filter(
        ordem__in=ordens,
        data_registro__date__range=[data_inicio, data_fim],
    )
    falta_peca_rows = (
        falta_peca_queryset
        .values('nome_peca')
        .annotate(
            ocorrencias=Count('id'),
            ordens=Count('ordem_id', distinct=True),
            quantidade_total=Coalesce(Sum('quantidade', output_field=FloatField()), Value(0.0)),
            ultima=Max('data_registro'),
        )
        .order_by('-ocorrencias', '-quantidade_total', 'nome_peca')[:12]
    )
    falta_peca_items = []
    for row in falta_peca_rows:
        base_qs = falta_peca_queryset.filter(nome_peca=row['nome_peca'])

        celulas = list(
            base_qs
            .exclude(ordem__maquina__nome__isnull=True)
            .exclude(ordem__maquina__nome__exact='')
            .values_list('ordem__maquina__nome', flat=True)
            .distinct()
            .order_by('ordem__maquina__nome')
        )

        conjuntos = list(
            base_qs
            .exclude(ordem__ordem_pecas_montagem__peca__isnull=True)
            .exclude(ordem__ordem_pecas_montagem__peca__exact='')
            .values_list('ordem__ordem_pecas_montagem__peca', flat=True)
            .distinct()
            .order_by('ordem__ordem_pecas_montagem__peca')
        )

        falta_peca_items.append({
            'nome_peca': row['nome_peca'] or 'Sem descricao',
            'ocorrencias': row['ocorrencias'],
            'ordens': row['ordens'],
            'quantidade_total': float(row['quantidade_total'] or 0),
            'ultima': localtime(row['ultima']).strftime('%d/%m %H:%M') if row['ultima'] else '-',
            'celulas': celulas,
            'conjuntos': conjuntos,
        })

    payload = {
        'periodo': {
            'data_inicio': data_inicio.isoformat(),
            'data_fim': data_fim.isoformat(),
        },
        'kpis': {
            'ordens_total': ordens.count(),
            'ordens_abertas': ordens.exclude(status_atual='finalizada').count(),
            'ordens_finalizadas': ordens.filter(status_atual='finalizada').count(),
            'ordens_interrompidas': ordens.filter(status_atual='interrompida').count(),
            'maquinas_ativas': ordens.filter(status_atual__in=['iniciada', 'interrompida']).exclude(maquina_id__isnull=True).values('maquina_id').distinct().count(),
            'cargas_programadas': ordens.values('data_carga').distinct().count(),
            'conjuntos_produzidos': pecas.filter(qtd_boa__gt=0).values('peca').distinct().count(),
            'pecas_planejadas': round(total_planejada, 1),
            'pecas_boas': round(total_boa, 1),
            'pecas_mortas': round(total_morta, 1),
            'eficiencia': eficiencia,
        },
        'charts': {
            'status': status_chart,
            'producao_por_maquina': producao_por_maquina,
            'andamento_cargas': andamento_cargas,
            'atividade_diaria': atividade_diaria,
        },
        'top_conjuntos': top_conjuntos,
        'interruption_ranking': interruption_ranking,
        'falta_peca_items': falta_peca_items,
    }

    return JsonResponse(payload)

def buscar_maquinas(request):

    maquinas = Maquina.objects.filter(setor__nome='montagem', tipo='maquina').values('id','nome')

    return JsonResponse({"maquinas":list(maquinas)})

def listar_conjuntos(request):
    """
    API para listar os conjuntos disponíveis para o setor de montagem.
    Aceita um parâmetro de busca opcional: ?termo=texto
    """
    termo = request.GET.get('termo', '').strip()

    if termo:
        conjuntos = Conjuntos.objects.filter(
            Q(codigo__icontains=termo) | Q(descricao__icontains=termo)
        ).values('id', 'codigo', 'descricao')
    else:
        conjuntos = Conjuntos.objects.values('id', 'codigo', 'descricao')

    return JsonResponse({"conjuntos": list(conjuntos)})

def listar_pecas_disponiveis(request):
    """
    Retorna uma lista de peças disponíveis (Pecas) para um Conjunto específico, 
    usando a coluna de código puro.
    """
    
    conjunto_input = request.GET.get('conjunto')
    if not conjunto_input:
        return JsonResponse({'erro': 'Parâmetro "conjunto" é obrigatório.'}, status=400)

    try:
        codigo_conjunto_param = conjunto_input.split(' - ')[0].strip()
    except IndexError:
        return JsonResponse({'erro': 'Formato de "conjunto" inválido. Esperado: "CODIGO - NOME".'}, status=400)
    
    pecas = (
        CarretasExplodidas.objects
        .filter(conjunto_peca__contains=codigo_conjunto_param)
        .exclude(descricao_peca__isnull=True)
        .exclude(descricao_peca__exact='')
        .values('descricao_peca')
        .distinct()
        .order_by('descricao_peca')
    )

    if pecas is None:
        return JsonResponse({'erro': 'Dados da base não disponíveis.'}, status=503)

    return JsonResponse({'pecas': list(pecas), 'conjunto_filtrado': codigo_conjunto_param}, status=200)

@csrf_exempt
def criar_ordem_fora_sequenciamento(request):

    """
    API para criar uma ordem fora do sequenciamento.
    Verifica se o conjunto escolhido ja tem na data de carga escolhida.
    Caso tenha, apenas acrescenta na quantidade planejada.
    Caso não tenha, cria uma nova ordem com a quantidade planejada.
    """

    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)

    data = json.loads(request.body)

    conjunto = data.get('peca')
    codigo_conjunto = data.get('peca').split(" - ", maxsplit=1)[0]  # Pega apenas o código do conjunto
    quantidade_planejada = data.get('quantidade')
    maquina = data.get('setor')
    data_carga = data.get('dataCarga')
    obs = data.get('observacao')

    ordens_existentes = Ordem.objects.filter(
        data_carga=data_carga,
        grupo_maquina='montagem',
        ordem_pecas_montagem__peca__contains=codigo_conjunto
    ).values_list('id', flat=True)

    if ordens_existentes:
        ordem = Ordem.objects.get(id=ordens_existentes[0])
        ordem.status_atual = 'aguardando_iniciar' if ordem.status_atual == 'finalizada' else ordem.status_atual
        ordem.save()
        pecas = PecasOrdem.objects.filter(ordem=ordem, peca__contains=codigo_conjunto)
        for peca in pecas:
            peca.qtd_planejada += int(quantidade_planejada)
            peca.save()
        return JsonResponse({'message': 'Quantidade planejada atualizada com sucesso!'})

    else:
        maquina = get_object_or_404(Maquina, pk=maquina)
        ordem = Ordem.objects.create(
            grupo_maquina='montagem',
            status_atual='aguardando_iniciar',
            data_carga=datetime.strptime(data_carga, '%Y-%m-%d').date(),
            maquina=maquina
        )  
        PecasOrdem.objects.create(
            ordem=ordem,
            peca=conjunto,
            qtd_planejada=quantidade_planejada,
            qtd_boa=0,
            qtd_morta=0
        )
        return JsonResponse({'message': 'Ordem criada com sucesso!'})

def api_ordens_finalizadas(request):
    def format_data(dt):
        if isinstance(dt, (datetime, date)):
            return dt.strftime("%d/%m/%Y")
        return ""

    def format_data_hora(dt):
        if isinstance(dt, (datetime, date)):
            data_final = dt - timedelta(hours=3) 
            return data_final.strftime("%d/%m/%Y %H:%M")
        return ""

    hoje = localtime(now()).date()

    data_inicio_str = request.GET.get('data_inicio')
    data_fim_str = request.GET.get('data_fim')

    try:
        data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date() if data_inicio_str else hoje - timedelta(days=1)
        data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date() if data_fim_str else hoje
    except ValueError:
        return JsonResponse({'erro': 'Formato de data inválido. Use YYYY-MM-DD.'}, status=400)

    final_results = []
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                o.ordem,
                m.nome AS maquina,
                po.peca AS conjunto,
                po.qtd_boa AS total_produzido,
                o.data_carga,
                co.data_fim AS data_finalizacao,
                concat(op.matricula, ' - ', op.nome) AS operador,
                o.obs_operador AS obs
            FROM apontamento_v2.core_ordem o
            LEFT JOIN apontamento_v2.cadastro_maquina m ON m.id = o.maquina_id
            LEFT JOIN apontamento_v2.cadastro_operador op ON op.id = o.operador_final_id
            INNER JOIN apontamento_v2.apontamento_montagem_pecasordem po ON o.id = po.ordem_id
            INNER JOIN apontamento_v2.core_ordemprocesso co on co.id = po.processo_ordem_id
            WHERE
                (co.data_fim - INTERVAL '3 hours')::date BETWEEN %s AND %s
                AND po.qtd_boa > 0
            ORDER BY co.data_fim;
        """, [data_inicio, data_fim])

        for row in cursor:
            ordem, maquina, conjunto, total_produzido, data_carga, data_finalizacao, operador, obs = row
            conjunto = conjunto or ''
            partes = conjunto.split(' - ', maxsplit=1)

            if len(partes) == 2:
                codigo = partes[0].strip()
                descricao = partes[1].strip()
                if descricao.startswith(codigo):
                    descricao = descricao[len(codigo):].strip(" -")
            else:
                codigo = conjunto.strip()
                descricao = ""

            final_results.append({
                'ordem': ordem,
                'maquina': maquina,
                'codigo': codigo,
                'descricao': descricao,
                'total_produzido': total_produzido,
                'data_carga': format_data(data_carga),
                'data_finalizacao': format_data_hora(data_finalizacao),
                'operador': operador,
                'obs': obs,
            })

    return JsonResponse(final_results, safe=False)

def _api_tempos_legacy(request):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT 
                o.id as id_ordem,
                o.ordem AS ordem,
                po.peca AS codigo,
                po.peca AS descricao,
                op.data_inicio,
                op.data_fim,
                o.data_carga,
                po.qtd_planejada AS qt_planejada,
                m.nome AS celula,
                op.status,
                po.qtd_boa AS qt_boa
            FROM apontamento_v2.core_ordem o
            LEFT JOIN apontamento_v2.core_ordemprocesso op ON op.ordem_id = o.id
            LEFT JOIN apontamento_v2.apontamento_montagem_pecasordem po ON po.processo_ordem_id = op.id
            LEFT JOIN apontamento_v2.cadastro_maquina m ON o.maquina_id = m.id
            WHERE o.grupo_maquina = 'montagem' AND op.data_inicio IS NOT NULL
            ORDER BY o.ordem, op.data_inicio
        """)
        columns = [col[0] for col in cursor.description]
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]

    # Reverso: de baixo pra cima
    last_by_ordem = {}

    for i in reversed(range(len(results))):
        row = results[i]
        ordem_id = row['id_ordem']

        if ordem_id not in last_by_ordem:
            # Armazena os últimos dados conhecidos (mais abaixo na lista)
            last_by_ordem[ordem_id] = {
                'codigo': row['codigo'],
                'descricao': row['descricao'],
                'qt_planejada': row['qt_planejada'],
                'qt_boa': row['qt_boa'],
            }
        else:
            # Preenche se estiver nulo
            for field in ['codigo', 'descricao', 'qt_planejada', 'qt_boa']:
                if row[field] in (None, ''):
                    row[field] = last_by_ordem[ordem_id][field]
                else:
                    # Atualiza valor "mais recente"
                    last_by_ordem[ordem_id][field] = row[field]

    return JsonResponse(results, safe=False)

def api_tempos(request):
    started_at = now()

    def parse_positive_int(value, default):
        try:
            parsed = int(value)
            return parsed if parsed > 0 else default
        except (TypeError, ValueError):
            return default

    page = parse_positive_int(request.GET.get('page'), 1)
    limit = min(parse_positive_int(request.GET.get('limit'), 100), 500)
    offset = (page - 1) * limit

    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    ordem = request.GET.get('ordem')
    maquina = (request.GET.get('maquina') or '').strip()
    status = (request.GET.get('status') or '').strip()

    current_piece = PecasOrdem.objects.filter(
        processo_ordem_id=OuterRef('pk')
    ).order_by('-id')
    latest_piece_for_order = PecasOrdem.objects.filter(
        ordem_id=OuterRef('ordem_id')
    ).order_by('-processo_ordem__data_inicio', '-id')
    total_qt_boa_for_order = (
        PecasOrdem.objects
        .filter(ordem_id=OuterRef('ordem_id'))
        .values('ordem_id')
        .annotate(total_qt_boa=Coalesce(Sum('qtd_boa', output_field=FloatField()), Value(0.0)))
        .values('total_qt_boa')
    )

    queryset = (
        OrdemProcesso.objects
        .filter(
            ordem__grupo_maquina='montagem',
            data_inicio__isnull=False,
        )
        .select_related('ordem', 'ordem__maquina')
        .annotate(
            current_peca=Subquery(current_piece.values('peca')[:1]),
            current_qt_planejada=Subquery(current_piece.values('qtd_planejada')[:1]),
            latest_peca=Subquery(latest_piece_for_order.values('peca')[:1]),
            latest_qt_planejada=Subquery(latest_piece_for_order.values('qtd_planejada')[:1]),
            descricao=Coalesce(F('current_peca'), F('latest_peca'), Value('')),
            qt_planejada=Coalesce(F('current_qt_planejada'), F('latest_qt_planejada')),
            qt_boa=Coalesce(Subquery(total_qt_boa_for_order[:1]), Value(0.0)),
            celula=F('ordem__maquina__nome'),
            ordem_numero=F('ordem__ordem'),
            ordem_data_carga=F('ordem__data_carga'),
        )
    )

    if data_inicio:
        parsed_data_inicio = parse_date(data_inicio)
        if parsed_data_inicio is None:
            return JsonResponse({'error': 'data_inicio inválida. Use YYYY-MM-DD.'}, status=400)
        queryset = queryset.filter(data_inicio__date__gte=parsed_data_inicio)

    if data_fim:
        parsed_data_fim = parse_date(data_fim)
        if parsed_data_fim is None:
            return JsonResponse({'error': 'data_fim inválida. Use YYYY-MM-DD.'}, status=400)
        queryset = queryset.filter(data_inicio__date__lte=parsed_data_fim)

    if ordem:
        try:
            queryset = queryset.filter(ordem__ordem=int(ordem))
        except ValueError:
            return JsonResponse({'error': 'ordem inválida. Use um número inteiro.'}, status=400)

    if maquina:
        maquina_filter = Q(ordem__maquina__nome__icontains=maquina)
        if maquina.isdigit():
            maquina_filter |= Q(ordem__maquina__id=int(maquina))
        queryset = queryset.filter(maquina_filter)

    if status:
        queryset = queryset.filter(status=status)

    total = queryset.count()
    rows = list(
        queryset
        .order_by('-data_inicio', '-id')
        .values(
            'ordem_id',
            'ordem_numero',
            'descricao',
            'data_inicio',
            'data_fim',
            'ordem_data_carga',
            'qt_planejada',
            'celula',
            'status',
            'qt_boa',
        )[offset:offset + limit]
    )

    items = []
    for row in rows:
        items.append({
            'ordem_id': row['ordem_id'],
            'ordem': row['ordem_numero'],
            'codigo': _extrair_codigo_peca(row['descricao']),
            'descricao': row['descricao'],
            'data_inicio': row['data_inicio'].isoformat() if row['data_inicio'] else None,
            'data_fim': row['data_fim'].isoformat() if row['data_fim'] else None,
            'data_carga': row['ordem_data_carga'].isoformat() if row['ordem_data_carga'] else None,
            'qt_planejada': row['qt_planejada'],
            'celula': row['celula'],
            'status': row['status'],
            'qt_boa': row['qt_boa'],
        })

    duration_ms = int((now() - started_at).total_seconds() * 1000)
    logger.info(
        "montagem.api_tempos page=%s limit=%s total=%s returned=%s duration_ms=%s filtros=%s",
        page,
        limit,
        total,
        len(items),
        duration_ms,
        {
            'data_inicio': data_inicio,
            'data_fim': data_fim,
            'ordem': ordem,
            'maquina': maquina,
            'status': status,
        }
    )

    return JsonResponse({
        'items': items,
        'page': page,
        'limit': limit,
        'total': total,
        'has_next': offset + len(items) < total,
    })

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
            ordem_process = OrdemProcesso.objects.filter(ordem_id=ordem_id).last()

            ordem_process.delete()
            
            updated_count = Ordem.objects.filter(id=ordem_id).update(
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

@login_required
def tempo_medio_fabricacao(request):
    """
    Retorna o tempo médio de fabricação por produto no setor de montagem.

    Calcula somando apenas os períodos com status='iniciada' e data_fim preenchida
    (tempo efetivo de produção, excluindo interrupções). Agrega por ordem e depois
    tira a média por produto.

    Parâmetros GET:
      - data_inicio / data_fim : intervalo de data_inicio do processo (default: últimos 30 dias)
      - maquina_id             : filtra por célula (opcional)
      - apenas_finalizadas     : '1' para incluir só ordens finalizadas (default: '1')
      - min_ordens             : mínimo de ordens para aparecer no resultado (default: 1)
      - limit                  : máximo de itens retornados (default: 30)
    """
    from collections import defaultdict

    hoje = localtime(now()).date()
    data_inicio = parse_date(request.GET.get('data_inicio') or '') or (hoje - timedelta(days=29))
    data_fim    = parse_date(request.GET.get('data_fim') or '') or hoje
    maquina_id  = (request.GET.get('maquina_id') or '').strip()
    apenas_fin  = request.GET.get('apenas_finalizadas', '1') == '1'
    min_ordens  = max(1, int(request.GET.get('min_ordens') or 1))
    limit       = min(int(request.GET.get('limit') or 30), 500)

    if data_inicio > data_fim:
        return JsonResponse({'error': 'data_inicio não pode ser maior que data_fim.'}, status=400)

    ordens_qs = Ordem.objects.filter(grupo_maquina='montagem', excluida=False)
    if apenas_fin:
        ordens_qs = ordens_qs.filter(status_atual='finalizada')
    if maquina_id:
        try:
            ordens_qs = ordens_qs.filter(maquina_id=int(maquina_id))
        except ValueError:
            return JsonResponse({'error': 'maquina_id inválido.'}, status=400)

    # Subquery: pega o nome do produto da primeira PecasOrdem da ordem
    peca_subquery = (
        PecasOrdem.objects
        .filter(ordem=OuterRef('ordem'))
        .order_by('id')
        .values('peca')[:1]
    )

    # Processos finalizados — todo o histórico, sem filtro de data
    processos_qs = (
        OrdemProcesso.objects
        .filter(
            ordem__in=ordens_qs,
            status='iniciada',
            data_fim__isnull=False,
            data_inicio__isnull=False,
        )
        .annotate(peca=Subquery(peca_subquery))
        .values('ordem_id', 'peca', 'data_inicio', 'data_fim')
    )

    # qtd_boa total por ordem (soma de todas as PecasOrdem da ordem)
    qtd_boa_por_ordem = {
        row['ordem_id']: float(row['total_boa'] or 0)
        for row in PecasOrdem.objects
            .filter(ordem__in=ordens_qs)
            .values('ordem_id')
            .annotate(total_boa=Sum('qtd_boa', output_field=FloatField()))
    }

    # Soma duração por ordem
    ordem_data = defaultdict(lambda: {'duracao_seg': 0.0, 'peca': ''})
    for p in processos_qs:
        duracao = (p['data_fim'] - p['data_inicio']).total_seconds()
        if duracao <= 0:
            continue
        ordem_data[p['ordem_id']]['duracao_seg'] += duracao
        if not ordem_data[p['ordem_id']]['peca']:
            ordem_data[p['ordem_id']]['peca'] = p['peca'] or ''

    # Agrega por produto — tempo por lote e por unidade
    peca_stats = defaultdict(lambda: {
        'total_seg_lote': 0.0,
        'total_seg_unidade': 0.0,
        'count_lote': 0,
        'count_unidade': 0,
    })
    for ordem_id, dados in ordem_data.items():
        peca = dados['peca']
        if not peca:
            continue
        seg = dados['duracao_seg']
        # tempo por lote (toda ordem conta)
        peca_stats[peca]['total_seg_lote'] += seg
        peca_stats[peca]['count_lote']     += 1
        # tempo por unidade (só ordens com produção registrada)
        qtd = qtd_boa_por_ordem.get(ordem_id, 0)
        if qtd > 0:
            peca_stats[peca]['total_seg_unidade'] += seg / qtd
            peca_stats[peca]['count_unidade']     += 1

    def seg_para_hm(seg):
        seg = int(seg)
        h, m = divmod(seg // 60, 60)
        return f'{h}h {m:02d}min' if h else f'{m}min'

    items = []
    for peca, v in peca_stats.items():
        if v['count_lote'] < min_ordens:
            continue
        media_lote_seg     = v['total_seg_lote'] / v['count_lote']
        media_unidade_seg  = (
            v['total_seg_unidade'] / v['count_unidade']
            if v['count_unidade'] > 0 else None
        )
        items.append({
            'peca': peca,
            'media_lote_formatado':    seg_para_hm(media_lote_seg),
            'media_unidade_formatado': seg_para_hm(media_unidade_seg) if media_unidade_seg else '-',
            'media_lote_minutos':      round(media_lote_seg / 60, 1),
            'ordens': v['count_lote'],
        })

    items.sort(key=lambda x: (-x['ordens'], x['media_lote_minutos']))

    return JsonResponse({'items': items[:limit], 'total': len(items)})


@login_required
def takt_time_data(request):
    """
    Calcula takt time e tempo de ciclo real por célula de montagem.

    Parâmetros GET:
      - data_inicio / data_fim : período planejado — filtra ordens por data_carga
      - qt_carretas            : quantidade de carretas planejadas (default: 1)
      - tempo_disp_min         : tempo disponível em minutos (default: 540 = 9h)

    O ciclo histórico é calculado sobre todos os apontamentos já realizados (sem filtro de data).
    """
    from collections import defaultdict

    hoje = localtime(now()).date()
    data_inicio = parse_date(request.GET.get('data_inicio') or '') or hoje
    data_fim    = parse_date(request.GET.get('data_fim') or '') or hoje

    try:
        qt_carretas = max(1, int(request.GET.get('qt_carretas') or 1))
    except (ValueError, TypeError):
        return JsonResponse({'error': 'qt_carretas inválido.'}, status=400)

    try:
        tempo_disp_min = max(1.0, float(request.GET.get('tempo_disp_min') or 540))
    except (ValueError, TypeError):
        return JsonResponse({'error': 'tempo_disp_min inválido.'}, status=400)

    if data_inicio > data_fim:
        return JsonResponse({'error': 'data_inicio não pode ser maior que data_fim.'}, status=400)

    takt_time_min = tempo_disp_min / qt_carretas

    # IDs das máquinas excluídas permanentemente do cálculo
    excluidas_ids = set(
        TaktCelulaExcluida.objects.values_list('maquina_id', flat=True)
    )

    ordens_qs = Ordem.objects.filter(grupo_maquina='montagem', excluida=False)

    peca_subquery = (
        PecasOrdem.objects
        .filter(ordem=OuterRef('ordem'))
        .order_by('id')
        .values('peca')[:1]
    )

    # Ciclo histórico: apenas ordens FINALIZADAS (mesmo critério do Tempo Médio de Fabricação)
    # Ordens em andamento ou interrompidas distorcem o ciclo (tempo parcial / qty incompleta)
    ordens_finalizadas_qs = ordens_qs.filter(status_atual='finalizada')

    processos = list(
        OrdemProcesso.objects
        .filter(
            ordem__in=ordens_finalizadas_qs,
            status='iniciada',
            data_fim__isnull=False,
            data_inicio__isnull=False,
        )
        .exclude(ordem__maquina_id__in=excluidas_ids)
        .annotate(peca=Subquery(peca_subquery))
        .values(
            'ordem_id', 'peca', 'data_inicio', 'data_fim',
            'ordem__maquina__nome',
        )
    )

    qtd_boa_por_ordem = {
        row['ordem_id']: float(row['total_boa'] or 0)
        for row in (
            PecasOrdem.objects
            .filter(ordem__in=ordens_finalizadas_qs)
            .values('ordem_id')
            .annotate(total_boa=Sum('qtd_boa', output_field=FloatField()))
        )
    }

    # maquina_nome -> ordem_id -> {duracao_seg, peca}
    maq_ordem = defaultdict(dict)
    for p in processos:
        duracao = (p['data_fim'] - p['data_inicio']).total_seconds()
        if duracao <= 0:
            continue
        maq = p['ordem__maquina__nome'] or 'Sem célula'
        oid = p['ordem_id']
        if oid not in maq_ordem[maq]:
            maq_ordem[maq][oid] = {'duracao_seg': 0.0, 'peca': p['peca'] or ''}
        maq_ordem[maq][oid]['duracao_seg'] += duracao
        if not maq_ordem[maq][oid]['peca']:
            maq_ordem[maq][oid]['peca'] = p['peca'] or ''

    cells = []
    total_cycle_time = 0.0

    for maq_nome, ordens in maq_ordem.items():
        peca_per_unit = defaultdict(list)
        all_per_unit = []
        for oid, dados in ordens.items():
            peca = dados['peca'] or 'Sem produto'
            qtd = qtd_boa_por_ordem.get(oid, 0)
            if qtd > 0:
                per_unit = dados['duracao_seg'] / qtd / 60
                peca_per_unit[peca].append(per_unit)
                all_per_unit.append(per_unit)

        if not all_per_unit:
            continue

        # Tempo de ciclo da célula = média geral de todas as ordens
        cell_cycle = sum(all_per_unit) / len(all_per_unit)

        # Breakdown por produto (para empilhamento no gráfico)
        conjuntos = []
        for peca_nome, times in peca_per_unit.items():
            avg = sum(times) / len(times)
            conjuntos.append({
                'nome': peca_nome,
                'cycle_time_min': round(avg, 2),
                'ordens': len(times),
            })
        conjuntos.sort(key=lambda x: -x['cycle_time_min'])

        cells.append({
            'nome': maq_nome,
            'cycle_time_min': round(cell_cycle, 2),
            'conjuntos': conjuntos,
            'num_ordens': len(ordens),
        })
        total_cycle_time += cell_cycle

    cells.sort(key=lambda x: x['nome'])

    num_operadores = round(total_cycle_time / takt_time_min, 1) if takt_time_min > 0 else 0

    # Ciclo médio global por peça (independe de célula) — usado como fallback.
    # Indexado também pelo código numérico (antes do " - ") para resolver casos
    # onde o planejado usa só o código ("030493") mas o histórico tem
    # o nome completo ("030493 - CHASSI 2 EIXOS RS/RD SS").
    peca_global = defaultdict(list)
    for maq_nome, ordens in maq_ordem.items():
        for oid, dados in ordens.items():
            peca = dados['peca'] or 'Sem produto'
            qtd = qtd_boa_por_ordem.get(oid, 0)
            if qtd > 0:
                peca_global[peca].append(dados['duracao_seg'] / qtd / 60)

    cycle_by_peca = {}
    for peca, times in peca_global.items():
        avg = round(sum(times) / len(times), 2)
        cycle_by_peca[peca] = avg
        # alias pelo código (parte antes de " - "), se existir
        codigo = peca.split(' - ')[0].strip()
        if codigo and codigo != peca and codigo not in cycle_by_peca:
            cycle_by_peca[codigo] = avg

    # Produção planejada no período (ordens com data_carga dentro do range).
    # Buscamos uma linha por ordem (via subquery) para não somar qtd_planejada
    # de múltiplos registros PecasOrdem da mesma ordem (um por operador/sessão).
    peca_plan_subq = (
        PecasOrdem.objects
        .filter(ordem=OuterRef('pk'))
        .order_by('id')
        .values('peca')[:1]
    )
    qtd_plan_subq = (
        PecasOrdem.objects
        .filter(ordem=OuterRef('pk'))
        .order_by('id')
        .values('qtd_planejada')[:1]
    )

    planned_rows = (
        Ordem.objects
        .filter(
            grupo_maquina='montagem',
            excluida=False,
            data_carga__range=[data_inicio, data_fim],
            maquina__isnull=False,
        )
        .exclude(maquina_id__in=excluidas_ids)
        .annotate(
            peca_nome=Subquery(peca_plan_subq),
            qtd_ordem=Subquery(qtd_plan_subq, output_field=FloatField()),
        )
        .values('maquina__nome', 'peca_nome')
        .annotate(qtd_total=Sum('qtd_ordem', output_field=FloatField()))
        .order_by('maquina__nome', 'peca_nome')
    )

    planned_by_cell = defaultdict(list)
    for row in planned_rows:
        cell_name = row['maquina__nome'] or 'Sem célula'
        planned_by_cell[cell_name].append({
            'peca': row['peca_nome'] or '—',
            'qtd_planejada': float(row['qtd_total'] or 0),
        })

    orders_count_by_cell = dict(
        Ordem.objects
        .filter(
            grupo_maquina='montagem',
            excluida=False,
            data_carga__range=[data_inicio, data_fim],
            maquina__isnull=False,
        )
        .exclude(maquina_id__in=excluidas_ids)
        .values('maquina__nome')
        .annotate(count=Count('id'))
        .values_list('maquina__nome', 'count')
    )

    planned_cells = [
        {'cell': c, 'pecas': sorted(p, key=lambda x: x['peca']), 'num_ordens': orders_count_by_cell.get(c, 0)}
        for c, p in sorted(planned_by_cell.items())
    ]

    # Todas as células de montagem para exibir no painel de configuração
    from cadastro.models import Maquina
    todas_celulas = list(
        Maquina.objects
        .filter(setor__nome__icontains='montagem')
        .order_by('nome')
        .values('id', 'nome')
    )

    return JsonResponse({
        'takt_time_min': round(takt_time_min, 2),
        'qt_carretas': qt_carretas,
        'tempo_disp_min': round(tempo_disp_min, 1),
        'cells': cells,
        'num_operadores_necessarios': num_operadores,
        'total_cycle_time_min': round(total_cycle_time, 2),
        'planned_production': planned_cells,
        'planned_period': {'data_inicio': str(data_inicio), 'data_fim': str(data_fim)},
        'celulas_excluidas': list(excluidas_ids),
        'todas_celulas': todas_celulas,
        'cycle_by_peca': cycle_by_peca,
    })


@csrf_exempt
def takt_toggle_celula_excluida(request):
    """POST {'maquina_id': id} — inclui ou exclui a célula do cálculo de takt time."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido.'}, status=405)
    try:
        body = json.loads(request.body)
        maquina_id = int(body.get('maquina_id', 0))
    except (ValueError, TypeError):
        return JsonResponse({'error': 'maquina_id inválido.'}, status=400)

    from cadastro.models import Maquina
    maquina = get_object_or_404(Maquina, pk=maquina_id)
    obj, created = TaktCelulaExcluida.objects.get_or_create(maquina=maquina)
    if not created:
        obj.delete()
        return JsonResponse({'status': 'incluida', 'maquina_id': maquina_id})
    return JsonResponse({'status': 'excluida', 'maquina_id': maquina_id})


def apontamento_qrcode(request):
    return render(request, 'apontamento_montagem/apontamento_qrcode.html')


@login_required
def erp_apontamentos_montagem(request):
    return render(request, "apontamento_montagem/erp_apontamentos_montagem.html")


@login_required
@require_GET
def api_erp_apontamentos_montagem(request):
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
            ordem__grupo_maquina='montagem',
        )
        .select_related('ordem', 'ordem__maquina', 'ordem__operador_final', 'operador', 'resp_apontamento')
        .annotate(
            # Data real de finalizacao/producao: prioriza a data da transicao
            # para "finalizada" (processo_ordem.data_inicio), depois a data em
            # que o apontamento foi confirmado, e so por ultimo a data de
            # criacao do registro (que reflete quando a ordem foi iniciada).
            data_producao_real=Coalesce('processo_ordem__data_inicio', 'data_apontamento', 'data'),
            ordem_ja_apontada=Exists(subquery_ordem_apontada),
            ordem_item_apontado_id=Subquery(subquery_ordem_apontada.values('id')[:1]),
            ordem_tipo_apontamento=Subquery(subquery_ordem_apontada.values('tipo_apontamento')[:1]),
            ordem_data_apontamento_ref=Subquery(subquery_ordem_apontada.values('data_apontamento')[:1]),
            ordem_chave_apontamento_ref=Subquery(subquery_ordem_apontada.values('chave_apontamento')[:1]),
            ordem_resp_username_ref=Subquery(subquery_ordem_apontada.values('resp_apontamento__username')[:1]),
        )
        .filter(data_producao_real__date__gte=date(2026, 6, 24))
        .order_by('data_producao_real', 'id')
    )

    if filtros['ordem']:
        queryset = queryset.filter(ordem__ordem__icontains=filtros['ordem'])

    if filtros['peca']:
        queryset = queryset.filter(peca__icontains=filtros['peca'])

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
        queryset = queryset.filter(data_producao_real__date__gte=data_producao_inicio)
    if data_producao_fim:
        queryset = queryset.filter(data_producao_real__date__lte=data_producao_fim)

    paginator = Paginator(queryset, limit)
    pagina = paginator.get_page(page)

    itens = []
    for item in pagina.object_list:
        resp = item.resp_apontamento
        operador = item.operador or (item.ordem.operador_final if item.ordem else None)
        peca_codigo = _extrair_codigo_peca(item.peca)
        peca_descricao = _extrair_descricao_peca(item.peca)

        itens.append({
            'id': item.id,
            'ordem_id': item.ordem_id,
            'ordem': item.ordem.ordem if item.ordem else '',
            'obs_operador': item.ordem.obs_operador if item.ordem else '',
            'peca_codigo': peca_codigo,
            'peca_descricao': peca_descricao,
            'qtd_boa': item.qtd_boa,
            'qtd_morta': item.qtd_morta,
            'qtd_planejada': item.qtd_planejada,
            'maquina': item.ordem.maquina.nome if item.ordem and item.ordem.maquina else '',
            'operador': f"{operador.matricula} - {operador.nome}" if operador else '',
            'apontado': item.apontado,
            'tipo_apontamento': item.tipo_apontamento or '',
            'chave_apontamento': item.chave_apontamento or '',
            'erro_apontamento': item.erro_apontamento or '',
            'resp_apontamento': _nome_responsavel_apontamento(resp),
            'resp_apontamento_username': resp.username if resp else '',
            'data_producao': localtime(item.data_producao_real).strftime('%d/%m/%Y %H:%M') if item.data_producao_real else '',
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
def api_erp_apontar_item_montagem(request, pk):
    try:
        body = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        body = {}

    tipo_apontamento = (body.get('tipo_apontamento') or 'manual').strip().lower()
    if tipo_apontamento not in ('manual', 'api'):
        return JsonResponse({'status': 'error', 'message': 'tipo_apontamento invalido.'}, status=400)

    with transaction.atomic():
        # select_for_update mantem o lock na linha durante toda a checagem + chamada ao ERP:
        # uma segunda requisicao concorrente para o mesmo item (duplo clique, retry de rede, etc.)
        # fica bloqueada ate essa transacao terminar e so entao ve o 'apontado' real, em vez de
        # fazer uma segunda chamada duplicada ao Innovaro.
        item = get_object_or_404(
            PecasOrdem.objects.select_for_update(of=('self',)).select_related('ordem', 'resp_apontamento'),
            pk=pk,
            ordem__grupo_maquina='montagem',
        )

        item_ja_apontado_ordem = (
            PecasOrdem.objects
            .filter(ordem_id=item.ordem_id, apontado=True)
            .exclude(pk=item.pk)
            .select_related('resp_apontamento')
            .order_by('-data_apontamento', '-id')
            .first()
        )

        if item.apontado or (item_ja_apontado_ordem and not item.erro_apontamento):
            item_referencia = item if item.apontado else item_ja_apontado_ordem
            resp_ref = getattr(item_referencia, 'resp_apontamento', None)
            return JsonResponse(
                {
                    'status': 'error',
                    'message': 'Esta ordem ja foi apontada e nao pode ser apontada novamente.',
                    'already_apontado': True,
                    'detalhes': {
                        'item_id': item_referencia.id,
                        'ordem_id': item_referencia.ordem_id,
                        'tipo_apontamento': item_referencia.tipo_apontamento or '',
                        'data_apontamento': localtime(item_referencia.data_apontamento).strftime('%d/%m/%Y %H:%M') if item_referencia.data_apontamento else '',
                        'resp_apontamento': _nome_responsavel_apontamento(resp_ref),
                        'chave_apontamento': item_referencia.chave_apontamento or '',
                    }
                },
                status=409
            )

        payload_integracao = None
        if tipo_apontamento == 'api':
            payload_integracao = _payload_apontamento_erp_montagem(item)

            if settings.DEBUG:
                print(
                    "[MONTAGEM][INNOVARO][PAYLOAD]",
                    json.dumps(payload_integracao, ensure_ascii=False, indent=2)
                )

            if (item.qtd_morta or 0) > 0:
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

            if os.getenv("DISABLE_ERP_APONTAMENTO") == "true":
                return JsonResponse({'status': 'error', 'message': 'ERP desabilitado temporariamente.'}, status=503)

            try:
                if os.getenv("DJANGO_ENV") == "dev":
                    response_integracao = requests.post(
                        "https://hcemag.innovaro.com.br/api/integracao/v1/producao/apontar",
                        json=payload_integracao,
                        auth=("luan araujo", "luanaraujo7"),
                        timeout=(10, 60),
                    )
                else:
                    response_integracao = requests.post(
                        "https://cemag.innovaro.com.br/api/integracao/v1/producao/apontar",
                        json=payload_integracao,
                        auth=("luan araujo", "luanaraujo7"),
                        timeout=(10, 60),
                    )
            except requests.RequestException as exc:
                return JsonResponse(
                    {
                        'status': 'error',
                        'message': f'Falha de comunicacao com API ERP: {exc}',
                        'payload_enviado': payload_integracao,
                    },
                    status=502
                )

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
                            'message': 'API ERP retornou erro de negocio.',
                            'description': descricao_erro,
                            'payload_enviado': payload_integracao,
                            'retorno_api': resposta_api_json,
                        },
                        status=422
                    )

                if status_erp.lower() == 'success':
                    item.chave_apontamento, aviso_chave = _normalizar_chave_apontamento_erp_montagem(
                        resposta_api_json,
                        payload_integracao,
                    )
                    item.erro_apontamento = aviso_chave
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
                        'message': 'API ERP nao retornou JSON valido.',
                        'payload_enviado': payload_integracao,
                        'retorno_api': (response_integracao.text or '')[:500],
                    },
                    status=502
                )

        item.apontado = True
        item.data_apontamento = now()
        item.tipo_apontamento = tipo_apontamento
        item.resp_apontamento = request.user
        if tipo_apontamento == 'manual':
            item.chave_apontamento = f"MANUAL-MONTAGEM-ITEM-{item.id}"
            item.erro_apontamento = None

        item.save(update_fields=[
            'apontado',
            'data_apontamento',
            'tipo_apontamento',
            'resp_apontamento',
            'chave_apontamento',
            'erro_apontamento',
        ])

        return JsonResponse({
            'status': 'success',
            'message': 'Apontamento confirmado com sucesso.',
            'item_id': item.id,
            'apontado': item.apontado,
            'tipo_apontamento': item.tipo_apontamento,
            'data_apontamento': localtime(item.data_apontamento).strftime('%d/%m/%Y %H:%M'),
            'resp_apontamento': _nome_responsavel_apontamento(request.user),
            'chave_apontamento': item.chave_apontamento or '',
            'erro_apontamento': item.erro_apontamento or '',
            'payload_enviado': payload_integracao if tipo_apontamento == 'api' else None,
        })

def api_apontamento_qrcode(request):
    if request.method != 'GET':
        return JsonResponse(
            {'status': 'error', 'message': 'Método não permitido'}, 
            status=405
        )

    try:
        ordem_id = request.GET.get('ordem_id')

        ordem = Ordem.objects.get(pk=ordem_id)
        ordem_pecas = ordem.ordem_pecas_montagem.all() # Pega todas as ordem peças relacionadas à ordem
        total_feito = ordem_pecas.aggregate(
            total_feito=Coalesce(Sum('qtd_boa', output_field=IntegerField()), Value(0, output_field=IntegerField()))
        )['total_feito'] or 0 # Soma a quantidade boa feita, ou 0 se não houver

        ordem_peca = ordem_pecas.first()  # Pega a primeira peça da ordem
        

        dados = {
            'ordem': ordem.ordem if ordem else None,
            'maquina': ordem.maquina.nome if ordem and ordem.maquina else None,
            'status': ordem.status_atual if ordem else None,
            'peca': ordem_peca.peca if ordem else None,
            'qtd_planejada': ordem_peca.qtd_planejada if ordem else 0,
            'qtd_boa': total_feito if ordem else 0,
            'data_carga': ordem.data_carga.strftime('%d/%m/%Y') if ordem and ordem.data_carga else None,
        }
        

        return JsonResponse({
            'status': 'success', 
            'message': 'Dados recebidos com sucesso',
            'dados': dados,
        })
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
