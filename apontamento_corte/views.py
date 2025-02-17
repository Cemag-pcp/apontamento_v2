from django.shortcuts import render
from django.http import JsonResponse
from django.views import View
from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.core.paginator import Paginator, EmptyPage
from django.views.decorators.http import require_GET
from django.utils.timezone import now,localtime
from django.db.models import Count, Q

from .models import Ordem,PecasOrdem
from core.models import OrdemProcesso,PropriedadesOrdem,MaquinaParada
from cadastro.models import Maquina, MotivoInterrupcao, Operador, Espessura, MotivoMaquinaParada
from .utils import *

import pandas as pd
import os
import tempfile
import re
import json
from urllib.parse import unquote
from datetime import datetime

# Caminho para a pasta temporária dentro do projeto
TEMP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'temp')

# Certifique-se de que a pasta existe
os.makedirs(TEMP_DIR, exist_ok=True)

def extrair_numeracao(nome_arquivo):
    match = re.search(r"(?i)OP\s*(\d+)", nome_arquivo)  # Permite espaços opcionais entre OP e o número
    print(match)
    if match:
        return match.group(1)
    return None

def planejamento(request):

    motivos = MotivoInterrupcao.objects.filter(setor__nome='corte', visivel=True)
    operadores = Operador.objects.filter(setor__nome='corte')
    espessuras = Espessura.objects.all()
    motivos_maquina_parada = MotivoMaquinaParada.objects.filter(setor__nome='serra').exclude(nome='Finalizada parcial')

    return render(request, 'apontamento_corte/planejamento.html', {'motivos':motivos,'operadores':operadores,'espessuras':espessuras,'motivos_maquina_parada':motivos_maquina_parada,})

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
            {'peca': peca.peca, 'quantidade': peca.qtd_planejada}
            for peca in ordem.ordem_pecas_corte.all()
        ]

        return JsonResponse({'pecas': pecas, 'propriedades': propriedades})

    except Ordem.DoesNotExist:
        return JsonResponse({'error': 'Ordem não encontrada.'}, status=404)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)    

def get_ordens_criadas(request):
    # Captura os parâmetros de filtro
    filtro_ordem = request.GET.get('ordem', '').strip()
    filtro_maquina = request.GET.get('maquina', '').strip()
    page = int(request.GET.get('page', 1))
    limit = int(request.GET.get('limit', 10))

    # Filtra as ordens com base nos parâmetros
    ordens_queryset = Ordem.objects.prefetch_related('ordem_pecas_corte').select_related('propriedade').filter(grupo_maquina__in=['plasma', 'laser_1', 'laser_2']).order_by('status_prioridade')

    if filtro_ordem:
        ordens_queryset = ordens_queryset.filter(ordem__icontains=filtro_ordem)
    if filtro_maquina:
        ordens_queryset = ordens_queryset.filter(grupo_maquina__icontains=filtro_maquina)

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
        'obs': ordem.obs,
        'status_atual': ordem.status_atual,
        'maquina': ordem.maquina.nome if ordem.maquina else None,
        'maquina_id': ordem.maquina.id if ordem.maquina else None,
        'propriedade': {
            'descricao_mp': ordem.propriedade.descricao_mp if ordem.propriedade else None,
            'quantidade': ordem.propriedade.quantidade if ordem.propriedade else None,
            'tipo_chapa': ordem.propriedade.get_tipo_chapa_display() if ordem.propriedade else None,
            'aproveitamento': ordem.propriedade.aproveitamento if ordem.propriedade else None,
            'retalho': 'Sim' if ordem.propriedade.retalho else None,
        }
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
                # grupo_maquina = body['grupo_maquina'].lower()
                pecas_geral = body.get('pecas_mortas', [])
                qtd_chapas = body.get('qtdChapas', None)
                maquina_request = body.get('maquina')
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

                    # Verifica se a quantidade de chapas mudaram
                    if int(qtd_chapas) != ordem.propriedade.quantidade:
                        ordem.propriedade.quantidade = int(qtd_chapas)
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
                    ordem.operador_final = get_object_or_404(Operador, pk=body.get('operadorFinal'))
                    ordem.obs_operador = body.get('obsFinal')
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
    # Filtra as ordens com base no status 'iniciada'
    ordens_queryset = Ordem.objects.prefetch_related('ordem_pecas_corte').select_related('propriedade') \
        .filter(status_atual='iniciada', grupo_maquina__in=['plasma','laser_1','laser_2'])

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
        'ordens': data,
        'page': ordens_page.number,
        'total_pages': paginator.num_pages,
        'total_ordens': paginator.count
    })

