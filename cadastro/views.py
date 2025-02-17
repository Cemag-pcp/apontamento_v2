from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .forms import UploadCSVForm
from .models import Pecas, Setor, Maquina, Operador, Mp, MotivoExclusao, MotivoInterrupcao, MotivoMaquinaParada
from . import views

import csv

def crud(request):

    return render(request, "crud/crud.html")

@require_GET
def buscar_maquinas(request):

    setor = request.GET.get('setor','')

    # Busca máquinas relacionadas a esse setor
    setor_obj = get_object_or_404(Setor, nome=setor)

    maquina_object = Maquina.objects.filter(setor=setor_obj, tipo='maquina')

    maquinas = [{'id':maquina.id, 'nome': maquina.nome} for maquina in maquina_object]

    return JsonResponse({'maquinas': maquinas})

@require_GET
def buscar_processos(request):
    setor = request.GET.get('setor', '')

    # Busca máquinas relacionadas a esse setor
    setor_obj = get_object_or_404(Setor, nome=setor)

    processo_object = Maquina.objects.filter(setor=setor_obj, tipo='processo')

    processos = [{'id': processo.id, 'nome': processo.nome} for processo in processo_object]

    return JsonResponse({'processos': processos})
