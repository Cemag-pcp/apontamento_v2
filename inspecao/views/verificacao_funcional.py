from django.shortcuts import render
from django.http import JsonResponse
from apontamento_pintura.models import TesteFuncional
from django.core.paginator import Paginator
import json
from datetime import timedelta

def verificacao_funcional_pintura(request):
    if request.method == 'GET':
        cores = ["Amarelo", "Azul", "Cinza", "Laranja", "Verde", "Vermelho"]
        return render(request,'verificacao_funcional/verificacao_funcional.html', {'cores': cores})
    else:
        return JsonResponse({'error':'Método não permitido!'})
    
def api_testes_funcionais_pintura(request):
    if request.method != "GET":
        return JsonResponse({"error": "Método não permitido"}, status=405)
    
    status_url = request.GET.get("status", None)

    if status_url == 'finalizado':
        status_url = ['aprovado','reprovado']
    else:
        status_url = ['pendente']


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
    datas = TesteFuncional.objects.filter(status__in=status_url).values('id','peca_ordem__id','peca_ordem__peca','peca_ordem__ordem_id__cor','status','peca_ordem__tipo','peca_ordem__ordem__data_carga', 'data_inicial', 'data_atualizacao')

    quantidade_total = datas.count()  # Total de itens sem filtro

    if cores_filtradas:
        datas = datas.filter(peca_ordem__ordem__cor__in=cores_filtradas)

    if data_filtrada:
        datas = datas.filter(data_inicial__date=data_filtrada)

    if pesquisa_filtrada:
        pesquisa_filtrada = pesquisa_filtrada.lower()
        datas = datas.filter(peca_ordem__peca__icontains=pesquisa_filtrada)

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
        data_ajustada = data['data_inicial'] - timedelta(hours=3)
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
                'data_carga': data['peca_ordem__ordem__data_carga'].strftime("%d/%m/%Y"),
                'data_inicial': data_ajustada.strftime("%d/%m/%Y %H:%M:%S") if data_ajustada else None,
                'data_atualizacao': (data['data_atualizacao'] - timedelta(hours=3)).strftime("%d/%m/%Y %H:%M:%S") if data['data_atualizacao'] else None,
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
        try:
            registro_teste = TesteFuncional.objects.get(pk=int(dados['idRegistro']))
            campos_obrigatorios = ['idRegistro','statusAderencia','statusTonalidade', 'espessura-camada-1','espessura-camada-2', 'espessura-camada-3']
            if "statusPolimerizacao" in dados: # PO
                campos_obrigatorios.append('statusPolimerizacao')
                for campo in campos_obrigatorios:
                    if campo not in dados:
                        return JsonResponse({'error': f'Campo {campo} é obrigatório!'},status=400)
                
                if type(dados['statusPolimerizacao']) is not bool:
                    return JsonResponse({'error':'Os campos de status devem ser booleanos!'}, status=400)
                
                # Registra o teste de polimerização
                registro_teste.polimerizacao = dados['statusPolimerizacao']
            
            if type(dados['statusAderencia']) is not bool or type(dados['statusTonalidade']) is not bool:
                return JsonResponse({'error':'Os campos de status devem ser booleanos!'}, status=400)
            
            registro_teste.aderencia = dados['statusAderencia']
            registro_teste.tonalidade = dados['statusTonalidade']

            if 'observacoes-teste' in dados:
                registro_teste.observacao = dados['observacoes-teste']
            # CAMPO DE IMAGEM A SER FEITO DEPOIS

            try:
                registro_teste.espessura_camada_1 = float(dados['espessura-camada-1'])
                registro_teste.espessura_camada_2 = float(dados['espessura-camada-2'])
                registro_teste.espessura_camada_3 = float(dados['espessura-camada-3'])
            except ValueError:
                return JsonResponse({'error':'Os campos de espessura devem ser numéricos!'}, status=400)
            
            resultados_espessura_camada = [registro_teste.espessura_camada_1,registro_teste.espessura_camada_2,registro_teste.espessura_camada_3]

            causa_reprovacao = []
            if "statusPolimerizacao" in dados: # PO
                if dados['statusPolimerizacao'] and dados['statusAderencia'] and dados['statusTonalidade']:
                    registro_teste.status = 'aprovado'
                    for espessura in resultados_espessura_camada:
                        if not (60 <= espessura <= 80):
                            registro_teste.status = 'reprovado'
                            causa_reprovacao.append('espessura fora do padrão (60-80 microns)')
                            break

                    #PU - 40 a 60 microns
	                #PÓ - 60 a 80 microns
                else:
                    causa_reprovacao.append('falha em algum teste (polimerização, aderência ou tonalidade)')
                    registro_teste.status = 'reprovado'
            else: # PU
                if dados['statusAderencia'] and dados['statusTonalidade']:
                    registro_teste.status = 'aprovado'
                    for espessura in resultados_espessura_camada:
                        if not (40 <= espessura <= 60):
                            registro_teste.status = 'reprovado'
                            causa_reprovacao.append('espessura fora do padrão (40-60 microns)')
                            break
                else:
                    registro_teste.status = 'reprovado'
                    causa_reprovacao.append('falha em algum teste (aderência ou tonalidade)')
            
            print(registro_teste.status)
            # registro_teste.save()
            if registro_teste.status == 'aprovado':
                return JsonResponse({'status':'ok'},status=200)
            elif registro_teste.status == 'reprovado':
                return JsonResponse({'status':'ok', 'causa_reprovacao': causa_reprovacao},status=200)
            else:
                return JsonResponse({'error':'Erro na alteração do status!'},status=400)
        except Exception as e:
            print(e)
            return JsonResponse({'error':'Ocorreu algum erro!'},status=400)
    else:
        return JsonResponse({'error': 'Método não permitido!'},status=405)    
    