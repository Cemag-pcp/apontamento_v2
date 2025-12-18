from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import (
    Q,
    Prefetch,
    Max,
    Sum,
    F,
    FloatField,
    ExpressionWrapper,
    Value,
    CharField,
    Count,
)
from django.db import transaction
from django.utils import timezone
from django.db.models.functions import (
    Concat,
    Cast,
    TruncMonth,
    ExtractYear,
    ExtractMonth,
)

from ..models import (
    Inspecao,
    DadosExecucaoInspecao,
    Reinspecao,
    Causas,
)
from core.models import Profile, Maquina
from apontamento_estamparia.models import (
    InfoAdicionaisInspecaoEstamparia,
    MedidasInspecaoEstamparia,
    DadosNaoConformidade,
    ImagemNaoConformidade,
)

from datetime import datetime, timedelta
from collections import defaultdict
import json


def inspecao_estamparia(request):

    maquinas = Maquina.objects.filter(setor__nome="estamparia", tipo="maquina")
    motivos = Causas.objects.filter(setor="estamparia")
    inspetores = Profile.objects.filter(
        tipo_acesso="inspetor", permissoes__nome="inspecao/estamparia"
    )

    inspetores = [
        {"nome_usuario": inspetor.user.username, "id": inspetor.user.id}
        for inspetor in inspetores
    ]

    maquinas = [
        {"nome": maquina.nome}
        for maquina in maquinas
    ]

    user_profile = Profile.objects.filter(user=request.user).first()
    if (
        user_profile
        and user_profile.tipo_acesso == "inspetor"
        and user_profile.permissoes.filter(nome="inspecao/estamparia").exists()
    ):
        inspetor_logado = {"nome_usuario": request.user.username, "id": request.user.id}
    else:
        inspetor_logado = None

    context = {
        "maquinas": maquinas,
        "motivos": motivos,
        "inspetores": inspetores,
        "inspetor_logado": inspetor_logado,
    }

    return render(request, "inspecao_estamparia.html", context)


