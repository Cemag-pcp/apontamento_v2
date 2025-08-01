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
from datetime import timedelta, datetime


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

        # Filtro por status0
        if status_param:
            if status_param == "nao_iniciado":
                query &= Q(dadosexecucaoinspecao__isnull=True)
            elif status_param == "em_andamento":
                query &= Q(dadosexecucaoinspecao__isnull=False) & Q(
                    dadosexecucaoinspecao__info_adicionais__inspecao_finalizada=False
                )
            # Removido o caso "finalizado" para não retornar inspeções finalizadas
        else:
            # Filtro padrão: não finalizadas
            query &= Q(dadosexecucaoinspecao__isnull=True) | Q(
                dadosexecucaoinspecao__info_adicionais__inspecao_finalizada=False
            )

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

        print(inspecoes)

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
                    elif ultima_execucao.info_adicionais.inspecao_completa:
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
                    "total_itens": paginator.count,
                    "itens_por_pagina": itens_por_pagina,
                },
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
        execucoes = DadosExecucaoInspecao.objects.filter(inspecao_id=id_inspecao).order_by('-num_execucao')
        if not execucoes.exists():
            return JsonResponse({"existe": False, "dados": []})

        ultima_execucao = execucoes.first()
        info_adicionais = getattr(ultima_execucao, "info_adicionais", None)
        
        medidas = MedidasProcessoSerraUsinagem.objects.filter(execucao=ultima_execucao)
        
        dados_organizados = {
            'inspecao_completa': info_adicionais.inspecao_completa if info_adicionais else False,
            'tipos_processo': {}
        }

        for medida in medidas:
            tipo = medida.tipo_processo
            detalhes = DetalheMedidaSerraUsinagem.objects.filter(
                medida_processo=medida
            ).order_by("amostra", "id")

            # Organiza por amostra e coleta cabeçalhos únicos
            amostras = {}
            cabecalhos = set()
            
            for detalhe in detalhes:
                amostra = detalhe.amostra
                if amostra not in amostras:
                    amostras[amostra] = {
                        'conforme': True,  # Será atualizado por cada medida
                        'medidas': []
                    }
                
                amostras[amostra]['medidas'].append({
                    'nome': detalhe.cabecalho,
                    'valor': detalhe.valor,
                    'conforme': detalhe.conforme
                })
                
                # Atualiza conforme geral da amostra
                if not detalhe.conforme:
                    amostras[amostra]['conforme'] = False
                
                cabecalhos.add(detalhe.cabecalho)

            dados_organizados['tipos_processo'][tipo] = {
                'cabecalhos': sorted(list(cabecalhos)),
                'amostras': amostras
            }

            print(dados_organizados)

        return JsonResponse({
            "existe": True,
            "dados": dados_organizados,
            "num_execucao": ultima_execucao.num_execucao
        })
        
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
    # Dados básicos
    data = request.POST
    inspecao_id = data.get("inspecao_id")
    inspetor_id = data.get("inspetor_id")
    observacao = data.get("observacao", "")
    ficha = request.FILES.get("ficha")

    # Dados estruturados
    inspecoes_ativas = json.loads(data.get("inspecoes_ativas", "[]"))
    medidas_serra = json.loads(data.get("medidas_serra", "[]"))
    medidas_usinagem = json.loads(data.get("medidas_usinagem", "[]"))
    medidas_furacao = json.loads(data.get("medidas_furacao", "[]"))
    nao_conformidades = json.loads(data.get("naoConformidades", "[]"))
    inspecao_completa = json.loads(data.get("inspecao_completa", "false"))

    print(inspecoes_ativas)
    print(medidas_serra)
    print(medidas_usinagem)
    print(medidas_furacao)

    # Obter instâncias
    inspecao = Inspecao.objects.get(id=inspecao_id)
    inspetor = Profile.objects.get(id=inspetor_id) if inspetor_id else None

    dados_execucao = DadosExecucaoInspecao.objects.filter(inspecao_id=inspecao_id).first()

    if not dados_execucao:
        dados_execucao = DadosExecucaoInspecao(
            inspecao=inspecao,
            inspetor=inspetor,
            conformidade=0,
            nao_conformidade=0,
            observacao=observacao,
        )

        dados_execucao.save()

    # Criar informações adicionais
    info_adicionais = InfoAdicionaisSerraUsinagem(
        dados_exec_inspecao=dados_execucao,
        inspecao_completa=inspecao_completa,
        ficha=ficha,
        observacoes_gerais=observacao,
        inspecao_finalizada=False,  # Inicialmente False
    )
    info_adicionais.save()

    # Processar medidas
    def processar_medidas(tipo_processo, medidas_data):
        if tipo_processo not in inspecoes_ativas:
            return

        medidas_processo = MedidasProcessoSerraUsinagem(
            execucao=dados_execucao,
            info_adicionais=info_adicionais,
            tipo_processo=tipo_processo,
        )
        medidas_processo.save()

        for idx, amostra_data in enumerate(medidas_data, 1):  # idx começa em 1
            conforme_amostra = amostra_data.pop("conforme", True)
            cabecalhos = set()

            # Primeiro verifica todos os cabeçalhos para garantir consistência
            for key, medida in amostra_data.items():
                if isinstance(medida, dict):
                    cabecalhos.add(medida["nome"])

            # Agora cria os registros de detalhes
            for key, medida in amostra_data.items():
                if isinstance(medida, dict):
                    DetalheMedidaSerraUsinagem.objects.create(
                        medida_processo=medidas_processo,
                        cabecalho=medida["nome"],
                        valor=medida["valor"],
                        conforme=medida.get("conforme", True),
                        amostra=idx,  # Usa o índice do array como número da amostra
                    )

            # Atualiza contagem de conformidade
            if conforme_amostra:
                dados_execucao.conformidade += 1
            else:
                dados_execucao.nao_conformidade += 1

    # Processar cada tipo de medida
    processar_medidas("serra", medidas_serra)
    processar_medidas("usinagem", medidas_usinagem)
    processar_medidas("furacao", medidas_furacao)

    # Processar não conformidades
    for nc_data in nao_conformidades:
        causa_nc = CausasNaoConformidade.objects.create(
            dados_execucao=dados_execucao, quantidade=nc_data.get("quantidade", 1)
        )

        for causa_id in nc_data.get("causas", []):
            causa = Causas.objects.get(id=causa_id)
            causa_nc.causa.add(causa)

        # Processar arquivos
        for arquivo in request.FILES.getlist(f'nc_files_{nc_data.get("id")}'):
            ArquivoCausa.objects.create(
                causa_nao_conformidade=causa_nc, arquivo=arquivo
            )

    # Verificar se está finalizada
    def verificar_finalizacao():
        for tipo in inspecoes_ativas:
            # Conta o número de amostras distintas para este tipo de processo
            amostras_distintas = (
                DetalheMedidaSerraUsinagem.objects.filter(
                    medida_processo__execucao=dados_execucao,
                    medida_processo__tipo_processo=tipo,
                )
                .values_list("amostra", flat=True)
                .distinct()
                .count()
            )

            if amostras_distintas < 3:
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
        }
    )


def envio_reinspecao_serra_usinagem(request):

    return JsonResponse({})
