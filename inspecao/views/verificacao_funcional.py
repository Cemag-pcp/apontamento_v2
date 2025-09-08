from django.shortcuts import render
from django.http import JsonResponse
from apontamento_pintura.models import TesteFuncional
from django.core.paginator import Paginator
import json

def verificacao_funcional_pintura(request):
    if request.method == 'GET':
        cores = ["Amarelo", "Azul", "Cinza", "Laranja", "Verde", "Vermelho"]
        return render(request,'verificacao_funcional/verificacao_funcional.html', {'cores': cores})
    else:
        return JsonResponse({'error':'Método não permitido!'})
    
def api_testes_funcionais_pintura_pendentes(request):
    if request.method != "GET":
        return JsonResponse({"error": "Método não permitido"}, status=405)

    # Captura os parâmetros enviados na URL
    cores_filtradas = (
        request.GET.get("cores", "").split(",") if request.GET.get("cores") else []
    )
    data_filtrada = request.GET.get("data", None)
    pesquisa_filtrada = request.GET.get("pesquisar", None)
    pagina = int(request.GET.get("pagina", 1))  # Página atual, padrão é 1
    itens_por_pagina = 12  # Itens por página

    # Filtra os dados
    # datas = Inspecao.objects.filter(pecas_ordem_pintura__isnull=False)
    datas = TesteFuncional.objects.filter(status='pendente').values('id','peca_ordem__id','peca_ordem__peca','peca_ordem__ordem_id__cor','status','peca_ordem__tipo','peca_ordem__ordem__data_carga')

    quantidade_total = datas.count()  # Total de itens sem filtro

    if cores_filtradas:
        datas = datas.filter(pecas_ordem_pintura__ordem__cor__in=cores_filtradas)

    if data_filtrada:
        datas = datas.filter(data_inspecao__date=data_filtrada)

    if pesquisa_filtrada:
        pesquisa_filtrada = pesquisa_filtrada.lower()
        datas = datas.filter(pecas_ordem_pintura__peca__icontains=pesquisa_filtrada)

    # datas = datas.select_related(
    #     "pecas_ordem_pintura",
    #     "pecas_ordem_pintura__ordem",
    #     "pecas_ordem_pintura__operador_fim",
    # ).order_by("-id")

    # Paginação
    paginador = Paginator(datas, itens_por_pagina)
    pagina_obj = paginador.get_page(pagina)

    dados = []
    for data in pagina_obj:
        # data_ajustada = data.data_inspecao - timedelta(hours=3)
        # matricula_nome_operador = None

        # item = {
        #     "id": data.id,
        #     "data": data_ajustada.strftime("%d/%m/%Y %H:%M:%S"),
        #     "peca": data.pecas_ordem_pintura.peca,
        #     "cor": data.pecas_ordem_pintura.ordem.cor,
        #     "qtd_apontada": data.pecas_ordem_pintura.qtd_boa,
        #     "tipo": data.pecas_ordem_pintura.tipo,
        #     "operador": matricula_nome_operador,
        # }

        item = {
                'id': data['id'],
                'peca_ordem_id':data['peca_ordem__id'],
                'peca': data['peca_ordem__peca'],
                'cor': data['peca_ordem__ordem_id__cor'],
                'status': data['status'],
                'tipo_pintura': data['peca_ordem__tipo'],
                'data_carga': data['peca_ordem__ordem__data_carga'].strftime("%d/%m/%Y")
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


def api_testes_funcionais_pintura_finalizados(request):
    # if request.method == 'GET':
    #     testes = list(TesteFuncional.objects.filter(status__in=['aprovado','reprovado']).values())

    #     return JsonResponse({'testes':testes})
    # else:
    #     return JsonResponse({'error':'Método não permitido!'})
    return 'oi'

    if request.method != "GET":
        return JsonResponse({"error": "Método não permitido"}, status=405)

    # Captura os filtros aplicados pela URL
    cores_filtradas = (
        request.GET.get("cores", "").split(",") if request.GET.get("cores") else []
    )

    status_verificacao_filtro = (
        request.GET.get("status-conformidade", "").split(",")
        if request.GET.get("status-conformidade")
        else []
    )
    
    data_filtrada = request.GET.get("data", None)
    pesquisa_filtrada = request.GET.get("pesquisar", None)
    pagina = int(request.GET.get("pagina", 1))  # Página atual, padrão é 1
    itens_por_pagina = 6  # Itens por página

    datas = TesteFuncional.objects.filter(status__in=['aprovado','reprovado'])

    quantidade_total = datas.count()  # Total de itens sem filtro

    if cores_filtradas:
        datas = datas.filter(
            pecas_ordem_pintura__ordem__cor__in=cores_filtradas
        ).distinct()

    if data_filtrada:
        datas = datas.filter(
            dadosexecucaoinspecao__data_execucao__date=data_filtrada
        ).distinct()

    if pesquisa_filtrada:
        datas = datas.filter(
            pecas_ordem_pintura__peca__icontains=pesquisa_filtrada
        ).distinct()

    # Filtro de status de conformidade
    if status_verificacao_filtro:
        # Verifica os casos possíveis de combinação de filtros
        if set(status_verificacao_filtro) == {"aprovado", "reprovado"}:
            pass
        elif "aprovado" in status_verificacao_filtro:
            # Apenas itens conformes (nao_conformidades = 0) E num_execucao=0
            datas = datas.filter(
                dadosexecucaoinspecao__nao_conformidade=0,
                dadosexecucaoinspecao__num_execucao=0,
            )
        elif "reprovado" in status_verificacao_filtro:
            # Apenas itens não conformes (nao_conformidades > 0) E num_execucao=0
            datas = datas.filter(
                dadosexecucaoinspecao__nao_conformidade__gt=0,
                dadosexecucaoinspecao__num_execucao=0,
            )

    datas = datas.select_related(
        "pecas_ordem_pintura",
        "pecas_ordem_pintura__ordem",
        "pecas_ordem_pintura__operador_fim",
    ).order_by("-dadosexecucaoinspecao__data_execucao")

    # Paginação
    paginador = Paginator(datas, itens_por_pagina)
    pagina_obj = paginador.get_page(pagina)

    dados = []
    for data in pagina_obj:
        # data_ajustada = DadosExecucaoInspecao.objects.filter(inspecao=data).values_list(
        #     "data_execucao", flat=True
        # ).last() - timedelta(hours=3)

        possui_nao_conformidade = DadosExecucaoInspecao.objects.filter(
            inspecao=data, nao_conformidade__gt=0
        ).exists()

        item = {
            "id": data.id,
            "id_dados_execucao": DadosExecucaoInspecao.objects.filter(inspecao=data)
            .values_list("id", flat=True)
            .first(),
            "data": data_ajustada.strftime("%d/%m/%Y %H:%M:%S"),
            "peca": data.pecas_ordem_pintura.peca,
            "cor": data.pecas_ordem_pintura.ordem.cor,
            "tipo": data.pecas_ordem_pintura.tipo,
            "inspetor": DadosExecucaoInspecao.objects.filter(inspecao=data)
            .values_list("inspetor__user__username", flat=True)
            .first(),
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

def realizar_verificacao_funcional(request):
    dados = json.loads(request.body)
    if request.method == 'POST':
        print(dados)
    return 'oi'