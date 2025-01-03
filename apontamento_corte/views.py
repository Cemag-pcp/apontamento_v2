from django.shortcuts import render
from django.http import JsonResponse
from django.views import View
from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.core.paginator import Paginator, EmptyPage
from django.views.decorators.http import require_GET
from django.utils.timezone import now

from .models import Ordem,PecasOrdem
from core.models import OrdemProcesso,PropriedadesOrdem
from cadastro.models import MotivoInterrupcao, Operador, Espessura
from .utils import *

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

    motivos = MotivoInterrupcao.objects.filter(setor__nome='corte')
    operadores = Operador.objects.filter(setor__nome='corte')
    espessuras = Espessura.objects.all()

    return render(request, 'apontamento_corte/planejamento.html', {'motivos':motivos,'operadores':operadores,'espessuras':espessuras})

def get_pecas_ordem(request, pk_ordem, name_maquina):
    try:
        # Busca a ordem com os relacionamentos necessários
        ordem = Ordem.objects.prefetch_related('ordem_pecas_corte', 'propriedade').get(ordem=pk_ordem, grupo_maquina=name_maquina)

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
    ordens_queryset = Ordem.objects.prefetch_related('ordem_pecas_corte').select_related('propriedade').filter(grupo_maquina__in=['plasma', 'laser_1', 'laser_2']).order_by('-status_prioridade')

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
        'ordem': ordem.ordem,
        'grupo_maquina': ordem.get_grupo_maquina_display(),
        'data_criacao': ordem.data_criacao.strftime('%d/%m/%Y %H:%M'),
        'obs': ordem.obs,
        'status_atual': ordem.status_atual,
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

                status = body['status']
                ordem_id = body['ordem_id']
                grupo_maquina = body['grupo_maquina'].lower()
                pecas_geral = body.get('pecas_mortas', [])
                qtd_chapas = body.get('qtdChapas', None)

                # Obtém a ordem
                ordem = Ordem.objects.get(ordem=ordem_id, grupo_maquina=grupo_maquina)
                
                # Validações básicas
                if ordem.status_atual == status:
                    return JsonResponse({'error': f'Essa ordem ja está {status}. Atualize a página.'}, status=400)

                if not ordem_id or not grupo_maquina or not status:
                    return JsonResponse({'error': 'Campos obrigatórios não enviados.'}, status=400)

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
                    # Pode ser que a ordem tenha sido reestarada, então não precisao atualizar a máquina
                    try:
                        ordem.maquina = body['maquina_nome']
                    except:
                        pass
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
        'ordem': ordem.ordem,
        'grupo_maquina': ordem.get_grupo_maquina_display(),
        'data_criacao': ordem.data_criacao.strftime('%d/%m/%Y %H:%M'),
        'obs': ordem.obs,
        'status_atual': ordem.status_atual,
        'maquina': ordem.get_maquina_display(),
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
            'ordem': ordem.ordem,
            'grupo_maquina': ordem.get_grupo_maquina_display(),
            'data_criacao': ordem.data_criacao.strftime('%d/%m/%Y %H:%M'),
            'obs': ordem.obs,
            'status_atual': ordem.status_atual,
            'maquina': ordem.get_maquina_display(),
            'motivo_interrupcao': ultimo_processo_interrompido.motivo_interrupcao.nome if ultimo_processo_interrompido and ultimo_processo_interrompido.motivo_interrupcao else None,
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

        if tipo_maquina=='plasma':
            # Exibir os dados lidos no console para depuração
            excel_tratado,propriedades = tratamento_planilha_plasma(ordem_producao_excel)
        elif tipo_maquina=='laser_2':

            # apenas para o laser2
            ordem_producao_excel_2 = pd.read_excel(uploaded_file, sheet_name='AllPartsList')

            excel_tratado,propriedades = tratamento_planilha_laser2(ordem_producao_excel,ordem_producao_excel_2)
        elif tipo_maquina=='laser_1':

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
                maquina=tipo_maquina if tipo_maquina in ['laser_1','laser_2'] else None
            )
            
            # salvar propriedades
            for prop in propriedades:
                PropriedadesOrdem.objects.create(
                    ordem=nova_ordem,
                    descricao_mp=prop['descricao_mp'],
                    espessura=prop['espessura'],
                    quantidade=prop['quantidade'],
                    aproveitamento=prop['aproveitamento'][:9],
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