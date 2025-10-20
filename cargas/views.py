
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.urls import reverse
from django.db.models.functions import Coalesce, Now
from django.db import models
from django.db.models import Sum,Q,CharField,Count,OuterRef, Subquery, F, Value, Avg
from django.utils.dateparse import parse_date
from django.views.decorators.csrf import csrf_exempt
from django.utils.timezone import now
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.views.decorators.http import require_POST, require_GET
from django.db.models import Func, FloatField, ExpressionWrapper

from apontamento_pintura.models import PecasOrdem as POPintura
from apontamento_montagem.models import PecasOrdem as POMontagem
from apontamento_solda.models import PecasOrdem as POSolda

from core.models import Ordem
from cargas.utils import consultar_carretas, gerar_sequenciamento, gerar_arquivos, criar_array_datas
from cadastro.models import Maquina
from cargas.utils import processar_ordens_montagem, processar_ordens_pintura, processar_ordens_solda, imprimir_ordens_montagem, imprimir_ordens_montagem_unitaria
from apontamento_pintura.models import CambaoPecas
from apontamento_pintura.views import ordens_criadas as ordens_criadas_pintura
from apontamento_montagem.views import ordens_criadas as ordens_criadas_montagem

import pandas as pd
import os
import io
import zipfile
from datetime import datetime
import requests
import json
from datetime import timedelta
import django

django.setup()
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "apontamento_v2.settings")  

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

    # data_inicio='2025-07-01'
    # data_final='2025-07-01'
    # setor='pintura'

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
    # tabela_completa['cor'].unique()

    if setor == 'pintura':
        tabela_completa = tabela_completa.groupby(['Código', 'Peca', 'Célula', 'Datas','Recurso_cor','cor']).agg({'Qtde_total': 'sum'}).reset_index()
        tabela_completa.drop_duplicates(subset=['Código','Datas','cor'], inplace=True)
    else:
        tabela_completa.drop_duplicates(subset=['Código','Datas','Célula'], inplace=True)

    # Criar a carga para a API de criar ordem
    ordens = []
    for _, row in tabela_completa.iterrows():
        ordens.append({
            "grupo_maquina": setor.lower(),
            "cor": row["cor"] if setor == 'pintura' else '',
            "obs": "Ordem gerada automaticamente",
            "peca_nome": str(row["Código"]) + " - " + row["Peca"],
            "qtd_planejada": int(row["Qtde_total"]),
            "data_carga": str(row["Datas"].date()) if setor in ['montagem', 'solda'] else row["Datas"],
            "setor_conjunto" : row["Célula"]
        })

    if setor.lower() == 'montagem':
        resultado = processar_ordens_montagem(request, ordens, grupo_maquina=setor.lower())
    elif setor.lower() == 'pintura':
        resultado = processar_ordens_pintura(ordens, grupo_maquina=setor.lower())
    else:
        resultado = processar_ordens_solda(ordens, grupo_maquina=setor.lower())

    if "error" in resultado:
        return JsonResponse({"error": resultado["error"]}, status=resultado.get("status", 400))

    return JsonResponse({"message": "Sequenciamento gerado com sucesso!", "detalhes": resultado})

