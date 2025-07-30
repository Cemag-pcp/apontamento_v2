from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q, Prefetch
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.db.models.functions import (
    Concat,
    Cast,
    TruncMonth,
    ExtractYear,
    ExtractMonth,
)

from apontamento_serra.models import MedidasProcesso
from ..models import (
    Inspecao,
    DadosExecucaoInspecao,
    Reinspecao,
    Causas,
    CausasNaoConformidade,
    ArquivoCausa,
)
from core.models import Profile, Maquina

from collections import defaultdict


def inspecao_serra_usinagem(request):

    maquinas = Maquina.objects.filter(
        Q(setor__nome="serra") | Q(setor__nome="usinagem"), tipo="maquina"
    )

    motivos = Causas.objects.filter(setor="serra-usinagem")
    inspetores = Profile.objects.filter(
        tipo_acesso="inspetor", permissoes__nome="inspecao/serra-usinagem"
    )

    inspetores = [
        {"nome_usuario": inspetor.user.username, "id": inspetor.user.id}
        for inspetor in inspetores
    ]

    user_profile = Profile.objects.filter(user=request.user).first()
    if (
        user_profile
        and user_profile.tipo_acesso == "inspetor"
        and user_profile.permissoes.filter(nome="inspecao/serra-usinagem").exists()
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

    return render(request, "inspecao_serra_usinagem.html", context=context)


def get_itens_inspecao_serra_usinagem(request):
    maquinas = request.GET.get("maquinas")  # Ex: "Serra1,Usinagem2"
    data = request.GET.get("data")  # Ex: "2025-07-30"
    pesquisar = request.GET.get("pesquisar")  # Ex: "peça 123"
    pagina = request.GET.get("pagina", 1)

    # Buscar inspeções do setor serra ou usinagem
    inspecoes = Inspecao.objects.filter(
        pecas_ordem_serra__isnull=False
    ) | Inspecao.objects.filter(pecas_ordem_usinagem__isnull=False)

    if maquinas:
        maquinas_lista = maquinas.split(",")
        inspecoes = inspecoes.filter(
            Q(pecas_ordem_serra__ordem__maquina__nome__in=maquinas_lista)
            | Q(pecas_ordem_usinagem__ordem__maquina__nome__in=maquinas_lista)
        )

    # Filtro por data
    if data:
        inspecoes = inspecoes.filter(data__data_inspecao=data)

    # Filtro por pesquisa (nome ou código da peça)
    if pesquisar:
        inspecoes = inspecoes.filter(
            Q(pecas_ordem_serra__peca__nome__icontains=pesquisar)
            | Q(pecas_ordem_serra__peca__codigo__icontains=pesquisar)
            | Q(pecas_ordem_usinagem__peca__nome__icontains=pesquisar)
            | Q(pecas_ordem_usinagem__peca__codigo__icontains=pesquisar)
        )

    # Prefetch para buscar execuções relacionadas (pode estar vazio)
    inspecoes = inspecoes.prefetch_related(
        Prefetch(
            "dadosexecucaoinspecao_set",
            queryset=DadosExecucaoInspecao.objects.select_related("inspetor__user"),
            to_attr="execucoes",
        ),
        "pecas_ordem_serra__peca",
        "pecas_ordem_serra__ordem__maquina",
        "pecas_ordem_serra__ordem__operador_final",
        "pecas_ordem_usinagem__peca",
        "pecas_ordem_usinagem__ordem__maquina",
        "pecas_ordem_usinagem__ordem__operador_final",
    ).order_by(
        "-id"
    )  # ou "-data_execucao" se quiser o mais recente primeiro

    print(inspecoes)

    # Paginação
    pagina = int(request.GET.get("pagina", 1))
    por_pagina = int(request.GET.get("por_pagina", 10))
    paginador = Paginator(inspecoes, por_pagina)
    pagina_obj = paginador.get_page(pagina)

    dados = []

    for inspecao in pagina_obj:
        # Prioriza serra ou usinagem
        ordem_peca = inspecao.pecas_ordem_serra or inspecao.pecas_ordem_usinagem
        if not ordem_peca:
            continue

        peca_info = ordem_peca.peca.codigo + " - " + ordem_peca.peca.descricao
        maquina_nome = (
            ordem_peca.ordem.maquina.nome if ordem_peca.ordem.maquina else "N/A"
        )
        operador_user = (
            ordem_peca.ordem.operador_final if ordem_peca.ordem.operador_final else None
        )
        matricula_nome_operador = (
            f"{operador_user.matricula} - {operador_user.nome}"
            if operador_user
            else "Sem operador"
        )

        if inspecao.execucoes:
            for execucao in inspecao.execucoes:
                item = {
                    "id": execucao.id,
                    "data": execucao.data_execucao.strftime("%d/%m/%Y %H:%M:%S"),
                    "peca": peca_info,
                    "maquina": maquina_nome,
                    "qtd_apontada": ordem_peca.qtd_boa,
                    "operador": matricula_nome_operador,
                    "status": "Em andamento",
                }
                dados.append(item)
        else:
            # Caso sem execução
            item = {
                "id": inspecao.id,
                "data": inspecao.data_inspecao,
                "peca": peca_info,
                "maquina": maquina_nome,
                "qtd_apontada": ordem_peca.qtd_boa,
                "operador": matricula_nome_operador,
                "status": "Não iniciado",
            }
            dados.append(item)

    return JsonResponse(
        {
            "dados": dados,
            "total": paginador.count,
            "total_filtrado": paginador.count,
            "pagina_atual": pagina_obj.number,
            "total_paginas": paginador.num_pages,
        },
        status=200,
    )


def get_itens_reinspecao_serra_usinagem(request):
    maquinas = request.GET.get("maquinas")  # Ex: "Serra1,Usinagem2"
    data = request.GET.get("data")  # Ex: "2025-07-30"
    pesquisar = request.GET.get("pesquisar")  # Ex: "peça 123"
    pagina = request.GET.get("pagina", 1)

    # Buscar reinspeções pendentes (não reinspecionadas) para serra ou usinagem
    reinspecoes = Reinspecao.objects.filter(
        reinspecionado=False, inspecao__pecas_ordem_serra__isnull=False
    ) | Reinspecao.objects.filter(
        reinspecionado=False, inspecao__pecas_ordem_usinagem__isnull=False
    )

    # Filtro por máquinas
    if maquinas:
        maquinas_lista = maquinas.split(",")
        reinspecoes = reinspecoes.filter(
            Q(inspecao__pecas_ordem_serra__ordem__maquina__nome__in=maquinas_lista)
            | Q(inspecao__pecas_ordem_usinagem__ordem__maquina__nome__in=maquinas_lista)
        )

    # Filtro por data
    if data:
        reinspecoes = reinspecoes.filter(data_reinspecao__date=data)

    # Filtro por pesquisa (nome ou código da peça)
    if pesquisar:
        reinspecoes = reinspecoes.filter(
            Q(inspecao__pecas_ordem_serra__peca__nome__icontains=pesquisar)
            | Q(inspecao__pecas_ordem_serra__peca__codigo__icontains=pesquisar)
            | Q(inspecao__pecas_ordem_usinagem__peca__nome__icontains=pesquisar)
            | Q(inspecao__pecas_ordem_usinagem__peca__codigo__icontains=pesquisar)
        )

    # Prefetch relacionamentos necessários
    reinspecoes = (
        reinspecoes.select_related(
            "inspecao__pecas_ordem_serra__peca",
            "inspecao__pecas_ordem_serra__ordem__maquina",
            "inspecao__pecas_ordem_serra__ordem__operador_final",
            "inspecao__pecas_ordem_usinagem__peca",
            "inspecao__pecas_ordem_usinagem__ordem__maquina",
            "inspecao__pecas_ordem_usinagem__ordem__operador_final",
        )
        .prefetch_related(
            Prefetch(
                "inspecao__dadosexecucaoinspecao_set",
                queryset=DadosExecucaoInspecao.objects.select_related("inspetor__user"),
                to_attr="execucoes",
            )
        )
        .order_by("-data_reinspecao")
    )

    # Paginação
    pagina = int(request.GET.get("pagina", 1))
    por_pagina = int(request.GET.get("por_pagina", 10))
    paginador = Paginator(reinspecoes, por_pagina)
    pagina_obj = paginador.get_page(pagina)

    dados = []

    for reinspecao in pagina_obj:
        inspecao = reinspecao.inspecao
        # Prioriza serra ou usinagem
        ordem_peca = inspecao.pecas_ordem_serra or inspecao.pecas_ordem_usinagem
        if not ordem_peca:
            continue

        peca_info = ordem_peca.peca.codigo + " - " + ordem_peca.peca.descricao
        maquina_nome = (
            ordem_peca.ordem.maquina.nome if ordem_peca.ordem.maquina else "N/A"
        )
        operador_user = (
            ordem_peca.ordem.operador_final if ordem_peca.ordem.operador_final else None
        )
        matricula_nome_operador = (
            f"{operador_user.matricula} - {operador_user.nome}"
            if operador_user
            else "Sem operador"
        )

        # Pega a última execução de inspeção (para mostrar dados da inspeção original)
        ultima_execucao = inspecao.execucoes[-1] if inspecao.execucoes else None

        item = {
            "id": reinspecao.id,
            "id_inspecao": inspecao.id,
            "data_solicitacao": reinspecao.data_reinspecao.strftime(
                "%d/%m/%Y %H:%M:%S"
            ),
            "peca": peca_info,
            "maquina": maquina_nome,
            "qtd_apontada": ordem_peca.qtd_boa,
            "operador": matricula_nome_operador,
            "status": "Pendente de reinspeção",
            "motivo_reinspecao": (
                reinspecao.motivo
                if hasattr(reinspecao, "motivo")
                else "Não especificado"
            ),
            "inspetor_original": (
                ultima_execucao.inspetor.user.username
                if ultima_execucao and ultima_execucao.inspetor
                else "N/A"
            ),
            "data_inspecao_original": (
                ultima_execucao.data_execucao.strftime("%d/%m/%Y %H:%M:%S")
                if ultima_execucao
                else "N/A"
            ),
            "conformidade_original": (
                ultima_execucao.conformidade if ultima_execucao else 0
            ),
            "nao_conformidade_original": (
                ultima_execucao.nao_conformidade if ultima_execucao else 0
            ),
        }
        dados.append(item)

    return JsonResponse(
        {
            "dados": dados,
            "total": paginador.count,
            "total_filtrado": paginador.count,
            "pagina_atual": pagina_obj.number,
            "total_paginas": paginador.num_pages,
        },
        status=200,
    )


def get_itens_inspecionados_serra_usinagem(request):
    maquinas = request.GET.get("maquinas")  # Ex: "Serra1,Usinagem2"
    data = request.GET.get("data")  # Ex: "2025-07-30"
    pesquisar = request.GET.get("pesquisar")  # Ex: "peça 123"
    pagina = request.GET.get("pagina", 1)

    # Buscar apenas inspeções que possuem execução (já inspecionadas)
    inspecoes = Inspecao.objects.filter(
        Q(pecas_ordem_serra__isnull=False) | Q(pecas_ordem_usinagem__isnull=False),
        dadosexecucaoinspecao__isnull=False,  # Filtra apenas inspeções com execução
    ).distinct()

    if maquinas:
        maquinas_lista = maquinas.split(",")
        inspecoes = inspecoes.filter(
            Q(pecas_ordem_serra__ordem__maquina__nome__in=maquinas_lista)
            | Q(pecas_ordem_usinagem__ordem__maquina__nome__in=maquinas_lista)
        )

    # Filtro por data
    if data:
        inspecoes = inspecoes.filter(data__data_inspecao=data)

    # Filtro por pesquisa (nome ou código da peça)
    if pesquisar:
        inspecoes = inspecoes.filter(
            Q(pecas_ordem_serra__peca__nome__icontains=pesquisar)
            | Q(pecas_ordem_serra__peca__codigo__icontains=pesquisar)
            | Q(pecas_ordem_usinagem__peca__nome__icontains=pesquisar)
            | Q(pecas_ordem_usinagem__peca__codigo__icontains=pesquisar)
        )

    # Prefetch para buscar execuções relacionadas (agora garantido que existem)
    inspecoes = inspecoes.prefetch_related(
        Prefetch(
            "dadosexecucaoinspecao_set",
            queryset=DadosExecucaoInspecao.objects.select_related(
                "inspetor__user",
                "info_adicionais",  # Adicionando o relacionamento com info_adicionais
            ),
            to_attr="execucoes",
        ),
        "pecas_ordem_serra__peca",
        "pecas_ordem_serra__ordem__maquina",
        "pecas_ordem_serra__ordem__operador_final",
        "pecas_ordem_usinagem__peca",
        "pecas_ordem_usinagem__ordem__maquina",
        "pecas_ordem_usinagem__ordem__operador_final",
    ).order_by("-id")

    # Paginação
    pagina = int(request.GET.get("pagina", 1))
    por_pagina = int(request.GET.get("por_pagina", 10))
    paginador = Paginator(inspecoes, por_pagina)
    pagina_obj = paginador.get_page(pagina)

    dados = []

    for inspecao in pagina_obj:
        # Prioriza serra ou usinagem
        ordem_peca = inspecao.pecas_ordem_serra or inspecao.pecas_ordem_usinagem
        if not ordem_peca:
            continue

        peca_info = ordem_peca.peca.codigo + " - " + ordem_peca.peca.descricao
        maquina_nome = (
            ordem_peca.ordem.maquina.nome if ordem_peca.ordem.maquina else "N/A"
        )
        operador_user = (
            ordem_peca.ordem.operador_final if ordem_peca.ordem.operador_final else None
        )
        matricula_nome_operador = (
            f"{operador_user.matricula} - {operador_user.nome}"
            if operador_user
            else "Sem operador"
        )

        # Agora só temos inspeções com execução
        for execucao in inspecao.execucoes:
            # Verifica se tem informações adicionais
            info_adicionais = getattr(execucao, "info_adicionais", None)

            item = {
                "id": execucao.id,
                "data": execucao.data_execucao.strftime("%d/%m/%Y %H:%M:%S"),
                "peca": peca_info,
                "maquina": maquina_nome,
                "qtd_apontada": ordem_peca.qtd_boa,
                "operador": matricula_nome_operador,
                "status": "Concluído",
                "inspetor": (
                    f"{execucao.inspetor.user.username}" if execucao.inspetor else "N/A"
                ),
                "conformidade": execucao.conformidade,
                "nao_conformidade": execucao.nao_conformidade,
                "observacao": execucao.observacao or "",
                "inspecao_completa": (
                    info_adicionais.inspecao_completa if info_adicionais else False
                ),
                "autoinspecao_noturna": (
                    info_adicionais.autoinspecao_noturna if info_adicionais else False
                ),
                "tem_ficha": bool(info_adicionais.ficha) if info_adicionais else False,
            }
            dados.append(item)

    return JsonResponse(
        {
            "dados": dados,
            "total": paginador.count,
            "total_filtrado": paginador.count,
            "pagina_atual": pagina_obj.number,
            "total_paginas": paginador.num_pages,
        },
        status=200,
    )