@require_GET
def get_ordens_interrompidas(request):
    # Filtra as ordens com base no status 'interrompida'
    ordens_queryset = Ordem.objects.prefetch_related('processos', 'ordem_pecas_corte').select_related('propriedade') \
        .filter(status_atual='interrompida', grupo_maquina__in=['plasma','laser_1','laser_2'])

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
    pecas = [unquote(p) for p in pecas.split(';')] if pecas else []
    
    maquina = unquote(request.GET.get('maquina', ''))
    ordem = unquote(request.GET.get('ordem', ''))

    page = int(request.GET.get('page', 1))
    limit = int(request.GET.get('limit', 10))
    draw = int(request.GET.get('draw', 1))

    #  Define a Query Base
    ordens_queryset = (
        Ordem.objects.filter(grupo_maquina__in=['plasma', 'laser_1', 'laser_2'], duplicada=False)
        .prefetch_related('ordem_pecas_corte')  # Evita queries repetidas para peças
        .select_related('propriedade')  # Carrega a propriedade diretamente
        .order_by('-propriedade__aproveitamento')
    )

    # otimização do Filtro de Peças
    if pecas:
        ordens_queryset = ordens_queryset.filter(
            ordem_pecas_corte__peca__in=pecas,
            ordem_pecas_corte__qtd_planejada__gt=0
        ).distinct()

    # Filtra Máquina e Ordem se necessário
    if maquina:
        ordens_queryset = ordens_queryset.filter(grupo_maquina=maquina)
    if ordem:
        ordens_queryset = ordens_queryset.filter(ordem=ordem)

    # Contagem de Registros para Paginação
    # records_total = Ordem.objects.filter(grupo_maquina__in=['plasma', 'laser_1', 'laser_2']).count()
    records_filtered = ordens_queryset.count()

    # Paginação eficiente
    paginator = Paginator(ordens_queryset, limit)
    try:
        ordens_page = paginator.page(page)
    except EmptyPage:
        return JsonResponse({'draw': draw, 'recordsTotal': records_filtered, 'recordsFiltered': records_filtered, 'data': []})

    # Otimização da Serialização dos Dados
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

    #  Ordena os dados com base no aproveitamento corrigido
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
            {'peca': peca.peca, 'quantidade': peca.qtd_planejada}
            for peca in ordem.ordem_pecas_corte.all()
            if peca.qtd_planejada > 0
        ]

        return JsonResponse({'pecas': pecas, 'propriedades': propriedades})

    except Ordem.DoesNotExist:
        return JsonResponse({'error': 'Ordem não encontrada.'}, status=404)

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

        with transaction.atomic():
            # Cria a nova ordem como duplicada
            nova_ordem = Ordem.objects.create(
                ordem_pai=ordem_original,
                duplicada=True,
                grupo_maquina=ordem_original.grupo_maquina,
                maquina=ordem_original.maquina if ordem_original.maquina in ['laser_1', 'laser_2'] else None,
                obs=obs_duplicar,
                status_atual='aguardando_iniciar',
                data_programacao=data_programacao
            )

            # Duplica as propriedades associadas
            if hasattr(ordem_original, 'propriedade'):
                propriedade_original = ordem_original.propriedade
                PropriedadesOrdem.objects.create(
                    ordem=nova_ordem,  # Associa a nova ordem
                    descricao_mp=propriedade_original.descricao_mp,
                    espessura=propriedade_original.espessura,
                    quantidade=qtd_chapa,
                    aproveitamento=propriedade_original.aproveitamento,
                    tipo_chapa=propriedade_original.tipo_chapa,
                    retalho=propriedade_original.retalho,
                )

            # Criar peças para ordem duplicada
            for peca in pecas:
                PecasOrdem.objects.create(
                    ordem=nova_ordem,
                    peca=peca['peca'],
                    qtd_planejada=peca['qtd_planejada']
                )

        return JsonResponse({'message': 'Ordem duplicada com sucesso', 'nova_ordem_id': nova_ordem.pk}, status=201)

    except Ordem.DoesNotExist:
        return JsonResponse({'error': 'Ordem original não encontrada'}, status=404)
    except Exception as e:
        return JsonResponse({'error': f'Erro ao duplicar ordem: {str(e)}'}, status=500)