def inspecionar_estamparia(request):

    if request.method != "POST":
        return JsonResponse({"error": "Método não permitido!"}, status=405)

    if request.method == "POST":

        print(request.POST)
        print(request.FILES)

        itemInspecionado = DadosExecucaoInspecao.objects.filter(
            inspecao__id=request.POST.get("id-inspecao")
        )

        if itemInspecionado:
            return JsonResponse({"error": "Item já inspecionado!"}, status=400)

        # Coletar dados simples do formulário
        dataInspecao = request.POST.get("dataInspecao")
        pecasProduzidas = int(request.POST.get("pecasProduzidas"))
        inspetor = request.POST.get("inspetor")
        numPecaDefeituosa = (
            int(request.POST.get("numPecaDefeituosa", None))
            if request.POST.get("numPecaDefeituosa", None)
            else 0
        )
        # Definindo a data de inspeção manualmente
        if dataInspecao == datetime.now().date().isoformat():
            dataInspecao = datetime.now()
        else:
            data_ontem = datetime.now() - timedelta(days=1)
            dataInspecao = data_ontem.replace(hour=20, minute=0, second=0, microsecond=0)

        # Coletar causas de peças mortas (JSON convertido para lista)
        causasPecaMorta_raw = request.POST.get("causasPecaMorta")
        causasPecaMorta = json.loads(causasPecaMorta_raw) if causasPecaMorta_raw else []

        inspecao = get_object_or_404(Inspecao, pk=request.POST.get("id-inspecao"))
        inspetor = Profile.objects.get(user__pk=inspetor)

        # Coletar não conformidades (JSON convertido para lista de dicionários)
        nao_conformidades_raw = request.POST.get("naoConformidades")
        nao_conformidades = (
            json.loads(nao_conformidades_raw) if nao_conformidades_raw else []
        )

        total_pecas_afetadas = 0

        # Faz um loop para percorrer cada não conformidade e somar a quantidade afetada
        for nao_conformidade in nao_conformidades:
            quantidade = (
                int(nao_conformidade.get("quantidadeAfetada", 0))
                if nao_conformidade.get("quantidadeAfetada", 0)
                else 0
            )
            total_pecas_afetadas += quantidade  # Acumula a quantidade afetada

        # model: DadosExecucaoInspecao
        tamanho_amostra = min(3, pecasProduzidas - numPecaDefeituosa)

        nao_conformidade = total_pecas_afetadas  # soma de todas não conformidade, não considera peças mortas

        conformidade = tamanho_amostra - nao_conformidade

        with transaction.atomic():

            new_dados_execucao_inspecao = DadosExecucaoInspecao.objects.create(
                inspecao=inspecao,
                inspetor=inspetor,
                conformidade=conformidade,
                nao_conformidade=nao_conformidade,
            )

            new_dados_execucao_inspecao.data_execucao = dataInspecao

            new_dados_execucao_inspecao.save()

            # model: InfoAdicionalEstamparia
            dados_exec_inspecao = get_object_or_404(
                DadosExecucaoInspecao, inspecao=inspecao
            )
            inspecao_completa = request.POST.get("inspecao_total")  # campo boleano
            auto_inspecao_noturna = request.POST.get("autoInspecaoNoturna")

            print(auto_inspecao_noturna)

            new_info_adicionais = InfoAdicionaisInspecaoEstamparia.objects.create(
                dados_exec_inspecao=dados_exec_inspecao,
                inspecao_completa=True if inspecao_completa == "sim" else False,
                autoinspecao_noturna=True if auto_inspecao_noturna == "true" else False,
                qtd_mortas=numPecaDefeituosa if numPecaDefeituosa > 0 else 0,
            )

            # Relacionar as causas ao objeto criado
            if causasPecaMorta:
                new_info_adicionais.motivo_mortas.set(
                    causasPecaMorta
                )  # Relaciona as causas pelo ManyToManyField

            # model: MedidasInspecaoEstamparia
            informacoes_adicionais_estamparia = get_object_or_404(
                InfoAdicionaisInspecaoEstamparia, pk=new_info_adicionais.pk
            )

            # Dicionários para armazenar os valores dinamicamente
            medidas_raw = request.POST.get("medidas")
            medidas = json.loads(medidas_raw) if medidas_raw else []

            for linha in medidas:
                campos = {
                    "informacoes_adicionais_estamparia": informacoes_adicionais_estamparia
                }

                for i in range(1, 5):
                    chave = f"medida{i}"
                    letra = chr(96 + i)  # 1→a, 2→b, etc.

                    if chave in linha:
                        campos[f"cabecalho_medida_{letra}"] = linha[chave]["nome"]
                        campos[f"medida_{letra}"] = linha[chave]["valor"]
                    else:
                        campos[f"cabecalho_medida_{letra}"] = None
                        campos[f"medida_{letra}"] = None

                MedidasInspecaoEstamparia.objects.create(**campos)

            if medidas:
                primeira_linha = medidas[0]  # pega a primeira linha de medidas

                cabecalho_medida_a = medida_a = None
                cabecalho_medida_b = medida_b = None
                cabecalho_medida_c = medida_c = None
                cabecalho_medida_d = medida_d = None

                if "medida1" in primeira_linha:
                    cabecalho_medida_a = primeira_linha["medida1"]["nome"]
                    medida_a = primeira_linha["medida1"]["valor"]

                if "medida2" in primeira_linha:
                    cabecalho_medida_b = primeira_linha["medida2"]["nome"]
                    medida_b = primeira_linha["medida2"]["valor"]

                if "medida3" in primeira_linha:
                    cabecalho_medida_c = primeira_linha["medida3"]["nome"]
                    medida_c = primeira_linha["medida3"]["valor"]

                if "medida4" in primeira_linha:
                    cabecalho_medida_d = primeira_linha["medida4"]["nome"]
                    medida_d = primeira_linha["medida4"]["valor"]

            MedidasInspecaoEstamparia.objects.create(
                informacoes_adicionais_estamparia=informacoes_adicionais_estamparia,
                cabecalho_medida_a=cabecalho_medida_a,
                medida_a=medida_a,
                cabecalho_medida_b=cabecalho_medida_b,
                medida_b=medida_b,
                cabecalho_medida_c=cabecalho_medida_c,
                medida_c=medida_c,
                cabecalho_medida_d=cabecalho_medida_d,
                medida_d=medida_d,
            )

            soma_qtd_nao_conformidade = 0
            # model: DadosNaoConformidade
            for index, nao_conformidade in enumerate(nao_conformidades, start=1):

                qt_nao_conformidade = (
                    int(nao_conformidade.get("quantidadeAfetada", 0))
                    if nao_conformidade.get("quantidadeAfetada") != ""
                    else 0
                )
                destino = nao_conformidade.get("destino")

                if destino != "sucata":
                    soma_qtd_nao_conformidade += qt_nao_conformidade

                causas = nao_conformidade.get(
                    "causas", []
                )  # Recebe a lista de IDs das causas
                imagens = request.FILES.getlist(
                    f"fotoNaoConformidade{index}"
                )  # Pega as imagens enviadas

                # Criar o objeto principal da não conformidade
                new_dados_nao_conformidade = DadosNaoConformidade.objects.create(
                    informacoes_adicionais_estamparia=informacoes_adicionais_estamparia,
                    qt_nao_conformidade=qt_nao_conformidade,
                    destino=destino,
                )

                # Relacionar as causas ao objeto criado
                if causas:
                    new_dados_nao_conformidade.causas.set(
                        causas
                    )  # Relaciona as causas pelo ManyToManyField

                # Salvar as imagens relacionadas
                for img in imagens:
                    ImagemNaoConformidade.objects.create(
                        nao_conformidade=new_dados_nao_conformidade, imagem=img
                    )

                # Salva o objeto principal
                new_dados_nao_conformidade.save()

            # Reinspecao
            if soma_qtd_nao_conformidade > 0:
                reinspecao = Reinspecao(inspecao=inspecao)
                reinspecao.save()

    return JsonResponse({"success": True, "message": "Inspeção realizada com sucesso!"})


