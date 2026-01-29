from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse, Http404
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.views.decorators.http import require_GET
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Prefetch, Count, Q
from django.views.decorators.csrf import csrf_exempt

from .forms import UploadCSVForm
from .models import Pecas, Setor, Maquina, Operador, Mp, MotivoExclusao, MotivoInterrupcao, MotivoMaquinaParada, Conjuntos, Carretas
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

@login_required
def cadastro_pecas(request):
    setor_estamparia = Setor.objects.filter(nome__iexact='estamparia').first()
    return render(
        request,
        'cadastro_pecas.html',
        {'default_setor_id': setor_estamparia.id if setor_estamparia else ''}
    )

@csrf_exempt
@login_required
def cadastro_pecas_api(request):
    
    """
    GET: lista pecas paginadas (com filtro opcional por setor).
    POST: cria nova peca.
    PATCH: atualiza peca.
    DELETE: remove peca.
    """

    def parse_float(value, field):
        if value in (None, ''):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            raise ValueError(f'{field} invalido.')

    def parse_fk(model, value, field):
        if value in (None, ''):
            return None
        try:
            return model.objects.get(pk=int(value))
        except (TypeError, ValueError, model.DoesNotExist):
            raise ValueError(f'{field} invalido.')

    def parse_setores(value):
        if value in (None, ''):
            return []
        if isinstance(value, list):
            ids = value
        elif isinstance(value, str):
            ids = [item for item in value.split(',') if item]
        else:
            raise ValueError('setores invalidos.')
        try:
            ids = [int(item) for item in ids]
        except (TypeError, ValueError):
            raise ValueError('setores invalidos.')
        if not ids:
            return []
        setores = list(Setor.objects.filter(id__in=ids))
        if len(setores) != len(set(ids)):
            raise ValueError('setores invalidos.')
        return setores

    if request.method == 'GET':
        page_number = request.GET.get('page', 1)
        page_size = request.GET.get('page_size', 50)
        
        try:
            page_number = int(page_number)
            page_size = int(page_size)
        except ValueError:
            return JsonResponse({'error': 'Parametros de paginacao invalidos.'}, status=400)

        queryset = Pecas.objects.all().order_by('codigo')

        search_param = request.GET.get('search')
        setor_param = request.GET.get('setor')
        
        if search_param:
            queryset = queryset.filter(
                Q(codigo__icontains=search_param) |
                Q(descricao__icontains=search_param) |
                Q(apelido__icontains=search_param)
            )
        
        if setor_param:
            try:
                setores_filtro = parse_setores(setor_param)
            except ValueError as exc:
                return JsonResponse({'error': str(exc)}, status=400)
            if setores_filtro:
                queryset = queryset.filter(setor__in=setores_filtro).distinct()

        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(page_number)

        pecas = []
        for peca in page_obj.object_list:
            conjunto_display = None
            if peca.conjunto:
                conjunto_display = f"{peca.conjunto.codigo} - {peca.conjunto.descricao}" if peca.conjunto.descricao else peca.conjunto.codigo

            pecas.append({
                'id': peca.id,
                'codigo': peca.codigo,
                'descricao': peca.descricao,
                'materia_prima': peca.materia_prima,
                'comprimento': peca.comprimento,
                'apelido': peca.apelido,
                'conjunto_id': peca.conjunto_id,
                'conjunto_display': conjunto_display,
                'processo_1_id': peca.processo_1_id,
                'processo_1_nome': peca.processo_1.nome if peca.processo_1 else None,
                'setor_ids': list(peca.setor.values_list('id', flat=True)),
                'setor_nomes': list(peca.setor.values_list('nome', flat=True)),
            })

        conjuntos = [
            {
                'id': conjunto.id,
                'label': f"{conjunto.codigo} - {conjunto.descricao}" if conjunto.descricao else conjunto.codigo
            }
            for conjunto in Conjuntos.objects.all().order_by('codigo')
        ]
        maquinas = [
            {'id': maquina.id, 'label': maquina.nome}
            for maquina in Maquina.objects.all().order_by('nome')
        ]
        setores = [
            {'id': setor.id, 'label': setor.nome}
            for setor in Setor.objects.all().order_by('nome')
        ]

        return JsonResponse({
            'results': pecas,
            'page': page_obj.number,
            'page_size': page_obj.paginator.per_page,
            'total_pages': paginator.num_pages,
            'total_items': paginator.count,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
            'meta': {
                'conjuntos': conjuntos,
                'maquinas': maquinas,
                'setores': setores,
            }
        })

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'JSON invalido.'}, status=400)

        codigo = (data.get('codigo') or '').strip()
        if not codigo:
            return JsonResponse({'error': 'Codigo e obrigatorio.'}, status=400)

        try:
            conjunto = parse_fk(Conjuntos, data.get('conjunto_id'), 'conjunto')
            processo_1 = parse_fk(Maquina, data.get('processo_1_id'), 'processo_1')
            comprimento = parse_float(data.get('comprimento'), 'comprimento')
            setores = parse_setores(data.get('setor_ids'))
        except ValueError as exc:
            return JsonResponse({'error': str(exc)}, status=400)

        if not setores:
            return JsonResponse({'error': 'Selecione ao menos um setor.'}, status=400)

        try:
            peca = Pecas.objects.create(
                codigo=codigo,
                descricao=(data.get('descricao') or '').strip() or None,
                materia_prima=(data.get('materia_prima') or '').strip() or None,
                comprimento=comprimento,
                apelido=(data.get('apelido') or '').strip() or None,
                conjunto=conjunto,
                processo_1=processo_1,
            )
            peca.setor.set(setores)
        except IntegrityError as e:
            print(e)
            return JsonResponse({'error': 'Codigo ja cadastrado.'}, status=400)

        return JsonResponse({'success': 'Peca criada com sucesso.', 'id': peca.id}, status=201)

    if request.method == 'PATCH':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'JSON invalido.'}, status=400)

        peca_id = data.get('id')
        if not peca_id:
            return JsonResponse({'error': 'ID da peca nao informado.'}, status=400)

        peca = get_object_or_404(Pecas, id=peca_id)

        try:
            conjunto = parse_fk(Conjuntos, data.get('conjunto_id'), 'conjunto')
            processo_1 = parse_fk(Maquina, data.get('processo_1_id'), 'processo_1')
            comprimento = parse_float(data.get('comprimento'), 'comprimento')
            setores = parse_setores(data.get('setor_ids'))
        except ValueError as exc:
            return JsonResponse({'error': str(exc)}, status=400)

        fields = {
            'codigo': (data.get('codigo') or '').strip(),
            'descricao': (data.get('descricao') or '').strip() or None,
            'materia_prima': (data.get('materia_prima') or '').strip() or None,
            'comprimento': comprimento,
            'apelido': (data.get('apelido') or '').strip() or None,
            'conjunto': conjunto,
            'processo_1': processo_1,
        }

        if not fields['codigo']:
            return JsonResponse({'error': 'Codigo e obrigatorio.'}, status=400)

        for campo, valor in fields.items():
            setattr(peca, campo, valor)

        try:
            peca.save()
            if setores:
                peca.setor.set(setores)
        except IntegrityError:
            return JsonResponse({'error': 'Codigo ja cadastrado.'}, status=400)

        return JsonResponse({'success': 'Peca atualizada com sucesso.'})

    if request.method == 'DELETE':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'JSON invalido.'}, status=400)

        peca_id = data.get('id')
        if not peca_id:
            return JsonResponse({'error': 'ID da peca nao informado.'}, status=400)

        peca = get_object_or_404(Pecas, id=peca_id)
        peca.delete()

        return JsonResponse({'success': 'Peca removida com sucesso.'})

    return JsonResponse({'error': 'Metodo nao permitido.'}, status=405)