def duplicar_op(request):

    return render(request, 'apontamento_corte/duplicar-op.html')

class ProcessarArquivoView(View):
    def post(self, request):
        
        """
        Faz o upload do arquivo, processa os dados e retorna como JSON.
        """

        # Verifica se o arquivo foi enviado
        uploaded_file = request.FILES.get('file')
        tipo_maquina = request.POST.get('tipoMaquina')

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
            ordem_producao_excel = pd.read_excel(uploaded_file)

            # Realizar o tratamento da planilha
            if tipo_maquina=='plasma':
                excel_tratado,propriedades = tratamento_planilha_plasma(ordem_producao_excel)
            elif tipo_maquina=='laser_2':
                # apenas para o laser2
                ordem_producao_excel_2 = pd.read_excel(uploaded_file, sheet_name='AllPartsList')

                excel_tratado,propriedades = tratamento_planilha_laser2(ordem_producao_excel,ordem_producao_excel_2)
            # elif tipo_maquina=='laser_1':

            #     comprimento = request.POST.get('comprimento')
            #     largura=request.POST.get('largura')

            #     espessura=get_object_or_404(Espessura, pk=request.POST.get('espessura'))
                
            #     # apenas para o laser1
            #     ordem_producao_excel_2 = pd.read_excel(uploaded_file, sheet_name='Nestings_Cost')
            #     excel_tratado,propriedades = tratamento_planilha_laser1(ordem_producao_excel,ordem_producao_excel_2,comprimento,largura,espessura.nome)

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
        """
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
        ordem_producao_excel = pd.read_excel(uploaded_file)

        tipo_maquina_tratada = tipo_maquina.replace("_"," ").title()

        tipo_maquina_object = get_object_or_404(Maquina, nome__contains=tipo_maquina_tratada) if tipo_maquina in ['laser_1','laser_2'] else None

        if tipo_maquina =='plasma':
            # Exibir os dados lidos no console para depuração
            excel_tratado,propriedades = tratamento_planilha_plasma(ordem_producao_excel)
        elif tipo_maquina_object.nome=='Laser 2 (JFY)':

            # apenas para o laser2
            ordem_producao_excel_2 = pd.read_excel(uploaded_file, sheet_name='AllPartsList')

            excel_tratado,propriedades = tratamento_planilha_laser2(ordem_producao_excel,ordem_producao_excel_2)
        elif tipo_maquina_object.nome=='Laser 1':

            comprimento = request.POST.get('comprimento')
            largura=request.POST.get('largura')

            espessura=get_object_or_404(Espessura, pk=request.POST.get('espessura'))
            
            # apenas para o laser1
            ordem_producao_excel_2 = pd.read_excel(uploaded_file, sheet_name='Nestings_Cost')
            excel_tratado,propriedades = tratamento_planilha_laser1(ordem_producao_excel,ordem_producao_excel_2,comprimento,largura,espessura.nome)

        pecas = excel_tratado.to_dict(orient='records')  # Converter para uma lista de dicionários

        with transaction.atomic():

            # criar ordem
            nova_ordem = Ordem.objects.create(
                ordem=int(numeracao_op),
                obs=descricao,
                grupo_maquina=tipo_maquina,
                data_programacao=data_programacao,
                maquina=tipo_maquina_object
            )
            
            # salvar propriedades
            for prop in propriedades:
                PropriedadesOrdem.objects.create(
                    ordem=nova_ordem,
                    descricao_mp=prop['descricao_mp'],
                    espessura=prop['espessura'],
                    quantidade=prop['quantidade'],
                    aproveitamento=SalvarArquivoView.corrigir_aproveitamento(prop['aproveitamento']),
                    tipo_chapa=tipo_chapa,
                    retalho=retalho
                )
            
            # salvar peças
            for peca in pecas:
                PecasOrdem.objects.create(
                    ordem=nova_ordem,
                    peca=peca['peca'],
                    qtd_planejada=peca['qtd_planejada']
                )

        return JsonResponse({'message': 'Dados salvos com sucesso!'})