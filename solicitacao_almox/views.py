from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseRedirect, HttpResponse, Http404, StreamingHttpResponse
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.db import IntegrityError
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db import transaction
from django.core.serializers import serialize
import csv

from cadastro_almox.models import (
    Cc,
    Funcionario,
    ItensSolicitacao,
    ItensTransferencia,
    DepositoDestino,
    ClasseRequisicao,
    OperadorAlmox,
    RegraSlaAlmox,
)
from core_almox.models import RegistroAcaoSolicitacaoAlmox
from core.utils import notificar_acao_almox
from core_almox.views import _chamar_innovaro_transferir

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
    funcionarios = Funcionario.objects.filter(ativo=True).order_by("nome", "matricula")
    itens_requisicao = ItensSolicitacao.objects.filter(ativo=True).order_by("codigo")
    itens_transferencia = ItensTransferencia.objects.filter(ativo=True).order_by("codigo")
    depositos_destino = DepositoDestino.objects.all()
    form_requisicao = SolicitacaoRequisicaoForm(request.POST, prefix="requisicao")
    centro_custo = Cc.objects.all()
    status_sla = RegraSlaAlmox.objects.filter(ativo=True).order_by("minutos_limite", "prioridade")

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

                    # Claim atômico antes de chamar o Innovaro
                    with transaction.atomic():
                        claimed = SolicitacaoTransferencia.objects.filter(
                            id=solicitacao.id, chave_innovaro__isnull=True
                        ).update(chave_innovaro='PROCESSANDO')

                    if claimed:
                        chave, erro = _chamar_innovaro_transferir(solicitacao)
                        if erro:
                            solicitacao.rpa = erro
                            solicitacao.chave_innovaro = None
                            solicitacao.save(update_fields=["rpa", "chave_innovaro"])
                        else:
                            solicitacao.entregue_por = operador
                            solicitacao.data_entrega = data_entrega
                            solicitacao.chave_innovaro = str(chave) if chave else None
                            solicitacao.save()
                            notificar_acao_almox("entregar", "transferencia", solicitacao.id)

                    return JsonResponse({"status": "sucesso", "operador": True})
                except Http404:
                    print(f"Operador com matrícula: {matricula} não encontrado!")
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
        "status_sla": status_sla,
    }

    return render(request, "solicitacao.html", context)


def get_cc_by_matricula(request):
    matricula = request.GET.get("matricula")
    if matricula:
        try:
            funcionario = Funcionario.objects.get(pk=matricula, ativo=True)
            cc_list = funcionario.cc.values("id", "nome")
            return JsonResponse({"cc": list(cc_list)})
        except Funcionario.DoesNotExist:
            return JsonResponse({"error": "Funcionário não encontrado"}, status=404)
    else:
        return JsonResponse({"error": "Matrícula não fornecida"}, status=400)


def get_unidade_by_item(request):
    item_id = request.GET.get("item_id")
    item = ItensSolicitacao.objects.filter(id=item_id, ativo=True).first()
    if item:
        unidade = item.unidade
        return JsonResponse({"unidade": unidade})
    return JsonResponse({"error": "Item não encontrado"}, status=404)