def get_itens_inspecao_estamparia(request):
    if request.method != "GET":
        return JsonResponse({"error": "Método não permitido"}, status=405)

    inspecoes_ids = set(
        DadosExecucaoInspecao.objects.values_list("inspecao", flat=True)
    )

    # Captura os parâmetros enviados na URL
    maquinas_filtradas = (
        request.GET.get("maquinas", "").split(",")
        if request.GET.get("maquinas")
        else []
    )
    
    data_inicio = request.GET.get("data_inicio", None)
    data_fim = request.GET.get("data_fim", None)

    pesquisa_filtrada = request.GET.get("pesquisar", None)
    pagina = int(request.GET.get("pagina", 1))  # Página atual, padrão é 1
    itens_por_pagina = 12  # Itens por página

    # Filtra os dados
    datas = Inspecao.objects.filter(pecas_ordem_estamparia__isnull=False).exclude(
        id__in=inspecoes_ids
    )

    quantidade_total = datas.count()  # Total de itens sem filtro

    if maquinas_filtradas:
        datas = datas.filter(
            pecas_ordem_estamparia__ordem__maquina__nome__in=maquinas_filtradas
        )

    if not data_fim:
        data_fim = data_inicio

    if data_inicio and data_fim:
        datas = datas.filter(
            data_inspecao__date__gte=data_inicio, data_inspecao__date__lte=data_fim
        )
    elif data_inicio:
        datas = datas.filter(data_inspecao__date__gte=data_inicio)
    elif data_fim:
        datas = datas.filter(data_inspecao__date__lte=data_fim)
    
    if pesquisa_filtrada:
        pesquisa_filtrada = pesquisa_filtrada.lower()
        datas = datas.filter(
            pecas_ordem_estamparia__peca__codigo__icontains=pesquisa_filtrada
        )

    datas = datas.select_related(
        "pecas_ordem_estamparia",
        "pecas_ordem_estamparia__ordem",
        "pecas_ordem_estamparia__operador",
    ).order_by("-id")

    # Paginação
    paginador = Paginator(datas, itens_por_pagina)
    pagina_obj = paginador.get_page(pagina)

    dados = []
    for data in pagina_obj:
        data_ajustada = data.data_inspecao - timedelta(hours=3)
        matricula_nome_operador = None

        if data.pecas_ordem_estamparia.operador:
            matricula_nome_operador = f"{data.pecas_ordem_estamparia.operador.matricula} - {data.pecas_ordem_estamparia.operador.nome}"

        # Operador
        if data.pecas_ordem_estamparia.operador:
            matricula_nome_operador = f"{data.pecas_ordem_estamparia.operador.matricula} - {data.pecas_ordem_estamparia.operador.nome}"

        # Peça
        peca_info = ""
        if data.pecas_ordem_estamparia.peca:
            peca_info = f"{data.pecas_ordem_estamparia.peca.codigo} - {data.pecas_ordem_estamparia.peca.descricao}"

        # Máquina
        maquina_nome = None
        if (
            data.pecas_ordem_estamparia.ordem
            and data.pecas_ordem_estamparia.ordem.maquina
        ):
            maquina_nome = data.pecas_ordem_estamparia.ordem.maquina.nome

        item = {
            "id": data.id,
            "data": data_ajustada.strftime("%d/%m/%Y %H:%M:%S"),
            "peca": peca_info,
            "maquina": maquina_nome,
            "qtd_apontada": data.pecas_ordem_estamparia.qtd_boa,
            "operador": matricula_nome_operador,
        }

        dados.append(item)

    return JsonResponse(
        {
            "dados": dados,
            "total": quantidade_total,
            "total_filtrado": paginador.count,  # Total de itens após filtro
            "pagina_atual": pagina_obj.number,
            "total_paginas": paginador.num_pages,
        },
        status=200,
    )


