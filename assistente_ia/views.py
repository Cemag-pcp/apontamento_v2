import json
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import MensagemChatAssistente
from .services import agente_producao_chat

LIMITE_MENSAGENS_POR_HORA = 30


@login_required
@require_POST
def chat(request):
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON inválido."}, status=400)

    mensagem = str(payload.get("mensagem") or "").strip()
    sessao_id = str(payload.get("sessao_id") or "").strip()

    if not mensagem:
        return JsonResponse({"error": "Informe uma mensagem."}, status=400)
    if not sessao_id:
        return JsonResponse({"error": "Sessão de chat inválida."}, status=400)

    uma_hora_atras = timezone.now() - timedelta(hours=1)
    total_recente = MensagemChatAssistente.objects.filter(
        usuario=request.user, role="user", criada_em__gte=uma_hora_atras
    ).count()
    if total_recente >= LIMITE_MENSAGENS_POR_HORA:
        return JsonResponse(
            {"error": "Limite de mensagens por hora atingido. Tente novamente mais tarde."},
            status=429,
        )

    historico_anterior = list(
        MensagemChatAssistente.objects.filter(usuario=request.user, sessao_id=sessao_id)
    )

    MensagemChatAssistente.objects.create(
        usuario=request.user, sessao_id=sessao_id, role="user", conteudo=mensagem,
    )

    try:
        resposta = agente_producao_chat.perguntar(mensagem, historico_anterior)
    except RuntimeError as exc:
        return JsonResponse({"error": str(exc)}, status=502)
    except Exception as exc:
        return JsonResponse({"error": f"Erro ao consultar o assistente: {exc}"}, status=500)

    MensagemChatAssistente.objects.create(
        usuario=request.user, sessao_id=sessao_id, role="assistant", conteudo=resposta,
    )

    return JsonResponse({"resposta": resposta, "sessao_id": sessao_id})


@login_required
def historico(request):
    sessao_id = str(request.GET.get("sessao_id") or "").strip()
    if not sessao_id:
        return JsonResponse({"error": "Informe sessao_id."}, status=400)

    mensagens = list(
        MensagemChatAssistente.objects.filter(
            usuario=request.user, sessao_id=sessao_id
        ).values("role", "conteudo")
    )
    return JsonResponse({"mensagens": mensagens})
