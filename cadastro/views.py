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
from .models import Pecas, Setor, Maquina, Operador, Mp, MotivoExclusao, MotivoInterrupcao, MotivoMaquinaParada, Conjuntos, Carretas, ItensExplodidos, CarretasExplodidas, EspessuraChapa
from . import views

import csv
import json
from decimal import Decimal, InvalidOperation

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
def maquinas(request):
    return render(request, 'maquinas/maquinas.html')

@csrf_exempt
@login_required
def api_maquinas(request):
    if request.method == 'GET':
        page_number = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 20))
        search = (request.GET.get('search') or '').strip()
        setor_param = request.GET.get('setor', '').strip()
        tipo_param = request.GET.get('tipo', '').strip()
        ativo_param = request.GET.get('ativo', 'true').lower()

        queryset = Maquina.objects.select_related('setor').order_by('nome')

        if ativo_param == 'false':
            queryset = queryset.filter(ativo=False)
        elif ativo_param != 'all':
            queryset = queryset.filter(ativo=True)

        if search:
            queryset = queryset.filter(Q(nome__icontains=search))
        if setor_param:
            queryset = queryset.filter(setor_id=setor_param)
        if tipo_param:
            queryset = queryset.filter(tipo=tipo_param)

        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(page_number)

        results = [
            {
                'id': m.id,
                'nome': m.nome,
                'setor_id': m.setor_id,
                'setor_nome': m.setor.nome,
                'tipo': m.tipo,
                'ativo': m.ativo,
            }
            for m in page_obj.object_list
        ]

        setores = [{'id': s.id, 'nome': s.nome} for s in Setor.objects.all().order_by('nome')]

        return JsonResponse({
            'results': results,
            'page': page_obj.number,
            'page_size': page_obj.paginator.per_page,
            'total_pages': paginator.num_pages,
            'total_items': paginator.count,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
            'meta': {'setores': setores},
        })

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'JSON invalido.'}, status=400)

        nome = (data.get('nome') or '').strip()
        setor_id = data.get('setor_id')
        tipo = (data.get('tipo') or '').strip()

        if not nome:
            return JsonResponse({'error': 'Nome e obrigatorio.'}, status=400)
        if not setor_id:
            return JsonResponse({'error': 'Setor e obrigatorio.'}, status=400)
        if tipo not in ('maquina', 'processo'):
            return JsonResponse({'error': 'Tipo invalido.'}, status=400)

        setor = get_object_or_404(Setor, id=setor_id)

        try:
            maquina = Maquina.objects.create(nome=nome, setor=setor, tipo=tipo)
        except IntegrityError:
            return JsonResponse({'error': 'Ja existe uma maquina com este nome, setor e tipo.'}, status=400)

        return JsonResponse({'success': 'Maquina criada com sucesso.', 'id': maquina.id}, status=201)

    if request.method == 'PATCH':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'JSON invalido.'}, status=400)

        maquina_id = data.get('id')
        if not maquina_id:
            return JsonResponse({'error': 'ID nao informado.'}, status=400)

        maquina = get_object_or_404(Maquina, id=maquina_id)

        nome = (data.get('nome') or '').strip()
        setor_id = data.get('setor_id')
        tipo = (data.get('tipo') or '').strip()

        if not nome:
            return JsonResponse({'error': 'Nome e obrigatorio.'}, status=400)
        if not setor_id:
            return JsonResponse({'error': 'Setor e obrigatorio.'}, status=400)
        if tipo not in ('maquina', 'processo'):
            return JsonResponse({'error': 'Tipo invalido.'}, status=400)

        maquina.nome = nome
        maquina.setor = get_object_or_404(Setor, id=setor_id)
        maquina.tipo = tipo

        try:
            maquina.save()
        except IntegrityError:
            return JsonResponse({'error': 'Ja existe uma maquina com este nome, setor e tipo.'}, status=400)

        return JsonResponse({'success': 'Maquina atualizada com sucesso.'})

    if request.method == 'PUT':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'JSON invalido.'}, status=400)

        maquina_id = data.get('id')
        if not maquina_id:
            return JsonResponse({'error': 'ID nao informado.'}, status=400)

        maquina = get_object_or_404(Maquina, id=maquina_id)
        maquina.ativo = not maquina.ativo
        maquina.save(update_fields=['ativo'])

        return JsonResponse({
            'success': f'Maquina {"ativada" if maquina.ativo else "desativada"} com sucesso.',
            'ativo': maquina.ativo,
        })

    return JsonResponse({'error': 'Metodo nao permitido.'}, status=405)

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
        page_size = request.GET.get('page_size', 10)

        try:
            page_number = int(page_number)
            page_size = int(page_size)
        except ValueError:
            return JsonResponse({'error': 'Parametros de paginacao invalidos.'}, status=400)

        queryset = (
            Pecas.objects
            .select_related('conjunto', 'processo_1')
            .prefetch_related('setor')
            .order_by('codigo')
        )

        ativo_param = request.GET.get('ativo', 'true').lower()
        if ativo_param == 'false':
            queryset = queryset.filter(ativo=False)
        elif ativo_param == 'all':
            pass  # sem filtro
        else:
            queryset = queryset.filter(ativo=True)

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
                'ativo': peca.ativo,
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

    if request.method == 'PUT':
        # Toggle ativo/inativo
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'JSON invalido.'}, status=400)

        peca_id = data.get('id')
        if not peca_id:
            return JsonResponse({'error': 'ID da peca nao informado.'}, status=400)

        peca = get_object_or_404(Pecas, id=peca_id)
        peca.ativo = not peca.ativo
        peca.save(update_fields=['ativo'])

        return JsonResponse({
            'success': f'Peca {"ativada" if peca.ativo else "desabilitada"} com sucesso.',
            'ativo': peca.ativo,
        })

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
    PUT: alterna ativo/inativo.
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
                'ativo': conjunto.ativo,
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

    if request.method == 'PUT':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'JSON invalido.'}, status=400)

        conjunto_id = data.get('id')
        if not conjunto_id:
            return JsonResponse({'error': 'ID do conjunto nao informado.'}, status=400)

        conjunto = get_object_or_404(Conjuntos, id=conjunto_id)
        conjunto.ativo = not conjunto.ativo
        conjunto.save(update_fields=['ativo'])

        return JsonResponse({
            'success': f'Conjunto {"ativado" if conjunto.ativo else "inativado"} com sucesso.',
            'ativo': conjunto.ativo,
        })

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


