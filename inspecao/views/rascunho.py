"""'Salvar parcial' das inspeções (pintura, montagem): o checklist e as fotos
ficam no servidor (RascunhoInspecao / RascunhoInspecaoFoto) para continuar
de qualquer aparelho. No envio final as fotos viram ArquivoCausa sem novo
upload (mesmo storage/pasta) e o rascunho é apagado."""

import json

from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone

from ..models import (
    ArquivoCausa,
    DadosExecucaoInspecao,
    RascunhoInspecao,
    RascunhoInspecaoFoto,
)


def apagar_arquivos_rascunho(nomes):
    """Remove do storage fotos de rascunho que não serão mais usadas."""
    storage = RascunhoInspecaoFoto._meta.get_field("arquivo").storage
    for nome in nomes:
        try:
            storage.delete(nome)
        except Exception:
            pass


def fotos_rascunho_json(rascunho):
    fotos = []
    for foto in rascunho.fotos.all().order_by("id"):
        try:
            url = foto.arquivo.url
        except Exception:
            url = ""
        fotos.append({"id": foto.id, "chave": foto.chave, "url": url})
    return fotos


def ids_com_rascunho(ids_inspecao):
    """Inspeções (dentre ids_inspecao) com "Salvar parcial" no servidor."""
    return set(
        RascunhoInspecao.objects.filter(inspecao__in=ids_inspecao).values_list("inspecao_id", flat=True)
    )


def anexar_fotos_rascunho(inspecao, causa_nao_conformidade, ids_fotos):
    """Fotos já salvas no rascunho entram na não conformidade reaproveitando
    o arquivo (sem novo upload)."""
    for foto in RascunhoInspecaoFoto.objects.filter(rascunho__inspecao=inspecao, id__in=ids_fotos):
        ArquivoCausa.objects.create(
            causa_nao_conformidade=causa_nao_conformidade,
            arquivo=foto.arquivo.name,
        )


def encerrar_rascunho(inspecao, dados_execucao):
    """Inspeção enviada: o rascunho deixa de valer. Apaga do storage (após o
    commit) só as fotos que não foram para nenhuma não conformidade.
    Chamar dentro do transaction.atomic do envio."""
    usadas = set(
        ArquivoCausa.objects.filter(
            causa_nao_conformidade__dados_execucao=dados_execucao
        ).values_list("arquivo", flat=True)
    )
    fotos_sobrando = [
        f.arquivo.name for f in RascunhoInspecaoFoto.objects.filter(rascunho__inspecao=inspecao)
        if f.arquivo.name not in usadas
    ]
    RascunhoInspecao.objects.filter(inspecao=inspecao).delete()
    transaction.on_commit(lambda: apagar_arquivos_rascunho(fotos_sobrando))


def responder_rascunho(request, inspecao):
    """API do rascunho de uma inspeção:
      GET    -> respostas do checklist + fotos já salvas
      POST   -> grava: "dados" (JSON das respostas), fotos novas em
                "foto__<chave>" e ids em "remover_fotos"
      DELETE -> descarta o rascunho e as fotos dele"""
    if request.method == "GET":
        rascunho = RascunhoInspecao.objects.filter(inspecao=inspecao).select_related("usuario").first()
        if not rascunho:
            return JsonResponse({"existe": False})
        return JsonResponse({
            "existe": True,
            "dados": rascunho.dados,
            "fotos": fotos_rascunho_json(rascunho),
            "usuario": rascunho.usuario.username if rascunho.usuario else None,
            "atualizado_em": timezone.localtime(rascunho.atualizado_em).strftime("%d/%m/%Y %H:%M"),
        })

    if request.method == "POST":
        if DadosExecucaoInspecao.objects.filter(inspecao=inspecao).exists():
            return JsonResponse({"error": "Item já inspecionado."}, status=400)
        try:
            dados = json.loads(request.POST.get("dados") or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"error": "Dados do rascunho inválidos."}, status=400)

        with transaction.atomic():
            rascunho, _ = RascunhoInspecao.objects.update_or_create(
                inspecao=inspecao,
                defaults={
                    "dados": dados,
                    "usuario": request.user if request.user.is_authenticated else None,
                },
            )
            remover = rascunho.fotos.filter(id__in=request.POST.getlist("remover_fotos"))
            arquivos_removidos = [f.arquivo.name for f in remover]
            remover.delete()
            for campo in request.FILES:
                if not campo.startswith("foto__"):
                    continue
                chave = campo[len("foto__"):][:60]
                for arquivo in request.FILES.getlist(campo):
                    RascunhoInspecaoFoto.objects.create(rascunho=rascunho, chave=chave, arquivo=arquivo)
            transaction.on_commit(lambda: apagar_arquivos_rascunho(arquivos_removidos))

        return JsonResponse({"success": True, "fotos": fotos_rascunho_json(rascunho)})

    if request.method == "DELETE":
        rascunho = RascunhoInspecao.objects.filter(inspecao=inspecao).first()
        if rascunho:
            nomes = [f.arquivo.name for f in rascunho.fotos.all()]
            rascunho.delete()
            apagar_arquivos_rascunho(nomes)
        return JsonResponse({"success": True})

    return JsonResponse({"error": "Método não permitido"}, status=405)
