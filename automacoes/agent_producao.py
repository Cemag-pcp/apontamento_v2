"""
Agent de produção usando Claude API com tool use.

Uso standalone (fora do Django):
    python automacoes/agent_producao.py

Uso via Django (em uma view ou management command):
    from automacoes.agent_producao import AgentProducao
    agent = AgentProducao()
    resposta = agent.perguntar("Quantas ordens estão em andamento hoje?")
"""

import os
import sys
import json
import django

# Configuração para rodar standalone (fora do Django server)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "apontamento_v2.settings.dev")
django.setup()

import anthropic
from django.db.models import Count, Q
from django.utils import timezone
from datetime import date

from core.models import Ordem, OrdemProcesso


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
        "description": "Busca os detalhes completos de uma ordem específica pelo número da ordem.",
        "input_schema": {
            "type": "object",
            "properties": {
                "numero_ordem": {
                    "type": "integer",
                    "description": "Número da ordem de produção.",
                }
            },
            "required": ["numero_ordem"],
        },
    },
    {
        "name": "ordens_interrompidas",
        "description": (
            "Lista ordens que foram interrompidas, com o motivo da interrupção. "
            "Útil para identificar gargalos ou problemas recorrentes."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "grupo_maquina": {
                    "type": "string",
                    "description": "Filtrar por setor. Omita para todos.",
                },
                "limite": {
                    "type": "integer",
                    "description": "Máximo de resultados. Padrão: 15.",
                },
            },
            "required": [],
        },
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
    try:
        ordem = Ordem.objects.select_related("maquina", "operador_final").get(
            ordem=numero_ordem, excluida=False
        )
    except Ordem.DoesNotExist:
        return f"Ordem {numero_ordem} não encontrada."
    except Ordem.MultipleObjectsReturned:
        # Pode haver duplicatas em setores diferentes
        ordens = Ordem.objects.filter(ordem=numero_ordem, excluida=False)
        return json.dumps(
            [{"id": o.id, "setor": o.grupo_maquina, "status": o.get_status_atual_display()} for o in ordens],
            ensure_ascii=False,
        )

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
        "ordem": ordem.ordem,
        "setor": ordem.get_grupo_maquina_display() if ordem.grupo_maquina else "—",
        "status_atual": ordem.get_status_atual_display(),
        "data_programacao": str(ordem.data_programacao) if ordem.data_programacao else "—",
        "operador": str(ordem.operador_final) if ordem.operador_final else "—",
        "obs": ordem.obs or "—",
        "ultima_atualizacao": ordem.ultima_atualizacao.strftime("%d/%m/%Y %H:%M"),
        "historico_recente": historico,
    }

    # Propriedades da chapa, se houver
    if hasattr(ordem, "propriedade"):
        p = ordem.propriedade
        dados["material"] = {
            "descricao": p.descricao_mp or "—",
            "quantidade": p.quantidade,
            "espessura": p.espessura or "—",
            "tamanho": p.tamanho or "—",
        }

    return json.dumps(dados, ensure_ascii=False)


def _ordens_interrompidas(grupo_maquina: str = None, limite: int = 15) -> str:
    qs = OrdemProcesso.objects.filter(
        status="interrompida"
    ).select_related("ordem", "motivo_interrupcao").order_by("-data_inicio")

    if grupo_maquina:
        qs = qs.filter(ordem__grupo_maquina=grupo_maquina)

    registros = qs[:limite]

    if not registros:
        return "Nenhuma interrupção encontrada."

    resultado = [
        {
            "ordem": r.ordem.ordem,
            "setor": r.ordem.get_grupo_maquina_display() if r.ordem.grupo_maquina else "—",
            "motivo": str(r.motivo_interrupcao) if r.motivo_interrupcao else "sem motivo registrado",
            "data": r.data_inicio.strftime("%d/%m/%Y %H:%M"),
        }
        for r in registros
    ]
    return json.dumps(resultado, ensure_ascii=False)


def _executar_ferramenta(nome: str, parametros: dict) -> str:
    """Despacha a chamada para a função correta."""
    if nome == "listar_ordens":
        return _listar_ordens(**parametros)
    elif nome == "resumo_producao":
        return _resumo_producao()
    elif nome == "buscar_ordem":
        return _buscar_ordem(**parametros)
    elif nome == "ordens_interrompidas":
        return _ordens_interrompidas(**parametros)
    return f"Ferramenta '{nome}' não reconhecida."


# ---------------------------------------------------------------------------
# Agent principal
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """Você é um assistente de PCP (Planejamento e Controle da Produção) integrado ao
sistema de apontamento de usinagem da empresa. Você tem acesso ao banco de dados de ordens de produção
e pode consultar informações sobre status, setores, interrupções e programação.

Responda sempre em português brasileiro de forma clara e objetiva.
Quando listar ordens, organize os dados em formato legível.
Ao identificar problemas (muitas ordens interrompidas, atrasos, etc.),
aponte isso proativamente ao usuário."""


class AgentProducao:
    """Agent que responde perguntas sobre produção usando ferramentas do banco."""

    def __init__(self, api_key: str = None):
        self.client = anthropic.Anthropic(
            api_key=api_key or os.environ.get("ANTHROPIC_API_KEY")
        )
        self.historico: list[dict] = []

    def perguntar(self, pergunta: str, nova_conversa: bool = False) -> str:
        """
        Envia uma pergunta ao agent e retorna a resposta.

        Args:
            pergunta: Texto da pergunta em linguagem natural.
            nova_conversa: Se True, limpa o histórico e começa uma nova conversa.
        """
        if nova_conversa:
            self.historico = []

        self.historico.append({"role": "user", "content": pergunta})

        # Loop agentico: continua até o modelo parar de chamar ferramentas
        while True:
            resposta = self.client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=self.historico,
            )

            # Adiciona resposta do assistente ao histórico
            self.historico.append({"role": "assistant", "content": resposta.content})

            # Se o modelo terminou (não quer mais usar ferramentas), retorna o texto
            if resposta.stop_reason == "end_turn":
                texto = next(
                    (b.text for b in resposta.content if hasattr(b, "text")), ""
                )
                return texto

            # Processa chamadas de ferramentas
            if resposta.stop_reason == "tool_use":
                resultados_ferramentas = []
                for bloco in resposta.content:
                    if bloco.type == "tool_use":
                        print(f"  [agent] chamando ferramenta: {bloco.name}({bloco.input})")
                        resultado = _executar_ferramenta(bloco.name, bloco.input)
                        resultados_ferramentas.append({
                            "type": "tool_result",
                            "tool_use_id": bloco.id,
                            "content": resultado,
                        })

                # Envia resultados de volta ao model
                self.historico.append({"role": "user", "content": resultados_ferramentas})
            else:
                # stop_reason inesperado
                break

        return "Não foi possível obter uma resposta."


# ---------------------------------------------------------------------------
# Teste rápido via linha de comando
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    agent = AgentProducao()

    perguntas = [
        "Qual é o resumo geral da produção agora?",
        "Tem alguma ordem interrompida na usinagem?",
    ]

    for pergunta in perguntas:
        print(f"\n{'='*60}")
        print(f"Pergunta: {pergunta}")
        print("="*60)
        resposta = agent.perguntar(pergunta)
        print(f"Resposta:\n{resposta}")
