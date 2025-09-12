from django.shortcuts import render
from django.http import JsonResponse
from django.utils import timezone
from apontamento_pintura.models import TesteFuncional
from django.core.paginator import Paginator
import json
import os
import traceback
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
    data_inicial_filtrada = request.GET.get("data", None)
    data_final_filtrada = request.GET.get("dataFinal", None)
    pesquisa_filtrada = request.GET.get("pesquisar", None)
    status_teste = request.GET.get("statusTeste", None)
    pagina = int(request.GET.get("pagina", 1))  # Página atual, padrão é 1
    itens_por_pagina = 12  # Itens por página

    # Filtra os dados
    # datas = Inspecao.objects.filter(pecas_ordem_pintura__isnull=False)
    datas = TesteFuncional.objects.filter(status__in=status_url).values(
        'id','peca_ordem__id','peca_ordem__peca','peca_ordem__ordem_id__cor','status','peca_ordem__tipo','peca_ordem__ordem__data_carga', 'data_inicial', 'data_atualizacao','peca_ordem__ordem__ordem'
        )

    quantidade_total = datas.count()  # Total de itens sem filtro

    if 'pendente' in status_url:
        datas = datas.order_by('-data_inicial')
    else:
        datas = datas.order_by('-data_atualizacao')

    if cores_filtradas:
        datas = datas.filter(peca_ordem__ordem__cor__in=cores_filtradas)

    if data_inicial_filtrada:
        datas = datas.filter(data_inicial__date=data_inicial_filtrada)

    if data_final_filtrada:
        datas = datas.filter(data_atualizacao__date=data_final_filtrada)

    if status_teste:
        status_teste = status_teste.split(',')
        datas = datas.filter(status__in=status_teste)

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
                'ordem': data['peca_ordem__ordem__ordem'],
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
    """
    Função que vai realizar a verificação funcional de uma peça
    Meta de espessura: PO - 60 a 80 microns (µm)
                       PU - 40 a 60 microns (µm)
    Modificar a meta caso seja necessário
    """
    if request.method == 'POST':
        print(request.POST)
        print(request.FILES)
        idRegistro = request.POST.get('idRegistro', None)
        polimerizacao  = request.POST.get('statusPolimerizacao', None)
        aderencia = request.POST.get('statusAderencia', None)
        tonalidade = request.POST.get('statusTonalidade', None)
        espessura_camada_1 = request.POST.get('espessura-camada-1', None)
        espessura_camada_2 = request.POST.get('espessura-camada-2', None)
        espessura_camada_3 = request.POST.get('espessura-camada-3', None)
        observacao = request.POST.get('observacoes-teste', None)

        try:
            registro_teste = TesteFuncional.objects.get(pk=int(idRegistro))
            campos_obrigatorios = ['idRegistro','statusAderencia','statusTonalidade', 'espessura-camada-1','espessura-camada-2', 'espessura-camada-3']
            if polimerizacao: # PO
                polimerizacao = bool(polimerizacao)
                campos_obrigatorios.append('statusPolimerizacao')
                for campo in campos_obrigatorios:
                    if campo not in request.POST:
                        return JsonResponse({'error': f'Campo {campo} é obrigatório!'},status=400)
                
                if type(polimerizacao) is not bool:
                    return JsonResponse({'error':'Os campos de status devem ser booleanos!'}, status=400)
                
                # Registra o teste de polimerização
                registro_teste.polimerizacao = polimerizacao
            
            aderencia = aderencia == 'true'
            tonalidade = tonalidade == 'true'

            if type(aderencia) is not bool or type(tonalidade) is not bool:
                return JsonResponse({'error':'Os campos de status devem ser booleanos!'}, status=400)
            
            
            registro_teste.aderencia = aderencia
            registro_teste.tonalidade = tonalidade

            if observacao:
                registro_teste.observacao = observacao
            # CAMPO DE IMAGEM A SER FEITO DEPOIS
            if 'imagem' in request.FILES:
                ext = os.path.splitext(request.FILES['imagem'].name)[1]  # pega a extensão, ex: ".jpg"
                nome_arquivo = f"{timezone.now().strftime('%Y%m%d%H%M%S')}{ext}"
                registro_teste.imagem = request.FILES['imagem']
                registro_teste.imagem.name = nome_arquivo

            try:
                registro_teste.espessura_camada_1 = float(espessura_camada_1)
                registro_teste.espessura_camada_2 = float(espessura_camada_2)
                registro_teste.espessura_camada_3 = float(espessura_camada_3)
            except ValueError:
                return JsonResponse({'error':'Os campos de espessura devem ser numéricos!'}, status=400)
            
            resultados_espessura_camada = [registro_teste.espessura_camada_1,registro_teste.espessura_camada_2,registro_teste.espessura_camada_3]

            causa_reprovacao = []
            if polimerizacao: # PO
                registro_teste.meta_espessura_camada = '60 a 80'
                if polimerizacao and aderencia and tonalidade:
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
                registro_teste.meta_espessura_camada = '40 a 60'
                if aderencia and tonalidade:
                    registro_teste.status = 'aprovado'
                    for espessura in resultados_espessura_camada:
                        if not (40 <= espessura <= 60):
                            registro_teste.status = 'reprovado'
                            causa_reprovacao.append('espessura fora do padrão (40-60 microns)')
                            break
                else:
                    registro_teste.status = 'reprovado'
                    causa_reprovacao.append('falha em algum teste (aderência ou tonalidade)')
            
            registro_teste.save()
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

