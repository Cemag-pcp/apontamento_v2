from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden
from django.db import transaction
from django.db.models import Q
from django.core.paginator import Paginator


from solicitacao_almox.models import SolicitacaoRequisicao, SolicitacaoTransferencia
from solicitacao_almox.forms import SolicitacaoRequisicaoForm, SolicitacaoTransferenciaForm
from cadastro_almox.forms import FuncionarioAlmoxForm, RegraSlaAlmoxForm
from cadastro_almox.models import (
    ClasseRequisicao,
    OperadorAlmox,
    Funcionario,
    ItensSolicitacao,
    ItensTransferencia,
    RegraSlaAlmox,
)
from core.models import Profile
from core_almox.models import RegistroAcaoSolicitacaoAlmox
from core.utils import notificar_acao_almox

from datetime import datetime
from urllib.parse import urlencode
from automacoes.conexao_plan import busca_saldo_recurso_central
from time import time
import environ
from zoneinfo import ZoneInfo
import os
import requests


env=environ.Env()


TIPOS_ACESSO_GERIR_CADASTRO_ALMOX = {"almoxarifado", "supervisor", "admin", "pcp"}


def _usuario_pode_gerir_cadastro_almox(request):
    if not request.user.is_authenticated:
        return False

    profile = Profile.objects.filter(user=request.user).first()
    return profile is not None and profile.tipo_acesso in TIPOS_ACESSO_GERIR_CADASTRO_ALMOX


def _cor_texto_contraste(cor_hex):
    if not cor_hex or len(cor_hex) != 7 or not cor_hex.startswith("#"):
        return "#ffffff"

    try:
        r = int(cor_hex[1:3], 16)
        g = int(cor_hex[3:5], 16)
        b = int(cor_hex[5:7], 16)
    except ValueError:
        return "#ffffff"

    luminancia = (0.299 * r) + (0.587 * g) + (0.114 * b)
    return "#000000" if luminancia > 186 else "#ffffff"


def _gerar_payload_solicitacao(solicitacao, tipo_solicitacao):
    payload = {
        'id': solicitacao.id,
        'tipo_solicitacao': tipo_solicitacao,
        'funcionario': str(solicitacao.funcionario),
        'item': str(solicitacao.item),
        'quantidade': str(solicitacao.quantidade),
        'obs': solicitacao.obs or '',
    }

    if tipo_solicitacao == 'requisicao':
        payload['classe_requisicao'] = str(solicitacao.classe_requisicao)
        payload['cc'] = str(solicitacao.cc)
    else:
        payload['deposito_destino'] = str(solicitacao.deposito_destino)

    return payload


def _registrar_acao_solicitacao(request, solicitacao, tipo_solicitacao, acao, motivo):
    RegistroAcaoSolicitacaoAlmox.objects.create(
        tipo_solicitacao=tipo_solicitacao,
        acao=acao,
        solicitacao_id_original=solicitacao.id,
        motivo=motivo.strip(),
        payload=_gerar_payload_solicitacao(solicitacao, tipo_solicitacao),
        usuario=request.user if request.user.is_authenticated else None,
    )

def _chamar_innovaro_transferir(solicitacao):
    """Retorna (chave_str | None, erro_str | None). Apenas para transferências."""
    payload = {
        "id": f"almox-transferencia-{solicitacao.id}",
        "pessoa": '4395',
        "recurso": solicitacao.item.codigo,
        "quantidade": solicitacao.quantidade,
        "depositoOrigem": "Almox central",
        "depositoDestino": solicitacao.deposito_destino.nome,
    }

    if os.getenv("DJANGO_ENV") == "dev":
        url = "https://hcemag.innovaro.com.br/api/integracao/v1/producao/transferir"
    else:
        url = "https://cemag.innovaro.com.br/api/integracao/v1/producao/transferir"

    print(f"[Innovaro] payload enviado: {payload}")
    print(f"[Innovaro] URL: {url}")

    try:
        response = requests.post(url, json=payload, auth=("luan araujo", "luanaraujo7"), timeout=(10, 60))
    except requests.RequestException as exc:
        print(f"[Innovaro] erro de conexão: {exc}")
        return None, f"Erro de conexão com o Innovaro: {exc}"

    print(f"[Innovaro] status: {response.status_code}")
    print(f"[Innovaro] resposta: {response.text}")

    try:
        resp_json = response.json()
    except ValueError:
        resp_json = {}

    if not response.ok or resp_json.get("status") == "Error":
        detail = resp_json.get("description") or response.text
        return None, f"Innovaro retornou erro: {detail}"

    chave = resp_json.get("chaveTransferencia")
    print(f"[Innovaro] chave extraída: {chave}")
    return chave, None