def carregar_classes(request):
    item_id = request.GET.get("item_id")
    id_solicitacao = request.GET.get("solicitacao_id")

    classes = ClasseRequisicao.objects.filter(itenssolicitacao=item_id, itenssolicitacao__ativo=True).values(
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


def _base_queryset_historico_requisicao():
    return SolicitacaoRequisicao.objects.select_related(
        "item",
        "funcionario",
        "cc",
        "classe_requisicao",
        "entregue_por",
    )


def _aplicar_filtros_historico_requisicao(solicitacoes, data):
    search_value = data.get("search[value]", "") or data.get("search", "")
    data_solicitacao_inicio = data.get("data_solicitacao_inicio", "")
    data_solicitacao_fim = data.get("data_solicitacao_fim", "")
    data_entrega_inicio = data.get("data_entrega_inicio", "")
    data_entrega_fim = data.get("data_entrega_fim", "")
    chave_innovaro = data.get("chave_innovaro", "")
    codigo_item = data.get("codigo_item", "")

    if search_value:
        solicitacoes = solicitacoes.filter(
            Q(item__nome__icontains=search_value)
            | Q(item__codigo__icontains=search_value)
            | Q(funcionario__nome__icontains=search_value)
            | Q(classe_requisicao__nome__icontains=search_value)
        )

    if data_solicitacao_inicio:
        solicitacoes = solicitacoes.filter(
            data_solicitacao__date__gte=data_solicitacao_inicio
        )

    if data_solicitacao_fim:
        solicitacoes = solicitacoes.filter(
            data_solicitacao__date__lte=data_solicitacao_fim
        )

    if data_entrega_inicio:
        solicitacoes = solicitacoes.filter(data_entrega__date__gte=data_entrega_inicio)

    if data_entrega_fim:
        solicitacoes = solicitacoes.filter(data_entrega__date__lte=data_entrega_fim)

    if chave_innovaro:
        solicitacoes = solicitacoes.filter(
            chave_innovaro__icontains=chave_innovaro.strip()
        )

    if codigo_item:
        solicitacoes = solicitacoes.filter(item__codigo__icontains=codigo_item.strip())

    return solicitacoes


def _serializar_historico_requisicao(solicitacao):
    status = "Pendente entrega" if solicitacao.entregue_por is None else "Entregue"
    data_ajustada_solicitacao = solicitacao.data_solicitacao - timedelta(hours=3)

    if solicitacao.data_entrega:
        data_ajustada_entrega = solicitacao.data_entrega - timedelta(hours=3)
        data_entrega_formatada = data_ajustada_entrega.strftime("%d/%m/%Y %H:%M")
    else:
        data_entrega_formatada = ""

    return {
        "classe_requisicao": solicitacao.classe_requisicao.nome,
        "quantidade": solicitacao.quantidade,
        "obs": solicitacao.obs,
        "data_solicitacao": data_ajustada_solicitacao.strftime("%d/%m/%Y %H:%M"),
        "cc__nome": solicitacao.cc.nome if solicitacao.cc else "",
        "funcionario__nome": solicitacao.funcionario.nome,
        "item": f"{solicitacao.item.codigo} - {solicitacao.item.nome}",
        "item__codigo": solicitacao.item.codigo,
        "item__nome": solicitacao.item.nome,
        "entregue_por__nome": (
            solicitacao.entregue_por.nome if solicitacao.entregue_por else "não Entregue"
        ),
        "ultima_atualizacao": solicitacao.data_solicitacao.strftime("%d/%m/%Y %H:%M"),
        "data_entrega": data_entrega_formatada,
        "status": status,
        "rpa": None
        if not solicitacao.rpa
        else (
            solicitacao.rpa
            if len(solicitacao.rpa) <= 45
            else f"{solicitacao.rpa[:45]}..."
        ),
        "chave_innovaro": solicitacao.chave_innovaro or "",
    }


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


@csrf_exempt
def solicitacao_data_requisicao(request):
    if request.method == "POST":
        draw = int(request.POST.get("draw", 0))
        start = int(request.POST.get("start", 0))
        length = int(request.POST.get("length", 10))

        solicitacoes = _base_queryset_historico_requisicao()
        solicitacoes = _aplicar_filtros_historico_requisicao(
            solicitacoes, request.POST
        )
        solicitacoes = solicitacoes.order_by("-data_solicitacao")

        paginator = Paginator(solicitacoes, length)
        page_number = start // length + 1
        solicitacoes_page = paginator.get_page(page_number)

        data = [
            _serializar_historico_requisicao(solicitacao)
            for solicitacao in solicitacoes_page
        ]

        return JsonResponse(
            {
                "draw": draw,
                "recordsTotal": paginator.count,
                "recordsFiltered": paginator.count,
                "data": data,
            }
        )


@login_required
def exportar_historico_requisicao_csv(request):
    solicitacoes = _base_queryset_historico_requisicao()
    solicitacoes = _aplicar_filtros_historico_requisicao(solicitacoes, request.GET)
    solicitacoes = solicitacoes.order_by("-data_solicitacao")

    class Echo:
        def write(self, value):
            return value

    def generate_rows():
        writer = csv.writer(Echo(), delimiter=";")
        yield "\ufeff"
        yield writer.writerow(
            [
                "RPA",
                "Chave Innovaro",
                "Data de Solicitacao",
                "Classe de Requisicao",
                "Item",
                "Quantidade",
                "Solicitante",
                "Observacoes",
                "Entregue por",
                "Data de Entrega",
                "Status almox",
            ]
        )

        for solicitacao in solicitacoes.iterator(chunk_size=500):
            item = _serializar_historico_requisicao(solicitacao)
            yield writer.writerow(
                [
                    item["rpa"] or "",
                    item["chave_innovaro"],
                    item["data_solicitacao"],
                    item["classe_requisicao"],
                    item["item"],
                    item["quantidade"],
                    item["funcionario__nome"],
                    item["obs"] or "",
                    item["entregue_por__nome"],
                    item["data_entrega"],
                    item["status"],
                ]
            )

    response = StreamingHttpResponse(
        generate_rows(),
        content_type="text/csv; charset=utf-8",
    )
    response["Content-Disposition"] = 'attachment; filename="historico_requisicao.csv"'
    return response


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


def _base_queryset_historico_transferencia():
    return SolicitacaoTransferencia.objects.select_related(
        "item",
        "funcionario",
        "deposito_destino",
        "entregue_por",
    )


def _aplicar_filtros_historico_transferencia(solicitacoes, data):
    search_value = data.get("search[value]", "") or data.get("search", "")
    data_solicitacao_inicio = data.get("data_solicitacao_inicio", "")
    data_solicitacao_fim = data.get("data_solicitacao_fim", "")
    data_entrega_inicio = data.get("data_entrega_inicio", "")
    data_entrega_fim = data.get("data_entrega_fim", "")
    chave_innovaro = data.get("chave_innovaro", "")
    codigo_item = data.get("codigo_item", "")
    codigo_item = data.get("codigo_item", "")

    if search_value:
        solicitacoes = solicitacoes.filter(
            Q(item__nome__icontains=search_value)
            | Q(item__codigo__icontains=search_value)
            | Q(funcionario__nome__icontains=search_value)
            | Q(deposito_destino__nome__icontains=search_value)
            | Q(chave_innovaro__icontains=search_value)
        )

    if data_solicitacao_inicio:
        solicitacoes = solicitacoes.filter(
            data_solicitacao__date__gte=data_solicitacao_inicio
        )

    if data_solicitacao_fim:
        solicitacoes = solicitacoes.filter(
            data_solicitacao__date__lte=data_solicitacao_fim
        )

    if data_entrega_inicio:
        solicitacoes = solicitacoes.filter(data_entrega__date__gte=data_entrega_inicio)

    if data_entrega_fim:
        solicitacoes = solicitacoes.filter(data_entrega__date__lte=data_entrega_fim)

    if chave_innovaro:
        solicitacoes = solicitacoes.filter(
            chave_innovaro__icontains=chave_innovaro.strip()
        )

    if codigo_item:
        solicitacoes = solicitacoes.filter(item__codigo__icontains=codigo_item.strip())

    return solicitacoes


def _serializar_historico_transferencia(solicitacao):
    status = "Pendente entrega" if solicitacao.entregue_por is None else "Entregue"
    data_ajustada_solicitacao = solicitacao.data_solicitacao - timedelta(hours=3)

    if solicitacao.data_entrega:
        data_ajustada_entrega = solicitacao.data_entrega - timedelta(hours=3)
        data_entrega_formatada = data_ajustada_entrega.strftime("%d/%m/%Y %H:%M")
    else:
        data_entrega_formatada = ""

    return {
        "quantidade": solicitacao.quantidade,
        "obs": solicitacao.obs,
        "data_solicitacao": data_ajustada_solicitacao.strftime("%d/%m/%Y %H:%M"),
        "deposito_destino__nome": solicitacao.deposito_destino.nome,
        "funcionario__nome": solicitacao.funcionario.nome,
        "item": f"{solicitacao.item.codigo} - {solicitacao.item.nome}",
        "item__codigo": solicitacao.item.codigo,
        "item__nome": solicitacao.item.nome,
        "entregue_por__nome": (
            solicitacao.entregue_por.nome if solicitacao.entregue_por else ""
        ),
        "data_entrega": data_entrega_formatada,
        "status": status,
        "rpa": None
        if not solicitacao.rpa
        else (
            solicitacao.rpa
            if len(solicitacao.rpa) <= 45
            else f"{solicitacao.rpa[:45]}..."
        ),
        "chave_innovaro": solicitacao.chave_innovaro or "",
    }


@csrf_exempt
def solicitacao_data_transferencia(request):
    if request.method == "POST":
        draw = int(request.POST.get("draw", 0))
        start = int(request.POST.get("start", 0))
        length = int(request.POST.get("length", 10))

        solicitacoes_base = _base_queryset_historico_transferencia()
        total_registros = solicitacoes_base.count()

        solicitacoes = _aplicar_filtros_historico_transferencia(
            solicitacoes_base, request.POST
        )
        total_filtrado = solicitacoes.count()
        solicitacoes = solicitacoes.order_by("-data_solicitacao")

        paginator = Paginator(solicitacoes, length)
        solicitacoes_page = paginator.get_page(start // length + 1)

        data = [
            _serializar_historico_transferencia(solicitacao)
            for solicitacao in solicitacoes_page
        ]

        return JsonResponse(
            {
                "draw": draw,
                "recordsTotal": total_registros,
                "recordsFiltered": total_filtrado,
                "data": data,
            }
        )


@login_required
def exportar_historico_transferencia_csv(request):
    solicitacoes = _base_queryset_historico_transferencia()
    solicitacoes = _aplicar_filtros_historico_transferencia(solicitacoes, request.GET)
    solicitacoes = solicitacoes.order_by("-data_solicitacao")

    class Echo:
        def write(self, value):
            return value

    def generate_rows():
        writer = csv.writer(Echo(), delimiter=";")
        yield "\ufeff"
        yield writer.writerow(
            [
                "RPA",
                "Chave Innovaro",
                "Data de Solicitacao",
                "Item",
                "Quantidade",
                "Deposito de destino",
                "Solicitante",
                "Observacoes",
                "Entregue por",
                "Data de Entrega",
                "Status almox",
            ]
        )

        for solicitacao in solicitacoes.iterator(chunk_size=500):
            item = _serializar_historico_transferencia(solicitacao)
            yield writer.writerow(
                [
                    item["rpa"] or "",
                    item["chave_innovaro"],
                    item["data_solicitacao"],
                    item["item"],
                    item["quantidade"],
                    item["deposito_destino__nome"],
                    item["funcionario__nome"],
                    item["obs"] or "",
                    item["entregue_por__nome"],
                    item["data_entrega"],
                    item["status"],
                ]
            )

    response = StreamingHttpResponse(
        generate_rows(),
        content_type="text/csv; charset=utf-8",
    )
    response["Content-Disposition"] = 'attachment; filename="historico_transferencia.csv"'
    return response


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
        motivo_edicao = (request.POST.get("motivo_edicao") or "").strip()
        if not motivo_edicao:
            return JsonResponse(
                {"status": "Erro", "mensagem": "Informe o motivo da edicao."},
                status=400,
            )

        if tipo_solicitacao == "requisicao":
            print(request.POST)
            item = request.POST.get("requisicao-item")
            classe_req = request.POST.get("requisicao-classe_requisicao")
            quantidade = request.POST.get("requisicao-quantidade")
            cc = request.POST.get("requisicao-cc")

            item_object = get_object_or_404(ItensSolicitacao, pk=item, ativo=True)
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

            item_object = get_object_or_404(ItensTransferencia, pk=item, ativo=True)
            deposito_destino_object = get_object_or_404(
                DepositoDestino, pk=deposito_destino
            )

            solicitacao.item = item_object
            solicitacao.deposito_destino = deposito_destino_object
            solicitacao.quantidade = quantidade

            solicitacao.save()

        RegistroAcaoSolicitacaoAlmox.objects.create(
            tipo_solicitacao=tipo_solicitacao,
            acao="edicao",
            solicitacao_id_original=solicitacao.id,
            motivo=motivo_edicao,
            payload={
                "id": solicitacao.id,
                "tipo_solicitacao": tipo_solicitacao,
                "funcionario": str(solicitacao.funcionario),
                "item": str(solicitacao.item),
                "quantidade": str(solicitacao.quantidade),
                "obs": solicitacao.obs or "",
                "classe_requisicao": str(solicitacao.classe_requisicao)
                if tipo_solicitacao == "requisicao"
                else "",
                "cc": str(solicitacao.cc) if tipo_solicitacao == "requisicao" else "",
                "deposito_destino": str(solicitacao.deposito_destino)
                if tipo_solicitacao == "transferencia"
                else "",
            },
            usuario=request.user if request.user.is_authenticated else None,
        )
        notificar_acao_almox("editar", tipo_solicitacao, solicitacao.id)

        return JsonResponse({"status": "Sucesso", "tipo": tipo_solicitacao})

    else:
        # Verifica se o tipo de solicitação é 'requisicao'
        if tipo_solicitacao == "requisicao":
            # Obtém a solicitação ou retorna um erro 404 se não for encontrada
            solicitacao = get_object_or_404(SolicitacaoRequisicao, pk=requisicao_id)

            # Obtém os itens relacionados a esta solicitação, filtrando pelo ID da solicitação
            itens_requisicao = ItensSolicitacao.objects.filter(ativo=True)

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
            itens_requisicao = ItensTransferencia.objects.filter(ativo=True)

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
    querysetRequisicaoErros = SolicitacaoRequisicao.objects.filter(
        (Q(rpa__isnull=False) & ~Q(rpa="OK")) & Q(data_entrega__isnull=False)
    )
    querysetRequisicaoNa = SolicitacaoRequisicao.objects.filter(
        (Q(rpa__isnull=True) & ~Q(rpa="OK")) & Q(data_entrega__isnull=False)
    )

    context = {
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
            ativo=True
        ).filter(
            Q(codigo__icontains=search) | Q(nome__icontains=search)
        ).order_by("codigo")
        format_result = lambda recurso: {
            "id": recurso.pk,
            "label": recurso.codigo + " - " + recurso.nome,
        }
    else:
        recursos = ItensTransferencia.objects.filter(
            ativo=True
        ).filter(
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
                    ItensTransferencia, pk=recurso, ativo=True
                )
                edicao_transferencia.save()
                return JsonResponse(
                    {"status": "success", "message": "Dados salvos com sucesso!"}
                )

            else:
                edicao_requisicao = SolicitacaoRequisicao.objects.get(pk=chave)
                edicao_requisicao.quantidade = quantidade
                edicao_requisicao.item = get_object_or_404(ItensSolicitacao, pk=recurso, ativo=True)
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


@csrf_exempt
@require_POST
def api_criar_requisicao(request):
    from cadastro.models import Pecas

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"status": "erro", "mensagem": "JSON inválido."}, status=400)

    for campo in ["funcionario_id", "cc_id", "status_id", "itens"]:
        if campo not in data or data[campo] in (None, ""):
            return JsonResponse({"status": "erro", "mensagem": f"Campo obrigatório ausente: {campo}"}, status=400)

    if not isinstance(data["itens"], list) or len(data["itens"]) == 0:
        return JsonResponse({"status": "erro", "mensagem": "O campo 'itens' deve ser uma lista não vazia."}, status=400)

    try:
        funcionario = get_object_or_404(Funcionario, pk=data["funcionario_id"], ativo=True)
        cc = get_object_or_404(Cc, pk=data["cc_id"])
        status_sla = get_object_or_404(RegraSlaAlmox, pk=data["status_id"], ativo=True)
    except Http404 as e:
        return JsonResponse({"status": "erro", "mensagem": str(e)}, status=404)

    operador_sesmt = OperadorAlmox.objects.filter(nome__iexact="sesmt", status=True).first()

    resultados = []
    for idx, item_data in enumerate(data["itens"]):
        for campo in ["codigo_produto", "classe_requisicao_id", "quantidade"]:
            if campo not in item_data or item_data[campo] in (None, ""):
                return JsonResponse({"status": "erro", "mensagem": f"Item {idx}: campo obrigatório ausente: {campo}"}, status=400)

        try:
            classe_requisicao = get_object_or_404(ClasseRequisicao, pk=item_data["classe_requisicao_id"])
            quantidade = float(item_data["quantidade"])
        except (ValueError, TypeError):
            return JsonResponse({"status": "erro", "mensagem": f"Item {idx}: valor inválido para 'quantidade'."}, status=400)
        except Http404 as e:
            return JsonResponse({"status": "erro", "mensagem": f"Item {idx}: {e}"}, status=404)

        codigo_produto = item_data["codigo_produto"]
        item = ItensSolicitacao.objects.filter(codigo=codigo_produto).first()
        item_criado = False
        if item is not None and not item.ativo:
            return JsonResponse(
                {"status": "erro", "mensagem": f"Item {idx}: produto {codigo_produto} está desabilitado para requisição."},
                status=400,
            )

        if item is None:
            peca = Pecas.objects.filter(codigo=codigo_produto).first()
            nome = peca.descricao if peca and peca.descricao else codigo_produto
            item = ItensSolicitacao.objects.create(codigo=codigo_produto, nome=nome)
            item.classe_requisicao.add(classe_requisicao)
            item_criado = True

        solicitacao = SolicitacaoRequisicao.objects.create(
            funcionario=funcionario,
            cc=cc,
            item=item,
            classe_requisicao=classe_requisicao,
            quantidade=quantidade,
            status=status_sla,
            obs=data.get("obs", ""),
        )

        if operador_sesmt:
            solicitacao.entregue_por = operador_sesmt
            solicitacao.data_entrega = datetime.now()
            solicitacao.save()

        resultados.append({
            "codigo_produto": codigo_produto,
            "id": solicitacao.id,
            "item_criado": item_criado,
        })

    return JsonResponse({
        "status": "sucesso",
        "operador_encontrado": operador_sesmt is not None,
        "requisicoes": resultados,
    }, status=201)
