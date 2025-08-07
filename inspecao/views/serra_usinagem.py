from django.shortcuts import render
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q, Prefetch
from django.db import transaction
from django.views.decorators.http import require_POST, require_GET

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
from datetime import timedelta, datetime, timezone


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


@require_GET
def get_itens_inspecao_serra_usinagem(request):
    try:
        # Parâmetros de paginação
        pagina = int(request.GET.get("pagina", 1))
        itens_por_pagina = int(request.GET.get("itens_por_pagina", 10))

        # Filtros
        maquinas_param = request.GET.get("maquinas", "")
        data_param = request.GET.get("data", "")
        pesquisar_param = request.GET.get("pesquisar", "").strip()
        status_param = request.GET.get("status", "")  # Novo filtro por status

        # Construção da query base
        query = Q(
            Q(pecas_ordem_serra__isnull=False) | Q(pecas_ordem_usinagem__isnull=False)
        )

        query &= (
            Q(dadosexecucaoinspecao__isnull=True) |  # Não iniciadas
            Q(dadosexecucaoinspecao__num_execucao=0)  # Primeira execução (num_execucao = 0)
        )

        # Filtro por status0
        if status_param:
            print(status_param == "Não iniciado")
            print(status_param)
            print("Não iniciado")
            if status_param == "Não iniciado":
                query &= Q(dadosexecucaoinspecao__isnull=True)
            elif status_param == "Em andamento":
                query &= Q(dadosexecucaoinspecao__isnull=False) & Q(
                    dadosexecucaoinspecao__info_adicionais__inspecao_finalizada=False
                )
            # Removido o caso "finalizado" para não retornar inspeções finalizadas
        else:
            # Filtro padrão: não finalizadas
            query &= Q(dadosexecucaoinspecao__isnull=True) | Q(
                dadosexecucaoinspecao__info_adicionais__inspecao_finalizada=False
            )
        
        total_sem_filtros = Inspecao.objects.filter(query).count()

        # Outros filtros (mantidos da versão anterior)
        if maquinas_param:
            maquinas_list = [m.strip() for m in maquinas_param.split(",") if m.strip()]
            if maquinas_list:
                query_maquinas = Q()
                for maquina in maquinas_list:
                    query_maquinas |= Q(
                        pecas_ordem_serra__ordem__maquina__nome__icontains=maquina
                    )
                    query_maquinas |= Q(
                        pecas_ordem_usinagem__ordem__maquina__nome__icontains=maquina
                    )
                query &= query_maquinas

        if data_param:
            try:
                data_filtro = datetime.strptime(data_param, "%Y-%m-%d").date()
                query &= Q(data_inspecao__date=data_filtro)
            except ValueError:
                pass

        if pesquisar_param:
            query_pesquisa = Q()
            if pesquisar_param.isdigit():
                query_pesquisa |= Q(id=int(pesquisar_param))
            query_pesquisa |= Q(
                pecas_ordem_serra__peca__codigo__icontains=pesquisar_param
            )
            query_pesquisa |= Q(
                pecas_ordem_serra__peca__nome__icontains=pesquisar_param
            )
            query_pesquisa |= Q(
                pecas_ordem_usinagem__peca__codigo__icontains=pesquisar_param
            )
            query_pesquisa |= Q(
                pecas_ordem_usinagem__peca__nome__icontains=pesquisar_param
            )
            query_pesquisa |= Q(
                pecas_ordem_serra__operador__nome__icontains=pesquisar_param
            )
            query_pesquisa |= Q(
                pecas_ordem_serra__operador__matricula__icontains=pesquisar_param
            )
            query_pesquisa |= Q(
                pecas_ordem_usinagem__operador__nome__icontains=pesquisar_param
            )
            query_pesquisa |= Q(
                pecas_ordem_usinagem__operador__matricula__icontains=pesquisar_param
            )
            query &= query_pesquisa

        # Aplica a query e ordenação
        inspecoes = Inspecao.objects.filter(query).distinct().order_by("-data_inspecao")

        # Paginação
        paginator = Paginator(inspecoes, itens_por_pagina)
        page_obj = paginator.get_page(pagina)

        # Construção dos resultados
        result = []
        for inspecao in page_obj:
            ordem_peca = inspecao.pecas_ordem_serra or inspecao.pecas_ordem_usinagem
            maquina_nome = (
                ordem_peca.ordem.maquina.nome if ordem_peca.ordem.maquina else "N/A"
            )
            peca_info = f"{ordem_peca.peca.codigo} - {ordem_peca.peca.descricao}"

            data_ajustada = inspecao.data_inspecao - timedelta(hours=3)

            matricula_nome_operador = ""
            if hasattr(ordem_peca, "operador") and ordem_peca.operador:
                matricula_nome_operador = (
                    f"{ordem_peca.operador.matricula} - {ordem_peca.operador.nome}"
                )

            # Determina status
            status_info = {
                "status": "Não iniciado",
                "inspecao_completa": False,
                "inspecao_finalizada": False,
            }

            if inspecao.dadosexecucaoinspecao_set.exists():
                ultima_execucao = inspecao.dadosexecucaoinspecao_set.order_by(
                    "-num_execucao"
                ).first()
                if ultima_execucao:
                    status_info["inspecao_completa"] = (
                        ultima_execucao.info_adicionais.inspecao_completa
                    )
                    status_info["inspecao_finalizada"] = (
                        ultima_execucao.info_adicionais.inspecao_finalizada
                    )

                    if ultima_execucao.info_adicionais.inspecao_finalizada:
                        status_info["status"] = "Finalizada"
                    elif ultima_execucao.info_adicionais.inspecao_finalizada:
                        status_info["status"] = "Completa"
                    else:
                        status_info["status"] = "Em andamento"

            result.append(
                {
                    "id": inspecao.id,
                    "data": data_ajustada.strftime("%d/%m/%Y %H:%M:%S"),
                    "peca": peca_info,
                    "maquina": maquina_nome,
                    "qtd_apontada": ordem_peca.qtd_boa,
                    "operador": matricula_nome_operador,
                    **status_info,
                }
            )

        return JsonResponse(
            {
                "dados": result,
                "paginacao": {
                    "pagina_atual": page_obj.number,
                    "total_paginas": paginator.num_pages,
                    "total_filtrado": paginator.count,
                    "itens_por_pagina": itens_por_pagina,
                },
                "total_inspecoes_sem_filtros": total_sem_filtros,
            },
            safe=False,
        )

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@require_GET
def get_execucao_inspecao_serra_usinagem(request):
    id_inspecao = request.GET.get("id_inspecao")
    if not id_inspecao:
        return JsonResponse({"error": "id_inspecao não informado"}, status=400)

    try:
        execucoes = DadosExecucaoInspecao.objects.filter(
            inspecao_id=id_inspecao
        ).order_by("-num_execucao")
        if not execucoes.exists():
            return JsonResponse({"existe": False, "dados": []})

        ultima_execucao = execucoes.first()
        info_adicionais = getattr(ultima_execucao, "info_adicionais", None)

        medidas = MedidasProcessoSerraUsinagem.objects.filter(execucao=ultima_execucao)

        dados_organizados = {
            "inspecao_completa": (
                info_adicionais.inspecao_completa if info_adicionais else False
            ),
            "tipos_processo": {},
        }

        for medida in medidas:
            tipo = medida.tipo_processo
            detalhes = DetalheMedidaSerraUsinagem.objects.filter(
                medida_processo=medida
            ).order_by("amostra", "id")

            # Organiza por amostra e coleta cabeçalhos mantendo a ordem e repetições
            amostras = {}
            cabecalhos_por_amostra = {}  # Para armazenar cabeçalhos por amostra
            cabecalhos_unicos = set()  # Para armazenar todos os cabeçalhos únicos

            for detalhe in detalhes:
                amostra = detalhe.amostra

                if amostra not in amostras:
                    amostras[amostra] = {"conforme": True, "medidas": []}
                    cabecalhos_por_amostra[amostra] = (
                        []
                    )  # Inicializa lista de cabeçalhos para esta amostra

                # Adiciona o cabeçalho na ordem em que aparece
                cabecalhos_por_amostra[amostra].append(detalhe.cabecalho)
                cabecalhos_unicos.add(detalhe.cabecalho)

                amostras[amostra]["medidas"].append(
                    {
                        "nome": detalhe.cabecalho,
                        "valor": detalhe.valor,
                        "conforme": detalhe.conforme,
                    }
                )

                if not detalhe.conforme:
                    amostras[amostra]["conforme"] = False

            # Verifica se todas as amostras têm a mesma sequência de cabeçalhos
            sequencia_cabecalhos = None
            cabecalhos_consistentes = True

            for amostra, cabecalhos in cabecalhos_por_amostra.items():
                if sequencia_cabecalhos is None:
                    sequencia_cabecalhos = cabecalhos
                elif cabecalhos != sequencia_cabecalhos:
                    cabecalhos_consistentes = False
                    break

            # Se todas as amostras têm a mesma sequência, usa essa sequência
            if cabecalhos_consistentes and sequencia_cabecalhos:
                cabecalhos_finais = sequencia_cabecalhos
            else:
                # Caso contrário, usa os cabeçalhos únicos em ordem alfabética (ou outra lógica)
                cabecalhos_finais = sorted(cabecalhos_unicos)

            dados_organizados["tipos_processo"][tipo] = {
                "cabecalhos": cabecalhos_finais,  # Agora é uma lista ordenada, não um set
                "amostras": amostras,
            }

        return JsonResponse(
            {
                "existe": True,
                "dados": dados_organizados,
                "num_execucao": ultima_execucao.num_execucao,
            }
        )

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def get_itens_reinspecao_serra_usinagem(request):
    maquinas = request.GET.get("maquinas")  # Ex: "Serra1,Usinagem2"
    data = request.GET.get("data")  # Ex: "2025-07-30"
    pesquisar = request.GET.get("pesquisar")  # Ex: "peça 123"
    pagina = request.GET.get("pagina", 1)

    # Buscar reinspeções pendentes (não reinspecionadas) para serra ou usinagem
    reinspecoes = Reinspecao.objects.filter(
        reinspecionado=False,
        inspecao__pecas_ordem_serra__isnull=False,
        inspecao__dadosexecucaoinspecao__info_adicionais__inspecao_finalizada=True,
    ) | Reinspecao.objects.filter(
        reinspecionado=False,
        inspecao__pecas_ordem_usinagem__isnull=False,
        inspecao__dadosexecucaoinspecao__info_adicionais__inspecao_finalizada=True,
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

        data_ajustada = reinspecao.data_reinspecao - timedelta(hours=3)
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
            "id": inspecao.id,
            "id_inspecao": inspecao.id,
            "data": data_ajustada.strftime(
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
            "inspetor": (
                ultima_execucao.inspetor.user.username
                if ultima_execucao and ultima_execucao.inspetor
                else "N/A"
            ),
            "data_inspecao": (
                ultima_execucao.data_execucao.strftime("%d/%m/%Y %H:%M:%S")
                if ultima_execucao
                else "N/A"
            ),
            "conformidade": (
                ultima_execucao.conformidade if ultima_execucao else 0
            ),
            "nao_conformidade": (
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

    # Buscar apenas inspeções que possuem execução com num_execucao=0
    inspecoes = Inspecao.objects.filter(
        Q(pecas_ordem_serra__isnull=False) | Q(pecas_ordem_usinagem__isnull=False),
        dadosexecucaoinspecao__isnull=False,  # Filtra apenas inspeções com execução
        dadosexecucaoinspecao__num_execucao=0  # Filtra apenas a primeira execução
    ).distinct()

    status_conformidade_filtrados = (
        request.GET.get("status-conformidade", "").split(",")
        if request.GET.get("status-conformidade")
        else []
    )

    if maquinas:
        maquinas_lista = maquinas.split(",")
        inspecoes = inspecoes.filter(
            Q(pecas_ordem_serra__ordem__maquina__nome__in=maquinas_lista)
            | Q(pecas_ordem_usinagem__ordem__maquina__nome__in=maquinas_lista)
        )
    
        # Filtro de status de conformidade
    if status_conformidade_filtrados:
        # Verifica os casos possíveis de combinação de filtros
        if set(status_conformidade_filtrados) == {"conforme", "nao_conforme"}:
            pass
        elif "conforme" in status_conformidade_filtrados:
            # Apenas itens conformes (nao_conformidades = 0) E num_execucao=0
            inspecoes = inspecoes.filter(
                dadosexecucaoinspecao__nao_conformidade=0,
                dadosexecucaoinspecao__num_execucao=0,
            )
        elif "nao_conforme" in status_conformidade_filtrados:
            # Apenas itens não conformes (nao_conformidades > 0) E num_execucao=0
            inspecoes = inspecoes.filter(
                dadosexecucaoinspecao__nao_conformidade__gt=0,
                dadosexecucaoinspecao__num_execucao=0,
            )

    # Filtro por data
    if data:
        inspecoes = inspecoes.filter(data_inspecao__date=data)

    # Filtro por pesquisa (nome ou código da peça)
    if pesquisar:
        inspecoes = inspecoes.filter(
            Q(pecas_ordem_serra__peca__nome__icontains=pesquisar)
            | Q(pecas_ordem_serra__peca__codigo__icontains=pesquisar)
            | Q(pecas_ordem_usinagem__peca__nome__icontains=pesquisar)
            | Q(pecas_ordem_usinagem__peca__codigo__icontains=pesquisar)
        )

    # Prefetch para buscar apenas execuções com num_execucao=0
    inspecoes = inspecoes.prefetch_related(
        Prefetch(
            "dadosexecucaoinspecao_set",
            queryset=DadosExecucaoInspecao.objects.filter(num_execucao=0).select_related(
                "inspetor__user",
                "info_adicionais",
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


        # Agora só temos inspeções com execução num_execucao=0
        for execucao in inspecao.execucoes:
            data_ajustada = execucao.data_execucao - timedelta(hours=3)
            info_adicionais = getattr(execucao, "info_adicionais", None)
            possui_nao_conformidade = execucao.nao_conformidade > 0 or execucao.num_execucao > 0

            item = {
                "id": inspecao.id,
                "data": data_ajustada.strftime("%d/%m/%Y %H:%M:%S"),
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
                "num_execucao": execucao.num_execucao,  # Adicionando num_execucao na resposta
                "possui_nao_conformidade": possui_nao_conformidade,
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
        # Dados básicos
        data = request.POST
        inspecao_id = data.get("inspecao_id")
        inspetor_id = data.get("inspetor")
        observacao = data.get("observacao", "")
        inspecao_completa = data.get("inspecao_total")
        inspecao_completa = True if inspecao_completa == "Sim" else False

        ficha = request.FILES.get("ficha")

        # Dados estruturados
        inspecoes_ativas = json.loads(data.get("inspecoes_ativas", "[]"))
        medidas_serra = json.loads(data.get("medidas_serra", "[]"))
        medidas_usinagem = json.loads(data.get("medidas_usinagem", "[]"))
        medidas_furacao = json.loads(data.get("medidas_furacao", "[]"))
        nao_conformidades = json.loads(data.get("naoConformidades", "[]"))

        print(medidas_serra)
        print(medidas_usinagem)
        print(medidas_furacao)
        print(inspecao_completa)

        with transaction.atomic():
            # Obter instância da inspeção
            inspecao = Inspecao.objects.get(id=inspecao_id)
            inspetor = Profile.objects.get(id=inspetor_id) if inspetor_id else None

            # Verificar se já existe execução para esta inspeção
            dados_execucao_existente = (
                DadosExecucaoInspecao.objects.filter(inspecao=inspecao)
                .order_by("-num_execucao")
                .first()
            )

            if dados_execucao_existente:
                # Usar a execução existente
                dados_execucao = dados_execucao_existente
                # Atualizar campos se necessário
                dados_execucao.conformidade = 0
                dados_execucao.nao_conformidade = 0
                dados_execucao.inspetor = inspetor
                dados_execucao.observacao = observacao
                dados_execucao.save()

                # Obter ou criar info_adicionais existente
                info_adicionais, created = (
                    InfoAdicionaisSerraUsinagem.objects.get_or_create(
                        dados_exec_inspecao=dados_execucao,
                        defaults={
                            "inspecao_completa": inspecao_completa,
                            "ficha": ficha,
                            "observacoes_gerais": observacao,
                        },
                    )
                )

                if not created:
                    # Atualizar info_adicionais existente
                    info_adicionais.inspecao_completa = inspecao_completa
                    if ficha:
                        info_adicionais.ficha = ficha
                    info_adicionais.observacoes_gerais = observacao
                    info_adicionais.save()
            else:
                # Criar nova execução
                dados_execucao = DadosExecucaoInspecao(
                    inspecao=inspecao,
                    inspetor=inspetor,
                    conformidade=0,
                    nao_conformidade=0,
                    observacao=observacao,
                )
                dados_execucao.save()

                # Criar novas info_adicionais
                info_adicionais = InfoAdicionaisSerraUsinagem(
                    dados_exec_inspecao=dados_execucao,
                    inspecao_completa=inspecao_completa,
                    ficha=ficha,
                    observacoes_gerais=observacao,
                    inspecao_finalizada=False,
                )
                info_adicionais.save()

            # Agrupar todas as medidas
            todas_medidas = {
                "serra": medidas_serra,
                "usinagem": medidas_usinagem,
                "furacao": medidas_furacao
            }

            # Determinar o número máximo de amostras entre todos os processos
            max_amostras = max(
                len(medidas_serra),
                len(medidas_usinagem),
                len(medidas_furacao)
            )

            # Processar cada amostra (posição 0 = 1ª amostra, posição 1 = 2ª amostra, etc.)
            for amostra_idx in range(max_amostras):
                amostra_conforme = True
                
                # Verificar cada tipo de processo para esta amostra
                for tipo_processo, medidas in todas_medidas.items():
                    if tipo_processo not in inspecoes_ativas:
                        continue
                        
                    # Verificar se existe medida para esta amostra no processo atual
                    if amostra_idx < len(medidas):
                        medida_amostra = medidas[amostra_idx]
                        if not medida_amostra.get('conforme', True):
                            amostra_conforme = False
                
                # Atualizar contagem conforme/nao conforme
                if amostra_conforme:
                    dados_execucao.conformidade += 1
                else:
                    dados_execucao.nao_conformidade += 1

            # Salvar as medidas no banco de dados
            def salvar_medidas(tipo_processo, medidas_data):
                if tipo_processo not in inspecoes_ativas:
                    return

                # Verificar se já existe medida para este tipo
                medida_existente = MedidasProcessoSerraUsinagem.objects.filter(
                    execucao=dados_execucao, tipo_processo=tipo_processo
                ).first()

                if medida_existente:
                    # Limpar detalhes existentes para reprocessar
                    medida_existente.detalhes.all().delete()
                    medida_processo = medida_existente
                else:
                    # Criar nova medida
                    medida_processo = MedidasProcessoSerraUsinagem(
                        execucao=dados_execucao,
                        info_adicionais=info_adicionais,
                        tipo_processo=tipo_processo,
                    )
                    medida_processo.save()

                # Processar cada amostra
                for amostra_idx, amostra_data in enumerate(medidas_data, 1):
                    # Salvar os detalhes das medidas no banco de dados
                    for medida_key, medida_valor in amostra_data.items():
                        print(amostra_data)
                        if medida_key != 'conforme' and isinstance(medida_valor, dict):
                            DetalheMedidaSerraUsinagem.objects.create(
                                medida_processo=medida_processo,
                                cabecalho=medida_valor['nome'],
                                valor=medida_valor['valor'],
                                conforme=amostra_data.get('conforme', True),
                                amostra=amostra_idx,
                            )

            # Salvar as medidas para cada tipo de processo
            for tipo_processo, medidas in todas_medidas.items():
                salvar_medidas(tipo_processo, medidas)

            if "naoConformidades" in request.POST:
                # Processar não conformidades (limpar existentes primeiro)
                CausasNaoConformidade.objects.filter(dados_execucao=dados_execucao).delete()

                bool_destino = False
                nao_conformidades = json.loads(request.POST.get("naoConformidades", "[]"))
                
                # Verificar se pelo menos um destino é "sucata"
                for nc_data in nao_conformidades:
                    if nc_data.get("destino", "").lower() == "sucata":
                        bool_destino = True
                        break  # Se encontrou um, pode parar de verificar

                reinspecao, _ = Reinspecao.objects.get_or_create(
                    inspecao=inspecao,
                    reinspecionado=bool_destino,
                )
                nao_conformidades = json.loads(request.POST.get("naoConformidades", "[]"))
                for nc_data in nao_conformidades:
                    if nc_data.get("causas"):
                        causa_nc = CausasNaoConformidade.objects.create(
                            dados_execucao=dados_execucao,
                            quantidade=int(nc_data.get("quantidadeAfetada", 1)),
                            destino=nc_data.get("destino"),
                        )
                        
                        # Adiciona causas
                        for causa_id in nc_data.get("causas", []):
                            try:
                                causa = Causas.objects.get(id=causa_id)
                                causa_nc.causa.add(causa)
                            except Causas.DoesNotExist:
                                continue
                        
                        # Processar arquivos - verifique se o nome do campo está correto
                        nc_id = nc_data.get("id")
                        for arquivo in request.FILES.getlist(f'nc_files_{nc_id}'):
                            print(f"Adicionando arquivo: {arquivo.name} para causa {causa_nc.id}")
                            ArquivoCausa.objects.create(
                                causa_nao_conformidade=causa_nc, 
                                arquivo=arquivo
                            )

            # Verificar finalização
            def verificar_finalizacao():
                # Obter a peça da ordem relacionada à inspeção
                pecas_ordem = None
                if inspecao.pecas_ordem_serra:
                    pecas_ordem = inspecao.pecas_ordem_serra
                elif inspecao.pecas_ordem_usinagem:
                    pecas_ordem = inspecao.pecas_ordem_usinagem
                
                if not pecas_ordem:
                    return False  # Se não houver peça relacionada, não pode finalizar
                
                qtd_produzida = pecas_ordem.qtd_boa
                
                for tipo in inspecoes_ativas:
                    amostras_count = (
                        DetalheMedidaSerraUsinagem.objects.filter(
                            medida_processo__execucao=dados_execucao,
                            medida_processo__tipo_processo=tipo,
                        )
                        .values("amostra")
                        .distinct()
                        .count()
                    )
                    
                    # Verifica se o número de amostras é suficiente baseado na quantidade produzida
                    if qtd_produzida >= 3:
                        # Se produção >= 3, exige 3 amostras
                        if amostras_count < 3:
                            return False
                    else:
                        # Se produção < 3, exige amostras igual à quantidade produzida
                        if amostras_count < qtd_produzida:
                            return False
                return True

            info_adicionais.inspecao_finalizada = verificar_finalizacao()
            info_adicionais.save()
            dados_execucao.save()

            return JsonResponse(
                {
                    "status": "success",
                    "message": "Inspeção registrada com sucesso",
                    "inspecao_finalizada": info_adicionais.inspecao_finalizada,
                    "execucao_id": dados_execucao.id,
                    "nova_execucao": not bool(dados_execucao_existente),
                }
            )

    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


def envio_reinspecao_serra_usinagem(request):
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

            inspecao = Inspecao.objects.get(id=id_inspecao)
            inspetor = Profile.objects.get(id=inspetor_id)

            # Criação do registro de execução
            dados_execucao = DadosExecucaoInspecao.objects.create(
                inspecao=inspecao,
                inspetor=inspetor,
                conformidade=int(conformidade),
                nao_conformidade=int(nao_conformidade),
            )

            info_adicionais = InfoAdicionaisSerraUsinagem.objects.create(
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
                    dados_nao_conformidade = CausasNaoConformidade.objects.create(
                        dados_execucao=dados_execucao,
                        quantidade=int(quantidade_afetada),
                        destino='retrabalho',  # Aqui você pode ajustar o destino conforme o seu fluxo
                    )

                    # Relacionar as causas
                    if causas_ids:
                        dados_nao_conformidade.causa.set(causas_ids)

                    # Salvar as imagens relacionadas
                    for imagem in imagens:
                        ArquivoCausa.objects.create(
                            causa_nao_conformidade=dados_nao_conformidade,
                            arquivo=imagem,
                        )
            else:
                reinspecao = Reinspecao.objects.filter(inspecao=inspecao).first()
                if reinspecao:
                    reinspecao.reinspecionado = True
                    reinspecao.save()

        return JsonResponse({"success": True})

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)

def get_historico_serra_usinagem(request, id):
    if request.method != "GET":
        return JsonResponse({"error": "Método não permitido"}, status=405)

    dados = (
        DadosExecucaoInspecao.objects.filter(inspecao__id=id)
        .select_related("inspetor__user")
        .prefetch_related(
            "info_adicionais",
            "medidas_processo",
            "medidas_processo__detalhes",
        )
        .order_by("-id")
    )

    list_history = []
    for dado in dados:
        info_adicionais = dado.info_adicionais if hasattr(dado, 'info_adicionais') else None
        medidas_processo = dado.medidas_processo.all()
        
        # Organizar medidas por tipo de processo
        medidas_por_processo = {}
        for processo in medidas_processo:
            detalhes = [
                {
                    "cabecalho": d.cabecalho,
                    "valor": d.valor,
                    "conforme": d.conforme,
                    "amostra": d.amostra,
                }
                for d in processo.detalhes.all()
            ]
            
            if processo.tipo_processo not in medidas_por_processo:
                medidas_por_processo[processo.tipo_processo] = []
                
            medidas_por_processo[processo.tipo_processo].extend(detalhes)

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
                "inspecao_completa": info_adicionais.inspecao_completa if info_adicionais else False,
                "inspecao_finalizada": info_adicionais.inspecao_finalizada if info_adicionais else False,
                "ficha_url": info_adicionais.ficha.url if info_adicionais and info_adicionais.ficha else None,
                "observacoes_gerais": info_adicionais.observacoes_gerais if info_adicionais else None,
            },
            "medidas_por_processo": medidas_por_processo,
            "total_medidas": dado.conformidade + dado.nao_conformidade,
        }
        list_history.append(history_item)

    return JsonResponse({"history": list_history}, status=200)

def get_historico_causas_serra_usinagem(request, id):
    if request.method != "GET":
        return JsonResponse({"error": "Método não permitido"}, status=405)

    try:
        dados_nao_conformidades = CausasNaoConformidade.objects.filter(
            dados_execucao__id=id
        ).prefetch_related("causa", "arquivos")

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
                causas_dict[dados.id]["quantidade"] = dados.quantidade
                causas_dict[dados.id]["imagens"] = [
                    {"id": arquivo.id, "url": arquivo.arquivo.url}
                    for arquivo in dados.arquivos.all()
                ]
            causas_dict[dados.id]["nomes"].extend(
                [causa.nome for causa in dados.causa.all()]
            )

        causas_list = list(causas_dict.values())

        return JsonResponse({"causas": causas_list}, status=200)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)