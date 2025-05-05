from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.urls import reverse
from django.db.models.functions import Coalesce
from django.db import models
from django.db.models import Sum,Q,Prefetch,Count,OuterRef, Subquery, F, Value, Avg
from django.utils.dateparse import parse_date
from django.views.decorators.csrf import csrf_exempt
from django.utils.timezone import now
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from apontamento_pintura.models import PecasOrdem as POPintura
from apontamento_montagem.models import PecasOrdem as POMontagem
from core.models import Ordem
from cargas.utils import consultar_carretas, gerar_sequenciamento, gerar_arquivos, criar_array_datas
from cadastro.models import Maquina
from cargas.utils import processar_ordens_montagem, processar_ordens_pintura

import pandas as pd
import os
import io
import zipfile
from datetime import datetime
import requests
import json
from datetime import timedelta

def home(request):

    return render(request, "cargas/home.html")

def buscar_dados_carreta_planilha(request):
    data_inicio = request.GET.get('data_inicio')
    data_final = request.GET.get('data_fim')

    # Converte as datas de string para datetime (garante que None não cause erro)
    if data_inicio:
        data_inicio = pd.to_datetime(data_inicio, errors='coerce')

    if data_final:
        data_final = pd.to_datetime(data_final, errors='coerce')

    # Verifica se as datas foram convertidas corretamente
    if pd.isna(data_inicio) or pd.isna(data_final):
        return JsonResponse({'error': 'Datas inválidas'}, status=400)

    # Chama a função corrigida com datas no formato correto
    cargas = consultar_carretas(data_inicio, data_final)

    return JsonResponse({'cargas': cargas})

