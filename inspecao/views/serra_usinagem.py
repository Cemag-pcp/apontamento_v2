from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q, Prefetch
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from django.db.models.functions import (
    Concat,
    Cast,
    TruncMonth,
    ExtractYear,
    ExtractMonth,
)

from apontamento_serra.models import (
    MedidasProcessoSerraUsinagem,
    DetalheMedidaSerraUsinagem,
    InfoAdicionaisSerraUsinagem,
)
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
import json


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
                    "id": inspecao.id,
                    "execucao_id": execucao.id,
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


@require_GET
def get_execucao_inspecao_serra_usinagem(request):
    id_inspecao = request.GET.get("id_inspecao")
    if not id_inspecao:
        return JsonResponse({"error": "id_inspecao não informado"}, status=400)

    try:
        execucoes = DadosExecucaoInspecao.objects.filter(inspecao_id=id_inspecao)
        if not execucoes.exists():
            return JsonResponse({"existe": False, "dados": []})

        dados = []
        for execucao in execucoes:
            info_adicionais = getattr(execucao, "info_adicionais", None)
            medidas = MedidasProcessoSerraUsinagem.objects.filter(execucao=execucao)
            for medida in medidas:
                # Agrupar detalhes por amostra
                detalhes = DetalheMedidaSerraUsinagem.objects.filter(
                    medida_processo=medida
                ).order_by("amostra", "id")

                amostras_dict = {}
                for detalhe in detalhes:
                    amostra = detalhe.amostra
                    if amostra not in amostras_dict:
                        amostras_dict[amostra] = []
                    amostras_dict[amostra].append({
                        "cabecalho": detalhe.cabecalho,
                        "valor": detalhe.valor,
                        "conforme": detalhe.conforme
                    })

                for amostra, detalhes_lista in amostras_dict.items():
                    dados.append({
                        "tipo_processo": medida.tipo_processo,
                        "inspecao_completa": (
                            info_adicionais.inspecao_completa
                            if info_adicionais
                            else False
                        ),
                        "amostra": amostra,
                        "detalhes": detalhes_lista,
                    })
                
                print(dados)

        return JsonResponse({"existe": True, "dados": dados})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

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


@require_POST
@transaction.atomic
def envio_inspecao_serra_usinagem(request):
    try:
        # 1. Obter dados básicos
        data = request.POST
        files = request.FILES

        print(data)

        id_inspecao = data.get("id-inspecao")
        pecas_produzidas = int(data.get("pecasProduzidas", 0))
        num_peca_defeituosa = 0
        inspetor_id = data.get("inspetor")
        inspecao_total = data.get("inspecao_total") == "Sim"

        # 2. Obter inspeções ativas
        inspecoes_ativas = json.loads(data.get("inspecoes_ativas", "[]"))

        # 3. Obter a instância de Inspecao
        try:
            inspecao = Inspecao.objects.get(id=id_inspecao)
        except Inspecao.DoesNotExist:
            return JsonResponse({"error": "Inspeção não encontrada"}, status=404)

        # 4. Obter o perfil do inspetor
        try:
            inspetor = Profile.objects.get(id=inspetor_id)
        except Profile.DoesNotExist:
            inspetor = None

        # 5. Calcular quantidades
        qtd_boa = pecas_produzidas - num_peca_defeituosa
        qtd_morta = num_peca_defeituosa

        # 6. Criar DadosExecucaoInspecao
        dados_execucao = DadosExecucaoInspecao.objects.create(
            inspecao=inspecao,
            inspetor=inspetor,
            conformidade=qtd_boa,
            nao_conformidade=qtd_morta,
        )

        # 7. Criar InfoAdicionais
        info_adicionais = InfoAdicionaisSerraUsinagem.objects.create(
            dados_exec_inspecao=dados_execucao,
            inspecao_completa=inspecao_total,
            observacoes_gerais=data.get("observacoes_gerais", ""),
        )

        # 8. Processar medidas técnicas por tipo de processo
        precisa_reinspecao = False

        for tipo_processo in inspecoes_ativas:
            medidas_key = f"medidas_{tipo_processo}"
            if medidas_key not in data:
                continue

            medidas_data = json.loads(data.get(medidas_key))

            # Criar registro de medidas do processo
            medidas_processo = MedidasProcessoSerraUsinagem.objects.create(
                execucao=dados_execucao,
                info_adicionais=info_adicionais,
                tipo_processo=tipo_processo,
            )

            # Processar cada amostra de medida
            for medida in medidas_data:
                amostra_num = medida.get("amostra", 1)  # Pega o número da amostra, padrão 1
                if not medida.get("conforme", False):
                    precisa_reinspecao = True

                for key, value in medida.items():
                    if key.startswith("medida"):
                        DetalheMedidaSerraUsinagem.objects.create(
                            medida_processo=medidas_processo,
                            cabecalho=value["nome"],
                            valor=float(value["valor"]),
                            amostra=amostra_num,  # Salva o número da amostra
                        )

        # 9. Processar não conformidades
        if "naoConformidades" in data:
            nao_conformidades = json.loads(data.get("naoConformidades"))

            for nc in nao_conformidades:
                if nc.get("destino") == "retrabalho":
                    precisa_reinspecao = True

        # 10. Atualizar quantidade de peças na ordem de produção
        if inspecao.pecas_ordem_serra:
            ordem_pecas = inspecao.pecas_ordem_serra
        elif inspecao.pecas_ordem_usinagem:
            ordem_pecas = inspecao.pecas_ordem_usinagem
        else:
            ordem_pecas = None

        if ordem_pecas:
            ordem_pecas.qtd_morta = qtd_morta
            ordem_pecas.qtd_boa = qtd_boa
            ordem_pecas.save()

        # 11. Criar reinspeção se necessário
        if precisa_reinspecao:
            Reinspecao.objects.create(inspecao=inspecao)

        # 12. Processar fotos das não conformidades
        for key in files:
            if key.startswith("fotos_nao_conformidade"):
                # Implementar lógica para salvar os arquivos
                # Exemplo: info_adicionais.ficha.save(files[key].name, files[key])
                pass

        return JsonResponse(
            {
                "success": True,
                "execucao_id": dados_execucao.id,
                "precisa_reinspecao": precisa_reinspecao,
                "qtd_boa": qtd_boa,
                "qtd_morta": qtd_morta,
            }
        )

    except Exception as e:
        return JsonResponse({"error": str(e), "success": False}, status=500)


def envio_reinspecao_serra_usinagem(request):

    return JsonResponse({})