@csrf_exempt
def atualizar_ordem_existente(request):
    """
    Atualiza as ordens de um dia específico:
    - Remove ordens sem apontamento que foram retiradas do sequenciamento
    - Mantém ordens que já têm apontamentos
    - Atualiza `qtd_planejada` de ordens já existentes
    - Cria novas ordens para itens adicionados
    - Retorna as ordens que não puderam ser removidas
    """

    data_inicio = request.GET.get('data_inicio')
    setor = request.GET.get('setor')
    # data_inicio = '2025-06-26'
    # setor = 'pintura'

    if not data_inicio or not setor:
        return HttpResponse("Erro: Parâmetros obrigatórios ausentes.", status=400)

    intervalo_datas_formatado = [
        datetime.strptime(data_inicio, "%Y-%m-%d").strftime("%Y-%m-%d")
    ]

    # Filtra ordens existentes do dia
    ordens_existentes_qs = Ordem.objects.filter(
        data_carga__in=intervalo_datas_formatado,
        grupo_maquina=setor
    )

    # Separar ordens que já têm apontamentos
    if setor == 'montagem':
        ordens_com_apontamentos = ordens_existentes_qs.annotate(
            total_produzido=Sum('ordem_pecas_montagem__qtd_boa')
        ).filter(total_produzido__gt=0)
    elif setor == 'pintura':
        ordens_com_apontamentos = ordens_existentes_qs.annotate(
            total_produzido=Sum('ordem_pecas_pintura__qtd_boa')
        ).filter(total_produzido__gt=0)
    else:
        ordens_com_apontamentos = ordens_existentes_qs.annotate(
            total_produzido=Sum('ordem_pecas_solda__qtd_boa')
        ).filter(total_produzido__gt=0)

    ordens_com_apontamentos_ids = set(ordens_com_apontamentos.values_list('id', flat=True))

    # Gerar a tabela completa
    tabela_completa = gerar_sequenciamento(data_inicio, data_inicio, setor)
    
    # print(tabela_completa[tabela_completa['cor'] == 'Amarelo'])

    if setor == 'pintura':
        tabela_completa = tabela_completa.groupby(['Código', 'Peca', 'Célula', 'Datas','Recurso_cor','cor']).agg({'Qtde_total': 'sum'}).reset_index()
        tabela_completa.drop_duplicates(subset=['Código', 'Datas', 'cor'], inplace=True)
        # tabela_completa["Datas"] = pd.to_datetime(tabela_completa["Datas"], format="%d/%m/%Y", errors="coerce").dt.strftime("%Y-%m-%d")
    else:
        tabela_completa.drop_duplicates(subset=['Código', 'Datas', 'Célula'], inplace=True)
        # tabela_completa["Datas"] = pd.to_datetime(tabela_completa["Datas"], format="%Y-%d-%m", errors="coerce").dt.strftime("%Y-%m-%d")

    # Conjunto de peças atuais
    if setor == 'pintura':
        pecas_atualizadas = set(
            (f"{str(row['Código'])} - {row['Peca']}", row['cor']) for _, row in tabela_completa.iterrows()
        )
    else:
        pecas_atualizadas = set(
            f"{str(row['Código'])} - {row['Peca']}" for _, row in tabela_completa.iterrows()
        )

    # Identificar ordens sem apontamento que não existem mais no sequenciamento
    if setor == 'montagem':
        ordens_sem_apontamento = ordens_existentes_qs.exclude(id__in=ordens_com_apontamentos_ids).filter(
            ~Q(ordem_pecas_montagem__peca__in=pecas_atualizadas)
        )
    elif setor == 'pintura':
        # ordens_sem_apontamento = ordens_existentes_qs.exclude(id__in=ordens_com_apontamentos_ids).filter(
        #     ~Q(ordem_pecas_pintura__peca__in=pecas_atualizadas)
        # )
        condicao = Q()
        for peca, cor in pecas_atualizadas:
            condicao |= Q(ordem_pecas_pintura__peca=peca, cor=cor)

        ordens_sem_apontamento = ordens_existentes_qs.exclude(id__in=ordens_com_apontamentos_ids).exclude(condicao)
    else:
        ordens_sem_apontamento = ordens_existentes_qs.exclude(id__in=ordens_com_apontamentos_ids).filter(
            ~Q(ordem_pecas_solda__peca__in=pecas_atualizadas)
        )

    # Remove essas ordens
    ordens_sem_apontamento.delete()

    # Preparar lista para criar novas ordens
    ordens_a_criar = []

    # tabela_completa = tabela_completa.iloc[31:32]
    # tabela_completa.reset_index(drop=True)

    for _, row in tabela_completa.iterrows():
        peca_nome = f"{str(row['Código'])} - {row['Peca']}"
        data_carga = row["Datas"]

        if setor == 'montagem':
            ordem_existente = Ordem.objects.filter(
                grupo_maquina=setor,
                data_carga=data_carga,
                ordem_pecas_montagem__peca=peca_nome
            ).first()
        elif setor == 'pintura':
            ordem_existente = Ordem.objects.filter(
                grupo_maquina=setor,
                data_carga=data_carga,
                ordem_pecas_pintura__peca=peca_nome,
                cor=row['cor']
            ).first()
        else:
            ordem_existente = Ordem.objects.filter(
                grupo_maquina=setor,
                data_carga=data_carga,
                ordem_pecas_solda__peca=peca_nome
            ).first()

        if ordem_existente:
            # Atualizar qtd_planejada na peça vinculada
            if setor == 'montagem':
                ordem_existente.ordem_pecas_montagem.filter(peca=peca_nome).update(qtd_planejada=int(row["Qtde_total"]))
            elif setor == 'pintura':
                ordem_existente.ordem_pecas_pintura.filter(peca=peca_nome).update(qtd_planejada=int(row["Qtde_total"]))
            else:
                ordem_existente.ordem_pecas_solda.filter(peca=peca_nome).update(qtd_planejada=int(row["Qtde_total"]))
        else:
            # Criar nova ordem
            ordens_a_criar.append({
                "grupo_maquina": setor.lower(),
                "cor": row["cor"] if setor == 'pintura' else '',
                "obs": "Ordem gerada automaticamente",
                "peca_nome": peca_nome,
                "qtd_planejada": int(row["Qtde_total"]),
                "data_carga": data_carga,
                "setor_conjunto": row["Célula"]
            })

    # Processar novas ordens
    if setor == 'montagem':
        resultado = processar_ordens_montagem(request, ordens_a_criar, atualizacao_ordem=True, grupo_maquina=setor.lower())
    elif setor == 'pintura':
        resultado = processar_ordens_pintura(ordens_a_criar, atualizacao_ordem=True, grupo_maquina=setor.lower())
    else:
        resultado = processar_ordens_solda(ordens_a_criar, atualizacao_ordem=True, grupo_maquina=setor.lower())

    if "error" in resultado:
        return JsonResponse({"error": resultado["error"]}, status=resultado.get("status", 400))

    # Retorno final
    return JsonResponse({
        "message": "Ordens atualizadas com sucesso!",
        "ordens_com_apontamentos": list(ordens_com_apontamentos.values('id', 'data_carga', 'grupo_maquina')),
        "novas_ordens_criadas": len(ordens_a_criar),
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
            elif setor == 'solda':
                data_programacao = data_remaneja - timedelta(days=2)
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

    # Algumas máquinas que não precisam está na contagem de montagem
    maquinas_excluidas = [
        'PLAT. TANQUE. CAÇAM. 2',
        'QUALIDADE',
        'FORJARIA',
        'ESTAMPARIA',
        'Carpintaria',
        'FEIXE DE MOLAS',
        'SERRALHERIA',
        'ROÇADEIRA'
    ]

    maquinas_excluidas_ids = Maquina.objects.filter(nome__in=maquinas_excluidas).values_list('id', flat=True)

    # Obtém os parâmetros da requisição
    start_date = request.GET.get('start')
    end_date = request.GET.get('end')

    # Converte as datas corretamente
    start_date = parse_iso_date(start_date)
    end_date = parse_iso_date(end_date)

    if not start_date or not end_date:
        return JsonResponse({"error": "Parâmetros 'start' e 'end' são obrigatórios"}, status=400)
    
    setores = ["pintura", "montagem", "solda"]
    andamento_cargas = []

    for setor in setores:

        # Define as cores e modelos conforme o setor
        if setor == "pintura":
            modelo = POPintura
        elif setor == "montagem":
            modelo = POMontagem
        else:
            modelo = POSolda
        
        if setor == "pintura":
            cor = "#28a745"
        elif setor == "montagem":
            cor = "#007bff"
        else:
            cor = "#ffc107" 

        # Filtra apenas as ordens dentro do intervalo solicitado
        cargas = Ordem.objects.filter(
            grupo_maquina=setor,
            data_carga__range=[start_date, end_date],
            ordem_pai__isnull=True
        ).order_by('data_carga').values_list('data_carga', flat=True).distinct()
        
        for data in cargas:
            total_planejado = modelo.objects.filter(
                ordem__data_carga=data,
                ordem__grupo_maquina=setor
            ).exclude(ordem__maquina__id__in=maquinas_excluidas_ids) \
            .values('ordem', 'peca').distinct().aggregate(
                total_planejado=Coalesce(Sum('qtd_planejada', output_field=models.FloatField()), Value(0.0))
            )["total_planejado"]

            total_finalizado = modelo.objects.filter(
                ordem__data_carga=data,
                ordem__grupo_maquina=setor
            ).exclude(ordem__maquina__id__in=maquinas_excluidas_ids) \
            .aggregate(
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
    conjunto_param = request.GET.get('conjunto', '')

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
        filtros_ordem['id'] = ordem_param
    if conjunto_param:
        filtros_ordem['ordem_pecas_montagem__peca__icontains'] = conjunto_param

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
    conjunto_param = request.GET.get('conjunto', '')

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
            filtros_ordem['data_carga'] = data_carga
        except ValueError:
            return JsonResponse({"error": "Formato de data inválido. Use YYYY-MM-DD."}, status=400)
    if cor:
        filtros_ordem['cor'] = cor
    if status_param:
        filtros_ordem['status_atual'] = status_param
    if ordem_param:
        filtros_ordem['id'] = ordem_param
    if conjunto_param:
        filtros_ordem['ordem_pecas_pintura__peca__icontains'] = conjunto_param

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

def historico_ordens_solda(request):
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
    conjunto_param = request.GET.get('conjunto', '')

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
        'grupo_maquina': 'solda'
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
        filtros_ordem['id'] = ordem_param
    if conjunto_param:
        filtros_ordem['ordem_pecas_solda__peca__icontains'] = conjunto_param

    # Recupera os IDs das ordens que atendem aos filtros
    ordem_ids = Ordem.objects.filter(**filtros_ordem).values_list('id', flat=True)

    # Consulta na PecasOrdem filtrando pelas ordens identificadas,
    # trazendo alguns campos da Ordem (usando a notação "ordem__<campo>"),
    # e agrupando para calcular as somas e o saldo.
    pecas_ordem_agg = POSolda.objects.filter(ordem_id__in=ordem_ids).values(
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
        elif setor == 'solda':
            atualizar_ordens = POSolda.objects.filter(ordem=ordem)
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
                    ordem_pecas_montagem__peca__in=pecas_ordem,
                    maquina=ordem.maquina
                ).exclude(id=ordem_id).exists()
            elif setor == 'solda':
                conflito = Ordem.objects.filter(
                    data_carga=nova_data_carga,
                    ordem_pecas_solda__peca__in=pecas_ordem,
                    maquina=ordem.maquina
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

@csrf_exempt
@require_POST
def excluir_ordens_dia_setor(request):
    """
    Exclui ordens de um dia e setor específicos via POST,
    somente se não houver apontamentos associados.
    
    Espera JSON no corpo da requisição com:
    {
        "data": "2025-06-03",
        "setor": "montagem"  # ou "pintura"
    }
    """

    try:
        payload = json.loads(request.body)
        data = payload.get('data')
        setor = payload.get('setor')
    except Exception:
        return JsonResponse({"error": "Erro ao ler o corpo da requisição. Envie JSON válido."}, status=400)

    if not data or not setor:
        return JsonResponse({"error": "Campos 'data' e 'setor' são obrigatórios."}, status=400)

    try:
        data_formatada = datetime.strptime(data, "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({"error": "Formato de data inválido. Use 'yyyy-mm-dd'."}, status=400)

    ordens_qs = Ordem.objects.filter(data_carga=data_formatada, grupo_maquina=setor)

    if setor == 'montagem':
        ordens_com_apontamentos = ordens_qs.annotate(
            total_apontado=Sum('ordem_pecas_montagem__qtd_boa')
        ).filter(total_apontado__gt=0)
    elif setor == 'pintura':
        ordens_com_apontamentos = ordens_qs.annotate(
            total_apontado=Sum('ordem_pecas_pintura__qtd_boa')
        ).filter(total_apontado__gt=0)
    elif setor == 'solda':
        ordens_com_apontamentos = ordens_qs.annotate(
            total_apontado=Sum('ordem_pecas_solda__qtd_boa')
        ).filter(total_apontado__gt=0)
    else:
        return JsonResponse({"error": "Setor inválido. Use 'montagem' ou 'pintura'."}, status=400)

    ordens_bloqueadas_ids = set(ordens_com_apontamentos.values_list('id', flat=True))

    if ordens_bloqueadas_ids:
        return JsonResponse({
            "error": "Existe ordens ja apontadas, retire elas dessa data."
        })   

    ordens_para_excluir = ordens_qs.exclude(id__in=ordens_bloqueadas_ids)
    total_excluidas = ordens_para_excluir.count()

    ordens_para_excluir.delete()

    return JsonResponse({
        "message": f"{total_excluidas} ordens excluídas com sucesso.",
        "ordens_bloqueadas": list(ordens_com_apontamentos.values("id", "data_carga", "grupo_maquina")),
    })    

@require_GET
def enviar_etiqueta_impressora(request):
    data_carga = request.GET.get('data_carga')

    payload_status = imprimir_ordens_montagem(data_carga)
    # aceita tanto (dict, status) quanto apenas dict
    if isinstance(payload_status, tuple):
        payload, status = payload_status
    else:
        payload, status = payload_status, 200

    return JsonResponse(payload, status=status)

@require_GET
def enviar_etiqueta_unitaria_impressora(request):
    ordem_id = request.GET.get('ordem_id')

    payload_status = imprimir_ordens_montagem_unitaria(ordem_id)
    # aceita tanto (dict, status) quanto apenas dict
    if isinstance(payload_status, tuple):
        payload, status = payload_status
    else:
        payload, status = payload_status, 200

    return JsonResponse(payload, status=status)

# API para consulta no google sheets
class AtTimeZone(Func):
    function = ''
    template = "%(expressions)s AT TIME ZONE '%(timezone)s'"
    output_field = CharField()

    def __init__(self, expression, timezone, **extra):
        super().__init__(expression, timezone=timezone, **extra)

class ToChar(Func):
    function = 'to_char'
    output_field = CharField()

def ordens_em_andamento_finalizada_pintura(request):
    """"
        traz as ordens aguardando inicio, em andamento e finalizadas na pintura
    """
    resultado = ordens_criadas_pintura(request)

    resultado_json_ordens_criadas = json.loads(resultado.content)

    ordens_aguardando_iniciar = []

    mes_atual = datetime.now().date().month

    data_hora_atual = datetime.now().strftime("%d/%m/%Y %H:%M:%S")


    for ordem in resultado_json_ordens_criadas['ordens']:
        data_carga_datetime = datetime.strptime(ordem['data_carga'], "%Y-%m-%d").date()
        if data_carga_datetime.month not in (mes_atual, mes_atual - 1):
            continue

        #adicionar que a ordem aguardando_iniciar criando do mês atual
        ordens_aguardando_iniciar.append({
            'status': ordem['status_atual'],
            'quantidade_pendurada': 0,
            'id_ordem': ordem['id'],
            'ordem': ordem['ordem'],
            'peca': ordem['peca_codigo'],
            'qtd_planejada': ordem['peca_qt_planejada'],
            'cor': ordem['cor'],
            'data_criacao_fmt': formatar_data_str(ordem['data_criacao']) if ordem['data_criacao'] else '',
            'data_carga_fmt': formatar_data_str(ordem['data_carga']) if ordem['data_carga'] else '',
            'data_pendura_fmt': '',
            'data_derruba_fmt': '',
            'tipo': '',
            'cambao_nome': '',
            'data_ultima_atualizacao': data_hora_atual,
        })


    qs = (
        CambaoPecas.objects
        .filter(
            peca_ordem__ordem__grupo_maquina='pintura',
            status__isnull=False
        )
        .select_related('peca_ordem', 'peca_ordem__ordem', 'cambao')
        .annotate(
            id_ordem=F('peca_ordem__ordem__id'),
            ordem=F('peca_ordem__ordem__ordem'),
            peca=F('peca_ordem__peca'),
            qtd_planejada=F('peca_ordem__qtd_planejada'),
            cor=F('peca_ordem__ordem__cor'),

            # use nomes sem colidir com fields reais
            data_criacao_fmt=ToChar(F('peca_ordem__ordem__data_criacao'), Value('DD/MM/YYYY')),
            data_carga_fmt=ToChar(F('peca_ordem__ordem__data_carga'), Value('DD/MM/YYYY')),
            data_pendura_fmt=ToChar(
                AtTimeZone(F('data_pendura'), 'America/Sao_Paulo'),
                Value('DD/MM/YYYY HH24:MI:SS')
            ),
            data_derruba_fmt=ToChar(
                AtTimeZone(F('data_fim'), 'America/Sao_Paulo'),
                Value('DD/MM/YYYY HH24:MI:SS')
            ),

            tipo=F('cambao__tipo'),
            cambao_nome=F('cambao__nome'),
            data_ultima_atualizacao=Value(data_hora_atual, output_field=CharField()) # já vem string
        )
        .values(
            'id_ordem',
            'ordem',
            'peca',
            'qtd_planejada',
            'cor',
            'status',
            'quantidade_pendurada',

            # valores formatados
            'data_criacao_fmt',
            'data_carga_fmt',
            'data_pendura_fmt',
            'data_derruba_fmt',
            
            'tipo',
            'cambao_nome',
            'data_ultima_atualizacao',
        )
        .order_by('-data_fim')[:1000]
    )

    data = list(qs)[::-1]

    resultado_final_concat = ordens_aguardando_iniciar + data

    resultado_final_concat = sorted(
        resultado_final_concat,
        key=lambda x: parse_data_fmt(x.get('data_derruba_fmt', ''))
    )

    return JsonResponse(resultado_final_concat, safe=False)

def verificar_cargas_geradas(request):

    qs = (
        Ordem.objects
        .filter(grupo_maquina__in=['pintura', 'montagem', 'solda'])
        .order_by('data_carga', 'grupo_maquina', 'data_criacao')  # precisa começar pelos do distinct
        .distinct('data_carga', 'grupo_maquina')                  # DISTINCT ON (data_carga, grupo_maquina)
        .annotate(
            data_criacao_fmt=ToChar(F('data_criacao'), Value('DD/MM/YYYY')),
            data_carga_fmt=ToChar(F('data_carga'), Value('DD/MM/YYYY'))

        )
        .values('data_criacao_fmt', 'data_carga_fmt', 'grupo_maquina')
    )
    return JsonResponse(list(qs), safe=False)

def formatar_data_str(data_str):
    """
    Recebe uma string de data (ex: '2025-10-07' ou '2025-10-07T00:00:00')
    e retorna no formato 'DD/MM/YYYY'.
    Se não conseguir converter, retorna a string original ou vazio.
    """
    if not data_str:
        return ''
    try:
        # Trata ISO completo ou só data
        if 'T' in data_str:
            data_obj = datetime.strptime(data_str[:10], "%Y-%m-%d")
        else:
            data_obj = datetime.strptime(data_str, "%Y-%m-%d")
        return data_obj.strftime('%d/%m/%Y')
    except Exception:
        return data_str

def parse_data_fmt(data_str):
    try:
        return datetime.strptime(data_str, "%d/%m/%Y")
    except Exception:
        return datetime.min  # Garante que datas inválidas fiquem no início

def ordens_status_montagem(request):
    """"
        traz as ordens aguardando inicio, em andamento e finalizadas na montagem
    """

    # Monta os filtros para a model Ordem
    filtros_ordem = {
        'grupo_maquina': 'montagem'
    }

    # Máquinas a excluir da contagem / retorno
    maquinas_excluidas = [
        'PLAT. TANQUE. CAÇAM. 2',
        'QUALIDADE',
        'FORJARIA',
        'ESTAMPARIA',
        'Carpintaria',
        'FEIXE DE MOLAS',
        'ROÇADEIRA'
    ]

    # Recupera os IDs das ordens que atendem aos filtros (ainda sem excluir máquinas, pois o filtro de máquina pode vir por parâmetro)
    ordem_ids = Ordem.objects.filter(**filtros_ordem).values_list('id', flat=True)

    # Consulta em PecasOrdem filtrando pelas ordens e EXCLUINDO as máquinas definidas em maquinas_excluidas
    pecas_ordem_queryset = POMontagem.objects.filter(ordem_id__in=ordem_ids).exclude(
        ordem__maquina__nome__in=maquinas_excluidas
    )

    data_hora_atual = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    pecas_ordem_agg = pecas_ordem_queryset.annotate(
        data_carga_fmt=ToChar(AtTimeZone(F('ordem__data_carga'), 'America/Sao_Paulo'), Value('DD/MM/YYYY')),
        data_ultima_atualizacao_ordem=ToChar(AtTimeZone(F('ordem__ultima_atualizacao'), 'America/Sao_Paulo'),
                                           Value('DD/MM/YYYY HH24:MI:SS')),
        total_boa=Coalesce(
            Sum('qtd_boa'), Value(0.0, output_field=FloatField())
        ),
        total_planejada=Coalesce(
            Avg('qtd_planejada'), Value(0.0, output_field=FloatField())
        ),
        data_ultima_chamada=Value(data_hora_atual, output_field=CharField()),

    ).annotate(
        restante=ExpressionWrapper(
            F('total_planejada') - F('total_boa'), output_field=FloatField()
        )
    ).values(
        'ordem__status_atual',               # status atual da ordem
        'ordem',                             # id da ordem (chave para o agrupamento)
        'total_boa',                         # quantidade feita
        'total_planejada',                   # quantidade planejada
        'restante',                          # quantidade restante
        'peca',                              # nome da peça
        'data_carga_fmt',                    # data da carga da ordem
        'data_ultima_atualizacao_ordem',     # última atualização da ordem'
        'ordem__maquina__nome',              # nome da máquina   
        'data_ultima_chamada'                # última chamada da API pelo sheets
    ).order_by('-ordem__ultima_atualizacao')[:1000]

    resultado_final = list(pecas_ordem_agg)


    return JsonResponse(resultado_final, safe=False)

def ordens_status_solda(request):
    """"
        traz as ordens aguardando inicio, em andamento e finalizadas na solda
    """
     
    # Monta os filtros para a model Ordem
    filtros_ordem = {
        'grupo_maquina': 'solda',
        'ordem_pai__isnull': True
    }

    # Recupera os IDs das ordens que atendem aos filtros
    ordem_ids = Ordem.objects.filter(**filtros_ordem).values_list('id', flat=True)

    # Consulta na PecasOrdem filtrando pelas ordens identificadas,
    # trazendo alguns campos da Ordem (usando a notação "ordem__<campo>"),
    # e agrupando para calcular as somas e o saldo.

    data_hora_atual = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    
    pecas_ordem_queryset = POSolda.objects.filter(ordem_id__in=ordem_ids)

    pecas_ordem_agg = pecas_ordem_queryset.annotate(
        data_carga_fmt=ToChar(AtTimeZone(F('ordem__data_carga'), 'America/Sao_Paulo'), Value('DD/MM/YYYY')),
        data_ultima_atualizacao_ordem=ToChar(AtTimeZone(F('ordem__ultima_atualizacao'), 'America/Sao_Paulo'),
                                           Value('DD/MM/YYYY HH24:MI:SS')),
        total_boa=Coalesce(
            Sum('qtd_boa'), Value(0.0, output_field=FloatField())
        ),
        total_planejada=Coalesce(
            Avg('qtd_planejada'), Value(0.0, output_field=FloatField())
        ),
        data_ultima_chamada=Value(data_hora_atual, output_field=CharField()),

    ).annotate(
        restante=ExpressionWrapper(
            F('total_planejada') - F('total_boa'), output_field=FloatField()
        )
    ).values(
        'ordem__status_atual',               # status atual da ordem
        'ordem',                             # id da ordem (chave para o agrupamento)
        'total_boa',                         # quantidade feita
        'total_planejada',                   # quantidade planejada
        'restante',                          # quantidade restante
        'peca',                              # nome da peça
        'data_carga_fmt',                    # data da carga da ordem
        'data_ultima_atualizacao_ordem',     # última atualização da ordem'
        'ordem__maquina__nome',              # nome da máquina   
        'data_ultima_chamada'                # última chamada da API pelo sheets
    ).order_by('-ordem__ultima_atualizacao')[:1000]

    resultado_final = list(pecas_ordem_agg)


    return JsonResponse(resultado_final, safe=False)