@login_required
def cadastro_conjuntos(request):
    return render(request, 'cadastro_conjuntos.html')

@csrf_exempt
@login_required
def cadastro_conjuntos_api(request):
    """
    GET: lista conjuntos paginados (com filtro opcional por carreta).
    POST: cria novo conjunto.
    PATCH: atualiza conjunto.
    DELETE: remove conjunto.
    """

    def parse_int(value, field):
        if value in (None, ''):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            raise ValueError(f'{field} invalido.')

    def parse_carretas(value):
        if value in (None, ''):
            return []
        if isinstance(value, list):
            ids = value
        elif isinstance(value, str):
            ids = [item for item in value.split(',') if item]
        else:
            raise ValueError('carretas invalidas.')
        try:
            ids = [int(item) for item in ids]
        except (TypeError, ValueError):
            raise ValueError('carretas invalidas.')
        if not ids:
            return []
        carretas = list(Carretas.objects.filter(id__in=ids))
        if len(carretas) != len(set(ids)):
            raise ValueError('carretas invalidas.')
        return carretas

    if request.method == 'GET':
        page_number = request.GET.get('page', 1)
        page_size = request.GET.get('page_size', 50)

        try:
            page_number = int(page_number)
            page_size = int(page_size)
        except ValueError:
            return JsonResponse({'error': 'Parametros de paginacao invalidos.'}, status=400)

        queryset = Conjuntos.objects.prefetch_related('carreta').order_by('codigo')

        search_param = request.GET.get('search')
        carreta_param = request.GET.get('carreta')

        if search_param:
            queryset = queryset.filter(
                Q(codigo__icontains=search_param) |
                Q(descricao__icontains=search_param)
            )

        if carreta_param:
            try:
                carretas_filtro = parse_carretas(carreta_param)
            except ValueError as exc:
                return JsonResponse({'error': str(exc)}, status=400)
            if carretas_filtro:
                queryset = queryset.filter(carreta__in=carretas_filtro).distinct()

        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(page_number)

        conjuntos = []
        for conjunto in page_obj.object_list:
            carretas = list(conjunto.carreta.all().order_by('codigo'))
            conjuntos.append({
                'id': conjunto.id,
                'codigo': conjunto.codigo,
                'descricao': conjunto.descricao,
                'quantidade': conjunto.quantidade,
                'carreta_ids': [carreta.id for carreta in carretas],
                'carreta_labels': [
                    f"{carreta.codigo} - {carreta.descricao}" if carreta.descricao else carreta.codigo
                    for carreta in carretas
                ],
            })

        carretas_meta = [
            {
                'id': carreta.id,
                'label': f"{carreta.codigo} - {carreta.descricao}" if carreta.descricao else carreta.codigo
            }
            for carreta in Carretas.objects.all().order_by('codigo')
        ]

        return JsonResponse({
            'results': conjuntos,
            'page': page_obj.number,
            'page_size': page_obj.paginator.per_page,
            'total_pages': paginator.num_pages,
            'total_items': paginator.count,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
            'meta': {
                'carretas': carretas_meta,
            }
        })

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'JSON invalido.'}, status=400)

        codigo = (data.get('codigo') or '').strip()
        if not codigo:
            return JsonResponse({'error': 'Codigo e obrigatorio.'}, status=400)

        try:
            quantidade = parse_int(data.get('quantidade'), 'quantidade')
            carretas = parse_carretas(data.get('carreta_ids'))
        except ValueError as exc:
            return JsonResponse({'error': str(exc)}, status=400)

        if quantidade is None:
            return JsonResponse({'error': 'Quantidade e obrigatoria.'}, status=400)

        try:
            conjunto = Conjuntos.objects.create(
                codigo=codigo,
                descricao=(data.get('descricao') or '').strip() or None,
                quantidade=quantidade,
            )
            if carretas:
                conjunto.carreta.set(carretas)
        except IntegrityError:
            return JsonResponse({'error': 'Nao foi possivel criar o conjunto.'}, status=400)

        return JsonResponse({'success': 'Conjunto criado com sucesso.', 'id': conjunto.id}, status=201)

    if request.method == 'PATCH':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'JSON invalido.'}, status=400)

        conjunto_id = data.get('id')
        if not conjunto_id:
            return JsonResponse({'error': 'ID do conjunto nao informado.'}, status=400)

        conjunto = get_object_or_404(Conjuntos, id=conjunto_id)

        try:
            quantidade = parse_int(data.get('quantidade'), 'quantidade')
            carretas = parse_carretas(data.get('carreta_ids'))
        except ValueError as exc:
            return JsonResponse({'error': str(exc)}, status=400)

        codigo = (data.get('codigo') or '').strip()
        if not codigo:
            return JsonResponse({'error': 'Codigo e obrigatorio.'}, status=400)

        if quantidade is None:
            return JsonResponse({'error': 'Quantidade e obrigatoria.'}, status=400)

        conjunto.codigo = codigo
        conjunto.descricao = (data.get('descricao') or '').strip() or None
        conjunto.quantidade = quantidade

        try:
            conjunto.save()
            conjunto.carreta.set(carretas)
        except IntegrityError:
            return JsonResponse({'error': 'Nao foi possivel salvar o conjunto.'}, status=400)

        return JsonResponse({'success': 'Conjunto atualizado com sucesso.'})

    if request.method == 'DELETE':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'JSON invalido.'}, status=400)

        conjunto_id = data.get('id')
        if not conjunto_id:
            return JsonResponse({'error': 'ID do conjunto nao informado.'}, status=400)

        conjunto = get_object_or_404(Conjuntos, id=conjunto_id)
        conjunto.delete()

        return JsonResponse({'success': 'Conjunto removido com sucesso.'})

    return JsonResponse({'error': 'Metodo nao permitido.'}, status=405)
