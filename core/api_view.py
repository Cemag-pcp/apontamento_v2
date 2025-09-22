from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import json
from datetime import timedelta as dt_timedelta
from .models import Notificacao
from .utils import notificacao_almoxarifado
from solicitacao_almox.models import SolicitacaoRequisicao, SolicitacaoTransferencia
from django.conf import settings

@csrf_exempt
@require_POST
def rpa_update_status(request):
    # 1. Segurança
    api_key = request.headers.get("X-API-KEY")
    print(api_key)
    print(settings.RPA_API_KEY)
    if not api_key or api_key != settings.RPA_API_KEY:
        return HttpResponseForbidden("Chave de API inválida.")

    # 2. Receber dados
    try:
        data = json.loads(request.body)
        requisicao_id = data["id"]
        status = data["status"]
        tipo_requisicao = data.get("tipo_requisicao") # .get() para ser opcional
    except (json.JSONDecodeError, KeyError):
        return JsonResponse({"error": "Dados inválidos."}, status=400)

    # 3. Lógica de Negócio com o ORM
    try:
        requisicao = SolicitacaoRequisicao.objects.get(id=requisicao_id)
        
        # Atualiza a requisição
        requisicao.rpa = status
        if "Regra Contábil" in status:
            requisicao.classe_requisicao_id = 3 if tipo_requisicao == 'Req p Consumo' else 4
        requisicao.save() # O ORM salva no banco

        notificacao_almoxarifado(
            titulo=f"Requisição #{requisicao.id} Processada",
            mensagem=f"Status do RPA: '{status}'",
            rota_acesso="/almox/solicitacoes-page/",
            tipo="info",
            chave="alerta_requisicoes_pendentes_almox",
        )
        return JsonResponse({"success": True})
    except SolicitacaoRequisicao.DoesNotExist:
        return JsonResponse({"error": "Requisição não encontrada."}, status=404)
    except Exception as e:
        return JsonResponse({"error": f"Erro interno: {str(e)}"}, status=500)

@csrf_exempt
@require_POST
def rpa_update_transfer(request):
    # Autorização simples via X-API-KEY (ideal: usar variável de ambiente em produção)
    api_key = request.headers.get("X-API-KEY")
    if not api_key or api_key != settings.RPA_API_KEY:
        return HttpResponseForbidden("Chave de API inválida.")

    try:
        data = json.loads(request.body)
        transferencia_id = data["id"]
        status = data["status"]

        # Campos extras opcionais (podem ajudar a compor a notificação)
        dep_destino = data.get("dep_destino")
        rec = data.get("rec")
        qtd = data.get("qtd")
        observacao = data.get("observacao")

    except (json.JSONDecodeError, KeyError):
        return JsonResponse({"error": "Dados inválidos."}, status=400)

    try:
        transf = SolicitacaoTransferencia.objects.get(id=transferencia_id)

        # Atualiza o status RPA (como você fazia via SQL)
        transf.rpa = status
        transf.save()

        # Opcional: cria uma notificação para o dono/solicitante da transferência
        # Ajuste 'profile' conforme o seu modelo (ex: transf.profile ou transf.solicitante.profile)
        try:
            titulo = f"Transferência #{transf.id} processada"
            msg_partes = [f"Status: {status}"]
            if dep_destino:
                msg_partes.append(f"Destino: {dep_destino}")
            if rec:
                msg_partes.append(f"Recurso: {rec}")
            if qtd:
                msg_partes.append(f"Qtd: {qtd}")
            if observacao:
                msg_partes.append(f"Obs: {observacao}")
            mensagem = " | ".join(msg_partes)

            notificacao_almoxarifado(
                titulo=titulo,
                mensagem=mensagem,
                rota_acesso="/almox/solicitacoes-page/",
                tipo="info",
                chave="alerta_transferencias_pendentes_almox",
            )
        except Exception:
            # Evita derrubar a API se a notificação falhar
            pass

        return JsonResponse({"success": True})
    except SolicitacaoTransferencia.DoesNotExist:
        return JsonResponse({"error": "Transferência não encontrada."}, status=404)
    except Exception as e:
        return JsonResponse({"error": f"Erro interno: {str(e)}"}, status=500)