def get_itens_reinspecao_estamparia(request):
    if request.method != "GET":
        return JsonResponse({"error": "Método não permitido"}, status=405)

    # Otimização 1: Usar exists() em vez de values_list para verificar reinspeções
    reinspecao_ids = Reinspecao.objects.filter(reinspecionado=False).values_list(
        "inspecao_id", flat=True
    )

    # Captura os filtros enviados pela URL
    maquinas_filtradas = (
        request.GET.get("maquinas", "").split(",")
        if request.GET.get("maquinas")
        else []
    )
    inspetores_filtrados = (
        request.GET.get("inspetores", "").split(",")
        if request.GET.get("inspetores")
        else []
    )

    data_inicio = request.GET.get("data_inicio", None)
    data_fim = request.GET.get("data_fim", None)
    
    pesquisa_filtrada = request.GET.get("pesquisar", None)
    pagina = int(request.GET.get("pagina", 1))
    itens_por_pagina = 6

    # Otimização 2: Construir a query de forma incremental
    query = Q(id__in=reinspecao_ids) & Q(pecas_ordem_estamparia__isnull=False)

    if maquinas_filtradas:
        query &= Q(pecas_ordem_estamparia__ordem__maquina__nome__in=maquinas_filtradas)

    if data_inicio and not data_fim:
        data_fim = data_inicio

    try:
        if data_inicio:
            data_inicio = datetime.strptime(data_inicio, "%Y-%m-%d").date()
        if data_fim:
            data_fim = datetime.strptime(data_fim, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        data_inicio = None
        data_fim = None

    if data_inicio and data_fim:
        query &= Q(dadosexecucaoinspecao__data_execucao__date__gte=data_inicio) & Q(
            dadosexecucaoinspecao__data_execucao__date__lte=data_fim
        )
    elif data_inicio:
        query &= Q(dadosexecucaoinspecao__data_execucao__date__gte=data_inicio)
    elif data_fim:
        query &= Q(dadosexecucaoinspecao__data_execucao__date__lte=data_fim)

    if pesquisa_filtrada:
        pesquisa_filtrada = pesquisa_filtrada.lower()
        query &= Q(pecas_ordem_estamparia__peca__icontains=pesquisa_filtrada)

    if inspetores_filtrados:
        query &= Q(
            dadosexecucaoinspecao__inspetor__user__username__in=inspetores_filtrados
        )

    # Otimização 3: Selecionar apenas os campos necessários e pré-carregar relacionamentos
    datas = (
        Inspecao.objects.filter(query)
        .select_related(
            "pecas_ordem_estamparia",
            "pecas_ordem_estamparia__ordem",
            "pecas_ordem_estamparia__ordem__maquina",
            "pecas_ordem_estamparia__peca",
        )
        .prefetch_related(
            "dadosexecucaoinspecao_set",
            "dadosexecucaoinspecao_set__inspetor",
            "dadosexecucaoinspecao_set__inspetor__user",
        )
        .order_by("-id")
    ).distinct()

    quantidade_total = Inspecao.objects.filter(
        id__in=reinspecao_ids, pecas_ordem_estamparia__isnull=False
    ).count()

    # Paginação
    paginador = Paginator(datas, itens_por_pagina)
    pagina_obj = paginador.get_page(pagina)

    conformidades_dict = {
        item["inspecao_id"]: item["total_conformidade"]
        for item in DadosExecucaoInspecao.objects.filter(
            inspecao_id__in=[inspecao.id for inspecao in pagina_obj]
        )
        .values("inspecao_id")
        .annotate(total_conformidade=Sum("conformidade"))
    }

    # Otimização 4: Reduzir consultas no loop usando prefetch_related e valores já carregados
    dados = []
    for data in pagina_obj:
        last_dados_execucao = data.dadosexecucaoinspecao_set.last()
        first_dados_execucao = data.dadosexecucaoinspecao_set.first()

        data_ajustada = DadosExecucaoInspecao.objects.filter(inspecao=data).values_list(
            "data_execucao", flat=True
        ).last() - timedelta(hours=3)

        try:
            info_adicionais = InfoAdicionaisInspecaoEstamparia.objects.get(
                dados_exec_inspecao=first_dados_execucao
            )
            qtd_mortas = info_adicionais.qtd_mortas if info_adicionais else 0
        except InfoAdicionaisInspecaoEstamparia.DoesNotExist:
            info_adicionais = None
            qtd_mortas = 0

        qtd_total = (
            data.pecas_ordem_estamparia.qtd_boa
            - conformidades_dict.get(data.id, 0)
            - qtd_mortas
        )

        # Se houver info adicionais, buscar nao conformidades destino sucata
        if info_adicionais:
            dados_nao_conformidade = DadosNaoConformidade.objects.filter(
                informacoes_adicionais_estamparia=info_adicionais, destino="sucata"
            )
            total_sucata = (
                dados_nao_conformidade.aggregate(total=Sum("qt_nao_conformidade"))[
                    "total"
                ]
                or 0
            )

            qtd_total -= total_sucata  # Subtrair as sucatas

        item = {
            "id": data.id,
            "data": data_ajustada.strftime("%d/%m/%Y %H:%M:%S"),
            "peca": f"{data.pecas_ordem_estamparia.peca.codigo} - {data.pecas_ordem_estamparia.peca.descricao}",
            "maquina": (
                data.pecas_ordem_estamparia.ordem.maquina.nome
                if data.pecas_ordem_estamparia.ordem.maquina
                else "Não identificada"
            ),
            "conformidade": (
                last_dados_execucao.conformidade if last_dados_execucao else None
            ),
            "qtd_total": qtd_total,
            "nao_conformidade": (
                last_dados_execucao.nao_conformidade if last_dados_execucao else None
            ),
            "inspetor": (
                last_dados_execucao.inspetor.user.username
                if last_dados_execucao and last_dados_execucao.inspetor
                else None
            ),
        }
        dados.append(item)

    return JsonResponse(
        {
            "dados": dados,
            "total": quantidade_total,
            "total_filtrado": paginador.count,
            "pagina_atual": pagina_obj.number,
            "total_paginas": paginador.num_pages,
        },
        status=200,
    )


def get_itens_inspecionados_estamparia(request):
    if request.method != "GET":
        return JsonResponse({"error": "Método não permitido"}, status=405)

    inspecionados_ids = set(
        DadosExecucaoInspecao.objects.values_list("inspecao", flat=True)
    )

    # Captura os filtros aplicados pela URL
    maquinas_filtradas = (
        request.GET.get("maquinas", "").split(",")
        if request.GET.get("maquinas")
        else []
    )
    inspetores_filtrados = (
        request.GET.get("inspetores", "").split(",")
        if request.GET.get("inspetores")
        else []
    )

    status_conformidade_filtrados = (
        request.GET.get("status-conformidade", "").split(",")
        if request.GET.get("status-conformidade")
        else []
    )

    data_inicio = request.GET.get("data_inicio", None)
    data_fim = request.GET.get("data_fim", None)

    pesquisa_filtrada = request.GET.get("pesquisar", None)
    pagina = int(request.GET.get("pagina", 1))  # Página atual, padrão é 1
    itens_por_pagina = 6  # Itens por página

    # Filtra os dados
    datas = Inspecao.objects.filter(
        id__in=inspecionados_ids, pecas_ordem_estamparia__isnull=False
    )

    quantidade_total = datas.count()  # Total de itens sem filtro

    if maquinas_filtradas:
        datas = datas.filter(
            pecas_ordem_estamparia__ordem__maquina__nome__in=maquinas_filtradas
        )

    if data_inicio and not data_fim:
        data_fim = data_inicio

    datas = datas.annotate(
        ultima_data_execucao=Max("dadosexecucaoinspecao__data_execucao")
    )

    if data_inicio and data_fim:
        datas = datas.filter(
            ultima_data_execucao__date__gte=data_inicio,
            ultima_data_execucao__date__lte=data_fim,
        ).order_by("-ultima_data_execucao")
    elif data_inicio:
        datas = datas.filter(
            ultima_data_execucao__date__gte=data_inicio
        ).order_by("-ultima_data_execucao")
    elif data_fim:
        datas = datas.filter(
            ultima_data_execucao__date__lte=data_fim
        ).order_by("-ultima_data_execucao")

    if pesquisa_filtrada:
        datas = datas.annotate(
            codigo_descricao=Concat(
                "pecas_ordem_estamparia__peca__codigo",
                Value(" - "),
                "pecas_ordem_estamparia__peca__descricao",
            )
        ).filter(codigo_descricao__icontains=pesquisa_filtrada)

    if inspetores_filtrados:
        datas = datas.filter(
            dadosexecucaoinspecao__inspetor__user__username__in=inspetores_filtrados
        )

    # Filtro de status de conformidade
    if status_conformidade_filtrados:
        # Verifica os casos possíveis de combinação de filtros
        if set(status_conformidade_filtrados) == {"conforme", "nao_conforme"}:
            pass
        elif "conforme" in status_conformidade_filtrados:
            # Apenas itens conformes (nao_conformidades = 0) E num_execucao=0
            datas = datas.filter(
                dadosexecucaoinspecao__nao_conformidade=0,
                dadosexecucaoinspecao__num_execucao=0,
            )
        elif "nao_conforme" in status_conformidade_filtrados:
            # Apenas itens não conformes (nao_conformidades > 0) E num_execucao=0
            datas = datas.filter(
                dadosexecucaoinspecao__nao_conformidade__gt=0,
                dadosexecucaoinspecao__num_execucao=0,
            )

    datas = datas.select_related(
        "pecas_ordem_estamparia",
        "pecas_ordem_estamparia__ordem",
        "pecas_ordem_estamparia__operador",
    ).order_by("-dadosexecucaoinspecao__data_execucao")

    # Paginação
    paginador = Paginator(datas, itens_por_pagina)
    pagina_obj = paginador.get_page(pagina)

    dados_execucao = DadosExecucaoInspecao.objects.filter(
        inspecao__in=pagina_obj
    ).select_related(
        "inspecao", "inspetor__user", "inspecao__pecas_ordem_estamparia__ordem__maquina"
    )

    # Cria um dicionário para mapear inspecao_id para seus dados de execução
    dados_execucao_dict = {de.inspecao_id: de for de in dados_execucao}

    dados = []
    for data in pagina_obj:
        de = dados_execucao_dict.get(data.id)

        if de:
            data_ajustada = DadosExecucaoInspecao.objects.filter(
                inspecao=data
            ).values_list("data_execucao", flat=True).last() - timedelta(hours=3)

            possui_nao_conformidade = de.nao_conformidade > 0 or de.num_execucao > 0

            item = {
                "id": data.id,
                "id_dados_execucao": de.id,
                "data": data_ajustada.strftime("%d/%m/%Y %H:%M:%S"),
                "peca": f"{data.pecas_ordem_estamparia.peca.codigo} - {data.pecas_ordem_estamparia.peca.descricao}",
                "maquina": (
                    data.pecas_ordem_estamparia.ordem.maquina.nome
                    if data.pecas_ordem_estamparia.ordem.maquina
                    else "Não identificada"
                ),
                "inspetor": de.inspetor.user.username if de.inspetor else None,
                "possui_nao_conformidade": possui_nao_conformidade,
            }

            dados.append(item)
    return JsonResponse(
        {
            "dados": dados,
            "total": quantidade_total,
            "total_filtrado": paginador.count,  # Total de itens após filtro
            "pagina_atual": pagina_obj.number,
            "total_paginas": paginador.num_pages,
        },
        status=200,
    )


def get_historico_estamparia(request, id):
    if request.method != "GET":
        return JsonResponse({"error": "Método não permitido"}, status=405)

    dados = (
        DadosExecucaoInspecao.objects.filter(inspecao__id=id)
        .select_related("inspetor__user")
        .prefetch_related(
            "infoadicionaisinspecaoestamparia_set",
            "infoadicionaisinspecaoestamparia_set__motivo_mortas",
            "infoadicionaisinspecaoestamparia_set__medidasinspecaoestamparia_set",
        )
        .order_by("-id")
    )

    list_history = []
    for dado in dados:
        info_adicionais = dado.infoadicionaisinspecaoestamparia_set.first()
        medidas = []

        if info_adicionais:
            total_medidas = dado.conformidade + dado.nao_conformidade
            medidas_qs = info_adicionais.medidasinspecaoestamparia_set.all()[
                :total_medidas
            ]

            medidas = [
                {
                    "cabecalhoMedidaA": m.cabecalho_medida_a,
                    "medidaA": m.medida_a,
                    "cabecalhoMedidaB": m.cabecalho_medida_b,
                    "medidaB": m.medida_b,
                    "cabecalhoMedidaC": m.cabecalho_medida_c,
                    "medidaC": m.medida_c,
                    "cabecalhoMedidaD": m.cabecalho_medida_d,
                    "medidaD": m.medida_d,
                }
                for m in medidas_qs
            ]

        history_item = {
            "id": dado.id,
            "id_inspecao": id,
            "data_execucao": (dado.data_execucao - timedelta(hours=3)).strftime(
                "%d/%m/%Y %H:%M:%S"
            ),
            "num_execucao": dado.num_execucao,
            "conformidade": dado.conformidade,
            "nao_conformidade": dado.nao_conformidade,
            "inspetor": dado.inspetor.user.username if dado.inspetor else None,
            "info_adicionais": {
                "id": info_adicionais.id if info_adicionais else None,
                "inspecao_completa": (
                    info_adicionais.inspecao_completa if info_adicionais else False
                ),
                "qtd_mortas": info_adicionais.qtd_mortas if info_adicionais else 0,
                "motivo_mortas": (
                    [motivo.nome for motivo in info_adicionais.motivo_mortas.all()]
                    if info_adicionais
                    else []
                ),
                "ficha_url": (
                    info_adicionais.ficha.url
                    if info_adicionais and info_adicionais.ficha
                    else None
                ),
            },
            "medidas_inspecao": medidas,
            "total_medidas": dado.conformidade
            + dado.nao_conformidade,  # Adicionando para facilitar no frontend
        }
        list_history.append(history_item)

    return JsonResponse({"history": list_history}, status=200)


def get_historico_causas_estamparia(request, id):
    if request.method != "GET":
        return JsonResponse({"error": "Método não permitido"}, status=405)

    try:
        dados_nao_conformidades = DadosNaoConformidade.objects.filter(
            informacoes_adicionais_estamparia__dados_exec_inspecao__id=id
        ).prefetch_related("causas", "imagens")

        causas_dict = defaultdict(
            lambda: {
                "id_nc": None,
                "nomes": [],
                "destino": None,
                "quantidade": None,
                "imagens": [],
            }
        )

        for dados in dados_nao_conformidades:
            if causas_dict[dados.id]["id_nc"] is None:
                causas_dict[dados.id]["id_nc"] = dados.id
                causas_dict[dados.id]["destino"] = dados.destino
                causas_dict[dados.id]["quantidade"] = dados.qt_nao_conformidade
                causas_dict[dados.id]["imagens"] = [
                    {"id": imagem.id, "url": imagem.imagem.url}
                    for imagem in dados.imagens.all()
                ]
            causas_dict[dados.id]["nomes"].extend(
                [causa.nome for causa in dados.causas.all()]
            )

        causas_list = list(causas_dict.values())

        return JsonResponse({"causas": causas_list}, status=200)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


def envio_reinspecao_estamparia(request):
    if request.method != "POST":
        return JsonResponse({"error": "Método não permitido!"}, status=405)

    try:
        with transaction.atomic():
            print(request.POST)
            print(request.FILES)
            id_inspecao = request.POST.get("idInspecao")
            id_execucao = request.POST.get("execucaoId")
            data_inspecao = request.POST.get("dataReinspecao")
            maquina = request.POST.get("maquinaReinspecao")
            pecas = request.POST.get("pecasProduzidasReinspecao")
            inspetor_id = request.POST.get("inspetorReinspecao")
            conformidade = request.POST.get("qtdConformidadeReinspecao")
            nao_conformidade = request.POST.get("qtdNaoConformidadeReinspecao")
            ficha_reinspecao = request.FILES.get("ficha_reinspecao")

            data_convertida = timezone.make_aware(datetime.fromisoformat(data_inspecao))

            inspecao = Inspecao.objects.get(id=id_inspecao)
            inspetor = Profile.objects.get(id=inspetor_id)

            # Criação do registro de execução
            dados_execucao = DadosExecucaoInspecao.objects.create(
                inspecao=inspecao,
                inspetor=inspetor,
                data_execucao=data_convertida,
                conformidade=int(conformidade),
                nao_conformidade=int(nao_conformidade),
            )

            # Criação das informações adicionais
            info_adicionais = InfoAdicionaisInspecaoEstamparia.objects.create(
                dados_exec_inspecao=dados_execucao,
                inspecao_completa=True,
                ficha=ficha_reinspecao,
            )

            if int(nao_conformidade) > 0:
                quantidade_total_causas = int(
                    request.POST.get("quantidade_total_causas", 0)
                )

                for i in range(1, quantidade_total_causas + 1):
                    causas_ids = request.POST.getlist(f"causas_reinspecao_{i}")
                    quantidade_afetada = request.POST.get(f"quantidade_reinspecao_{i}")
                    imagens = request.FILES.getlist(f"imagens_reinspecao_{i}")

                    # Criar o objeto principal da não conformidade
                    dados_nao_conformidade = DadosNaoConformidade.objects.create(
                        informacoes_adicionais_estamparia=info_adicionais,
                        qt_nao_conformidade=int(quantidade_afetada),
                        destino="Reinspeção",  # Aqui você pode ajustar o destino conforme o seu fluxo
                    )

                    # Relacionar as causas
                    if causas_ids:
                        dados_nao_conformidade.causas.set(causas_ids)

                    # Salvar as imagens relacionadas
                    for imagem in imagens:
                        ImagemNaoConformidade.objects.create(
                            nao_conformidade=dados_nao_conformidade,
                            imagem=imagem,
                        )
            else:
                reinspecao = Reinspecao.objects.filter(inspecao=inspecao).first()
                if reinspecao:
                    reinspecao.reinspecionado = True
                    reinspecao.save()

        return JsonResponse({"success": True})

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


### dashboard estamparia ###


def dashboard_estamparia(request):

    return render(request, "dashboard/estamparia.html")


def indicador_estamparia_analise_temporal(request):
    """
    select
        id.data_execucao as data_inspecao,
        id.conformidade,
        id.nao_conformidade,
        ii.data_inspecao as data_producao,
        ii.pecas_ordem_pintura_id,
        app.peca,
        app.tipo,
        app.qtd_boa,
        ic2.nome as nome_conformidade
    from apontamento_v2.inspecao_inspecao ii
    left join apontamento_v2.inspecao_dadosexecucaoinspecao id on ii.id = id.inspecao_id
    left join apontamento_v2.apontamento_pintura_pecasordem app on app.id = ii.pecas_ordem_pintura_id
    left join apontamento_v2.inspecao_causasnaoconformidade ic on ic.dados_execucao_id = id.id
    left join apontamento_v2.inspecao_causasnaoconformidade_causa icc on icc.causasnaoconformidade_id = ic.id
    left join apontamento_v2.inspecao_causas ic2 on ic2.id = icc.causas_id
    where ii.pecas_ordem_pintura_id notnull
    order by id.data_execucao desc;
    """

    # Recebe os parâmetros de data
    setor = request.GET.get("setor")
    data_inicio = request.GET.get("data_inicio")
    data_fim = request.GET.get("data_fim")

    try:
        if data_inicio:
            data_inicio = datetime.strptime(data_inicio, "%Y-%m-%d")
        if data_fim:
            data_fim = datetime.strptime(data_fim, "%Y-%m-%d") + timedelta(days=1)
    except ValueError:
        return JsonResponse(
            {"erro": "Formato de data inválido. Use YYYY-MM-DD."}, status=400
        )

    # Filtra somente as produções com peça ligada (mesmo sem inspeção)
    queryset = Inspecao.objects.filter(pecas_ordem_estamparia__isnull=False)

    if data_inicio:
        queryset = queryset.filter(data_inspecao__gte=data_inicio)
    if data_fim:
        queryset = queryset.filter(data_inspecao__lte=data_fim)

    queryset = (
        queryset.annotate(
            mes=Cast(TruncMonth("data_inspecao"), output_field=CharField()),
            qtd_boa=F("pecas_ordem_estamparia__qtd_boa"),
            conformidade=F("dadosexecucaoinspecao__conformidade"),
            nao_conformidade=F("dadosexecucaoinspecao__nao_conformidade"),
        )
        .values("mes")
        .annotate(
            qtd_peca_produzida=Count("id"),
            qtd_peca_inspecionada=Count("dadosexecucaoinspecao__id"),
            soma_conformidade=Sum("conformidade"),
            soma_nao_conformidade=Sum("nao_conformidade"),
        )
        .order_by("mes")
    )

    resultado = []
    for item in queryset:
        conformidade = item["soma_conformidade"] or 0
        nao_conformidade = item["soma_nao_conformidade"] or 0
        taxa_nc = (nao_conformidade / conformidade) if conformidade else 0

        resultado.append(
            {
                "mes": item["mes"][:7],  # YYYY-MM
                "qtd_peca_produzida": item["qtd_peca_produzida"] or 0,
                "qtd_peca_inspecionada": item["qtd_peca_inspecionada"] or 0,
                "taxa_nao_conformidade": round(taxa_nc, 4),
            }
        )

    return JsonResponse(resultado, safe=False)


def indicador_estamparia_resumo_analise_temporal(request):
    data_inicio = request.GET.get("data_inicio")
    data_fim = request.GET.get("data_fim")

    try:
        if data_inicio:
            data_inicio = datetime.strptime(data_inicio, "%Y-%m-%d")
        if data_fim:
            data_fim = datetime.strptime(data_fim, "%Y-%m-%d") + timedelta(days=1)
    except ValueError:
        return JsonResponse(
            {"erro": "Formato de data inválido. Use YYYY-MM-DD."}, status=400
        )

    # Query principal
    queryset = Inspecao.objects.filter(pecas_ordem_estamparia__isnull=False)

    if data_inicio:
        queryset = queryset.filter(data_inspecao__gte=data_inicio)
    if data_fim:
        queryset = queryset.filter(data_inspecao__lte=data_fim)

    # Anotações e agregações
    queryset = (
        queryset.annotate(
            ano=ExtractYear("data_inspecao"),
            mes_num=ExtractMonth("data_inspecao"),
            qtd_boa=F("pecas_ordem_estamparia__qtd_boa"),
            conformidade=F("dadosexecucaoinspecao__conformidade"),
            nao_conformidade=F("dadosexecucaoinspecao__nao_conformidade"),
            qtd_inspecionada=ExpressionWrapper(
                F("dadosexecucaoinspecao__conformidade")
                + F("dadosexecucaoinspecao__nao_conformidade"),
                output_field=FloatField(),
            ),
        )
        .values("ano", "mes_num")
        .annotate(
            total_produzida=Count("id"),
            total_inspecionada=Count("dadosexecucaoinspecao__id"),
            total_nao_conforme=Count(
                "dadosexecucaoinspecao__id", filter=Q(nao_conformidade__gt=0)
            ),
        )
        .order_by("ano", "mes_num")
    )

    # Monta JSON
    resultado = []
    for item in queryset:
        mes_formatado = f"{item['ano']}-{item['mes_num']}"

        total_prod = item["total_produzida"] or 0
        total_insp = item["total_inspecionada"] or 0
        total_nc = item["total_nao_conforme"] or 0

        perc_insp = (total_insp / total_prod) * 100 if total_prod else 0

        resultado.append(
            {
                "Data": mes_formatado,
                "N° de peças produzidas": int(total_prod),
                "N° de inspeções": int(total_insp),
                "N° de não conformidades": int(total_nc),
                "% de inspeção": f"{perc_insp:.2f} %",
            }
        )

    return JsonResponse(resultado, safe=False)


def causas_nao_conformidade_mensal_estamparia(request):
    data_inicio = request.GET.get("data_inicio")
    data_fim = request.GET.get("data_fim")

    try:
        if data_inicio:
            data_inicio = datetime.strptime(data_inicio, "%Y-%m-%d")
        if data_fim:
            data_fim = datetime.strptime(data_fim, "%Y-%m-%d") + timedelta(days=1)
    except ValueError:
        return JsonResponse(
            {"erro": "Formato de data inválido. Use YYYY-MM-DD."}, status=400
        )

    queryset = DadosNaoConformidade.objects.filter(
        informacoes_adicionais_estamparia__dados_exec_inspecao__inspecao__data_inspecao__isnull=False,
        informacoes_adicionais_estamparia__dados_exec_inspecao__inspecao__pecas_ordem_estamparia__isnull=False,
        causas__isnull=False,
    )

    if data_inicio:
        queryset = queryset.filter(
            informacoes_adicionais_estamparia__dados_exec_inspecao__inspecao__data_inspecao__gte=data_inicio
        )
    if data_fim:
        queryset = queryset.filter(
            informacoes_adicionais_estamparia__dados_exec_inspecao__inspecao__data_inspecao__lte=data_fim
        )

    resultados = (
        queryset.annotate(
            mes_formatado=Concat(
                ExtractYear(
                    "informacoes_adicionais_estamparia__dados_exec_inspecao__inspecao__data_inspecao"
                ),
                Value("-"),
                ExtractMonth(
                    "informacoes_adicionais_estamparia__dados_exec_inspecao__inspecao__data_inspecao"
                ),
                output_field=CharField(),
            ),
            peca_info=Concat(
                F(
                    "informacoes_adicionais_estamparia__dados_exec_inspecao__inspecao__pecas_ordem_estamparia__peca__codigo"
                ),
                Value(" - "),
                F(
                    "informacoes_adicionais_estamparia__dados_exec_inspecao__inspecao__pecas_ordem_estamparia__peca__descricao"
                ),
                output_field=CharField(),
            ),
        )
        .values(
            "mes_formatado",
            "causas__nome",
            "destino",
            "peca_info",  # Usando a anotação que criamos
        )
        .annotate(total_nao_conformidades=Sum("qt_nao_conformidade"))
        .order_by("mes_formatado", "causas__nome")
    )

    # Formatação final
    resultado = [
        {
            "Data": item["mes_formatado"],
            "Causa": item["causas__nome"],
            "Destino": item["destino"],
            "Peça": item["peca_info"],  # Formato "codigo - descricao"
            "Soma do N° Total de não conformidades": item["total_nao_conformidades"],
        }
        for item in resultados
    ]

    return JsonResponse(resultado, safe=False)


def imagens_nao_conformidade_estamparia(request):
    data_inicio = request.GET.get("data_inicio")
    data_fim = request.GET.get("data_fim")

    try:
        if data_inicio:
            data_inicio = datetime.strptime(data_inicio, "%Y-%m-%d")
        if data_fim:
            data_fim = datetime.strptime(data_fim, "%Y-%m-%d") + timedelta(days=1)
    except ValueError:
        return JsonResponse(
            {"erro": "Formato de data inválido. Use YYYY-MM-DD."}, status=400
        )

    # Query otimizada com select_related e prefetch_related específicos
    queryset = (
        DadosNaoConformidade.objects.filter(
            informacoes_adicionais_estamparia__dados_exec_inspecao__data_execucao__isnull=False,
            informacoes_adicionais_estamparia__dados_exec_inspecao__inspecao__pecas_ordem_estamparia__isnull=False,
        )
        .select_related(
            "informacoes_adicionais_estamparia",
            "informacoes_adicionais_estamparia__dados_exec_inspecao",
        )
        .prefetch_related(
            Prefetch("causas", queryset=Causas.objects.only("nome")),
            Prefetch("imagens", queryset=ImagemNaoConformidade.objects.only("imagem")),
        )
        .only(
            "qt_nao_conformidade",
            "informacoes_adicionais_estamparia__dados_exec_inspecao__data_execucao",
        )
    )

    if data_inicio:
        queryset = queryset.filter(
            informacoes_adicionais_estamparia__dados_exec_inspecao__data_execucao__gte=data_inicio
        )
    if data_fim:
        queryset = queryset.filter(
            informacoes_adicionais_estamparia__dados_exec_inspecao__data_execucao__lte=data_fim
        )

    # Pré-carrega todos os dados relacionados de uma vez
    dados_completos = list(queryset)

    resultado = []
    for item in dados_completos:
        date = (
            item.informacoes_adicionais_estamparia.dados_exec_inspecao.data_execucao
            - timedelta(hours=3)
        )
        data_execucao = date.strftime("%Y-%m-%d %H:%M:%S")

        # Acessa os dados já pré-carregados
        causas = [c.nome for c in item.causas.all()]
        imagens = [
            imagem.imagem.url
            for imagem in item.imagens.all()
            if hasattr(imagem, "imagem")
        ]

        for url in imagens:
            resultado.append(
                {
                    "data_execucao": data_execucao,
                    "causas": causas,
                    "quantidade": item.qt_nao_conformidade,
                    "imagem_url": url,
                }
            )

    return JsonResponse(resultado, safe=False)


def ficha_inspecao_estamparia(request):

    data_inicio = request.GET.get("data_inicio")
    data_fim = request.GET.get("data_fim")

    try:
        if data_inicio:
            data_inicio = datetime.strptime(data_inicio, "%Y-%m-%d")
        if data_fim:
            # Adiciona 1 dia para incluir todo o dia especificado
            data_fim = datetime.strptime(data_fim, "%Y-%m-%d") + timedelta(days=1)
    except ValueError:
        return JsonResponse(
            {"erro": "Formato de data inválido. Use YYYY-MM-DD."}, status=400
        )

    # Query base com joins e prefetch necessários
    queryset = (
        InfoAdicionaisInspecaoEstamparia.objects.select_related("dados_exec_inspecao")
        .prefetch_related("motivo_mortas")
        .filter(
            dados_exec_inspecao__data_execucao__isnull=False,
            ficha__isnull=False,  # Apenas registros com ficha
        )
    )

    # Aplica filtros de data
    if data_inicio:
        queryset = queryset.filter(dados_exec_inspecao__data_execucao__gte=data_inicio)
    if data_fim:
        queryset = queryset.filter(dados_exec_inspecao__data_execucao__lt=data_fim)

    # Annotate com dados adicionais
    queryset = queryset.annotate(data_execucao=F("dados_exec_inspecao__data_execucao"))

    # Prepara os resultados
    resultados = []
    for item in queryset:
        if item.ficha:  # Garante que só retorne itens com ficha
            resultados.append(
                {
                    "data_execucao": item.data_execucao.strftime("%Y-%m-%d %H:%M:%S"),
                    "inspecao_completa": item.inspecao_completa,
                    "qtd_mortas": item.qtd_mortas,
                    "motivos_mortas": [
                        causa.nome for causa in item.motivo_mortas.all()
                    ],
                    "ficha_url": request.build_absolute_uri(item.ficha.url),
                }
            )

    return JsonResponse(resultados, safe=False)