def _chamar_innovaro_transferir_lote(solicitacoes):
    """Envia lista de transferências ao Innovaro. Retorna lista de (solicitacao, chave, erro)."""
    payload = [
        {
            "id": f"almox-transferencia-{s.id}",
            "pessoa": '4395',
            "recurso": s.item.codigo,
            "quantidade": s.quantidade,
            "depositoOrigem": "Almox central",
            "depositoDestino": s.deposito_destino.nome,
        }
        for s in solicitacoes
    ]

    if os.getenv("DJANGO_ENV") == "dev":
        url = "https://hcemag.innovaro.com.br/api/integracao/v1/producao/transferir"
    else:
        url = "https://cemag.innovaro.com.br/api/integracao/v1/producao/transferir"

    print(f"[Innovaro Lote] payload: {payload}")
    print(f"[Innovaro Lote] URL: {url}")

    try:
        response = requests.post(url, json=payload, auth=("luan araujo", "luanaraujo7"), timeout=(10, 60))
    except requests.RequestException as exc:
        print(f"[Innovaro Lote] erro de conexão: {exc}")
        return [(s, None, f"Erro de conexão: {exc}") for s in solicitacoes]

    print(f"[Innovaro Lote] status: {response.status_code}")
    print(f"[Innovaro Lote] resposta: {response.text}")

    try:
        resp_list = response.json()
        if not isinstance(resp_list, list):
            resp_list = [resp_list]
    except ValueError:
        err = f"Resposta inválida do Innovaro: {response.text}"
        return [(s, None, err) for s in solicitacoes]

    result_map = {item.get("id"): item for item in resp_list}

    results = []
    for s in solicitacoes:
        item_resp = result_map.get(f"almox-transferencia-{s.id}", {})
        if item_resp.get("status") == "Error":
            results.append((s, None, item_resp.get("description") or "Erro desconhecido"))
        else:
            results.append((s, item_resp.get("chaveTransferencia"), None))

    return results


