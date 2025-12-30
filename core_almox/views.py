from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse


from solicitacao_almox.models import SolicitacaoRequisicao, SolicitacaoTransferencia
from solicitacao_almox.forms import SolicitacaoRequisicaoForm, SolicitacaoTransferenciaForm
from cadastro_almox.models import OperadorAlmox, Funcionario, ItensSolicitacao, ItensTransferencia

from datetime import datetime
from automacoes.conexao_plan import busca_saldo_recurso_central
from time import time
import environ
from zoneinfo import ZoneInfo


env=environ.Env()

@login_required
def lista_solicitacoes(request):
    tipo_sol = request.POST.get("type_sol")
    requisicoes = SolicitacaoRequisicao.objects.filter(entregue_por=None)
    transferencias = SolicitacaoTransferencia.objects.filter(entregue_por=None)
    operadores_entrega = OperadorAlmox.objects.filter(status=True)

    draw = int(request.POST.get('draw', 1))
    start = int(request.POST.get('start', 0))  # Índice da primeira linha da página atual
    length = int(request.POST.get('length', 10))  # Quantidade de registros por página
    # search = request.GET.get('search[value]', '')  # Texto de pesquisa, se houver

    if request.method == "POST":
        if "type_sol" in request.POST:
            pass
        elif "entregar" in request.POST:
            print('entregar')
            solicitacao_id = request.POST.get("solicitacao_id")
            tipo_solicitacao = request.POST.get("tipo_solicitacao")
            if tipo_solicitacao == "requisicao":
                solicitacao = get_object_or_404(SolicitacaoRequisicao, id=solicitacao_id)
            else:
                solicitacao = get_object_or_404(SolicitacaoTransferencia, id=solicitacao_id)

            # Solicitar matrícula e data
            matricula = request.POST.get("matricula")
            data_entrega = request.POST.get("data_entrega")

            entregue_por = get_object_or_404(OperadorAlmox, matricula=matricula)

            # Aqui você poderia adicionar a lógica para salvar esses dados ou marcar como entregue
            solicitacao.entregue_por = entregue_por
            solicitacao.data_entrega = data_entrega
            
            solicitacao.save()

            # return redirect("sol_page")

            return JsonResponse({
                'status': 'Sucesso',
                'tipo': tipo_solicitacao
            })

        elif "apagar" in request.POST:
            
            solicitacao_id = request.POST.get("solicitacao_id")
            tipo_solicitacao = request.POST.get("tipo_solicitacao")
            if tipo_solicitacao == "requisicao":
                SolicitacaoRequisicao.objects.filter(id=solicitacao_id).delete()
            else:
                SolicitacaoTransferencia.objects.filter(id=solicitacao_id).delete()

            # return redirect("sol_page")
            return JsonResponse({
                'status': 'Sucesso',
                'tipo': tipo_solicitacao
            })

        elif "editar" in request.POST:
            
            solicitacao_id = request.POST.get("solicitacao_id")
            tipo_solicitacao = request.POST.get("tipo_solicitacao")
            funcionario = request.POST.get("funcionario")
            item = request.POST.get("item")
            quantidade = request.POST.get("quantidade")
            

            if tipo_solicitacao == "requisicao":
                solicitacao = get_object_or_404(SolicitacaoRequisicao, id=solicitacao_id)
            else:
                solicitacao = get_object_or_404(SolicitacaoTransferencia, id=solicitacao_id)

            solicitacao.funcionario = funcionario
            solicitacao.item = item
            solicitacao.quantidade = quantidade
            solicitacao.save()

            # return redirect("sol_page")

            return JsonResponse({
                'status': 'Sucesso',
                'tipo': tipo_solicitacao
            })
        
    order_column = int(request.POST.get('order[0][column]', 0))  # Indica qual coluna foi ordenada
    order_dir = request.POST.get('order[0][dir]', 'asc')  # Direção de ordenação: 'asc' ou 'desc'
 
    # credentials_google = {
    #     "type": env("type"),
    #     "project_id": env("project_id"),
    #     "private_key_id": env('private_key_id'),
    #     "private_key": env('private_key'),
    #     "client_email": env('client_email'),
    #     "client_id": env('client_id'),
    #     "auth_uri": env('auth_uri'),
    #     "token_uri": env('token_uri'),
    #     "auth_provider_x509_cert_url": env('auth_provider_x509_cert_url'),
    #     "client_x509_cert_url": env('client_x509_cert_url'),
    #     "universe_domain": env('universe_domain')
    # }

    # Uso do set que evita codigos repetidos
    if tipo_sol == "requisicao":
        if order_column == 0:
            requisicoes = requisicoes.order_by('id' if order_dir == 'asc' else '-id')
        codigos_produtos = set(req.item.codigo for req in requisicoes)
        saldos,data = busca_saldo_recurso_central(codigos_produtos)
        for item in requisicoes:
            item.saldo = saldos.get(item.item.codigo, '0')

        requisicoes_paginadas = requisicoes[start:start+length]
       
        
        requisicoes_data = [
        {
            "id": req.id,
            "funcionario": f"{req.funcionario.matricula} - {req.funcionario.nome}",
            "item": f"{req.item.codigo} - {req.item.nome}",  # Supondo que 'nome' é o campo que contém o nome do item
            "quantidade": req.quantidade,
            "classe_requisicao": req.classe_requisicao.nome,
            "saldo": req.saldo,
            "data_solicitacao": req.data_solicitacao.isoformat(),
            "acoes": 'acoes'
        }
        for req in requisicoes_paginadas
        ]

        return JsonResponse({
            "operadores": list(operadores_entrega.values()),
            "requisicoes": requisicoes_data,
            "data_ultimo_saldo":data,
            "draw": draw,  # Envia de volta o parâmetro 'draw' para sincronização
            "recordsTotal": requisicoes.count(),  # Total de registros (sem filtros)
            "recordsFiltered": requisicoes.count()
            }
        )


    else:
        #ordenando a tabela pelo id
        if order_column == 0:
            transferencias = transferencias.order_by('id' if order_dir == 'asc' else '-id')
        codigos_produtos= set(transfer.item.codigo for transfer in transferencias)
        saldos,data = busca_saldo_recurso_central(codigos_produtos)
        for item in transferencias:
            item.saldo = saldos.get(item.item.codigo, '0')

        transferencias_paginadas = transferencias[start:start + length]
        
        transferencias_data = [
        {
            "id": trans.id,
            "funcionario": f"{trans.funcionario.matricula} - {trans.funcionario.nome}",
            "item": f"{trans.item.codigo} - {trans.item.nome}",  # Supondo que 'nome' é o campo que contém o nome do item
            "quantidade": trans.quantidade,
            "saldo": trans.saldo,
            "data_solicitacao": trans.data_solicitacao.isoformat(),
            "acoes": 'acoes'
        }
        for trans in transferencias_paginadas
        ]

        return JsonResponse({
                "operadores": list(operadores_entrega.values()),
                "transferencias": transferencias_data,
                "data_ultimo_saldo":data,
                "recordsTotal": transferencias.count(),  # Total de registros (sem filtros)
                "recordsFiltered": transferencias.count()
            }
        )

