from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseRedirect, HttpResponse, Http404
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.db import IntegrityError
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db import transaction
from django.core.serializers import serialize

from cadastro_almox.models import (
    Cc,
    Funcionario,
    ItensSolicitacao,
    ItensTransferencia,
    DepositoDestino,
    ClasseRequisicao,
    OperadorAlmox,
)

from .forms import (
    SolicitacaoRequisicaoForm,
    SolicitacaoTransferenciaForm,
    SolicitacaoCadastroItemRequisicaoForm,
    SolicitacaoCadastroItemTransferenciaForm,
    SolicitacaoCadastroMatriculaForm,
)
from .models import (
    SolicitacaoRequisicao,
    SolicitacaoTransferencia,
    SolicitacaoCadastroItem,
    SolicitacaoNovaMatricula,
)
from cadastro_almox.models import Cc
# from core.utils import (
#     notificacao_almoxarifado,
#     verificar_e_notificar_requisicoes_pendentes,
#     verificar_e_notificar_transferencias_pendentes,
# )

from datetime import datetime, timedelta
import json


def criar_solicitacoes(request):
    funcionarios = Funcionario.objects.all()
    itens_requisicao = ItensSolicitacao.objects.all()
    itens_transferencia = ItensTransferencia.objects.all()
    depositos_destino = DepositoDestino.objects.all()
    form_requisicao = SolicitacaoRequisicaoForm(request.POST, prefix="requisicao")
    centro_custo = Cc.objects.all()

    if request.method == "POST":
        form_type = request.POST.get("form_type")
        if form_type == "requisicao":
            form_requisicao = SolicitacaoRequisicaoForm(
                request.POST, prefix="requisicao"
            )
            if form_requisicao.is_valid():
                solicitacao_id = form_requisicao.save().id
                solicitacao = get_object_or_404(
                    SolicitacaoRequisicao, id=solicitacao_id
                )
                matricula = solicitacao.funcionario.matricula
                try:
                    operador = get_object_or_404(
                        OperadorAlmox, matricula=matricula, status=True
                    )
                    now = datetime.now()
                    data_entrega = now.strftime("%Y-%m-%dT%H:%M")
                    solicitacao.entregue_por = operador
                    solicitacao.data_entrega = data_entrega
                    solicitacao.save()
                    return JsonResponse({"status": "sucesso", "operador": True})
                except Http404:
                    print(f"Operador com matrícula: {matricula} não encontrado!")
                    # verificar_e_notificar_requisicoes_pendentes()
                    return JsonResponse({"status": "sucesso", "operador": False})
            else:
                return JsonResponse({"status": "erro"})

        elif form_type == "transferencia":
            form_transferencia = SolicitacaoTransferenciaForm(
                request.POST, prefix="transferencia"
            )
            if form_transferencia.is_valid():
                solicitacao_id = form_transferencia.save().id
                solicitacao = get_object_or_404(
                    SolicitacaoTransferencia, id=solicitacao_id
                )
                matricula = solicitacao.funcionario.matricula
                try:
                    operador = get_object_or_404(
                        OperadorAlmox, matricula=matricula, status=True
                    )
                    now = datetime.now()
                    data_entrega = now.strftime("%Y-%m-%dT%H:%M")
                    solicitacao.entregue_por = operador
                    solicitacao.data_entrega = data_entrega
                    solicitacao.save()
                    return JsonResponse({"status": "sucesso", "operador": True})
                except Http404:
                    print(f"Operador com matrícula: {matricula} não encontrado!")
                    # verificar_e_notificar_transferencias_pendentes()
                    return JsonResponse({"status": "sucesso", "operador": False})
            else:
                return JsonResponse({"status": "erro"})

    context = {
        "form_requisicao": form_requisicao,
        "depositos": depositos_destino,
        "funcionarios": funcionarios,
        "itens": itens_requisicao,
        "itens_transferencia": itens_transferencia,
        "centro_custo": centro_custo,
    }

    return render(request, "solicitacao.html", context)


def get_cc_by_matricula(request):
    matricula = request.GET.get("matricula")
    if matricula:
        try:
            funcionario = Funcionario.objects.get(pk=matricula)
            cc_list = funcionario.cc.values("id", "nome")
            return JsonResponse({"cc": list(cc_list)})
        except Funcionario.DoesNotExist:
            return JsonResponse({"error": "Funcionário não encontrado"}, status=404)
    else:
        return JsonResponse({"error": "Matrícula não fornecida"}, status=400)