@login_required
def lista_solicitacoes(request):
    tipo_sol = request.POST.get("type_sol")
    requisicoes = SolicitacaoRequisicao.objects.filter(entregue_por=None).select_related(
        "funcionario", "item", "classe_requisicao", "status"
    )
    transferencias = SolicitacaoTransferencia.objects.filter(entregue_por=None).select_related(
        "funcionario", "item", "status", "deposito_destino"
    )
    operadores_entrega = OperadorAlmox.objects.filter(status=True)

    draw = int(request.POST.get('draw', 1))
    start = int(request.POST.get('start', 0))  # Índice da primeira linha da página atual
    length = int(request.POST.get('length', 10))  # Quantidade de registros por página
    # search = request.GET.get('search[value]', '')  # Texto de pesquisa, se houver

    if request.method == "POST":
        if "type_sol" in request.POST:
            pass
        elif "entregar_lote" in request.POST:
            ids_raw = request.POST.getlist("solicitacao_ids[]")
            matricula = request.POST.get("matricula")
            data_entrega = request.POST.get("data_entrega")

            entregue_por = get_object_or_404(OperadorAlmox, matricula=matricula)
            solicitacoes = list(
                SolicitacaoTransferencia.objects.filter(id__in=ids_raw)
                .select_related("funcionario", "item", "deposito_destino")
            )

            # Claim atômico: marca como PROCESSANDO apenas as que ainda não têm chave
            with transaction.atomic():
                claimed_count = SolicitacaoTransferencia.objects.filter(
                    id__in=[s.id for s in solicitacoes], chave_innovaro__isnull=True
                ).update(chave_innovaro='PROCESSANDO')

            # Recarrega do banco para saber quais foram claimadas
            solicitacoes_db = list(
                SolicitacaoTransferencia.objects.filter(id__in=[s.id for s in solicitacoes])
                .select_related("funcionario", "item", "deposito_destino")
            )

            erros = []
            for s in solicitacoes_db:
                if s.chave_innovaro != 'PROCESSANDO':
                    msg = ('Solicitação em processamento por outro usuário.'
                           if s.chave_innovaro == 'PROCESSANDO'
                           else f'Solicitação #{s.id} já foi processada no Innovaro (chave: {s.chave_innovaro}).')
                    erros.append({"id": s.id, "erro": msg})

            solicitacoes = [s for s in solicitacoes_db if s.chave_innovaro == 'PROCESSANDO']

            if not solicitacoes:
                return JsonResponse({'status': 'Erro', 'mensagem': 'Todas as solicitações selecionadas já foram processadas ou estão em processamento.', 'erros': erros}, status=409)

            resultados = _chamar_innovaro_transferir_lote(solicitacoes)

            sucesso = []
            for sol, chave, erro in resultados:
                if erro:
                    sol.rpa = erro
                    sol.chave_innovaro = None  # libera o claim
                    sol.save(update_fields=["rpa", "chave_innovaro"])
                    erros.append({"id": sol.id, "erro": erro})
                else:
                    sol.entregue_por = entregue_por
                    sol.data_entrega = data_entrega
                    sol.chave_innovaro = str(chave) if chave else None
                    sol.save()
                    notificar_acao_almox("entregar", "transferencia", sol.id)
                    sucesso.append(sol.id)

            return JsonResponse({
                'status': 'Parcial' if erros else 'Sucesso',
                'tipo': 'transferencia',
                'sucesso': sucesso,
                'erros': erros,
            })

        elif "entregar" in request.POST:
            solicitacao_id = request.POST.get("solicitacao_id")
            tipo_solicitacao = request.POST.get("tipo_solicitacao")
            if tipo_solicitacao == "requisicao":
                solicitacao = get_object_or_404(SolicitacaoRequisicao, id=solicitacao_id)
            else:
                solicitacao = get_object_or_404(SolicitacaoTransferencia, id=solicitacao_id)

            matricula = request.POST.get("matricula")
            data_entrega = request.POST.get("data_entrega")

            entregue_por = get_object_or_404(OperadorAlmox, matricula=matricula)

            if tipo_solicitacao == "transferencia":
                # Claim atômico: só avança se chave_innovaro ainda for nula
                with transaction.atomic():
                    claimed = SolicitacaoTransferencia.objects.filter(
                        id=solicitacao.id, chave_innovaro__isnull=True
                    ).update(chave_innovaro='PROCESSANDO')

                if not claimed:
                    solicitacao.refresh_from_db()
                    chave_atual = solicitacao.chave_innovaro or ''
                    msg = ('Solicitação em processamento por outro usuário. Aguarde.'
                           if chave_atual == 'PROCESSANDO'
                           else f'Solicitação #{solicitacao.id} já foi processada no Innovaro (chave: {chave_atual}).')
                    return JsonResponse({'status': 'Erro', 'mensagem': msg}, status=409)

                chave, erro = _chamar_innovaro_transferir(solicitacao)
                if erro:
                    solicitacao.rpa = erro
                    solicitacao.chave_innovaro = None  # libera o claim
                    solicitacao.save(update_fields=["rpa", "chave_innovaro"])
                    return JsonResponse({'status': 'Erro', 'mensagem': erro}, status=502)
            else:
                chave = None

            solicitacao.entregue_por = entregue_por
            solicitacao.data_entrega = data_entrega
            if chave:
                solicitacao.chave_innovaro = str(chave)
            solicitacao.save()

            notificar_acao_almox("entregar", tipo_solicitacao, solicitacao.id)

            return JsonResponse({
                'status': 'Sucesso',
                'tipo': tipo_solicitacao
            })

        elif "apagar" in request.POST:
            motivo = (request.POST.get("motivo_exclusao") or "").strip()
            if not motivo:
                return JsonResponse({'status': 'Erro', 'mensagem': 'Informe o motivo da exclusao.'}, status=400)

            solicitacao_id = request.POST.get("solicitacao_id")
            tipo_solicitacao = request.POST.get("tipo_solicitacao")
            if tipo_solicitacao == "requisicao":
                solicitacao = get_object_or_404(SolicitacaoRequisicao, id=solicitacao_id)
            else:
                solicitacao = get_object_or_404(SolicitacaoTransferencia, id=solicitacao_id)

            _registrar_acao_solicitacao(request, solicitacao, tipo_solicitacao, 'exclusao', motivo)
            solicitacao_pk = solicitacao.id
            solicitacao.delete()
            notificar_acao_almox("apagar", tipo_solicitacao, solicitacao_pk)

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
            "prioridade": req.status.prioridade if req.status else "",
            "prioridade_cor": req.status.cor if req.status else "#6c757d",
            "prioridade_cor_texto": _cor_texto_contraste(req.status.cor) if req.status else "#ffffff",
            "classe_requisicao": req.classe_requisicao.nome,
            "cc": str(req.cc) if req.cc else "",
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
            "prioridade": trans.status.prioridade if trans.status else "",
            "prioridade_cor": trans.status.cor if trans.status else "#6c757d",
            "prioridade_cor_texto": _cor_texto_contraste(trans.status.cor) if trans.status else "#ffffff",
            "deposito_destino": str(trans.deposito_destino) if trans.deposito_destino else "",
            "saldo": trans.saldo,
            "data_solicitacao": trans.data_solicitacao.isoformat(),
            "rpa": trans.rpa or "",
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
            item = get_object_or_404(ItensSolicitacao, codigo=item_codigo, ativo=True)
            solicitacao = get_object_or_404(SolicitacaoRequisicao, id=solicitacao_id)
        elif tipo_solicitacao == "transferencia":
            # Extraia o código do item da string recebida
            item_codigo = item_str.split(" - ")[0].strip()  # Supondo que o primeiro item seja o código do item
            item = get_object_or_404(ItensTransferencia, codigo=item_codigo, ativo=True)
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