@login_required
def dashboard(request):
    requisicoes = SolicitacaoRequisicao.objects.filter(entregue_por=None).order_by('-data_solicitacao')
    transferencias = SolicitacaoTransferencia.objects.filter(entregue_por=None).order_by('-data_solicitacao')

    print(requisicoes)

    # data_requisicao_list = [req.pk,req.data_solicitacao for req in requisicoes]
    # data_transferencia_list = [tra.data_solicitacao for tra in transferencias]
    data_requisicao_list = [{"id": req.id, "data_solicitacao": req.data_solicitacao.isoformat() } for req in requisicoes]
    data_transferencia_list = [{"id": tra.id, "data_solicitacao": tra.data_solicitacao.isoformat() } for tra in transferencias]
    # data_requisicao_list = serialize('json', requisicoes)
    # data_transferencia_list = serialize('json', transferencias)

    context = {
        "requisicoes": requisicoes,
        "transferencias": transferencias,
        "requisicoes_datas": data_requisicao_list,
        "transferencias_datas": data_transferencia_list
    }

    return render(request, "dashboard/dashboard.html", context)

@login_required
def atualizar_dados(request):
    requisicoes = SolicitacaoRequisicao.objects.filter(entregue_por=None).order_by('-data_solicitacao')
    transferencias = SolicitacaoTransferencia.objects.filter(entregue_por=None).order_by('-data_solicitacao')

    # Crie uma lista personalizada para requisições
    requisicoes_data = [

        {
            "funcionario": f"{req.funcionario.matricula} - {req.funcionario.nome}",
            "item": f"{req.item.codigo} - {req.item.nome}",  # Supondo que 'nome' é o campo que contém o nome do item
            "quantidade": req.quantidade,
            "id": req.id,
            "data_solicitacao": req.data_solicitacao.astimezone(ZoneInfo("America/Sao_Paulo")).strftime('%d/%m/%Y %H:%M:%S'),
        }
        for req in requisicoes
    ]

    # Crie uma lista personalizada para transferências
    transferencias_data = [
        {
            "funcionario": f"{trans.funcionario.matricula} - {trans.funcionario.nome}",
            "item": f"{trans.item.codigo} - {trans.item.nome}",  # Supondo que 'nome' é o campo que contém o nome do item
            "quantidade": trans.quantidade,
            "id": trans.id,
            "data_solicitacao": trans.data_solicitacao.astimezone(ZoneInfo("America/Sao_Paulo")).strftime('%d/%m/%Y %H:%M:%S'),
        }
        for trans in transferencias
    ]

    return JsonResponse({
        "requisicoes": requisicoes_data,
        "transferencias": transferencias_data,
    })

