from django.shortcuts import render
from django.http import JsonResponse
from .models import (
    Inspecao,
    DadosExecucaoInspecao,
    Reinspecao,
    Causas,
    CausasNaoConformidade,
    InspecaoEstanqueidade,
    DadosExecucaoInspecaoEstanqueidade,
    ReinspecaoEstanqueidade,
    DetalhesPressaoTanque,
    InfoAdicionaisExecTubosCilindros,
    CausasEstanqueidadeTubosCilindros,
)
from datetime import timezone, datetime, timedelta


def inspecao_montagem(request):
    return render(request, "inspecao_montagem.html")


def inspecao_pintura(request):
    return render(request, "inspecao_pintura.html")


def get_itens_inspecao_pintura(request):

    if request.method == "GET":
        data = Inspecao.objects.filter(pecas_ordem_pintura__isnull=False).order_by("-id")

        dados = []
        for d in data:

            data_ajustada = d.data_inspecao - timedelta(hours=3)

            matricula_nome_operador = None

            if d.pecas_ordem_pintura.operador_fim:
                matricula_nome_operador = f"{d.pecas_ordem_pintura.operador_fim.matricula} - {d.pecas_ordem_pintura.operador_fim.nome}" 
            
            dados.append({
                "data": data_ajustada.strftime("%d/%m/%Y %H:%M:%S"),
                "peca": d.pecas_ordem_pintura.peca,
                "maquina": d.pecas_ordem_pintura.ordem.maquina,
                "cor": d.pecas_ordem_pintura.ordem.cor,
                "tipo": d.pecas_ordem_pintura.tipo,
                "operador": matricula_nome_operador
            })
        
        print({"dados":dados})

        return JsonResponse({"dados":dados}, status=200)
    else:
        return JsonResponse({"error":"Método não permitido"}, status=405)

def inspecao_estamparia(request):
    return render(request, "inspecao_estamparia.html")


def inspecao_tanque(request):
    return render(request, "inspecao_tanque.html")


def inspecao_tubos_cilindros(request):
    return render(request, "inspecao_tubos_cilindros.html")


def reteste_estanqueidade_tubos_cilindros(request):
    return
