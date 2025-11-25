from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.conf import settings

from .models import Notificacao
from .utils import notificar_erro_requisicoes_se_acima_limite, notificar_erro_transferencias_se_acima_limite
from solicitacao_almox.models import SolicitacaoRequisicao, SolicitacaoTransferencia

import json
from datetime import timedelta as dt_timedelta

@csrf_exempt
@require_POST
def rpa_update_status(request):
    # Segurança via X-API-KEY
    api_key = (request.headers.get("X-API-KEY") or "").strip()
    if not api_key or api_key != (settings.RPA_API_KEY or "").strip():
        return HttpResponseForbidden("Chave de API inválida.")

    # Dados
    try:
        data = json.loads(request.body)
        requisicao_id = data["id"]
        status = data["status"]
        tipo_requisicao = data.get("tipo_requisicao")
    except Exception:
        return JsonResponse({"error": "Dados inválidos."}, status=400)

    # Lógica de negócio
    try:
        requisicao = SolicitacaoRequisicao.objects.get(id=requisicao_id)
        requisicao.rpa = status
        if status and ("Regra Contábil" in status):
            requisicao.classe_requisicao_id = 3 if tipo_requisicao == "Req p Consumo" else 4
        requisicao.save()

        # Dispara alerta SOMENTE se a contagem de erros ultrapassar o limite
        notificar_erro_requisicoes_se_acima_limite()

        return JsonResponse({"success": True})
    except SolicitacaoRequisicao.DoesNotExist:
        return JsonResponse({"error": "Requisição não encontrada."}, status=404)
    except Exception as e:
        return JsonResponse({"error": f"Erro interno: {str(e)}"}, status=500)

@csrf_exempt
@require_POST
def rpa_update_transfer(request):
    # Segurança via X-API-KEY
    api_key = (request.headers.get("X-API-KEY") or "").strip()
    if not api_key or api_key != (settings.RPA_API_KEY or "").strip():
        return HttpResponseForbidden("Chave de API inválida.")

    # Dados
    try:
        data = json.loads(request.body)
        transferencia_id = data["id"]
        status = data["status"]
        # extras opcionais
        dep_destino = data.get("dep_destino")
        rec = data.get("rec")
        qtd = data.get("qtd")
        observacao = data.get("observacao")
    except Exception:
        return JsonResponse({"error": "Dados inválidos."}, status=400)

    # Lógica de negócio
    try:
        transf = SolicitacaoTransferencia.objects.get(id=transferencia_id)
        transf.rpa = status
        transf.save()

        # Dispara alerta SOMENTE se a contagem de erros ultrapassar o limite
        notificar_erro_transferencias_se_acima_limite()

        return JsonResponse({"success": True})
    except SolicitacaoTransferencia.DoesNotExist:
        return JsonResponse({"error": "Transferência não encontrada."}, status=404)
    except Exception as e:
        return JsonResponse({"error": f"Erro interno: {str(e)}"}, status=500)