def processar_edicao(request):
    if request.method == "POST":
        solicitacao_id = request.POST.get("solicitacao_id")
        tipo_solicitacao = request.POST.get("tipo_solicitacao")
        funcionario_str = request.POST.get("funcionario")
        item_str = request.POST.get("item")
        quantidade = request.POST.get("quantidade")

        # Extraia a matrícula do funcionário da string recebida
        matricula = funcionario_str.split(" - ")[0].strip()  # Supondo que o segundo item seja a matrícula

        # Busque a instância de Funcionario usando a matrícula
        funcionario = get_object_or_404(Funcionario, matricula=matricula)

        # Identifica o tipo de solicitação e recupera o objeto correspondente
        if tipo_solicitacao == "requisicao":
            # Extraia o código do item da string recebida
            item_codigo = item_str.split(" - ")[0].strip()  # Supondo que o primeiro item seja o código do item
            item = get_object_or_404(ItensSolicitacao, codigo=item_codigo)
            solicitacao = get_object_or_404(SolicitacaoRequisicao, id=solicitacao_id)
        elif tipo_solicitacao == "transferencia":
            # Extraia o código do item da string recebida
            item_codigo = item_str.split(" - ")[0].strip()  # Supondo que o primeiro item seja o código do item
            item = get_object_or_404(ItensTransferencia, codigo=item_codigo)
            solicitacao = get_object_or_404(SolicitacaoTransferencia, id=solicitacao_id)

        # Atualiza os campos da solicitação com os novos valores
        solicitacao.funcionario = funcionario
        solicitacao.item = item
        solicitacao.quantidade = quantidade
        solicitacao.save()

        return redirect("lista_solicitacoes")

    return redirect("lista_solicitacoes")

def editar_transferencia(request, id):
    
    transferencia = get_object_or_404(SolicitacaoTransferencia, id=id)
    if request.method == "POST":
        form = SolicitacaoTransferenciaForm(request.POST, instance=transferencia)
        if form.is_valid():
            form.save()
            return redirect('lista_solicitacoes')
    else:
        form = SolicitacaoTransferenciaForm(instance=transferencia)

    return render(request, 'home/editar_solicitacao.html', {'form': form})

@login_required    
def page_solicitacoes(request):
    return render(request, "home/lista_solicitacoes.html")

def processarCodigos(requisicoes,transferencias):

    codigos_produtos = set(req.item.codigo for req in requisicoes)
    codigos_produtos.update(transfer.item.codigo for transfer in transferencias)

    tempo_entrada = time()
    saldos,data = busca_saldo_recurso_central(codigos_produtos)
    tempo_saida = time()
    print("terminou a função em :" ,tempo_saida-tempo_entrada)

    todos_itens = list(requisicoes) + list(transferencias)

    # Atribuindo saldo para todos os itens
    # Atribuição de uma coluna de saldo para cada produto (não salvará no banco)
    for item in todos_itens:
        item.saldo = saldos.get(item.item.codigo, '0')
    
    return 'teste'