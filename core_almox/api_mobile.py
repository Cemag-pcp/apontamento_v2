"""API do almoxarifado pro app mobile (mesmo login/token da expedição).

Entrega pelo app: o almoxarife bipa a etiqueta da prateleira (código do item),
confere/ajusta a quantidade e confirma. A regra de entrega é a mesma da tela
web (core_almox.views.entregar_solicitacao).
"""
from django.db.models import F
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from cadastro_almox.models import OperadorAlmox
from solicitacao_almox.models import SolicitacaoRequisicao, SolicitacaoTransferencia

from .views import _cor_texto_contraste, entregar_solicitacao

MODELOS = {
    "requisicao": SolicitacaoRequisicao,
    "transferencia": SolicitacaoTransferencia,
}


def _modelo(tipo):
    modelo = MODELOS.get(tipo)
    if not modelo:
        return None
    return modelo


def _serializar(sol, tipo):
    status = sol.status
    destino = str(sol.cc) if tipo == "requisicao" and sol.cc else (
        str(sol.deposito_destino) if tipo == "transferencia" and sol.deposito_destino else ""
    )
    return {
        "id": sol.id,
        "tipo": tipo,
        "funcionario": f"{sol.funcionario.matricula} - {sol.funcionario.nome}",
        "item_codigo": sol.item.codigo,
        "item_nome": sol.item.nome,
        "unidade": sol.item.unidade or "",
        "quantidade": sol.quantidade,
        "destino": destino,
        "classe_requisicao": str(sol.classe_requisicao) if tipo == "requisicao" else "",
        "obs": sol.obs or "",
        "prioridade": status.prioridade if status else "",
        "prioridade_cor": status.cor if status else "#6c757d",
        "prioridade_cor_texto": _cor_texto_contraste(status.cor) if status else "#ffffff",
        "data_solicitacao": sol.data_solicitacao.isoformat(),
        "rpa": getattr(sol, "rpa", None) or "",
    }


class SolicitacoesPendentesView(APIView):
    """Solicitações ainda não entregues, mais urgentes primeiro."""

    def get(self, request):
        tipo = request.query_params.get("tipo", "requisicao")
        modelo = _modelo(tipo)
        if not modelo:
            return Response({"erro": "Tipo inválido."}, status=400)

        relacionados = ["funcionario", "item", "status"]
        relacionados += ["cc", "classe_requisicao"] if tipo == "requisicao" else ["deposito_destino"]
        qs = (
            modelo.objects.filter(entregue_por=None)
            .select_related(*relacionados)
            .order_by(F("status__minutos_limite").asc(nulls_last=True), "data_solicitacao")
        )
        return Response([_serializar(s, tipo) for s in qs])


class OperadoresView(APIView):
    def get(self, request):
        operadores = OperadorAlmox.objects.filter(status=True).order_by("nome")
        return Response([{"matricula": o.matricula, "nome": o.nome} for o in operadores])


class EntregarSolicitacaoView(APIView):
    def post(self, request, tipo, solicitacao_id):
        modelo = _modelo(tipo)
        if not modelo:
            return Response({"erro": "Tipo inválido."}, status=400)
        solicitacao = get_object_or_404(modelo.objects.select_related("item"), pk=solicitacao_id)

        if solicitacao.entregue_por_id:
            return Response({"erro": "Esta solicitação já foi entregue."}, status=409)

        # a etiqueta bipada tem que ser do item da solicitação
        codigo_lido = str(request.data.get("codigo_lido") or "").strip()
        if codigo_lido.upper() != solicitacao.item.codigo.strip().upper():
            return Response(
                {"erro": f"Item bipado ({codigo_lido or 'nenhum'}) não é o da solicitação ({solicitacao.item.codigo})."},
                status=400,
            )

        try:
            quantidade = float(request.data.get("quantidade"))
        except (TypeError, ValueError):
            return Response({"erro": "Quantidade inválida."}, status=400)
        if quantidade <= 0:
            return Response({"erro": "A quantidade entregue deve ser maior que zero."}, status=400)

        operador = OperadorAlmox.objects.filter(matricula=request.data.get("matricula"), status=True).first()
        if not operador:
            return Response({"erro": "Selecione o operador que está entregando."}, status=400)

        status_http, mensagem = entregar_solicitacao(
            solicitacao, tipo, operador, timezone.now(), quantidade_entregue=quantidade
        )
        if status_http != 200:
            return Response({"erro": mensagem}, status=status_http)
        return Response({"status": "Sucesso", "id": solicitacao.id, "quantidade_entregue": quantidade})
