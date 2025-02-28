from django.shortcuts import render
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


def inspecao_montagem(request):
    return render(request, "inspecao_montagem.html")


def inspecao_pintura(request):
    return render(request, "inspecao_pintura.html")


def inspecao_estamparia(request):
    return render(request, "inspecao_estamparia.html")


def inspecao_tanque(request):
    return render(request, "inspecao_tanque.html")


def inspecao_tubos_cilindros(request):
    return render(request, "inspecao_tubos_cilindros.html")


def reteste_estanqueidade_tubos_cilindros(request):
    return