@login_required
def configuracoes_sla(request):
    if not _usuario_pode_gerir_cadastro_almox(request):
        return HttpResponseForbidden("Sem permissao para gerenciar configuracoes do almoxarifado.")

    regra_edicao = None
    regra_id = request.GET.get('editar')

    if regra_id:
        regra_edicao = get_object_or_404(RegraSlaAlmox, pk=regra_id)

    if request.method == 'POST':
        acao = request.POST.get('acao')

        if acao == 'excluir':
            regra = get_object_or_404(RegraSlaAlmox, pk=request.POST.get('regra_id'))
            regra.delete()
            return redirect('configuracoes_sla')

        regra_pk = request.POST.get('regra_id')
        regra_instancia = None
        if regra_pk:
            regra_instancia = get_object_or_404(RegraSlaAlmox, pk=regra_pk)

        form = RegraSlaAlmoxForm(request.POST, instance=regra_instancia)
        if form.is_valid():
            form.save()
            return redirect('configuracoes_sla')
        regra_edicao = regra_instancia
    else:
        form = RegraSlaAlmoxForm(instance=regra_edicao)

    context = {
        'form': form,
        'regra_edicao': regra_edicao,
        'regras_sla': RegraSlaAlmox.objects.all(),
    }
    return render(request, 'home/configuracoes_sla.html', context)


