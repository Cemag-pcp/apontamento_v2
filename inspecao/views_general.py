from django.http import JsonResponse
from django.db import transaction
from .models import (
    DadosExecucaoInspecao,
    Reinspecao,
    Causas,
)

def motivos_causas(request, setor):

    motivos = Causas.objects.filter(setor=setor)

    return JsonResponse({"motivos": list(motivos.values())})


def delete_execution(request):

    if request.method != "DELETE":
        return JsonResponse({"error": "Método não permitido"}, status=405)

    try:
        with transaction.atomic():
            id_execucao = request.GET.get("idDadosExecucao")
            id_inspecao = request.GET.get("idInspecao")
            primeira_execucao = request.GET.get("primeiraExecucao")

            execucao = DadosExecucaoInspecao.objects.get(pk=id_execucao)
            reinspecao = Reinspecao.objects.filter(inspecao=id_inspecao).first()

            execucao.delete()

            if primeira_execucao == "true" and reinspecao:
                reinspecao.delete()
            elif reinspecao:
                reinspecao.reinspecionado = False
                reinspecao.save()

        return JsonResponse(
            {"success": True, "message": "Execução deletada com sucesso"}
        )

    except DadosExecucaoInspecao.DoesNotExist:
        return JsonResponse({"error": "Execução não encontrada"}, status=404)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def delete_execution_estanqueidade(request):

    if request.method != "DELETE":
        return JsonResponse({"error": "Método não permitido"}, status=405)

    try:
        with transaction.atomic():
            id_execucao = request.GET.get("idDadosExecucao")
            id_inspecao = request.GET.get("idInspecao")
            primeira_execucao = request.GET.get("primeiraExecucao")

            execucao = DadosExecucaoInspecao.objects.get(pk=id_execucao)
            reinspecao = Reinspecao.objects.filter(inspecao=id_inspecao).first()

            execucao.delete()

            if primeira_execucao == "true" and reinspecao:
                reinspecao.delete()
            elif reinspecao:
                reinspecao.reinspecionado = False
                reinspecao.save()

        return JsonResponse(
            {"success": True, "message": "Execução deletada com sucesso"}
        )

    except DadosExecucaoInspecao.DoesNotExist:
        return JsonResponse({"error": "Execução não encontrada"}, status=404)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