def _clean_produto(value):
    if value is None:
        return None
    produto = str(value).strip()
    if not produto:
        return None
    return produto


@login_required
def cadastro_itens_explodidos(request):
    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'add_single':
            produto = _clean_produto(request.POST.get('produto'))
            if not produto:
                messages.error(request, 'Informe o produto para cadastrar.')
                return redirect('cadastro:cadastro_itens_explodidos')

            obj, created = ItensExplodidos.objects.get_or_create(produto=produto)
            if created:
                messages.success(request, f'Produto "{obj.produto}" cadastrado com sucesso.')
            else:
                messages.warning(request, f'Produto "{obj.produto}" ja esta cadastrado.')
            return redirect('cadastro:cadastro_itens_explodidos')

        if action == 'upload_csv':
            file = request.FILES.get('file')
            if not file:
                messages.error(request, 'Selecione um arquivo CSV para importar.')
                return redirect('cadastro:cadastro_itens_explodidos')

            if not file.name.lower().endswith('.csv'):
                messages.error(request, 'Arquivo invalido. Envie um arquivo .csv.')
                return redirect('cadastro:cadastro_itens_explodidos')

            raw_bytes = file.read()

            try:
                decoded = raw_bytes.decode('utf-8-sig')
            except UnicodeDecodeError:
                try:
                    decoded = raw_bytes.decode('latin-1')
                except UnicodeDecodeError:
                    messages.error(request, 'Nao foi possivel ler o arquivo CSV (encoding invalido).')
                    return redirect('cadastro:cadastro_itens_explodidos')

            rows = csv.reader(decoded.splitlines())
            produtos = set()

            for row in rows:
                if not row:
                    continue
                produto = _clean_produto(row[0])
                if not produto:
                    continue
                if produto.lower() == 'produto':
                    continue
                produtos.add(produto)

            if not produtos:
                messages.warning(request, 'Nenhum produto valido encontrado no CSV.')
                return redirect('cadastro:cadastro_itens_explodidos')

            existentes = set(
                ItensExplodidos.objects.filter(produto__in=produtos).values_list('produto', flat=True)
            )
            novos = [ItensExplodidos(produto=produto) for produto in produtos if produto not in existentes]
            ItensExplodidos.objects.bulk_create(novos, ignore_conflicts=True)

            messages.success(
                request,
                f'Importacao concluida. Novos: {len(novos)} | Ja existentes: {len(existentes)}.'
            )
            return redirect('cadastro:cadastro_itens_explodidos')

        if action == 'delete':
            item_id = request.POST.get('id')
            if not item_id:
                messages.error(request, 'ID do item nao informado para exclusao.')
                return redirect('cadastro:cadastro_itens_explodidos')

            item = get_object_or_404(ItensExplodidos, id=item_id)
            produto = item.produto
            item.delete()
            messages.success(request, f'Produto "{produto}" removido com sucesso.')
            return redirect('cadastro:cadastro_itens_explodidos')

        messages.error(request, 'Acao invalida.')
        return redirect('cadastro:cadastro_itens_explodidos')

    search = (request.GET.get('search') or '').strip()
    queryset = ItensExplodidos.objects.all().order_by('produto')
    if search:
        queryset = queryset.filter(produto__icontains=search)

    paginator = Paginator(queryset, 50)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        'cadastro_itens_explodidos.html',
        {
            'page_obj': page_obj,
            'search': search,
            'total_items': paginator.count,
        }
    )


