from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse, Http404
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.views.decorators.http import require_GET

from .forms import UploadCSVForm
from .models import Pecas, Setor, Maquina, Operador, Mp, MotivoExclusao, MotivoInterrupcao, MotivoMaquinaParada
from . import views

import csv
import json

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

def operadores(request):

    return render(request,'operadores/operadores.html')

def api_operadores(request):
    operadores = (
        Operador.objects
        .select_related('setor')  # Carrega setor junto
        # .prefetch_related('maquinas')  # Caso vá usar as máquinas
        .values('id', 'matricula', 'nome', 'setor__nome','status','setor')  # Retorna só os campos necessários
    )

    operadores_data = [
        {
            'id': operador['id'],
            'matricula': operador['matricula'],
            'nome': operador['nome'],
            'setor': operador['setor__nome'],
            'setor_id': operador['setor'],
            # 'maquinas': [maquina.nome for maquina in operador.maquinas.all()],
            'status': operador['status']
        } for operador in operadores
    ]

    return JsonResponse({'operadores':operadores_data})

def add_operador(request):
    
    if request.method == 'POST':
        try:
            dados = json.loads(request.body)

            nome = dados['nome']
            matricula = dados['matricula']
            setor_id = dados['setor']

            operador = Operador.objects.create(
                nome=nome,
                matricula=matricula,
                setor_id=setor_id,
            )

            return JsonResponse({'message': 'Operador criado com sucesso'}, status=201)

        except json.JSONDecodeError:
            return JsonResponse({'error': 'JSON inválido'}, status=400)
        except KeyError as e:
            return JsonResponse({'error': f'Campo ausente: {str(e)}'}, status=400)
        except ValidationError as e:
                return JsonResponse({'error': str(e)}, status=400)
        except IntegrityError:
            return JsonResponse({'error': 'Matrícula já cadastrada para este setor'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    else:
        return JsonResponse({'error': 'Método não permitido'}, status=405)

def edit_operador(request,pk):

    try:
        operador = get_object_or_404(Operador, pk=pk)

        if request.method == 'PUT':
            try:
                dados = json.loads(request.body)

                if operador.matricula != dados['matricula']:
                    operador.matricula = dados['matricula']
                if operador.nome != dados['nome']:
                    operador.nome = dados['nome']
                if operador.setor != dados['setor']:
                    operador.setor_id = dados['setor']
                operador.save()

                return JsonResponse({'message': 'Ok'}, status=200)

            except json.JSONDecodeError:
                return JsonResponse({'error': 'JSON inválido'}, status=400)
            except KeyError as e:
                return JsonResponse({'error': f'Campo ausente: {str(e)}'}, status=400)
            except ValidationError as e:
                return JsonResponse({'error': str(e)}, status=400)
            except IntegrityError:
                return JsonResponse({'error': 'Matrícula já cadastrada para este setor'}, status=400)
            except Exception as e:
                return JsonResponse({'error': str(e)}, status=500)
        elif request.method == 'PATCH':
            try:          
                if operador.status != 'inativo':
                    operador.status = 'inativo'
                    operador.save()

                return JsonResponse({'message': 'Ok'}, status=200)
            except json.JSONDecodeError:
                return JsonResponse({'error': 'JSON inválido'}, status=400)
            except KeyError as e:
                return JsonResponse({'error': f'Campo ausente: {str(e)}'}, status=400)
            except (ValidationError, IntegrityError) as e:
                return JsonResponse({'error': str(e)}, status=400)
            except Exception as e:
                return JsonResponse({'error': str(e)}, status=500)

    except Http404:
        return JsonResponse({'error': 'Operador não encontrado'}, status=404)

def api_setores(request):
    setores = Setor.objects.all().values()

    setores_data = [{'id': setor['id'], 'nome': setor['nome']} for setor in setores]

    return JsonResponse({'setores': setores_data})