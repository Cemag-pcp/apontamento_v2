"""
Exemplo de como usar o AgentProducao em uma view Django.

Adicione ao urls.py:
    path('pcp/agent/', views_agent.chat_agent, name='chat_agent'),

Adicione a view ao seu views.py (ou crie um views_agent.py).
"""

# ---- views_agent.py --------------------------------------------------------

from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
import json

from automacoes.agent_producao import AgentProducao

# Mantém um agent por sessão do usuário (em memória; use cache/Redis para produção)
_agents: dict[str, AgentProducao] = {}


@login_required
@require_POST
def chat_agent(request):
    """
    Endpoint JSON para conversar com o agent de produção.

    POST /pcp/agent/
    Body: {"mensagem": "Quantas ordens estão em andamento?", "nova_conversa": false}

    Response: {"resposta": "..."}
    """
    dados = json.loads(request.body)
    mensagem = dados.get("mensagem", "").strip()
    nova_conversa = dados.get("nova_conversa", False)

    if not mensagem:
        return JsonResponse({"erro": "Mensagem não pode ser vazia."}, status=400)

    # Recupera ou cria agent para este usuário
    user_key = str(request.user.id)
    if nova_conversa or user_key not in _agents:
        _agents[user_key] = AgentProducao()

    agent = _agents[user_key]
    resposta = agent.perguntar(mensagem, nova_conversa=nova_conversa)

    return JsonResponse({"resposta": resposta})


# ---- Exemplo de Management Command -----------------------------------------
# Salve como: core/management/commands/agent_cli.py

MANAGEMENT_COMMAND_EXEMPLO = '''
from django.core.management.base import BaseCommand
from automacoes.agent_producao import AgentProducao

class Command(BaseCommand):
    help = "Conversa interativa com o agent de produção"

    def handle(self, *args, **options):
        agent = AgentProducao()
        self.stdout.write("Agent de Produção iniciado. Digite 'sair' para encerrar.\\n")

        while True:
            pergunta = input("Você: ").strip()
            if pergunta.lower() in ("sair", "exit", "quit"):
                break
            if not pergunta:
                continue
            resposta = agent.perguntar(pergunta)
            self.stdout.write(f"Agent: {resposta}\\n")
'''