def gerar_arquivos_sequenciamento(request):
    """
    Gera arquivos Excel do sequenciamento, compacta em ZIP e chama a API 'criar_ordem'.
    """
    data_inicio = request.GET.get('data_inicio')
    data_final = request.GET.get('data_fim')
    setor = request.GET.get('setor')

    if not data_inicio or not data_final or not setor:
        return HttpResponse("Erro: Parâmetros obrigatórios ausentes.", status=400)

    # Gerar os arquivos e a tabela completa
    arquivos_gerados = gerar_arquivos(data_inicio, data_final, setor)

    if not arquivos_gerados:
        return HttpResponse("Nenhum arquivo foi gerado.", status=500)

    # Criar ZIP na memória
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for filename in arquivos_gerados:
            with open(filename, "rb") as f:
                zip_file.writestr(os.path.basename(filename), f.read())

    zip_buffer.seek(0)

    # Retornar ZIP para download
    response = HttpResponse(zip_buffer, content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="sequenciamento_{datetime.now().strftime("%Y%m%d")}.zip"'

    # Remover arquivos temporários
    for filename in arquivos_gerados:
        os.remove(filename)

    return response
    
def gerar_dados_sequenciamento(request):

    """
    Chama a API 'criar_ordem'.
    """

    data_inicio = request.GET.get('data_inicio')
    data_final = request.GET.get('data_fim')
    setor = request.GET.get('setor')

    if not data_inicio or not data_final or not setor:
        return HttpResponse("Erro: Parâmetros obrigatórios ausentes.", status=400)

    intervalo_datas = criar_array_datas(data_inicio, data_final)

    # formatando data string
    intervalo_datas_formatado = [datetime.strptime(data, "%d/%m/%Y").strftime("%Y-%m-%d") for data in intervalo_datas]

    # Verifica se já existe uma carga na nova data
    if Ordem.objects.filter(grupo_maquina=setor, data_carga__in=intervalo_datas_formatado).exists():
        return JsonResponse({'error': 'Já existe uma carga programada para essa data'}, status=400)

    # Gerar os arquivos e a tabela completa
    tabela_completa = gerar_sequenciamento(data_inicio, data_final, setor)

    if setor == 'pintura':
        tabela_completa.drop_duplicates(subset=['Código','Datas','cor'], inplace=True)
        tabela_completa["Datas"] = pd.to_datetime(tabela_completa["Datas"], format="%d/%m/%Y", errors="coerce")
        tabela_completa["Datas"] = tabela_completa["Datas"].dt.strftime("%Y-%m-%d")
    else:
        tabela_completa.drop_duplicates(subset=['Código','Datas','Célula'], inplace=True)
        tabela_completa["Datas"] = pd.to_datetime(tabela_completa["Datas"], format="%d/%m/%Y", errors="coerce")
        tabela_completa["Datas"] = tabela_completa["Datas"].dt.strftime("%Y-%m-%d")

    # Criar a carga para a API de criar ordem
    ordens = []
    for _, row in tabela_completa.iterrows():
        ordens.append({
            "grupo_maquina": setor.lower(),
            "cor": row["cor"] if setor == 'pintura' else '',
            "obs": "Ordem gerada automaticamente",
            "peca_nome": str(row["Código"]) + " - " + row["Peca"],
            "qtd_planejada": int(row["Qtde_total"]),
            "data_carga" : row["Datas"],#.strftime("%Y-%m-%d") if isinstance(row["Datas"], pd.Timestamp) else datetime.strptime(str(row["Datas"]), "%d/%m/%Y").strftime("%Y-%m-%d")
            "setor_conjunto" : row["Célula"]
        })

    if setor.lower() == 'montagem':
        resultado = processar_ordens_montagem(ordens, grupo_maquina=setor.lower())
    else:
        resultado = processar_ordens_pintura(ordens, grupo_maquina=setor.lower())

    if "error" in resultado:
        return JsonResponse({"error": resultado["error"]}, status=resultado.get("status", 400))

    return JsonResponse({"message": "Sequenciamento gerado com sucesso!", "detalhes": resultado})

@csrf_exempt
def atualizar_ordem_existente(request):
    
    """
    Chama a API 'criar_ordem'.
    """

    data_inicio = request.GET.get('data_inicio')
    setor = request.GET.get('setor')

    if not data_inicio or not setor:
        return HttpResponse("Erro: Parâmetros obrigatórios ausentes.", status=400)

    intervalo_datas = criar_array_datas(data_inicio, data_inicio)

    # formatando data string
    intervalo_datas_formatado = [datetime.strptime(data, "%d/%m/%Y").strftime("%Y-%m-%d") for data in intervalo_datas]

    # Para montagem
    # Excluir ordens que ainda não possuem apontamentos registrados
    if setor == 'montagem':
        Ordem.objects.annotate(
            total_produzido=Sum('ordem_pecas_montagem__qtd_boa')
        ).filter(
            total_produzido=0,  # Apenas ordens SEM apontamento
            data_carga__in=intervalo_datas_formatado,
            grupo_maquina=setor
        ).delete()

        # Filtra ordens que ja possuem apontamentos
        ordens_com_apontamentos = Ordem.objects.annotate(
            total_produzido=Sum('ordem_pecas_montagem__qtd_boa')
        ).filter(
            total_produzido__gt=0,  # (qtd_boa > 0)
            data_carga__in=intervalo_datas_formatado,
            grupo_maquina=setor
        )
    # para pintura
    else:
        Ordem.objects.annotate(
            total_produzido=Sum('ordem_pecas_pintura__qtd_boa')
        ).filter(
            Q(total_produzido=0) | Q(total_produzido__isnull=True),
            data_carga__in=intervalo_datas_formatado,
            grupo_maquina=setor
        ).delete()

        # Filtra ordens que ja possuem apontamentos
        ordens_com_apontamentos = Ordem.objects.annotate(
            total_produzido=Sum('ordem_pecas_pintura__qtd_boa')
        ).filter(
            total_produzido__gt=0,  # (qtd_boa > 0)
            data_carga__in=intervalo_datas_formatado,
            grupo_maquina=setor
        )

    # Gerar os arquivos e a tabela completa
    tabela_completa = gerar_sequenciamento(data_inicio, data_inicio, setor)
    
    if setor == 'pintura':
        tabela_completa.drop_duplicates(subset=['Código','Datas','cor'], inplace=True)
        tabela_completa["Datas"] = pd.to_datetime(tabela_completa["Datas"], format="%d/%m/%Y", errors="coerce")
        tabela_completa["Datas"] = tabela_completa["Datas"].dt.strftime("%Y-%m-%d")
    else:
        tabela_completa.drop_duplicates(subset=['Código','Datas','Célula'], inplace=True)
        tabela_completa["Datas"] = pd.to_datetime(tabela_completa["Datas"], format="%Y-%d-%m", errors="coerce")
        tabela_completa["Datas"] = tabela_completa["Datas"].dt.strftime("%Y-%m-%d")

    # Criar a carga para a API de criar ordem
    ordens = []
    for _, row in tabela_completa.iterrows():
        
        # para montagem
        if setor=='montagem':
        
            ordem_existente = Ordem.objects.filter(
                grupo_maquina=setor.lower(),
                data_carga=row["Datas"],
                ordem_pecas_montagem__peca=str(row["Código"]) + " - " + row["Peca"]
            ).exists()
        
        # para pintura
        else:
            
            ordem_existente = Ordem.objects.filter(
                grupo_maquina=setor.lower(),
                data_carga=row["Datas"],
                ordem_pecas_pintura__peca=str(row["Código"]) + " - " + row["Peca"]
            ).exists()
       
        if not ordem_existente:  # Evita duplicatas
            ordens.append({
                "grupo_maquina": setor.lower(),
                "cor": row["cor"] if setor == 'pintura' else '',
                "obs": "Ordem gerada automaticamente",
                "peca_nome": str(row["Código"]) + " - " + row["Peca"],
                "qtd_planejada": int(row["Qtde_total"]),
                "data_carga": row["Datas"],
                "setor_conjunto": row["Célula"]
            })

    if setor.lower() == 'montagem':
        resultado = processar_ordens_montagem(ordens, atualizacao_ordem=True, grupo_maquina=setor.lower())
    else:
        resultado = processar_ordens_pintura(ordens, atualizacao_ordem=True, grupo_maquina=setor.lower())

    if "error" in resultado:
        return JsonResponse({"error": resultado["error"]}, status=resultado.get("status", 400))

    # Retornar JSON com informações sobre ordens que precisam ser atualizadas manualmente
    return JsonResponse({
        "message": "Ordens atualizadas com sucesso!",
        "ordens_a_serem_atualizadas": list(ordens_com_apontamentos.values_list()),  # Converte QuerySet em lista
        "novas_ordens_criadas": len(ordens),  # Quantidade de novas ordens adicionadas
    })

@csrf_exempt
def remanejar_carga(request):
    """ Remaneja cargas cuja data_carga é igual à data antiga e move para a nova data. """

    if request.method == 'POST':
        try:
            data = json.loads(request.body)

            setor = data.get('setor')  # "montagem" ou "pintura"
            data_atual = data.get('dataAtual')  # Data da carga que será movida
            data_remaneja = data.get('dataRemanejar')  # Nova data

            if not setor or not data_atual or not data_remaneja:
                return JsonResponse({'error': 'Setor, data atual e nova data são obrigatórios'}, status=400)

            # Converte as datas para o formato correto
            data_atual = datetime.strptime(data_atual, "%Y-%m-%d").date()
            data_remaneja = datetime.strptime(data_remaneja, "%Y-%m-%d").date()

            # Filtra apenas as ordens do setor cuja `data_carga` é igual à `data_atual`
            ordens_atualizadas = Ordem.objects.filter(
                grupo_maquina=setor,
                data_carga=data_atual
            )

            if not ordens_atualizadas.exists():
                return JsonResponse({'error': 'Nenhuma carga encontrada para essa data'}, status=404)

            # Verifica se já existe uma carga na nova data
            if Ordem.objects.filter(grupo_maquina=setor, data_carga=data_remaneja).exists():
                return JsonResponse({'error': 'Já existe uma carga programada para essa data'}, status=400)

            # **Recalcula `data_programacao` apenas uma vez, pois todas as ordens seguem a mesma lógica**
            if setor == 'montagem':
                data_programacao = data_remaneja - timedelta(days=3)
            elif setor == 'pintura':
                data_programacao = data_remaneja - timedelta(days=1)

            # Ajusta `data_programacao` para sexta-feira se cair no fim de semana
            while data_programacao.weekday() in [5, 6]:  # 5 = Sábado, 6 = Domingo
                data_programacao -= timedelta(days=1)

            # Atualiza todas as ordens filtradas em um único comando SQL
            ordens_atualizadas.update(data_carga=data_remaneja, data_programacao=data_programacao)

            return JsonResponse({'message': 'Carga remanejada com sucesso!'})

        except json.JSONDecodeError:
            return JsonResponse({'error': 'JSON inválido'}, status=400)

    return JsonResponse({'error': 'Método não permitido'}, status=405)

def parse_iso_date(date_str):
    """ Converte datas ISO do FullCalendar ('YYYY-MM-DDTHH:mm:ssZ') para 'YYYY-MM-DD' """
    try:
        return datetime.strptime(date_str[:10], "%Y-%m-%d").date()
    except ValueError:
        return None

def andamento_cargas(request):
    """ Retorna as cargas de um setor dentro do intervalo solicitado pelo FullCalendar """

    # Obtém os parâmetros da requisição
    start_date = request.GET.get('start')
    end_date = request.GET.get('end')

    # Converte as datas corretamente
    start_date = parse_iso_date(start_date)
    end_date = parse_iso_date(end_date)

    if not start_date or not end_date:
        return JsonResponse({"error": "Parâmetros 'start' e 'end' são obrigatórios"}, status=400)
    
    setores = ["pintura", "montagem"]
    andamento_cargas = []

    for setor in setores:

        # Define as cores e modelos conforme o setor
        modelo = POPintura if setor == "pintura" else POMontagem
        cor = "#28a745" if setor == "pintura" else "#007bff"

        # Filtra apenas as ordens dentro do intervalo solicitado
        cargas = Ordem.objects.filter(
            grupo_maquina=setor,
            data_carga__range=[start_date, end_date]
        ).order_by('data_carga').values_list('data_carga', flat=True).distinct()
        
        for data in cargas:
            total_planejado = modelo.objects.filter(
                ordem__data_carga=data,
                ordem__grupo_maquina=setor
            ).values('ordem', 'peca').distinct().aggregate(
                total_planejado=Coalesce(Sum('qtd_planejada', output_field=models.FloatField()), Value(0.0))
            )["total_planejado"]

            total_finalizado = modelo.objects.filter(
                ordem__data_carga=data,
                ordem__grupo_maquina=setor
            ).aggregate(
                total_finalizado=Coalesce(Sum('qtd_boa', output_field=models.FloatField()), Value(0.0))
            )["total_finalizado"]

            percentual_concluido = (total_finalizado / total_planejado * 100) if total_planejado > 0 else 0.0

            andamento_cargas.append({
                "id": f"{setor}-{data.strftime('%Y-%m-%d')}",  # Gera um ID único baseado no setor e data
                "title": f"{setor.capitalize()} - {round(percentual_concluido, 2)}%",
                "start": data.strftime("%Y-%m-%d"),  # Formato correto para FullCalendar
                "end": data.strftime("%Y-%m-%d"),  # Evento de 1 dia
                "backgroundColor": cor,  # Cor baseada no setor
                "borderColor": cor,
                "extendedProps": {"setor": setor, "data_atual": data.strftime("%Y-%m-%d")}  # Propriedade personalizada
            })

    return JsonResponse(andamento_cargas, safe=False)  # Retorna um ARRAY direto

def historico_cargas(request):

    return render(request, "cargas/historico.html")

def historico_ordens_montagem(request):
    """
    View que agrega os dados de PecasOrdem (por ordem) e junta com a model Ordem,
    trazendo algumas colunas da Ordem e calculando o saldo:
        saldo = soma(qtd_planejada) - soma(qtd_boa)
    
    Parâmetros esperados na URL (via GET):
      - data_carga: data da carga (default: hoje)
      - maquina: nome da máquina (opcional)
      - status: status da ordem (opcional)
      - page: número da página
      - limit: quantidade de itens por página

    """

    data_carga = request.GET.get('data_carga')
    maquina_param = request.GET.get('setor', None) # Chassi, Içamento...
    status_param = request.GET.get('status', None)
    ordem_param = request.GET.get('ordem', None)

    # Paginação
    page = request.GET.get('page', 1)
    limit = request.GET.get('limit', 10)  # Default: 10 itens por página

    try:
        limit = int(limit)
        page = int(page)
    except ValueError:
        return JsonResponse({"error": "Parâmetros de paginação inválidos."}, status=400)

    # Monta os filtros para a model Ordem
    filtros_ordem = {
        'grupo_maquina': 'montagem'
    }

    if data_carga:
        try:
            data_carga = datetime.strptime(data_carga, "%Y-%m-%d").date()
            filtros_ordem['data_carga'] = data_carga  # Removida a vírgula extra
        except ValueError:
            return JsonResponse({"error": "Formato de data inválido. Use YYYY-MM-DD."}, status=400)
    if maquina_param:
        maquina = get_object_or_404(Maquina, pk=maquina_param)
        filtros_ordem['maquina'] = maquina
    if status_param:
        filtros_ordem['status_atual'] = status_param
    if ordem_param:
        filtros_ordem['ordem'] = ordem_param

    # Recupera os IDs das ordens que atendem aos filtros
    ordem_ids = Ordem.objects.filter(**filtros_ordem).values_list('id', flat=True)

    # Consulta na PecasOrdem filtrando pelas ordens identificadas,
    # trazendo alguns campos da Ordem (usando a notação "ordem__<campo>"),
    # e agrupando para calcular as somas e o saldo.
    pecas_ordem_agg = POMontagem.objects.filter(ordem_id__in=ordem_ids).values(
        'ordem',                    # id da ordem (chave para o agrupamento)
        'ordem__data_carga',        # data da carga da ordem
        'ordem__data_programacao',  # data da programação da ordem
        'ordem__maquina__nome',     # nome da máquina (ajuste se necessário)
        'ordem__status_atual',      # status atual da ordem
        'peca',                     # nome da peça
    ).annotate(
        total_planejada=Coalesce(
            Avg('qtd_planejada'), Value(0.0, output_field=models.FloatField())
        ),
        total_produzido=Coalesce(
            Sum('qtd_boa'), Value(0.0, output_field=models.FloatField())
        )
    )

    # Aplicando a paginação
    paginator = Paginator(pecas_ordem_agg, limit)
    
    try:
        ordens_paginadas = paginator.page(page)
    except PageNotAnInteger:
        ordens_paginadas = paginator.page(1)
    except EmptyPage:
        ordens_paginadas = []

    maquinas = Ordem.objects.filter(id__in=ordem_ids).values('maquina__nome', 'maquina__id').distinct()

    return JsonResponse({
        "ordens": list(ordens_paginadas),
        "maquinas": list(maquinas),
        "total_ordens": paginator.count,
        "total_paginas": paginator.num_pages,
        "pagina_atual": page
    })

def historico_ordens_pintura(request):
    """
    View que agrega os dados de PecasOrdem (por ordem) e junta com a model Ordem,
    trazendo algumas colunas da Ordem e calculando o saldo:
        saldo = soma(qtd_planejada) - soma(qtd_boa)
    
    Parâmetros esperados na URL (via GET):
      - data_carga: data da carga (default: hoje)
      - maquina: nome da máquina (opcional)
      - status: status da ordem (opcional)
      - page: número da página
      - limit: quantidade de itens por página

    """

    data_carga = request.GET.get('data_carga')
    cor = request.GET.get('cor', '') # Chassi, Içamento...
    status_param = request.GET.get('status', '')
    ordem_param = request.GET.get('ordem', '')

    # Paginação
    page = request.GET.get('page', 1)
    limit = request.GET.get('limit', 10)  # Default: 10 itens por página

    try:
        limit = int(limit)
        page = int(page)
    except ValueError:
        return JsonResponse({"error": "Parâmetros de paginação inválidos."}, status=400)

    # Monta os filtros para a model Ordem
    filtros_ordem = {
        'grupo_maquina': 'pintura'
    }

    if data_carga:
        try:
            data_carga = datetime.strptime(data_carga, "%Y-%m-%d").date()
            filtros_ordem['data_carga'] = data_carga  # Removida a vírgula extra
        except ValueError:
            return JsonResponse({"error": "Formato de data inválido. Use YYYY-MM-DD."}, status=400)
    if cor:
        filtros_ordem['cor'] = cor
    if status_param:
        filtros_ordem['status_atual'] = status_param
    if ordem_param:
        filtros_ordem['id'] = ordem_param

    # Recupera os IDs das ordens que atendem aos filtros
    ordem_ids = Ordem.objects.filter(**filtros_ordem).values_list('id', flat=True)

    # Consulta na PecasOrdem filtrando pelas ordens identificadas,
    # trazendo alguns campos da Ordem (usando a notação "ordem__<campo>"),
    # e agrupando para calcular as somas e o saldo.
    pecas_ordem_agg = POPintura.objects.filter(ordem_id__in=ordem_ids).values(
        'ordem',                    # id da ordem (chave para o agrupamento)
        'ordem__data_carga',        # data da carga da ordem
        'ordem__data_programacao',  # data da programação da ordem
        'ordem__cor',               # cor
        'ordem__status_atual',      # status atual da ordem
        'peca',                     # nome da peça
    ).annotate(
        total_planejada=Coalesce(
            Avg('qtd_planejada'), Value(0.0, output_field=models.FloatField())
        ),
        total_produzido=Coalesce(
            Sum('qtd_boa'), Value(0.0, output_field=models.FloatField())
        )

    )

    # Aplicando a paginação
    paginator = Paginator(pecas_ordem_agg, limit)
    
    try:
        ordens_paginadas = paginator.page(page)
    except PageNotAnInteger:
        ordens_paginadas = paginator.page(1)
    except EmptyPage:
        ordens_paginadas = []

    return JsonResponse({
        "ordens": list(ordens_paginadas),
        "total_ordens": paginator.count,
        "total_paginas": paginator.num_pages,
        "pagina_atual": page
    })

@csrf_exempt
def editar_planejamento(request):
    if request.method != "POST":
        return JsonResponse({"erro": "Método não permitido. Use POST!"}, status=405)

    try:
        # Carregar dados do corpo da requisição
        data = json.loads(request.body)

        nova_data_carga = data.get('novaDataCarga')
        qt_planejada = data.get('novaQtdPlan')
        ordem_id = data.get('ordemId')
        setor = data.get('setor')

        # Validação de campos obrigatórios
        if not ordem_id or not setor:
            return JsonResponse({"erro": "Os campos 'setor' e 'ordem_id' são obrigatórios!"}, status=400)

        # Buscar a ordem
        ordem = get_object_or_404(Ordem, pk=ordem_id)

        # Determinar o modelo correto com base no setor
        if setor == 'montagem':
            atualizar_ordens = POMontagem.objects.filter(ordem=ordem)
        else:
            atualizar_ordens = POPintura.objects.filter(ordem=ordem)

        if nova_data_carga:
            try:
                nova_data_carga = datetime.strptime(nova_data_carga, "%Y-%m-%d").date()
            except ValueError:
                return JsonResponse({"erro": "Formato de data inválido. Use YYYY-MM-DD."}, status=400)

            pecas_ordem = atualizar_ordens.values_list('peca', flat=True)

            if setor == 'montagem':
                conflito = Ordem.objects.filter(
                    data_carga=nova_data_carga,
                    ordem_pecas_montagem__peca__in=pecas_ordem
                ).exclude(id=ordem_id).exists()
            else:  # pintura
                conflito = Ordem.objects.filter(
                    data_carga=nova_data_carga,
                    ordem_pecas_pintura__peca__in=pecas_ordem,
                    cor=ordem.cor
                ).exclude(id=ordem_id).exists()

            if conflito:
                return JsonResponse({"erro": "Já existe uma ordem com o mesmo conjunto para essa data!"}, status=400)

            ordem.data_carga = nova_data_carga
            ordem.save()

        # Atualiza a quantidade planejada, se necessário
        if qt_planejada:
            atualizar_ordens.update(qtd_planejada=qt_planejada)

        return JsonResponse({"mensagem": "Planejamento atualizado com sucesso!"}, status=200)

    except json.JSONDecodeError:
        return JsonResponse({"erro": "Erro ao processar JSON. Verifique o formato da requisição!"}, status=400)

    except Exception as e:
        return JsonResponse({"erro": f"Ocorreu um erro: {str(e)}"}, status=500)    

    