def get_unidade_by_item(request):
    item_id = request.GET.get("item_id")
    item = ItensSolicitacao.objects.filter(id=item_id).first()
    if item:
        unidade = item.unidade
        return JsonResponse({"unidade": unidade})
    return JsonResponse({"error": "Item não encontrado"}, status=404)


def carregar_classes(request):
    item_id = request.GET.get("item_id")
    id_solicitacao = request.GET.get("solicitacao_id")

    classes = ClasseRequisicao.objects.filter(itenssolicitacao=item_id).values(
        "id", "nome"
    )
    if id_solicitacao:
        solicitacao = get_object_or_404(SolicitacaoRequisicao, pk=id_solicitacao)
        return JsonResponse(
            {
                "classes": list(classes),
                "classe_escolhida": solicitacao.classe_requisicao.pk,
            }
        )

    return JsonResponse({"classes": list(classes)})


@login_required
def historico_requisicao(request):

    return render(request, "historico-requisicao.html")


@csrf_exempt
def solicitacao_data_requisicao(request):
    if request.method == "POST":
        draw = int(request.POST.get("draw", 0))
        start = int(request.POST.get("start", 0))
        length = int(request.POST.get("length", 10))

        # Filtro de busca
        search_value = request.POST.get("search[value]", "")

        solicitacoes = SolicitacaoRequisicao.objects.all()

        if search_value:
            solicitacoes = solicitacoes.filter(
                Q(item__nome__icontains=search_value)
                | Q(funcionario__nome__icontains=search_value)
                | Q(classe_requisicao__nome__icontains=search_value)
            )

        # Ordenação
        solicitacoes = solicitacoes.order_by('-data_solicitacao')

        # Paginação
        paginator = Paginator(solicitacoes, length)
        page_number = start // length + 1
        solicitacoes_page = paginator.get_page(page_number)

        data = []
        for solicitacao in solicitacoes_page:
            status = (
                "Pendente entrega" if solicitacao.entregue_por is None else "Entregue"
            )

            data_ajustada_solicitacao = solicitacao.data_solicitacao - timedelta(hours=3)
            data_ajustada_entrega = solicitacao.data_solicitacao - timedelta(hours=3) if solicitacao.data_entrega else ""

            if solicitacao.data_entrega:
                data_ajustada_entrega = solicitacao.data_solicitacao - timedelta(hours=3)
                data_ajustada_entrega = data_ajustada_entrega.strftime("%d/%m/%Y %H:%M")
            else:
                data_ajustada_entrega = ""

            # Acessando centros de custo (cc) do Funcionario
            cc_nomes = ", ".join([cc.nome for cc in solicitacao.funcionario.cc.all()])

            data.append(
                {
                    "classe_requisicao": solicitacao.classe_requisicao.nome,  # Ajustado para evitar a serialização do objeto
                    "quantidade": solicitacao.quantidade,
                    "obs": solicitacao.obs,
                    "data_solicitacao": data_ajustada_solicitacao.strftime(
                        "%d/%m/%Y %H:%M"
                    ),
                    "cc__nome": cc_nomes,  # Agora pegando corretamente os centros de custo
                    "funcionario__nome": solicitacao.funcionario.nome,
                    "item__nome": solicitacao.item.nome,
                    "entregue_por__nome": (
                        solicitacao.entregue_por.nome
                        if solicitacao.entregue_por
                        else "Não Entregue"
                    ),
                    "ultima_atualizacao": solicitacao.data_solicitacao.strftime(
                        "%d/%m/%Y %H:%M"
                    ),
                    "data_entrega": data_ajustada_entrega,
                    "status": status,
                    "rpa": None if not solicitacao.rpa else (solicitacao.rpa if len(solicitacao.rpa) <= 45 else f"{solicitacao.rpa[:45]}..."),
                }
            )

        return JsonResponse(
            {
                "draw": draw,
                "recordsTotal": paginator.count,
                "recordsFiltered": paginator.count,
                "data": data,
            }
        )


@login_required
def historico_transferencia(request):

    return render(request, "historico-transferencia.html")