@login_required
def gerenciar_funcionarios_almox(request):
    if not _usuario_pode_gerir_cadastro_almox(request):
        return HttpResponseForbidden("Sem permissao para gerenciar solicitantes do almoxarifado.")

    funcionario_edicao = None
    funcionario_id = request.GET.get('editar')
    search_nome = (request.GET.get('search_nome') or '').strip()

    if funcionario_id:
        funcionario_edicao = get_object_or_404(
            Funcionario.objects.prefetch_related('cc'),
            pk=funcionario_id,
        )

    if request.method == 'POST':
        acao = request.POST.get('acao')

        if acao == 'alternar_status':
            funcionario = get_object_or_404(Funcionario, pk=request.POST.get('funcionario_id'))
            funcionario.ativo = not funcionario.ativo
            funcionario.save(update_fields=['ativo'])
            return redirect('gerenciar_funcionarios_almox')

        funcionario_pk = request.POST.get('funcionario_id')
        funcionario_instancia = None
        if funcionario_pk:
            funcionario_instancia = get_object_or_404(Funcionario, pk=funcionario_pk)

        form = FuncionarioAlmoxForm(request.POST, instance=funcionario_instancia)
        if form.is_valid():
            form.save()
            return redirect('gerenciar_funcionarios_almox')
        funcionario_edicao = funcionario_instancia
    else:
        form = FuncionarioAlmoxForm(instance=funcionario_edicao)

    funcionarios_qs = Funcionario.objects.prefetch_related('cc')
    if search_nome:
        funcionarios_qs = funcionarios_qs.filter(nome__icontains=search_nome)

    funcionarios = list(funcionarios_qs.order_by('-ativo', 'nome', 'matricula'))
    ativos = sum(1 for funcionario in funcionarios if funcionario.ativo)

    context = {
        'form': form,
        'funcionario_edicao': funcionario_edicao,
        'funcionarios': funcionarios,
        'search_nome': search_nome,
        'total_funcionarios': len(funcionarios),
        'total_ativos': ativos,
        'total_inativos': len(funcionarios) - ativos,
    }
    return render(request, 'home/funcionarios_almox.html', context)


@login_required
def gerenciar_requisicoes_almox(request):
    if not _usuario_pode_gerir_cadastro_almox(request):
        return HttpResponseForbidden("Sem permissao para gerenciar produtos requisitaveis do almoxarifado.")

    search = (request.GET.get("search") or request.POST.get("search") or "").strip()
    status = (request.GET.get("status") or request.POST.get("status") or "").strip()
    page = request.GET.get("page") or request.POST.get("page") or 1
    erro_cadastro = ""
    novo_item_form = {
        "codigo": "",
        "nome": "",
        "unidade": "",
        "ativo": True,
        "classes": [],
    }

    if request.method == "POST":
        acao = request.POST.get("acao")

        if acao == "criar":
            codigo = (request.POST.get("codigo") or "").strip()
            nome = (request.POST.get("nome") or "").strip()
            unidade = (request.POST.get("unidade") or "").strip()
            classe_ids = request.POST.getlist("classes")
            ativo = request.POST.get("ativo") == "on"

            novo_item_form = {
                "codigo": codigo,
                "nome": nome,
                "unidade": unidade,
                "ativo": ativo,
                "classes": classe_ids,
            }

            if not codigo or not nome:
                erro_cadastro = "Informe código e nome do produto."
            elif not classe_ids:
                erro_cadastro = "Selecione ao menos uma classe de requisição."
            elif ItensSolicitacao.objects.filter(codigo=codigo).exists():
                erro_cadastro = "Já existe um produto com este código."
            else:
                item = ItensSolicitacao.objects.create(
                    codigo=codigo,
                    nome=nome,
                    unidade=unidade or None,
                    ativo=ativo,
                )
                item.classe_requisicao.set(classe_ids)
                return redirect(f"{request.path}?search={codigo}")

        else:
            item = get_object_or_404(ItensSolicitacao, pk=request.POST.get("item_id"))
            item.ativo = not item.ativo
            item.save(update_fields=["ativo"])
            params = {}
            if search:
                params["search"] = search
            if status:
                params["status"] = status
            if page:
                params["page"] = page
            if params:
                return redirect(f"{request.path}?{urlencode(params)}")
            return redirect("gerenciar_requisicoes_almox")

    itens_qs = ItensSolicitacao.objects.prefetch_related("classe_requisicao")
    if search:
        itens_qs = itens_qs.filter(Q(codigo__icontains=search) | Q(nome__icontains=search))
    if status == "ativos":
        itens_qs = itens_qs.filter(ativo=True)
    elif status == "inativos":
        itens_qs = itens_qs.filter(ativo=False)

    itens_qs = itens_qs.order_by("-ativo", "codigo", "nome")
    total_itens = itens_qs.count()
    total_ativos = itens_qs.filter(ativo=True).count()
    total_inativos = total_itens - total_ativos
    paginator = Paginator(itens_qs, 20)
    page_obj = paginator.get_page(page)

    query_base = {}
    if search:
        query_base["search"] = search
    if status:
        query_base["status"] = status
    query_string = urlencode(query_base)

    context = {
        "itens": page_obj,
        "page_obj": page_obj,
        "query_string": query_string,
        "search": search,
        "status": status,
        "total_itens": total_itens,
        "total_ativos": total_ativos,
        "total_inativos": total_inativos,
        "classes_requisicao": ClasseRequisicao.objects.order_by("nome"),
        "erro_cadastro": erro_cadastro,
        "novo_item_form": novo_item_form,
    }
    return render(request, "home/requisicoes_almox.html", context)


