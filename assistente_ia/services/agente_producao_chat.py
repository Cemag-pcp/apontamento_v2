"""
Agent de chat sobre produção usando a Claude API com tool use.

Mesmo padrão de ferramentas de automacoes/agent_producao.py, adaptado para
rodar dentro do processo Django já inicializado (sem django.setup()) e com
o histórico persistido em MensagemChatAssistente em vez de em memória.
"""

import os
import json

import anthropic
from django.apps import apps as django_apps
from django.db.models import Avg, Count, Max, Min, Q, Sum
from django.utils import timezone

from core.models import Ordem, OrdemProcesso

# Apps de infraestrutura (não são dados de negócio do cmgprod) e modelos
# especificamente sensíveis (controle de acesso, tokens públicos) — nunca
# consultáveis via ORM livre, mesmo com acesso amplo às demais tabelas.
DENY_APPS = {
    'admin', 'auth', 'contenttypes', 'sessions', 'messages', 'staticfiles',
    'storages', 'channels', 'corsheaders', 'authtoken', 'daphne', 'assistente_ia',
}
DENY_MODELS = {'core.profile', 'cargas.linkacompanhamento'}
LIMITE_MAX_CONSULTA_ORM = 100


# ---------------------------------------------------------------------------
# Ferramentas que o agent pode usar
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "listar_ordens",
        "description": (
            "Lista ordens de produção filtrando por status e/ou setor (grupo_maquina). "
            "Retorna número da ordem, setor, status atual e data de programação."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": [
                        "aguardando_iniciar", "iniciada", "finalizada",
                        "interrompida", "agua_prox_proc"
                    ],
                    "description": "Filtrar por status da ordem. Omita para todos os status.",
                },
                "grupo_maquina": {
                    "type": "string",
                    "enum": [
                        "laser_1", "laser_2", "laser_3", "plasma", "prensa",
                        "usinagem", "serra", "prod_esp", "estamparia",
                        "montagem", "pintura"
                    ],
                    "description": "Filtrar por setor/grupo de máquina. Omita para todos os setores.",
                },
                "limite": {
                    "type": "integer",
                    "description": "Número máximo de ordens a retornar. Padrão: 20.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "resumo_producao",
        "description": (
            "Retorna um resumo da produção atual: total de ordens por status e por setor. "
            "Use para perguntas como 'qual é o status geral da produção?' ou 'quantas ordens estão em andamento?'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "buscar_ordem",
        "description": (
            "Busca os detalhes completos de uma ordem específica por número. O sistema tem dois "
            "números diferentes para uma ordem: o número sequencial do setor (campo 'ordem', usado "
            "na maioria das telas/relatórios) e o ID interno (chave primária, usado no '#' exibido "
            "nos cards do quadro kanban de montagem/solda). Esta ferramenta tenta os dois "
            "automaticamente, então basta passar o número que o usuário informou."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "numero_ordem": {
                    "type": "integer",
                    "description": "Número da ordem informado pelo usuário (sequencial do setor ou o '#' do kanban).",
                }
            },
            "required": ["numero_ordem"],
        },
    },
    {
        "name": "ordens_interrompidas",
        "description": (
            "Lista ordens que foram interrompidas, com setor, máquina/célula e motivo da "
            "interrupção. Útil para identificar gargalos ou problemas recorrentes, inclusive "
            "'quais células estão paradas por falta de peça' (use o filtro motivo)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "grupo_maquina": {
                    "type": "string",
                    "description": "Filtrar por setor. Omita para todos.",
                },
                "motivo": {
                    "type": "string",
                    "description": "Filtrar pelo motivo da interrupção (busca parcial, ex: 'falta de peça'). Omita para todos.",
                },
                "limite": {
                    "type": "integer",
                    "description": "Máximo de resultados. Padrão: 15.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "buscar_peca",
        "description": (
            "Busca uma peça pelo código em TODOS os setores de uma vez (corte/laser/plasma, "
            "montagem, pintura, usinagem, estamparia, solda, serra, prod. especiais) — não peça "
            "pro usuário informar o setor antes de buscar. Retorna em quais ordens ela aparece, "
            "setor, status da ordem e quantidade planejada/boa/perdida. Use para perguntas como "
            "'quando foi cortada a peça X?', 'em quais ordens está a peça X?' ou 'tem alguma ordem "
            "aberta para a peça X?'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "codigo_peca": {
                    "type": "string",
                    "description": "Código da peça a buscar (ex: 409753).",
                },
                "limite": {
                    "type": "integer",
                    "description": "Máximo de resultados. Padrão: 10.",
                },
            },
            "required": ["codigo_peca"],
        },
    },
    {
        "name": "pecas_da_ordem",
        "description": (
            "Lista os códigos de peça (ou conjunto) registrados dentro de uma ordem específica — "
            "o que está sendo/foi produzido nela, com quantidade planejada/boa/perdida. Direção "
            "inversa de buscar_peca: aqui você tem o número da ordem e quer os códigos de "
            "peça; use para 'quais peças/códigos tem na ordem X' ou 'o que está sendo cortado na "
            "ordem X'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "numero_ordem": {
                    "type": "integer",
                    "description": "Número da ordem (sequencial do setor ou o '#' do kanban).",
                },
            },
            "required": ["numero_ordem"],
        },
    },
    {
        "name": "listar_modelos",
        "description": (
            "Lista todos os modelos (tabelas) do sistema cmgprod disponíveis para consulta via "
            "consultar_orm, agrupados por app. Use quando não souber qual modelo consultar."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "descrever_modelo",
        "description": (
            "Descreve os campos de um modelo (tabela) do sistema: nome, tipo, opções (choices) e "
            "relacionamentos. Use antes de consultar_orm para saber quais campos/filtros existem."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "modelo": {
                    "type": "string",
                    "description": "Nome do modelo no formato app_label.ModelName (ex: core.Ordem, cargas.Carga).",
                },
            },
            "required": ["modelo"],
        },
    },
    {
        "name": "consultar_orm",
        "description": (
            "Consulta genérica e somente-leitura a qualquer modelo (tabela) do sistema cmgprod via "
            "Django ORM. Use listar_modelos e descrever_modelo antes para saber o nome do modelo e "
            "dos campos. Use para qualquer pergunta que as ferramentas específicas não cobrem."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "modelo": {
                    "type": "string",
                    "description": "Nome do modelo no formato app_label.ModelName (ex: core.Ordem).",
                },
                "filtros": {
                    "type": "object",
                    "description": (
                        "Filtros no estilo Django ORM: {\"campo\": valor} ou "
                        "{\"campo__lookup\": valor} (lookups: gte, lte, gt, lt, icontains, date, "
                        "isnull, in, etc). Ex: {\"grupo_maquina\": \"montagem\", "
                        "\"ultima_atualizacao__date\": \"2026-07-28\"}."
                    ),
                },
                "campos": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Campos a retornar. Omita para retornar todos os campos simples do modelo.",
                },
                "ordenar_por": {
                    "type": "string",
                    "description": "Campo para ordenar (prefixe com '-' para decrescente).",
                },
                "limite": {
                    "type": "integer",
                    "description": f"Máximo de registros. Padrão: 20, máximo: {LIMITE_MAX_CONSULTA_ORM}.",
                },
            },
            "required": ["modelo"],
        },
    },
    {
        "name": "agregar_orm",
        "description": (
            "Calcula uma agregação (soma, contagem, média, mínimo ou máximo) sobre um modelo do "
            "sistema, com filtros opcionais. SEMPRE use esta ferramenta para perguntas do tipo "
            "'quantos/quanto no total', 'soma de X', 'média de X' — em vez de listar os registros "
            "com consultar_orm e somar manualmente."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "modelo": {
                    "type": "string",
                    "description": "Nome do modelo no formato app_label.ModelName (ex: apontamento_montagem.PecasOrdem).",
                },
                "operacao": {
                    "type": "string",
                    "enum": ["soma", "contagem", "media", "minimo", "maximo"],
                    "description": "Operação de agregação.",
                },
                "campo": {
                    "type": "string",
                    "description": "Campo numérico a agregar (ex: qtd_boa). Não necessário para 'contagem'.",
                },
                "filtros": {
                    "type": "object",
                    "description": "Filtros no estilo Django ORM, igual ao de consultar_orm.",
                },
            },
            "required": ["modelo", "operacao"],
        },
    },
    {
        "name": "producao_celula_montagem",
        "description": (
            "Calcula quantos conjuntos (ordens) uma célula de montagem produziu num dia, usando a "
            "mesma lógica validada da tela de ocupação de células (baseada em OrdemProcesso "
            "'iniciada' na máquina/célula). SEMPRE use esta ferramenta — em vez de consultar_orm ou "
            "agregar_orm — para perguntas como 'quantos conjuntos a célula X montou hoje/ontem/no "
            "dia Y', pois os campos de apontamento de outros modelos não são confiáveis para isso."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "nome_celula": {
                    "type": "string",
                    "description": "Nome (ou parte do nome) da célula/máquina de montagem, ex: chassi.",
                },
                "data": {
                    "type": "string",
                    "description": "Data no formato AAAA-MM-DD. Omita para hoje.",
                },
            },
            "required": ["nome_celula"],
        },
    },
    {
        "name": "cambao_em_processo_pintura",
        "description": (
            "Lista os cambões (carrinhos) atualmente EM USO na pintura, com cor, tipo, peças "
            "penduradas e horário de início. IMPORTANTE: a pintura não rastreia trabalho em "
            "andamento via Ordem.status_atual='iniciada' como os outros setores — o status da "
            "Ordem não muda durante a pintura. Use SEMPRE esta ferramenta (não listar_ordens nem "
            "consultar_orm em core.Ordem) para perguntas como 'tem cambão em processo?', 'o que "
            "está pintando agora?' ou 'quais peças estão na pintura no momento?'."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
]


# ---------------------------------------------------------------------------
# Implementação das ferramentas (acesso ao banco Django)
# ---------------------------------------------------------------------------

def _listar_ordens(status: str = None, grupo_maquina: str = None, limite: int = 20) -> str:
    qs = Ordem.objects.filter(excluida=False)
    if status:
        qs = qs.filter(status_atual=status)
    if grupo_maquina:
        qs = qs.filter(grupo_maquina=grupo_maquina)

    ordens = qs.order_by("-ultima_atualizacao")[:limite]

    if not ordens:
        return "Nenhuma ordem encontrada com os filtros informados."

    resultado = []
    for o in ordens:
        resultado.append({
            "ordem": o.ordem,
            "setor": o.get_grupo_maquina_display() if o.grupo_maquina else "—",
            "status": o.get_status_atual_display(),
            "data_programacao": str(o.data_programacao) if o.data_programacao else "—",
            "ultima_atualizacao": o.ultima_atualizacao.strftime("%d/%m/%Y %H:%M"),
        })

    return json.dumps(resultado, ensure_ascii=False)


def _resumo_producao() -> str:
    por_status = (
        Ordem.objects.filter(excluida=False)
        .values("status_atual")
        .annotate(total=Count("id"))
        .order_by("status_atual")
    )
    por_setor = (
        Ordem.objects.filter(excluida=False)
        .values("grupo_maquina")
        .annotate(total=Count("id"))
        .order_by("-total")
    )

    status_map = {
        "aguardando_iniciar": "Aguardando iniciar",
        "iniciada": "Em andamento",
        "finalizada": "Finalizada",
        "interrompida": "Interrompida",
        "agua_prox_proc": "Aguardando próx. processo",
    }

    resumo_status = {status_map.get(r["status_atual"], r["status_atual"]): r["total"] for r in por_status}
    resumo_setor = {r["grupo_maquina"] or "sem setor": r["total"] for r in por_setor}

    return json.dumps({
        "por_status": resumo_status,
        "por_setor": resumo_setor,
        "total_geral": Ordem.objects.filter(excluida=False).count(),
        "data_hora": timezone.now().strftime("%d/%m/%Y %H:%M"),
    }, ensure_ascii=False)


def _buscar_ordem(numero_ordem: int) -> str:
    qs_base = Ordem.objects.select_related("maquina", "operador_final")
    ordens = list(qs_base.filter(ordem=numero_ordem, excluida=False))
    encontrado_por_id = False

    if not ordens:
        # Não achou pelo número sequencial do setor — tenta pelo ID interno
        # (o "#" exibido no kanban de montagem/solda é o ID, não o campo 'ordem').
        por_id = qs_base.filter(id=numero_ordem, excluida=False).first()
        if por_id:
            ordens = [por_id]
            encontrado_por_id = True

    if not ordens:
        return (
            f"Ordem {numero_ordem} não encontrada (tentei tanto pelo número sequencial "
            f"do setor quanto pelo ID interno)."
        )

    if len(ordens) > 1:
        return json.dumps(
            [{"id": o.id, "setor": o.grupo_maquina, "status": o.get_status_atual_display()} for o in ordens],
            ensure_ascii=False,
        )

    ordem = ordens[0]

    processos = ordem.processos.order_by("-data_inicio")[:5]
    historico = [
        {
            "status": p.get_status_display(),
            "inicio": p.data_inicio.strftime("%d/%m/%Y %H:%M"),
            "fim": p.data_fim.strftime("%d/%m/%Y %H:%M") if p.data_fim else "em aberto",
            "motivo_interrupcao": str(p.motivo_interrupcao) if p.motivo_interrupcao else None,
        }
        for p in processos
    ]

    dados = {
        "id_interno": ordem.id,
        "ordem": ordem.ordem,
        "setor": ordem.get_grupo_maquina_display() if ordem.grupo_maquina else "—",
        "maquina_celula": ordem.maquina.nome if ordem.maquina else "—",
        "status_atual": ordem.get_status_atual_display(),
        "data_programacao": str(ordem.data_programacao) if ordem.data_programacao else "—",
        "operador": str(ordem.operador_final) if ordem.operador_final else "—",
        "obs": ordem.obs or "—",
        "ultima_atualizacao": ordem.ultima_atualizacao.strftime("%d/%m/%Y %H:%M"),
        "historico_recente": historico,
    }
    if encontrado_por_id:
        dados["observacao"] = (
            f"Encontrado pelo ID interno {ordem.id} (o número informado bate com o '#' do "
            f"kanban), não pelo número sequencial do setor (que é {ordem.ordem})."
        )

    if hasattr(ordem, "propriedade"):
        p = ordem.propriedade
        dados["material"] = {
            "descricao": p.descricao_mp or "—",
            "quantidade": p.quantidade,
            "espessura": p.espessura or "—",
            "tamanho": p.tamanho or "—",
        }

    return json.dumps(dados, ensure_ascii=False)


_STOPWORDS_PT = {"de", "da", "do", "das", "dos", "e", "a", "o", "em", "por"}


def _ordens_interrompidas(grupo_maquina: str = None, motivo: str = None, limite: int = 15) -> str:
    qs = OrdemProcesso.objects.filter(
        status="interrompida"
    ).select_related("ordem", "ordem__maquina", "motivo_interrupcao").order_by("-data_inicio")

    if grupo_maquina:
        qs = qs.filter(ordem__grupo_maquina=grupo_maquina)
    if motivo:
        # Busca por palavra-chave em vez de frase exata: "falta de peça" deve
        # bater com um motivo cadastrado como "Falta peça" (sem o "de").
        termos = [t for t in motivo.split() if t.lower() not in _STOPWORDS_PT] or [motivo]
        for termo in termos:
            qs = qs.filter(motivo_interrupcao__nome__icontains=termo)

    registros = qs[:limite]

    if not registros:
        return "Nenhuma interrupção encontrada."

    resultado = [
        {
            "ordem": r.ordem.ordem,
            "setor": r.ordem.get_grupo_maquina_display() if r.ordem.grupo_maquina else "—",
            "celula_maquina": r.ordem.maquina.nome if r.ordem.maquina else "—",
            "motivo": str(r.motivo_interrupcao) if r.motivo_interrupcao else "sem motivo registrado",
            "data": r.data_inicio.strftime("%d/%m/%Y %H:%M"),
        }
        for r in registros
    ]
    return json.dumps(resultado, ensure_ascii=False)


def _texto_peca(p, peca_field):
    """'peca' é CharField livre em alguns setores e ForeignKey pra cadastro.Pecas em outros."""
    if not peca_field.is_relation:
        return p.peca
    peca = p.peca
    if not peca:
        return "—"
    return f"{peca.codigo} - {peca.descricao}"


def _buscar_peca(codigo_peca: str, limite: int = 10) -> str:
    resultado = []
    for app_label in _APPS_PECAS_ORDEM:
        try:
            Model = django_apps.get_model(app_label, "PecasOrdem")
        except LookupError:
            continue
        peca_field = next((f for f in Model._meta.fields if f.name == "peca"), None)
        if not peca_field:
            continue

        if peca_field.is_relation:
            qs = Model.objects.filter(
                Q(peca__codigo__icontains=codigo_peca) | Q(peca__descricao__icontains=codigo_peca)
            ).select_related("ordem", "peca")
        else:
            qs = Model.objects.filter(peca__icontains=codigo_peca).select_related("ordem")

        for p in qs:
            if not p.ordem:
                continue
            data_apontamento = getattr(p, "data_apontamento", None)
            resultado.append({
                "app": app_label,
                "ordem": p.ordem.ordem,
                "id_interno_ordem": p.ordem_id,
                "setor": p.ordem.get_grupo_maquina_display() if p.ordem.grupo_maquina else "—",
                "status_ordem": p.ordem.get_status_atual_display(),
                "aberta": p.ordem.status_atual != "finalizada",
                "peca": _texto_peca(p, peca_field),
                "qtd_planejada": p.qtd_planejada,
                "qtd_boa": p.qtd_boa,
                "qtd_morta": p.qtd_morta,
                "apontado": getattr(p, "apontado", None),
                "data_apontamento": data_apontamento.strftime("%d/%m/%Y %H:%M") if data_apontamento else "—",
                "_ultima_atualizacao": p.ordem.ultima_atualizacao,
            })

    if not resultado:
        return f"Nenhum registro encontrado para a peça '{codigo_peca}' em nenhum setor."

    # Prioriza ordens ainda abertas e mais recentes, já que o limite pode
    # cortar antes de chegar nas mais relevantes se ordenado por padrão do banco.
    resultado.sort(key=lambda r: (not r["aberta"], -r["_ultima_atualizacao"].timestamp()))
    for r in resultado:
        del r["_ultima_atualizacao"]

    return json.dumps(resultado[:limite], ensure_ascii=False)


_APPS_PECAS_ORDEM = [
    "apontamento_corte", "apontamento_montagem", "apontamento_pintura", "apontamento_usinagem",
    "apontamento_estamparia", "apontamento_solda", "apontamento_serra", "apontamento_prod_especiais",
]


def _pecas_da_ordem(numero_ordem: int) -> str:
    ordens = list(Ordem.objects.filter(ordem=numero_ordem, excluida=False))
    encontrado_por_id = False

    if not ordens:
        por_id = Ordem.objects.filter(id=numero_ordem, excluida=False).first()
        if por_id:
            ordens = [por_id]
            encontrado_por_id = True

    if not ordens:
        return f"Ordem {numero_ordem} não encontrada (tentei pelo número sequencial do setor e pelo ID interno)."

    if len(ordens) > 1:
        return json.dumps(
            {
                "erro": "Mais de uma ordem tem esse número, em setores diferentes. Refaça a "
                        "busca usando o ID interno de uma das opções abaixo.",
                "opcoes": [{"id": o.id, "setor": o.grupo_maquina} for o in ordens],
            },
            ensure_ascii=False,
        )

    ordem = ordens[0]
    pecas = []
    for app_label in _APPS_PECAS_ORDEM:
        try:
            Model = django_apps.get_model(app_label, "PecasOrdem")
        except LookupError:
            continue
        peca_field = next((f for f in Model._meta.fields if f.name == "peca"), None)
        qs = Model.objects.filter(ordem_id=ordem.id)
        if peca_field and peca_field.is_relation:
            qs = qs.select_related("peca")

        for p in qs:
            if peca_field:
                identificador = _texto_peca(p, peca_field)
            else:
                conjunto = getattr(p, "conjunto", None)
                identificador = str(conjunto) if conjunto else "—"
            data_apontamento = getattr(p, "data_apontamento", None)
            item = {
                "app": app_label,
                "peca": identificador,
                "qtd_planejada": p.qtd_planejada,
                "qtd_boa": p.qtd_boa,
                "qtd_morta": p.qtd_morta,
                "apontado": getattr(p, "apontado", None),
                "tipo_apontamento": getattr(p, "tipo_apontamento", None),
                "data_apontamento": data_apontamento.strftime("%d/%m/%Y %H:%M") if data_apontamento else None,
            }
            erro = getattr(p, "erro_apontamento", None)
            if erro:
                item["erro_apontamento"] = erro
            pecas.append(item)

    if not pecas:
        return f"Nenhuma peça registrada para a ordem {numero_ordem} (setor: {ordem.grupo_maquina or '—'})."

    dados = {
        "ordem": ordem.ordem,
        "id_interno": ordem.id,
        "setor": ordem.get_grupo_maquina_display() if ordem.grupo_maquina else "—",
        "pecas": pecas,
    }
    if encontrado_por_id:
        dados["observacao"] = (
            f"Ordem encontrada pelo ID interno {ordem.id} (número sequencial do setor é {ordem.ordem})."
        )
    return json.dumps(dados, ensure_ascii=False)


def _modelo_permitido(app_label: str, model_name: str) -> bool:
    if app_label in DENY_APPS:
        return False
    if f"{app_label}.{model_name}".lower() in DENY_MODELS:
        return False
    return True


def _resolver_modelo(modelo: str):
    if "." not in modelo:
        raise ValueError(f"Formato inválido, use app_label.ModelName (ex: core.Ordem). Recebido: '{modelo}'")
    app_label, model_name = modelo.split(".", 1)
    if not _modelo_permitido(app_label, model_name.lower()):
        raise ValueError(f"Modelo '{modelo}' não disponível para consulta.")
    try:
        return django_apps.get_model(app_label, model_name)
    except LookupError:
        raise ValueError(f"Modelo '{modelo}' não encontrado. Use listar_modelos para ver os disponíveis.")


def _listar_modelos() -> str:
    resultado = []
    for config in django_apps.get_app_configs():
        if config.label in DENY_APPS:
            continue
        modelos = [
            f"{config.label}.{model.__name__}"
            for model in config.get_models()
            if _modelo_permitido(config.label, model.__name__.lower())
        ]
        if modelos:
            resultado.append({"app": config.label, "modelos": modelos})
    return json.dumps(resultado, ensure_ascii=False)


def _descrever_modelo(modelo: str) -> str:
    try:
        Model = _resolver_modelo(modelo)
    except ValueError as exc:
        return str(exc)

    campos = []
    for f in Model._meta.get_fields():
        if getattr(f, "many_to_many", False) or getattr(f, "one_to_many", False):
            continue
        info = {
            "nome": f.name,
            "tipo": f.get_internal_type() if hasattr(f, "get_internal_type") else type(f).__name__,
        }
        choices = getattr(f, "choices", None)
        if choices:
            info["opcoes"] = [c[0] for c in choices]
        if getattr(f, "is_relation", False) and f.related_model:
            info["relaciona_com"] = f"{f.related_model._meta.app_label}.{f.related_model.__name__}"
        campos.append(info)

    return json.dumps({"modelo": modelo, "campos": campos}, ensure_ascii=False)


def _consultar_orm(modelo: str, filtros: dict = None, campos: list = None, ordenar_por: str = None, limite: int = 20) -> str:
    try:
        Model = _resolver_modelo(modelo)
    except ValueError as exc:
        return str(exc)

    qs = Model.objects.all()

    if filtros:
        try:
            qs = qs.filter(**filtros)
        except Exception as exc:
            return f"Filtro inválido: {exc}"

    if ordenar_por:
        try:
            qs = qs.order_by(ordenar_por)
        except Exception as exc:
            return f"Campo de ordenação inválido: {exc}"

    limite = min(int(limite or 20), LIMITE_MAX_CONSULTA_ORM)

    if not campos:
        campos = [f.name for f in Model._meta.fields]

    try:
        registros = list(qs.values(*campos)[:limite])
    except Exception as exc:
        return f"Erro na consulta: {exc}"

    if not registros:
        return "Nenhum registro encontrado."

    return json.dumps(registros, ensure_ascii=False, default=str)


_OPERACOES_AGREGACAO = {
    "soma": Sum, "contagem": Count, "media": Avg, "minimo": Min, "maximo": Max,
}


def _agregar_orm(modelo: str, operacao: str, campo: str = None, filtros: dict = None) -> str:
    try:
        Model = _resolver_modelo(modelo)
    except ValueError as exc:
        return str(exc)

    if operacao not in _OPERACOES_AGREGACAO:
        return f"Operação '{operacao}' inválida. Use uma de: {', '.join(_OPERACOES_AGREGACAO)}."

    if not campo:
        if operacao == "contagem":
            campo = "id"
        else:
            return "Informe o campo numérico a agregar (ex: qtd_boa)."

    qs = Model.objects.all()
    if filtros:
        try:
            qs = qs.filter(**filtros)
        except Exception as exc:
            return f"Filtro inválido: {exc}"

    try:
        resultado = qs.aggregate(valor=_OPERACOES_AGREGACAO[operacao](campo))
    except Exception as exc:
        return f"Erro na agregação: {exc}"

    valor = resultado["valor"]
    return json.dumps(
        {"modelo": modelo, "operacao": operacao, "campo": campo, "resultado": valor if valor is not None else 0},
        ensure_ascii=False, default=str,
    )


def _producao_celula_montagem(nome_celula: str, data: str = None) -> str:
    from datetime import date as date_cls

    from cadastro.models import Maquina
    from apontamento_montagem.views import _calcular_ocupacao_celula

    maquinas = list(Maquina.objects.filter(setor__nome="montagem", tipo="maquina", nome__icontains=nome_celula))

    if not maquinas:
        opcoes = list(
            Maquina.objects.filter(setor__nome="montagem", tipo="maquina")
            .values_list("nome", flat=True).distinct()
        )
        return json.dumps(
            {"erro": f"Nenhuma célula de montagem encontrada com o nome '{nome_celula}'.", "celulas_disponiveis": opcoes},
            ensure_ascii=False,
        )
    if len(maquinas) > 1:
        return json.dumps(
            {"erro": "Mais de uma célula corresponde a esse nome, especifique.", "opcoes": [m.nome for m in maquinas]},
            ensure_ascii=False,
        )

    maquina = maquinas[0]

    if data:
        try:
            dia = date_cls.fromisoformat(data)
        except ValueError:
            return f"Data inválida: '{data}'. Use o formato AAAA-MM-DD."
    else:
        dia = timezone.localdate()

    resultado = _calcular_ocupacao_celula(maquina.id, dia)
    ordens_produzindo = sorted({
        item["ordem"] for item in resultado["linha_do_tempo"]
        if item["situacao"] == "produzindo" and item["ordem"]
    })

    return json.dumps({
        "celula": maquina.nome,
        "data": dia.isoformat(),
        "conjuntos_montados": len(ordens_produzindo),
        "ordens": ordens_produzindo,
        "tempo_produzindo": resultado["tempo_produzindo"],
        "tempo_parado": resultado["tempo_parado"],
        "percentual_produzindo": resultado["percentual_produzindo"],
    }, ensure_ascii=False)


def _cambao_em_processo_pintura() -> str:
    from apontamento_pintura.models import Cambao

    cambaos = (
        Cambao.objects.filter(status="em uso", ativo=True)
        .prefetch_related("pecas_no_cambao__peca_ordem__ordem")
        .order_by("cor", "nome")
    )

    if not cambaos:
        return "Nenhum cambão em processo na pintura no momento."

    resultado = []
    for c in cambaos:
        pecas_ativas = [cp for cp in c.pecas_no_cambao.all() if cp.status != "finalizada"]
        inicio = min((cp.data_pendura for cp in pecas_ativas if cp.data_pendura), default=None)
        resultado.append({
            "cambao": c.nome,
            "cor": c.cor,
            "tipo": c.tipo,
            "inicio": timezone.localtime(inicio).strftime("%d/%m/%Y %H:%M:%S") if inicio else "—",
            "pecas": [
                {
                    "peca": cp.peca_ordem.peca if cp.peca_ordem else "—",
                    "quantidade": cp.quantidade_pendurada,
                    "ordem": cp.peca_ordem.ordem.ordem if cp.peca_ordem and cp.peca_ordem.ordem else None,
                    "data_carga": (
                        str(cp.peca_ordem.ordem.data_carga)
                        if cp.peca_ordem and cp.peca_ordem.ordem and cp.peca_ordem.ordem.data_carga
                        else "—"
                    ),
                }
                for cp in pecas_ativas
            ],
        })

    return json.dumps(resultado, ensure_ascii=False)


def _executar_ferramenta(nome: str, parametros: dict) -> str:
    if nome == "listar_ordens":
        return _listar_ordens(**parametros)
    elif nome == "resumo_producao":
        return _resumo_producao()
    elif nome == "buscar_ordem":
        return _buscar_ordem(**parametros)
    elif nome == "ordens_interrompidas":
        return _ordens_interrompidas(**parametros)
    elif nome == "buscar_peca":
        return _buscar_peca(**parametros)
    elif nome == "pecas_da_ordem":
        return _pecas_da_ordem(**parametros)
    elif nome == "listar_modelos":
        return _listar_modelos()
    elif nome == "descrever_modelo":
        return _descrever_modelo(**parametros)
    elif nome == "consultar_orm":
        return _consultar_orm(**parametros)
    elif nome == "agregar_orm":
        return _agregar_orm(**parametros)
    elif nome == "producao_celula_montagem":
        return _producao_celula_montagem(**parametros)
    elif nome == "cambao_em_processo_pintura":
        return _cambao_em_processo_pintura()
    return f"Ferramenta '{nome}' não reconhecida."


# ---------------------------------------------------------------------------
# Agent principal
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """Você é o assistente de IA do sistema cmgprod, integrado a todo o sistema de
apontamento de produção da empresa (produção, corte, montagem, pintura, expedição, cargas,
almoxarifado, compras, comercial, etc). Você SÓ responde perguntas relacionadas a este sistema,
usando exclusivamente os dados reais retornados pelas ferramentas disponíveis.

Você tem ferramentas específicas para as perguntas mais comuns de produção (ordens, resumo,
interrupções, peças cortadas, produção por célula de montagem) e ferramentas genéricas
(listar_modelos, descrever_modelo, consultar_orm, agregar_orm) que dão acesso de leitura a
qualquer outra tabela do sistema. Quando a pergunta não for coberta pelas ferramentas específicas,
use listar_modelos/descrever_modelo para descobrir o modelo e os campos certos.

Para perguntas de "quantos/quanto no total", soma, contagem ou média, SEMPRE use agregar_orm — que
calcula direto no banco — em vez de consultar_orm seguido de soma manual. NUNCA mostre a conta
sendo feita (tipo "3 + 5 + 7 + ... = 91"): o cálculo é interno, a resposta é só o resultado final.

Cuidado com campos de "apontamento"/"data_apontamento" em modelos como PecasOrdem: em muitas
células esses campos ficam nulos mesmo quando a ordem foi concluída, porque o fluxo real de
conclusão usa core.Ordem.status_atual + core.Ordem.ultima_atualizacao (e core.OrdemProcesso para
o histórico de status). Para perguntas de "quantos X foram concluídos/produzidos hoje/no período"
por setor ou célula (máquina), prefira filtrar por Ordem.status_atual='finalizada' e
Ordem.ultima_atualizacao (ou OrdemProcesso com status='finalizada' e data_fim), usando
Ordem.maquina__nome para a célula — só use os campos de apontamento de outros modelos se
descrever_modelo mostrar que eles de fato têm dados preenchidos para o filtro em questão. Se dois
campos parecerem indicar a mesma coisa com respostas diferentes, avise o usuário da ambiguidade em
vez de escolher um silenciosamente.

Quando o usuário perguntar sobre uma peça por código sem informar o setor (ex: "tem ordem aberta
pra peça X?", "onde está a peça X?"), use buscar_peca diretamente — ela já busca em todos os
setores de uma vez. Não peça pro usuário informar o setor antes de tentar.

Ao filtrar texto (nomes, descrições, motivos) com __icontains, use uma palavra-chave curta e
característica (ex: "peça", "chassi") em vez da frase inteira que o usuário digitou — o texto
cadastrado no banco raramente bate palavra por palavra com a frase da pergunta (preposições como
"de"/"por" costumam estar ausentes). Se um filtro de texto não retornar nada, tente de novo com
um termo mais curto antes de concluir que não existe.

Cuidado também: core.Ordem tem DOIS números diferentes — o campo 'ordem' (sequencial por setor,
usado na maioria das telas/relatórios) e o 'id' (chave primária, usado como o "#" exibido nos
cards do kanban de montagem/solda). Quando o usuário mencionar um número de ordem (com ou sem
"#") e a busca por 'ordem' não encontrar nada, tente também por 'id' antes de dizer que não
existe — a ferramenta buscar_ordem já faz isso automaticamente.

Cuidado também: no setor de PINTURA, Ordem.status_atual NÃO muda pra 'iniciada' quando a peça
entra em produção — o trabalho em andamento ali é rastreado por CAMBÃO (carrinho), não pela
ordem. Perguntas como "tem cambão em processo?", "o que está pintando agora?" ou "quantas ordens
estão em produção na pintura?" devem usar cambao_em_processo_pintura, nunca listar_ordens ou
consultar_orm em core.Ordem filtrando pintura.

Para perguntas de "por que essa ordem voltou/não apontou/deu erro", use pecas_da_ordem — o campo
erro_apontamento (quando presente) traz o motivo exato retornado pela integração com o ERP (ex:
"ERP desabilitado temporariamente", "item com qtd_morta > 0 bloqueado automaticamente"). Combine
com buscar_ordem para trazer o histórico de status (OrdemProcesso) junto, quando a pergunta pedir
o histórico completo.

Se a pergunta não tiver relação com o sistema cmgprod (ex: perguntas gerais, de conhecimento
público, sobre outros assuntos), recuse educadamente e explique que você só responde sobre o
sistema cmgprod. Nunca invente dados: se uma ferramenta não retornar a informação pedida, diga
que não encontrou, não tente adivinhar.

Responda sempre em português brasileiro de forma direta e curta. Vá direto ao dado pedido, sem
introdução, sem repetir a pergunta, sem seções de "Observação"/"Importante"/"Recomendação" e sem
emojis, a menos que o usuário peça uma análise. Quando listar vários registros, use uma tabela
enxuta com só as colunas relevantes para a pergunta. Só comente algo além do dado (ex: um padrão
ou problema notável) se isso for realmente útil e em uma frase, não um parágrafo."""

MODEL = "claude-haiku-4-5"

# Desliga temporariamente a chamada real a API da Anthropic. Enquanto True, o
# chat continua funcionando normalmente (widget, persistencia, historico),
# mas so devolve uma mensagem fixa, sem gastar tokens nem chamar a API.
DESABILITADO_TEMPORARIAMENTE = True
MENSAGEM_DESABILITADO = "Estamos em fase de teste"


def _historico_para_claude(mensagens):
    return [
        {"role": m.role, "content": m.conteudo}
        for m in mensagens
    ]


def perguntar(pergunta: str, historico_anterior) -> str:
    """
    Envia uma pergunta ao agent, dado o histórico de mensagens já persistidas
    (lista de MensagemChatAssistente ordenada por criada_em, sem a pergunta atual).
    Retorna o texto da resposta do assistente.
    """
    if DESABILITADO_TEMPORARIAMENTE:
        return MENSAGEM_DESABILITADO

    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    historico = _historico_para_claude(historico_anterior)
    historico.append({"role": "user", "content": pergunta})

    while True:
        resposta = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=historico,
        )

        historico.append({"role": "assistant", "content": resposta.content})

        if resposta.stop_reason == "end_turn":
            texto = next(
                (b.text for b in resposta.content if hasattr(b, "text")), ""
            )
            return texto

        if resposta.stop_reason == "tool_use":
            resultados_ferramentas = []
            for bloco in resposta.content:
                if bloco.type == "tool_use":
                    resultado = _executar_ferramenta(bloco.name, bloco.input)
                    resultados_ferramentas.append({
                        "type": "tool_result",
                        "tool_use_id": bloco.id,
                        "content": resultado,
                    })
            historico.append({"role": "user", "content": resultados_ferramentas})
        else:
            break

    return "Não foi possível obter uma resposta."