@csrf_exempt
def solicitacao_data_transferencia(request):
    if request.method == "POST":
        draw = int(request.POST.get("draw", 0))
        start = int(request.POST.get("start", 0))
        length = int(request.POST.get("length", 10))

        # Mapeamento do índice da coluna para o campo correspondente no banco de dados
        columns = [
            "quantidade",
            "obs",
            "data_solicitacao",
            "deposito_destino__nome",
            "funcionario__nome",
            "item__nome",
            "entregue_por__nome",
            "ultima_atualizacao",
            "data_entrega",
            "rpa",
        ]

        # Filtrando as execuções (se houver busca)
        search_value = request.POST.get("search[value]", "")

        solicitacoes = SolicitacaoTransferencia.objects.all()

        if search_value:
            solicitacoes = solicitacoes.filter(item__nome__contains=search_value)

        # Aplicando ordenação
        solicitacoes = solicitacoes.order_by('-data_solicitacao')

        # Paginação
        paginator = Paginator(solicitacoes, length)
        solicitacoes_page = paginator.get_page(start // length + 1)

        data = []
        for solicitacao in solicitacoes_page:
            status = (
                "Pendente entrega" if solicitacao.entregue_por is None else "Entregue"
            )

            data_ajustada_solicitacao = solicitacao.data_solicitacao - timedelta(hours=3)
            data_ajustada_entrega = solicitacao.data_solicitacao - timedelta(hours=3) if solicitacao.data_entrega else ""

            if solicitacao.data_entrega:
                data_ajustada_entrega = solicitacao.data_solicitacao - timedelta(hours=3)
                data_ajustada_entrega = data_ajustada_entrega.strftime("%d/%m/%Y %H:%M")
            else:
                data_ajustada_entrega = ""

            data.append(
                {
                    "quantidade": solicitacao.quantidade,
                    "obs": solicitacao.obs,
                    "data_solicitacao": data_ajustada_solicitacao.strftime(
                        "%d/%m/%Y %H:%M"
                    ),
                    "deposito_destino__nome": solicitacao.deposito_destino.nome,
                    "funcionario__nome": solicitacao.funcionario.nome,
                    "item__nome": solicitacao.item.nome,
                    "entregue_por__nome": (
                        solicitacao.entregue_por.nome
                        if solicitacao.entregue_por
                        else ""
                    ),
                    "data_entrega": data_ajustada_entrega,
                    "status": status,
                    "rpa": None if not solicitacao.rpa else (solicitacao.rpa if len(solicitacao.rpa) <= 45 else f"{solicitacao.rpa[:45]}..."),
                }
            )

        return JsonResponse(
            {
                "draw": draw,
                "recordsTotal": paginator.count,
                "recordsFiltered": paginator.count,
                "data": data,
            }
        )


def cadastro_novo_item(request):

    if request.method == "POST":

        pk_funcionario = request.POST.get("id-funcionario-cadastro-item")
        tipo_solicitacao = request.POST.get("tipo_solicitacao")
        codigo = request.POST.get("id-codigo-item")
        descricao = request.POST.get("id-descricao-item")
        quantidade = request.POST.get("id-quantidade-solicitante")
        cc = request.POST.get("requisicao-cc-novo-item")

        funcionario = get_object_or_404(Funcionario, pk=pk_funcionario)

        if tipo_solicitacao == "transferencia":

            pk_deposito = request.POST.get("id-cadastrar-deposito")

            deposito_destino_object = get_object_or_404(DepositoDestino, pk=pk_deposito)

            SolicitacaoCadastroItem.objects.create(
                funcionario=funcionario,
                tipo_solicitacao=tipo_solicitacao,
                codigo=codigo,
                descricao=descricao,
                quantidade=quantidade,
                deposito_destino=deposito_destino_object,
            )

            # notificacao_almoxarifado(
            #     titulo="Nova Solicitação para criação de itens para Transferência",
            #     rota_acesso="/almox/gerir-solicitacao-cadastro/",
            #     mensagem=f"O colaborador {funcionario.matricula} - {funcionario.nome} solicitou um novo item para cadastro: {codigo} - {descricao}.",
            # )

        else:

            cc_object = get_object_or_404(Cc, pk=cc)

            SolicitacaoCadastroItem.objects.create(
                funcionario=funcionario,
                tipo_solicitacao=tipo_solicitacao,
                codigo=codigo,
                descricao=descricao,
                quantidade=quantidade,
                cc=cc_object,
            )

            # notificacao_almoxarifado(
            #     titulo="Nova Solicitação para criação de itens para Requição",
            #     rota_acesso="/almox/gerir-solicitacao-cadastro/",
            #     mensagem=f"O colaborador {funcionario.matricula} - {funcionario.nome} solicitou um novo item para cadastro: {codigo} - {descricao}.",
            # )

    return redirect("criar_solicitacoes")


def cadastro_nova_matricula(request):

    if request.method == "POST":

        matricula = request.POST.get("id-matricula-solicitante")
        nome = request.POST.get("id-nome-solicitante")
        pk_cc = request.POST.get("id-ccusto-solicitante")

        cc_object = get_object_or_404(Cc, pk=pk_cc)

        SolicitacaoNovaMatricula.objects.create(
            matricula=matricula, nome=nome, cc=cc_object
        )

        # notificacao_almoxarifado(
        #     titulo="Nova Solicitação de Matrícula",
        #     rota_acesso="/almox/gerir-solicitacao-cadastro/",
        #     mensagem=f"Nova Solicitação de Matrícula: {matricula} - {nome} para o CC {cc_object.codigo} - {cc_object.nome}.",
        # )

    return redirect("criar_solicitacoes")


@login_required
def gerir_solicitacoes(request):

    cadastro_matricula = SolicitacaoNovaMatricula.objects.filter(aprovado=False)
    cadastro_item = SolicitacaoCadastroItem.objects.filter(aprovado=False)
    mensagem_erro = None  # Variável para armazenar a mensagem de erro

    if request.method == "POST":

        with transaction.atomic():

            tipo_cadastro = request.POST.get("tipo_cadastro")
            solicitacao_id = request.POST.get("id")

            print(request.POST)

            if "add" in request.POST:

                if tipo_cadastro == "item":

                    solicitacao = get_object_or_404(
                        SolicitacaoCadastroItem, pk=solicitacao_id
                    )
                    solicitacao.aprovado = True
                    solicitacao.data_aprovacao = datetime.now()
                    solicitacao.save()

                    if solicitacao.tipo_solicitacao == "requisicao":

                        try:
                            opcao = int(request.POST.get("opcao"))

                            classe_object = get_object_or_404(
                                ClasseRequisicao, pk=opcao
                            )

                            # Cadastrando novo item
                            novo_item = ItensSolicitacao.objects.create(
                                codigo=solicitacao.codigo, nome=solicitacao.descricao
                            )

                            # Adicionando ao ManyToManyField 'classe_requisicao'
                            novo_item.classe_requisicao.add(
                                classe_object
                            )  # 'opcao' deve ser um objeto ClasseRequisicao

                            # Buscando funcionário
                            funcionario_object = get_object_or_404(
                                Funcionario, pk=solicitacao.funcionario.pk
                            )

                            # Criando a solicitação
                            nova_solicitacao = SolicitacaoRequisicao.objects.create(
                                quantidade=solicitacao.quantidade,
                                funcionario=funcionario_object,
                                item=novo_item,
                                classe_requisicao=classe_object,
                                cc=solicitacao.cc,
                            )

                        except IntegrityError:
                            # Captura o erro de integridade (violação da chave UNIQUE ou outros erros de integridade)
                            mensagem_erro = "Erro: O código do item já existe."

                    else:

                        try:

                            # Cadastrando novo item
                            novo_item = ItensTransferencia.objects.create(
                                codigo=solicitacao.codigo,
                                nome=solicitacao.descricao,
                            )
                            novo_item.save()

                            # Criando solicitação
                            funcionario_object = get_object_or_404(
                                Funcionario, pk=solicitacao.funcionario.pk
                            )
                            cc_object = (
                                funcionario_object.cc
                            )  # Aqui você acessa diretamente o 'cc' do funcionário

                            nova_solicitacao = SolicitacaoTransferencia.objects.create(
                                quantidade=solicitacao.quantidade,
                                deposito_destino=solicitacao.deposito_destino,
                                funcionario=solicitacao.funcionario,
                                item=novo_item,
                            )
                            nova_solicitacao.save()

                        except IntegrityError:
                            # Captura o erro de integridade (violação da chave UNIQUE)
                            mensagem_erro = "Erro: O código do item já existe."

                else:

                    solicitacao = get_object_or_404(
                        SolicitacaoNovaMatricula, pk=solicitacao_id
                    )
                    solicitacao.aprovado = True
                    solicitacao.data_aprovacao = datetime.now()
                    solicitacao.save()

                    try:

                        # Cadastrando nova matricula
                        cc_object = get_object_or_404(Cc, nome=solicitacao.cc)

                        novo_item = Funcionario.objects.create(
                            matricula=solicitacao.matricula,
                            nome=solicitacao.nome,
                        )

                        novo_item.cc.add(cc_object)

                        novo_item.save()

                    except IntegrityError:
                        mensagem_erro = "Erro: Matrícula já cadastrada"

            if "apagar" in request.POST:

                if tipo_cadastro == "item":
                    SolicitacaoCadastroItem.objects.filter(id=solicitacao_id).delete()
                else:
                    SolicitacaoNovaMatricula.objects.filter(id=solicitacao_id).delete()

                return redirect("gerir_solicitacoes")

    context = {
        "cadastro_matricula": cadastro_matricula,
        "cadastro_item": cadastro_item,
        "mensagem_erro": mensagem_erro,  # Adiciona a mensagem de erro ao contexto
    }

    return render(request, "solicitacao-cadastro.html", context)


@csrf_exempt
def edit_solicitacao_cadastro_item(request, pk, tipo_cadastro):

    item = get_object_or_404(SolicitacaoCadastroItem, pk=pk)

    if tipo_cadastro == "requisicao":
        form = SolicitacaoCadastroItemRequisicaoForm(instance=item)
    else:
        form = SolicitacaoCadastroItemTransferenciaForm(instance=item)
    form = form.as_p()

    return HttpResponse(form)


@csrf_exempt
def receberFormEdit(request):

    if request.method == "POST":

        tipoRequisicao = request.POST.get("itemOuMatricula")
        pk = int(request.POST.get("pk"))
        if tipoRequisicao == "item":

            tipo_cadastro = request.POST.get("tipo_cadastro")

            item = get_object_or_404(SolicitacaoCadastroItem, pk=pk)

            if tipo_cadastro == "requisicao":

                form = SolicitacaoCadastroItemRequisicaoForm(
                    request.POST, instance=item
                )
                if form.is_valid():
                    form.save()
            else:
                form = SolicitacaoCadastroItemTransferenciaForm(
                    request.POST, instance=item
                )
                if form.is_valid():
                    form.save()
        else:
            matricula = get_object_or_404(SolicitacaoNovaMatricula, pk=pk)
            form = SolicitacaoCadastroMatriculaForm(request.POST, instance=matricula)

            if form.is_valid():
                form.save()

    return redirect("gerir_solicitacoes")


def edit_solicitacao_cadastro_matricula(request, pk):

    matricula = get_object_or_404(SolicitacaoNovaMatricula, pk=pk)

    if request.method == "POST":

        form = SolicitacaoCadastroMatriculaForm(request.POST, instance=matricula)

        if form.is_valid():

            form.save()

            return redirect("gerir_solicitacoes")
    else:

        form = SolicitacaoCadastroMatriculaForm(instance=matricula)
        form = form.as_p()

    # return render(request,'matricula/edit-matricula-cadastro.html', {'form':form})
    return HttpResponse(form)


def edit_solicitacao(request, tipo_solicitacao, requisicao_id):

    if request.method == "POST":

        if tipo_solicitacao == "requisicao":
            print(request.POST)
            item = request.POST.get("requisicao-item")
            classe_req = request.POST.get("requisicao-classe_requisicao")
            quantidade = request.POST.get("requisicao-quantidade")
            cc = request.POST.get("requisicao-cc")

            item_object = get_object_or_404(ItensSolicitacao, pk=item)
            classe_object = get_object_or_404(ClasseRequisicao, pk=classe_req)
            print(classe_object)
            cc_object = get_object_or_404(Cc, pk=cc)

            solicitacao = get_object_or_404(SolicitacaoRequisicao, pk=requisicao_id)

            solicitacao.item = item_object
            solicitacao.classe_requisicao = classe_object
            solicitacao.quantidade = quantidade
            solicitacao.cc = cc_object

            solicitacao.save()

        else:

            solicitacao = get_object_or_404(SolicitacaoTransferencia, pk=requisicao_id)

            item = request.POST.get("transferencia-item")
            deposito_destino = request.POST.get("transferencia-deposito_destino")
            quantidade = float(
                request.POST.get("transferencia-quantidade").replace(",", ".")
            )

            item_object = get_object_or_404(ItensTransferencia, pk=item)
            deposito_destino_object = get_object_or_404(
                DepositoDestino, pk=deposito_destino
            )

            solicitacao.item = item_object
            solicitacao.deposito_destino = deposito_destino_object
            solicitacao.quantidade = quantidade

            solicitacao.save()

        return JsonResponse({"status": "Sucesso", "tipo": tipo_solicitacao})

    else:
        # Verifica se o tipo de solicitação é 'requisicao'
        if tipo_solicitacao == "requisicao":
            # Obtém a solicitação ou retorna um erro 404 se não for encontrada
            solicitacao = get_object_or_404(SolicitacaoRequisicao, pk=requisicao_id)

            # Obtém os itens relacionados a esta solicitação, filtrando pelo ID da solicitação
            itens_requisicao = ItensSolicitacao.objects.all()

            # Obtém o funcionário relacionado à solicitação
            solicitante = solicitacao.funcionario

            item = solicitacao.item

            # Obtém outros detalhes que você pode querer passar no contexto
            item_escolhido_codigo = (
                solicitacao.item.codigo if solicitacao.item else None
            )
            cc = (
                solicitante.cc.all()
            )  # Se `cc` for um campo ManyToManyField no funcionário
            classe = (
                item.classe_requisicao.all()
            )  # Supondo que exista um campo 'classe_requisicao' na solicitação
            obs = solicitacao.obs  # Caso haja um campo 'observacao'
            quantidade = solicitacao.quantidade
            quantidade = str(quantidade).replace(",", ".")

            # Define o contexto a ser passado para o template
            context = {
                "solicitante": f"{solicitante.matricula} - {solicitante.nome}",
                "itens": list(itens_requisicao.values()),
                "item_escolhido_codigo": item_escolhido_codigo,
                "ccs": list(cc.values()),
                "classes": list(classe.values()),
                "quantidade": quantidade,
                "obs": obs,
                "unidade": item.unidade,
                "classe_escolhida": solicitacao.classe_requisicao.pk,
                "tipo_solicitacao": tipo_solicitacao,
                "cc_escolhido": solicitacao.cc.pk,
            }
            # data = serialize('json',context)

            # Renderiza o template com o contexto definido
            # return render(request, 'editar_solicitacao.html', context)
            return JsonResponse(context, safe=False)

        else:
            # Obtém a solicitação ou retorna um erro 404 se não for encontrada
            solicitacao = get_object_or_404(SolicitacaoTransferencia, pk=requisicao_id)

            # Obtém os itens relacionados a esta solicitação, filtrando pelo ID da solicitação
            itens_requisicao = ItensTransferencia.objects.all()

            # Obtém o funcionário relacionado à solicitação
            solicitante = solicitacao.funcionario

            item = solicitacao.item

            # Obtém outros detalhes que você pode querer passar no contexto
            item_escolhido_codigo = (
                solicitacao.item.codigo if solicitacao.item else None
            )
            obs = solicitacao.obs  # Caso haja um campo 'observacao'
            quantidade = solicitacao.quantidade
            quantidade = str(quantidade).replace(",", ".")
            deposito_destino = solicitacao.deposito_destino.nome
            depositos = DepositoDestino.objects.all()

            # Define o contexto a ser passado para o template
            context = {
                "solicitante_transferencia": f"{solicitante.matricula} - {solicitante.nome}",
                "itens_transferencia": list(itens_requisicao.values()),
                "item_escolhido_codigo_transferencia": item_escolhido_codigo,
                "quantidade_transferencia": quantidade,
                "obs_transferencia": obs,
                "deposito_destino_escolhido_transferencia": deposito_destino,
                "depositos_transferencia": list(depositos.values()),
                "tipo_solicitacao_transferencia": tipo_solicitacao,
            }
            # Renderiza o template com o contexto definido
            # return render(request, 'editar_solicitacao.html', context)
            return JsonResponse(context, safe=False)


def home_erros(request):
    querysetTransferenciaErros = SolicitacaoTransferencia.objects.filter(
        (Q(rpa__isnull=False) & ~Q(rpa="OK")) & Q(data_entrega__isnull=False)
    )

    querysetTransferenciaNa = SolicitacaoTransferencia.objects.filter(
        (Q(rpa__isnull=True) & ~Q(rpa="OK")) & Q(data_entrega__isnull=False)
    )

    querysetRequisicaoErros = SolicitacaoRequisicao.objects.filter(
        (Q(rpa__isnull=False) & ~Q(rpa="OK")) & Q(data_entrega__isnull=False)
    )
    querysetRequisicaoNa = SolicitacaoRequisicao.objects.filter(
        (Q(rpa__isnull=True) & ~Q(rpa="OK")) & Q(data_entrega__isnull=False)
    )

    context = {
        "qtdTransferenciaErros": len(querysetTransferenciaErros),
        "qtdTransferenciaNa": len(querysetTransferenciaNa),
        "qtdRequisicaoErros": len(querysetRequisicaoErros),
        "qtdRequisicaoNa": len(querysetRequisicaoNa),
    }

    return render(request, "erros.html", context)


def data_erros_transferencia(request):

    queryset = SolicitacaoTransferencia.objects.filter(
        (Q(rpa__isnull=True) | ~Q(rpa="OK")) & Q(data_entrega__isnull=False)
    )

    itens_transferencia_erros = []

    for item in queryset:
        itens_transferencia_erros.append(
            {
                "chave": item.pk,
                "item": f"{item.item.codigo} - {item.item.nome}",
                "qtd": item.quantidade,
                "data_solicitacao": item.data_solicitacao,
                "data_entrega": item.data_entrega,
                "dep_destino": item.deposito_destino.nome,
                "solicitante": item.funcionario.nome,
                "erro": item.rpa,
            }
        )

    # Paginação
    page = int(request.GET.get("start", 0)) // int(request.GET.get("length", 10)) + 1
    limit = int(request.GET.get("length", 10))
    paginator = Paginator(itens_transferencia_erros, limit)

    try:
        instrumentos_page = paginator.page(page)
    except EmptyPage:
        instrumentos_page = []

    data = {
        "draw": int(request.GET.get("draw", 1)),
        "recordsTotal": paginator.count,
        "recordsFiltered": paginator.count,
        "data": list(instrumentos_page),
    }

    return JsonResponse(data)


def data_erros_requisicao(request):

    queryset = SolicitacaoRequisicao.objects.filter(
        (Q(rpa__isnull=True) | ~Q(rpa="OK")) & Q(data_entrega__isnull=False)
    )

    itens_requisicao_erros = []

    for item in queryset:
        itens_requisicao_erros.append(
            {
                "chave": item.pk,
                "item": f"{item.item.codigo} - {item.item.nome}",
                "qtd": item.quantidade,
                "data_solicitacao": item.data_solicitacao,
                "data_entrega": item.data_entrega,
                "classe_req": item.classe_requisicao.nome,
                "solicitante": item.funcionario.nome,
                "cc": item.cc.nome,
                "erro": item.rpa,
            }
        )
    print("Erros de requisição: ", len(itens_requisicao_erros))

    # Paginação
    page = int(request.GET.get("start", 0)) // int(request.GET.get("length", 10)) + 1
    limit = int(request.GET.get("length", 10))
    paginator = Paginator(itens_requisicao_erros, limit)

    try:
        instrumentos_page = paginator.page(page)
    except EmptyPage:
        instrumentos_page = []

    data = {
        "draw": int(request.GET.get("draw", 1)),
        "recordsTotal": paginator.count,
        "recordsFiltered": paginator.count,
        "data": list(instrumentos_page),
    }

    return JsonResponse(data)


def get_data_solicitacao(request):

    tipo_solicitacao = request.GET.get("type")
    chave = int(request.GET.get("chave"))

    if tipo_solicitacao == "requisicao":

        editar_item = get_object_or_404(SolicitacaoRequisicao, pk=chave)
        recurso_selecionado = {
            "id": editar_item.item.pk,
            "label": editar_item.item.codigo + " - " + editar_item.item.nome,
        }

        return JsonResponse(
            {
                "quantidade": editar_item.quantidade,
                "classe": int(editar_item.classe_requisicao.pk),
                "cc": editar_item.cc.nome,
                "recurso_selecionado": recurso_selecionado,
            }
        )

    else:

        editar_item = get_object_or_404(SolicitacaoTransferencia, pk=chave)
        recurso_selecionado = {
            "id": editar_item.item.pk,
            "label": editar_item.item.codigo + " - " + editar_item.item.nome,
        }

        return JsonResponse(
            {
                "quantidade": editar_item.quantidade,
                "recurso_selecionado": recurso_selecionado,
            }
        )


def get_recursos(request):
    tipo_solicitacao = request.GET.get("type")

    # Validações
    if tipo_solicitacao not in ["requisicao", "transferencia"]:
        return JsonResponse({"error": "Tipo de solicitação inválido"}, status=400)

    # Pega o termo de busca e parâmetros de paginação
    search = request.GET.get("search", "")
    page = int(request.GET.get("page", 1))
    per_page = 10

    # Define a query base e o mapeamento de resultados
    if tipo_solicitacao == "requisicao":
        recursos = ItensSolicitacao.objects.filter(
            Q(codigo__icontains=search) | Q(nome__icontains=search)
        ).order_by("codigo")
        format_result = lambda recurso: {
            "id": recurso.pk,
            "label": recurso.codigo + " - " + recurso.nome,
        }
    else:
        recursos = ItensTransferencia.objects.filter(
            Q(codigo__icontains=search) | Q(nome__icontains=search)
        ).order_by("codigo")
        format_result = lambda recurso: {
            "id": recurso.pk,
            "label": recurso.codigo + " - " + recurso.nome,
        }

    # Paginação
    paginator = Paginator(recursos, per_page)
    recursos_page = paginator.get_page(page)

    return JsonResponse(
        {
            "results": [format_result(recurso) for recurso in recursos_page],
            "next": recursos_page.has_next(),
        }
    )


def receber_edicao(request):

    if request.method == "POST":

        with transaction.atomic():

            # Parseia os dados JSON recebidos
            data = json.loads(request.body)
            chave = data.get("editarChave")
            quantidade = data.get("editarQuantidade")
            classe = int(data.get("editarClasse"))
            tipo = data.get("editarType")
            recurso = int(data.get("recurso"))

            if tipo == "transferencia":
                edicao_transferencia = SolicitacaoTransferencia.objects.get(pk=chave)
                edicao_transferencia.quantidade = quantidade
                edicao_transferencia.item = get_object_or_404(
                    ItensTransferencia, pk=recurso
                )
                edicao_transferencia.save()
                return JsonResponse(
                    {"status": "success", "message": "Dados salvos com sucesso!"}
                )

            else:
                edicao_requisicao = SolicitacaoRequisicao.objects.get(pk=chave)
                edicao_requisicao.quantidade = quantidade
                edicao_requisicao.item = get_object_or_404(ItensSolicitacao, pk=recurso)
                edicao_requisicao.classe_requisicao = get_object_or_404(
                    ClasseRequisicao, pk=classe
                )
                edicao_requisicao.save()
                return JsonResponse(
                    {"status": "success", "message": "Dados salvos com sucesso!"}
                )

    return JsonResponse(
        {"status": "error", "message": "Método não permitido"}, status=405
    )


def receber_ajuste_manual(request):

    if request.method == "POST":
        data = json.loads(request.body)

        chave = data.get("manualChave")
        tipo = data.get("manualTipo")

        with transaction.atomic():

            if tipo == "transferencia":
                transferencia = SolicitacaoTransferencia.objects.get(pk=chave)
                transferencia.rpa = "OK"
                transferencia.save()
                return JsonResponse(
                    {"status": "success", "message": "Dados salvos com sucesso!"}
                )

            else:
                requisicao = SolicitacaoRequisicao.objects.get(pk=chave)
                requisicao.rpa = "OK"
                requisicao.save()
                return JsonResponse(
                    {"status": "success", "message": "Dados salvos com sucesso!"}
                )