@login_required
def cadastro_carretas_explodidas(request):
    return render(request, 'cadastro_carretas_explodidas.html')


@login_required
def chapas_corte(request):
    return render(request, 'chapas_corte.html')


@csrf_exempt
@login_required
def chapas_corte_api(request):

    def parse_decimal(value):
        if value in (None, ''):
            raise ValueError('Espessura e obrigatoria.')
        try:
            return Decimal(str(value).strip().replace(',', '.'))
        except (InvalidOperation, ValueError):
            raise ValueError('Espessura invalida.')

    def parse_decimal_optional(value, field):
        if value in (None, ''):
            return None
        try:
            return Decimal(str(value).strip().replace(',', '.'))
        except (InvalidOperation, ValueError):
            raise ValueError(f'{field} invalida.')

    def format_decimal_optional(value):
        if value in (None, ''):
            return ''
        return str(value).replace('.', ',').rstrip('0').rstrip(',')

    def format_intervalo_largura(largura_minima, largura_maxima):
        minima = format_decimal_optional(largura_minima)
        maxima = format_decimal_optional(largura_maxima)
        if minima and maxima and minima == maxima:
            return minima
        if minima and maxima:
            return f'{minima} ate {maxima}'
        if minima:
            return f'{minima}+'
        if maxima:
            return f'ate {maxima}'
        return ''

    def get_tipos_chapa(obj):
        tipos = obj.tipos_chapa or []
        if not tipos and obj.tipo_chapa:
            tipos = [obj.tipo_chapa]
        return tipos

    def get_tipos_chapa_display(obj):
        labels = dict(EspessuraChapa.TIPO_CHAPA_CHOICES)
        return ', '.join(labels.get(tipo, tipo) for tipo in get_tipos_chapa(obj))

    def tipos_chapa_conflitam(tipos_a, tipos_b):
        if not tipos_a or not tipos_b:
            return True
        return bool(set(tipos_a) & set(tipos_b))

    def intervalos_largura_sobrepostos(min_a, max_a, min_b, max_b):
        if max_a is not None and min_b is not None and max_a < min_b:
            return False
        if max_b is not None and min_a is not None and max_b < min_a:
            return False
        return True

    def buscar_conflito_intervalo_largura(como_aparece, espessura, largura_minima, largura_maxima, tipos_chapa, item_id=None):
        queryset = EspessuraChapa.objects.filter(
            como_aparece_planilha__iexact=como_aparece,
            espessura=espessura,
            ativo=True,
        )
        if item_id:
            queryset = queryset.exclude(id=item_id)

        for chapa in queryset:
            if not tipos_chapa_conflitam(get_tipos_chapa(chapa), tipos_chapa):
                continue
            if intervalos_largura_sobrepostos(chapa.largura, chapa.largura_maxima, largura_minima, largura_maxima):
                return chapa
        return None

    def serialize(obj):
        return {
            'id': obj.id,
            'como_aparece_planilha': obj.como_aparece_planilha,
            'espessura': str(obj.espessura).replace('.', ',').rstrip('0').rstrip(','),
            'codigo': obj.codigo or '',
            'largura': format_decimal_optional(obj.largura),
            'largura_maxima': format_decimal_optional(obj.largura_maxima),
            'largura_intervalo': format_intervalo_largura(obj.largura, obj.largura_maxima),
            'tipo_chapa': obj.tipo_chapa or '',
            'tipos_chapa': get_tipos_chapa(obj),
            'tipo_chapa_display': get_tipos_chapa_display(obj),
            'ativo': obj.ativo,
        }

    if request.method == 'GET':
        page_number = request.GET.get('page', 1)
        page_size = request.GET.get('page_size', 50)
        ativo_param = request.GET.get('ativo', 'true').lower()
        search = (request.GET.get('search') or '').strip()

        try:
            page_number = int(page_number)
            page_size = int(page_size)
        except ValueError:
            return JsonResponse({'error': 'Parametros de paginacao invalidos.'}, status=400)

        queryset = EspessuraChapa.objects.all().order_by('espessura', 'como_aparece_planilha')

        if ativo_param == 'false':
            queryset = queryset.filter(ativo=False)
        elif ativo_param != 'all':
            queryset = queryset.filter(ativo=True)

        if search:
            queryset = queryset.filter(
                Q(como_aparece_planilha__icontains=search) |
                Q(codigo__icontains=search)
            )

        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(page_number)

        return JsonResponse({
            'results': [serialize(item) for item in page_obj.object_list],
            'page': page_obj.number,
            'page_size': page_obj.paginator.per_page,
            'total_pages': paginator.num_pages,
            'total_items': paginator.count,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
        })

    if request.method in ('POST', 'PATCH'):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'JSON invalido.'}, status=400)

        como_aparece = (data.get('como_aparece_planilha') or '').strip()
        codigo = (data.get('codigo') or '').strip() or None
        tipos_chapa = data.get('tipos_chapa')

        if not como_aparece:
            return JsonResponse({'error': 'Como aparece na planilha e obrigatorio.'}, status=400)

        try:
            espessura = parse_decimal(data.get('espessura'))
            largura = parse_decimal_optional(data.get('largura'), 'Largura minima')
            largura_maxima = parse_decimal_optional(data.get('largura_maxima'), 'Largura maxima')
        except ValueError as exc:
            return JsonResponse({'error': str(exc)}, status=400)

        if largura is not None and largura_maxima is not None and largura_maxima < largura:
            return JsonResponse({'error': 'Largura maxima deve ser maior ou igual a largura minima.'}, status=400)

        tipos_validos = {choice[0] for choice in EspessuraChapa.TIPO_CHAPA_CHOICES}
        if tipos_chapa in (None, ''):
            tipos_chapa = []
        elif isinstance(tipos_chapa, str):
            tipos_chapa = [tipos_chapa] if tipos_chapa else []
        elif not isinstance(tipos_chapa, list):
            return JsonResponse({'error': 'Tipos de chapa invalidos.'}, status=400)

        tipos_chapa = [str(tipo).strip() for tipo in tipos_chapa if str(tipo).strip()]
        if any(tipo not in tipos_validos for tipo in tipos_chapa):
            return JsonResponse({'error': 'Tipo de chapa invalido.'}, status=400)
        tipo_chapa = tipos_chapa[0] if tipos_chapa else None
        item_id = data.get('id') if request.method == 'PATCH' else None

        conflito = buscar_conflito_intervalo_largura(
            como_aparece,
            espessura,
            largura,
            largura_maxima,
            tipos_chapa,
            item_id=item_id,
        )
        if conflito:
            intervalo = format_intervalo_largura(conflito.largura, conflito.largura_maxima) or 'sem limite'
            return JsonResponse({
                'error': (
                    'Ja existe uma chapa ativa com esta espessura, tipo e intervalo de largura '
                    f'sobreposto: {conflito.como_aparece_planilha} | codigo {conflito.codigo or "-"} | largura {intervalo}.'
                )
            }, status=400)

        if request.method == 'POST':
            try:
                item = EspessuraChapa.objects.create(
                    como_aparece_planilha=como_aparece,
                    espessura=espessura,
                    codigo=codigo,
                    largura=largura,
                    largura_maxima=largura_maxima,
                    tipo_chapa=tipo_chapa,
                    tipos_chapa=tipos_chapa,
                )
            except IntegrityError:
                return JsonResponse({'error': 'Nao foi possivel criar a chapa de corte.'}, status=400)

            return JsonResponse({'success': 'Chapa de corte criada com sucesso.', 'id': item.id}, status=201)

        if not item_id:
            return JsonResponse({'error': 'ID nao informado.'}, status=400)

        item = get_object_or_404(EspessuraChapa, id=item_id)
        item.como_aparece_planilha = como_aparece
        item.espessura = espessura
        item.codigo = codigo
        item.largura = largura
        item.largura_maxima = largura_maxima
        item.tipo_chapa = tipo_chapa
        item.tipos_chapa = tipos_chapa

        try:
            item.save()
        except IntegrityError:
            return JsonResponse({'error': 'Nao foi possivel atualizar a chapa de corte.'}, status=400)

        return JsonResponse({'success': 'Chapa de corte atualizada com sucesso.'})

    if request.method == 'PUT':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'JSON invalido.'}, status=400)

        item_id = data.get('id')
        if not item_id:
            return JsonResponse({'error': 'ID nao informado.'}, status=400)

        item = get_object_or_404(EspessuraChapa, id=item_id)
        item.ativo = not item.ativo
        item.save(update_fields=['ativo'])

        return JsonResponse({
            'success': f'Chapa de corte {"ativada" if item.ativo else "inativada"} com sucesso.',
            'ativo': item.ativo,
        })

    return JsonResponse({'error': 'Metodo nao permitido.'}, status=405)