def detalhes_verificacao_funcional(request,id):
    if request.method != 'GET':
        return JsonResponse({'error': 'Método não permitido!'},status=405)
    
    try:
        registro_testes = TesteFuncional.objects.get(pk=id)

        #PU - 40 a 60 microns
        #PÓ - 60 a 80 microns
        media_condicao_espessura = (int(registro_testes.espessura_camada_1) + int(registro_testes.espessura_camada_2) + int(registro_testes.espessura_camada_3)) / 3

        resultado_espessura = 'Aprovado'
        if registro_testes.peca_ordem.tipo == 'PU':
            if media_condicao_espessura < 40 or media_condicao_espessura > 60:
                resultado_espessura = 'Reprovado'
        else:
            if media_condicao_espessura < 60 or media_condicao_espessura > 80:
                resultado_espessura = 'Reprovado'

        dados_registro = {
            'status':'ok',
            'id': registro_testes.id,
            'peca': registro_testes.peca_ordem.peca,
            'cor': registro_testes.peca_ordem.ordem.cor,
            'tipo_pintura': registro_testes.peca_ordem.tipo,
            'data_carga': registro_testes.peca_ordem.ordem.data_carga.strftime("%d/%m/%Y"),
            'status_registro': registro_testes.status.capitalize(),
            'aderencia': "Aprovado" if registro_testes.aderencia is True else "Reprovado",
            'tonalidade': "Aprovado" if registro_testes.tonalidade is True else "Reprovado",
            'polimerizacao': ("Aprovado" if registro_testes.polimerizacao is True else "Reprovado" if registro_testes.polimerizacao is False else "Somente para PÓ"),
            'espessura_camada_1': registro_testes.espessura_camada_1,
            'espessura_camada_2': registro_testes.espessura_camada_2,
            'espessura_camada_3': registro_testes.espessura_camada_3,
            'meta_espessura': registro_testes.meta_espessura_camada + ' µm' if registro_testes.meta_espessura_camada else 'Não definida',
            'media_espessura': round(media_condicao_espessura,2),
            'imagem_url': registro_testes.imagem.url if registro_testes.imagem else None,
            'resultado_espessura': resultado_espessura,
            'observacao': registro_testes.observacao if registro_testes.observacao else 'Nenhuma observação registrada.',
            'data_inicial': (registro_testes.data_inicial - timedelta(hours=3)).strftime("%d/%m/%Y %H:%M:%S") if registro_testes.data_inicial else None,
            'data_atualizacao': (registro_testes.data_atualizacao - timedelta(hours=3)).strftime("%d/%m/%Y %H:%M:%S") if registro_testes.data_atualizacao else None,
        }

        return JsonResponse(dados_registro, status=200)
    except TesteFuncional.DoesNotExist:
        return JsonResponse({'error': 'Registro não encontrado!'}, status=404)
    except Exception as e:
        traceback.print_exc(e)
        return JsonResponse({'error': 'Ocorreu um erro ao buscar os detalhes!'}, status=500)
    