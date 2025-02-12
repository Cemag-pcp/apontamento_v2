from django.shortcuts import render, redirect
from django.contrib import messages

from .forms import UploadCSVForm
from .models import Pecas, Setor, Maquina, Operador, Mp, MotivoExclusao, MotivoInterrupcao, MotivoMaquinaParada
from . import views

import csv

def crud(request):

    return render(request, "crud/crud.html")