@csrf_exempt
@login_required
def cadastro_carretas_explodidas_api(request):

    CAMPOS_TEXTO = [
        'grupo1', 'grupo2', 'codigo_peca', 'descricao_peca',
        'mp_peca', 'total_peca', 'conjunto_peca',
        'primeiro_processo', 'segundo_processo', 'carreta', 'grupo', 'peso',
    ]

    if request.method == 'GET':
        page_number = request.GET.get('page', 1)
        page_size = request.GET.get('page_size', 50)
        try:
            page_number = int(page_number)
            page_size = int(page_size)
        except ValueError:
            return JsonResponse({'error': 'Parametros de paginacao invalidos.'}, status=400)

        queryset = CarretasExplodidas.objects.all().order_by('id')

        search = request.GET.get('search', '').strip()
        carreta_filtro = request.GET.get('carreta', '').strip()

        if search:
            queryset = queryset.filter(
                Q(codigo_peca__icontains=search) |
                Q(descricao_peca__icontains=search)
            )
        if carreta_filtro:
            queryset = queryset.filter(carreta__icontains=carreta_filtro)

        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(page_number)

        results = [
            {campo: getattr(obj, campo) for campo in ['id'] + CAMPOS_TEXTO}
            for obj in page_obj.object_list
        ]

        carretas_lista = (
            CarretasExplodidas.objects
            .exclude(carreta__isnull=True)
            .exclude(carreta='')
            .values_list('carreta', flat=True)
            .distinct()
            .order_by('carreta')
        )

        return JsonResponse({
            'results': results,
            'page': page_obj.number,
            'page_size': page_obj.paginator.per_page,
            'total_pages': paginator.num_pages,
            'total_items': paginator.count,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
            'meta': {
                'carretas': list(carretas_lista),
            },
        })

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'JSON invalido.'}, status=400)

        obj = CarretasExplodidas()
        for campo in CAMPOS_TEXTO:
            setattr(obj, campo, (data.get(campo) or '').strip() or None)
        obj.save()
        return JsonResponse({'success': 'Registro criado com sucesso.', 'id': obj.id}, status=201)

    if request.method == 'PATCH':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'JSON invalido.'}, status=400)

        obj_id = data.get('id')
        if not obj_id:
            return JsonResponse({'error': 'ID nao informado.'}, status=400)

        obj = get_object_or_404(CarretasExplodidas, id=obj_id)
        for campo in CAMPOS_TEXTO:
            setattr(obj, campo, (data.get(campo) or '').strip() or None)
        obj.save()
        return JsonResponse({'success': 'Registro atualizado com sucesso.'})

    if request.method == 'DELETE':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'JSON invalido.'}, status=400)

        obj_id = data.get('id')
        if not obj_id:
            return JsonResponse({'error': 'ID nao informado.'}, status=400)

        obj = get_object_or_404(CarretasExplodidas, id=obj_id)
        obj.delete()
        return JsonResponse({'success': 'Registro removido com sucesso.'})

    return JsonResponse({'error': 'Metodo nao permitido.'}, status=405)