@login_required
def gerenciar_transferencias_almox(request):
    if not _usuario_pode_gerir_cadastro_almox(request):
        return HttpResponseForbidden("Sem permissao para gerenciar produtos transferiveis do almoxarifado.")

    search = (request.GET.get("search") or request.POST.get("search") or "").strip()
    status = (request.GET.get("status") or request.POST.get("status") or "").strip()
    page = request.GET.get("page") or request.POST.get("page") or 1
    erro_cadastro = ""
    novo_item_form = {
        "codigo": "",
        "nome": "",
        "unidade": "",
        "ativo": True,
    }

    if request.method == "POST":
        acao = request.POST.get("acao")

        if acao == "criar":
            codigo = (request.POST.get("codigo") or "").strip()
            nome = (request.POST.get("nome") or "").strip()
            unidade = (request.POST.get("unidade") or "").strip()
            ativo = request.POST.get("ativo") == "on"

            novo_item_form = {
                "codigo": codigo,
                "nome": nome,
                "unidade": unidade,
                "ativo": ativo,
            }

            if not codigo or not nome:
                erro_cadastro = "Informe código e nome do produto."
            elif ItensTransferencia.objects.filter(codigo=codigo).exists():
                erro_cadastro = "Já existe um produto com este código."
            else:
                ItensTransferencia.objects.create(
                    codigo=codigo,
                    nome=nome,
                    unidade=unidade or None,
                    ativo=ativo,
                )
                return redirect(f"{request.path}?search={codigo}")

        else:
            item = get_object_or_404(ItensTransferencia, pk=request.POST.get("item_id"))
            item.ativo = not item.ativo
            item.save(update_fields=["ativo"])
            params = {}
            if search:
                params["search"] = search
            if status:
                params["status"] = status
            if page:
                params["page"] = page
            if params:
                return redirect(f"{request.path}?{urlencode(params)}")
            return redirect("gerenciar_transferencias_almox")

    itens_qs = ItensTransferencia.objects.all()
    if search:
        itens_qs = itens_qs.filter(Q(codigo__icontains=search) | Q(nome__icontains=search))
    if status == "ativos":
        itens_qs = itens_qs.filter(ativo=True)
    elif status == "inativos":
        itens_qs = itens_qs.filter(ativo=False)

    itens_qs = itens_qs.order_by("-ativo", "codigo", "nome")
    total_itens = itens_qs.count()
    total_ativos = itens_qs.filter(ativo=True).count()
    total_inativos = total_itens - total_ativos
    paginator = Paginator(itens_qs, 20)
    page_obj = paginator.get_page(page)

    query_base = {}
    if search:
        query_base["search"] = search
    if status:
        query_base["status"] = status
    query_string = urlencode(query_base)

    context = {
        "itens": page_obj,
        "page_obj": page_obj,
        "query_string": query_string,
        "search": search,
        "status": status,
        "total_itens": total_itens,
        "total_ativos": total_ativos,
        "total_inativos": total_inativos,
        "erro_cadastro": erro_cadastro,
        "novo_item_form": novo_item_form,
    }
    return render(request, "home/transferencias_almox.html", context)
