from django.shortcuts import render
from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404
from django.contrib.auth import authenticate, login
from django.contrib.auth.views import LoginView
from django.contrib.auth.decorators import login_required, permission_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.exceptions import ObjectDoesNotExist
from django.utils.timezone import now
from django.utils.timesince import timesince
from django.db import transaction, IntegrityError
from django.db.models import Prefetch, Count, Q
from django.contrib.auth.models import User
from django.contrib import messages
from django.views.decorators.http import require_GET, require_POST
from django.core.paginator import Paginator

from .models import Ordem, Versao
from cadastro.models import MotivoExclusao,MotivoMaquinaParada,MotivoInterrupcao,Pecas,Maquina,CarretasExplodidas,Setor,Conjuntos
from core.models import Ordem,MaquinaParada,OrdemProcesso,Profile,PropriedadesOrdem,RotaAcesso, Notificacao
from apontamento_corte.models import PecasOrdem as PecasOrdemCorte
from apontamento_serra.models import PecasOrdem as PecasOrdemSerra
from apontamento_usinagem.models import PecasOrdem as PecasOrdemUsinagem
from apontamento_estamparia.models import PecasOrdem as PecasOrdemEstamparia

import json
import time

@login_required  # Garante que apenas usuários autenticados possam acessar a view
def excluir_ordem(request):
    # Verifica se o usuário tem o tipo de acesso "pcp"
    if not hasattr(request.user, 'profile') or request.user.profile.tipo_acesso not in ['pcp','supervisor','admin']:
        return JsonResponse({'error': 'Acesso negado: você não tem permissão para excluir ordens.'}, status=403)

    if request.method == 'POST':
        try:
            # Decodifica o corpo da requisição
            data = json.loads(request.body)
            ordem_id = data['ordem_id']
            motivo = data['motivo']
            setor = data['setor']

            # Busca o motivo de exclusão
            motivo_exclusao = get_object_or_404(MotivoExclusao, pk=int(motivo))

            # Busca a ordem
            ordem = get_object_or_404(Ordem, pk=ordem_id, grupo_maquina=setor)

            # Verifica o status atual da ordem antes de permitir a exclusão
            if ordem.status_atual in ['aguardando_iniciar', 'finalizada']:
                # Exceção para o setor de corte (opção de retirar do sequenciamento)
                if setor in ['laser_1','laser_2','laser_1','laser_3','plasma']:
                    print('adicionando o motivo...')
                    ordem.motivo_retirar_sequenciada = motivo_exclusao
                    print('retirando do sequenciamento...')
                    ordem.sequenciada = False
                    print("salvando no banco...")
                    ordem.save()
                else:
                    ordem.excluida = True
                    ordem.motivo_exclusao = motivo_exclusao
                    ordem.save(update_fields=['excluida', 'motivo_exclusao'])
                return JsonResponse({'success': 'Ordem excluída com sucesso.'}, status=201)
            elif setor == 'usinagem' and ordem.status_atual != "iniciada":
                ordem.excluida = True
                ordem.motivo_exclusao = motivo_exclusao
                ordem.save(update_fields=['excluida', 'motivo_exclusao'])
                return JsonResponse({'success': 'Ordem excluída com sucesso.'}, status=201)
            else:
                return JsonResponse({'error': 'Finalize a ordem para excluí-la.'}, status=400)

        except Exception as e:
            print(f"Erro ao excluir ordem: {str(e)}")
            return JsonResponse({'error': 'Erro interno no servidor.'}, status=500)

    return JsonResponse({'error': 'Método não permitido.'}, status=405)





@login_required
def pecas_estamparia(request):
    return render(request, 'core/pecas_estamparia.html')


@csrf_exempt
@login_required
def pecas_estamparia_api(request):
    """
    GET: lista peças de estamparia paginadas.
    PATCH: atualiza qtd_boa e qtd_morta de uma peça de estamparia.
    """
    if request.method == 'GET':
        page_number = request.GET.get('page', 1)
        page_size = request.GET.get('page_size', 50)

        try:
            page_number = int(page_number)
            page_size = int(page_size)
        except ValueError:
            return JsonResponse({'error': 'Parâmetros de paginação inválidos.'}, status=400)

        queryset = (
            PecasOrdemEstamparia.objects
            .select_related('ordem', 'peca')
            .filter(ordem__grupo_maquina='estamparia')
            .order_by('-data', '-id')
        )

        ordem_param = request.GET.get('ordem')
        if ordem_param:
            try:
                queryset = queryset.filter(ordem__ordem=int(ordem_param))
            except ValueError:
                queryset = queryset.filter(ordem__ordem_duplicada__icontains=ordem_param)

        peca_param = request.GET.get('peca')
        if peca_param:
            queryset = queryset.filter(
                Q(peca__codigo__icontains=peca_param) |
                Q(peca__descricao__icontains=peca_param)
            )

        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(page_number)

        pecas = []
        for po in page_obj.object_list:
            ordem_display = po.ordem.ordem if po.ordem and po.ordem.ordem is not None else (po.ordem.ordem_duplicada if po.ordem else None)
            peca_display = f"{po.peca.codigo} - {po.peca.descricao}" if po.peca else None
            pecas.append({
                'id': po.id,
                'ordem_id': po.ordem_id,
                'ordem_numero': ordem_display,
                'grupo_maquina': po.ordem.get_grupo_maquina_display() if po.ordem else None,
                'peca_id': po.peca_id,
                'peca_codigo': po.peca.codigo if po.peca else None,
                'peca_descricao': po.peca.descricao if po.peca else None,
                'peca_display': peca_display,
                'qtd_planejada': po.qtd_planejada,
                'qtd_boa': po.qtd_boa,
                'qtd_morta': po.qtd_morta,
                'data': po.data.strftime('%d/%m/%Y %H:%M') if po.data else None,
            })

        return JsonResponse({
            'results': pecas,
            'page': page_obj.number,
            'page_size': page_obj.paginator.per_page,
            'total_pages': paginator.num_pages,
            'total_items': paginator.count,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
        })

    if request.method == 'PATCH':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'JSON inválido.'}, status=400)

        pecas_id = data.get('id')
        if not pecas_id:
            return JsonResponse({'error': 'ID da peça não informado.'}, status=400)

        peca_ordem = get_object_or_404(
            PecasOrdemEstamparia.objects.select_related('ordem'),
            id=pecas_id,
            ordem__grupo_maquina='estamparia'
        )

        # qtd_total = float(data.get('qtd_boa')) + float(data.get('qtd_morta'))
        # if not qtd_total == peca_ordem.qtd_planejada:
        #     return JsonResponse({'error': 'Quantidade total precisa ser igual a quantidade planejada.'}, status=400)

        campos_para_atualizar = {}
        for campo in ['qtd_boa', 'qtd_morta']:
            if campo in data:
                try:
                    campos_para_atualizar[campo] = float(data[campo])
                except (TypeError, ValueError):
                    return JsonResponse({'error': f'{campo} inválido.'}, status=400)

        if not campos_para_atualizar:
            return JsonResponse({'error': 'Nenhum campo válido para atualizar.'}, status=400)

        for campo, valor in campos_para_atualizar.items():
            setattr(peca_ordem, campo, valor)

        peca_ordem.save(update_fields=list(campos_para_atualizar.keys()))

        return JsonResponse({
            'success': 'Peça atualizada com sucesso.',
            'peca': {
                'id': peca_ordem.id,
                'qtd_boa': peca_ordem.qtd_boa,
                'qtd_morta': peca_ordem.qtd_morta,
            }
        })

    return JsonResponse({'error': 'Método não permitido.'}, status=405)


@login_required
def pecas_usinagem(request):
    return render(request, 'core/pecas_usinagem.html')


@csrf_exempt
@login_required
def pecas_usinagem_api(request):
    """
    GET: lista peças de usinagem paginadas.
    PATCH: atualiza qtd_boa e qtd_morta de uma peça de usinagem.
    """
    if request.method == 'GET':
        page_number = request.GET.get('page', 1)
        page_size = request.GET.get('page_size', 50)

        try:
            page_number = int(page_number)
            page_size = int(page_size)
        except ValueError:
            return JsonResponse({'error': 'Parâmetros de paginação inválidos.'}, status=400)

        queryset = (
            PecasOrdemUsinagem.objects
            .select_related('ordem', 'peca')
            .filter(ordem__grupo_maquina='usinagem')
            .order_by('-data', '-id')
        )

        ordem_param = request.GET.get('ordem')
        if ordem_param:
            try:
                queryset = queryset.filter(ordem__ordem=int(ordem_param))
            except ValueError:
                queryset = queryset.filter(ordem__ordem_duplicada__icontains=ordem_param)

        peca_param = request.GET.get('peca')
        if peca_param:
            queryset = queryset.filter(
                Q(peca__codigo__icontains=peca_param) |
                Q(peca__descricao__icontains=peca_param)
            )

        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(page_number)

        pecas = []
        for po in page_obj.object_list:
            ordem_display = po.ordem.ordem if po.ordem and po.ordem.ordem is not None else (po.ordem.ordem_duplicada if po.ordem else None)
            peca_display = f"{po.peca.codigo} - {po.peca.descricao}" if po.peca else None
            pecas.append({
                'id': po.id,
                'ordem_id': po.ordem_id,
                'ordem_numero': ordem_display,
                'grupo_maquina': po.ordem.get_grupo_maquina_display() if po.ordem else None,
                'peca_id': po.peca_id,
                'peca_codigo': po.peca.codigo if po.peca else None,
                'peca_descricao': po.peca.descricao if po.peca else None,
                'peca_display': peca_display,
                'qtd_planejada': po.qtd_planejada,
                'qtd_boa': po.qtd_boa,
                'qtd_morta': po.qtd_morta,
                'data': po.data.strftime('%d/%m/%Y %H:%M') if po.data else None,
            })

        return JsonResponse({
            'results': pecas,
            'page': page_obj.number,
            'page_size': page_obj.paginator.per_page,
            'total_pages': paginator.num_pages,
            'total_items': paginator.count,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
        })

    if request.method == 'PATCH':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'JSON inválido.'}, status=400)

        pecas_id = data.get('id')
        if not pecas_id:
            return JsonResponse({'error': 'ID da peça não informado.'}, status=400)

        peca_ordem = get_object_or_404(
            PecasOrdemUsinagem.objects.select_related('ordem'),
            id=pecas_id,
            ordem__grupo_maquina='usinagem'
        )

        # qtd_total = float(data.get('qtd_boa')) + float(data.get('qtd_morta'))
        # if not qtd_total == peca_ordem.qtd_planejada:
        #     return JsonResponse({'error': 'Quantidade total precisa ser igual a quantidade planejada.'}, status=400)

        campos_para_atualizar = {}
        for campo in ['qtd_boa', 'qtd_morta']:
            if campo in data:
                try:
                    campos_para_atualizar[campo] = float(data[campo])
                except (TypeError, ValueError):
                    return JsonResponse({'error': f'{campo} inválido.'}, status=400)

        if not campos_para_atualizar:
            return JsonResponse({'error': 'Nenhum campo válido para atualizar.'}, status=400)

        for campo, valor in campos_para_atualizar.items():
            setattr(peca_ordem, campo, valor)

        peca_ordem.save(update_fields=list(campos_para_atualizar.keys()))

        return JsonResponse({
            'success': 'Peça atualizada com sucesso.',
            'peca': {
                'id': peca_ordem.id,
                'qtd_boa': peca_ordem.qtd_boa,
                'qtd_morta': peca_ordem.qtd_morta,
            }
        })

    return JsonResponse({'error': 'Método não permitido.'}, status=405)


@login_required
def pecas_serra(request):
    return render(request, 'core/pecas_serra.html')


@csrf_exempt
@login_required
def pecas_serra_api(request):
    """
    GET: lista peças de serra paginadas.
    PATCH: atualiza qtd_boa e qtd_morta de uma peça de serra.
    """
    if request.method == 'GET':
        page_number = request.GET.get('page', 1)
        page_size = request.GET.get('page_size', 50)

        try:
            page_number = int(page_number)
            page_size = int(page_size)
        except ValueError:
            return JsonResponse({'error': 'Parâmetros de paginação inválidos.'}, status=400)

        queryset = (
            PecasOrdemSerra.objects
            .select_related('ordem', 'peca')
            .filter(ordem__grupo_maquina='serra')
            .order_by('-data', '-id')
        )

        ordem_param = request.GET.get('ordem')
        if ordem_param:
            try:
                queryset = queryset.filter(ordem__ordem=int(ordem_param))
            except ValueError:
                queryset = queryset.filter(ordem__ordem_duplicada__icontains=ordem_param)

        peca_param = request.GET.get('peca')
        if peca_param:
            queryset = queryset.filter(
                Q(peca__codigo__icontains=peca_param) |
                Q(peca__descricao__icontains=peca_param)
            )

        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(page_number)

        pecas = []
        for po in page_obj.object_list:
            ordem_display = po.ordem.ordem if po.ordem and po.ordem.ordem is not None else (po.ordem.ordem_duplicada if po.ordem else None)
            peca_display = f"{po.peca.codigo} - {po.peca.descricao}" if po.peca else None
            pecas.append({
                'id': po.id,
                'ordem_id': po.ordem_id,
                'ordem_numero': ordem_display,
                'grupo_maquina': po.ordem.get_grupo_maquina_display() if po.ordem else None,
                'peca_id': po.peca_id,
                'peca_codigo': po.peca.codigo if po.peca else None,
                'peca_descricao': po.peca.descricao if po.peca else None,
                'peca_display': peca_display,
                'qtd_planejada': po.qtd_planejada,
                'qtd_boa': po.qtd_boa,
                'qtd_morta': po.qtd_morta,
                'data': po.data.strftime('%d/%m/%Y %H:%M') if po.data else None,
            })

        return JsonResponse({
            'results': pecas,
            'page': page_obj.number,
            'page_size': page_obj.paginator.per_page,
            'total_pages': paginator.num_pages,
            'total_items': paginator.count,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
        })

    if request.method == 'PATCH':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'JSON inválido.'}, status=400)

        pecas_id = data.get('id')
        if not pecas_id:
            return JsonResponse({'error': 'ID da peça não informado.'}, status=400)

        peca_ordem = get_object_or_404(
            PecasOrdemSerra.objects.select_related('ordem'),
            id=pecas_id,
            ordem__grupo_maquina='serra'
        )

        # qtd_total = float(data.get('qtd_boa')) + float(data.get('qtd_morta'))
        # if not qtd_total == peca_ordem.qtd_planejada:
        #     return JsonResponse({'error': 'Quantidade total precisa ser igual a quantidade planejada.'}, status=400)

        campos_para_atualizar = {}
        for campo in ['qtd_boa', 'qtd_morta']:
            if campo in data:
                try:
                    campos_para_atualizar[campo] = float(data[campo])
                except (TypeError, ValueError):
                    return JsonResponse({'error': f'{campo} inválido.'}, status=400)

        if not campos_para_atualizar:
            return JsonResponse({'error': 'Nenhum campo válido para atualizar.'}, status=400)

        for campo, valor in campos_para_atualizar.items():
            setattr(peca_ordem, campo, valor)

        peca_ordem.save(update_fields=list(campos_para_atualizar.keys()))

        return JsonResponse({
            'success': 'Peça atualizada com sucesso.',
            'peca': {
                'id': peca_ordem.id,
                'qtd_boa': peca_ordem.qtd_boa,
                'qtd_morta': peca_ordem.qtd_morta,
            }
        })

    return JsonResponse({'error': 'Método não permitido.'}, status=405)


@login_required
def pecas_corte(request):
    return render(request, 'core/pecas_corte.html')


@csrf_exempt
@login_required
def pecas_corte_api(request):
    """
    GET: lista peças de corte paginadas.
    PATCH: atualiza qtd_boa e qtd_morta de uma peça de corte.
    """
    corte_grupos = ['laser_1', 'laser_2', 'laser_3', 'plasma']

    if request.method == 'GET':
        page_number = request.GET.get('page', 1)
        page_size = request.GET.get('page_size', 50)

        try:
            page_number = int(page_number)
            page_size = int(page_size)
        except ValueError:
            return JsonResponse({'error': 'Parâmetros de paginação inválidos.'}, status=400)

        queryset = (
            PecasOrdemCorte.objects
            .select_related('ordem')
            .filter(ordem__grupo_maquina__in=corte_grupos)
            .order_by('-data', '-id')
        )

        ordem_param = request.GET.get('ordem')
        if ordem_param:
            try:
                queryset = queryset.filter(ordem__ordem=int(ordem_param))
            except ValueError:
                queryset = queryset.filter(ordem__ordem_duplicada__icontains=ordem_param)

        peca_param = request.GET.get('peca')
        if peca_param:
            queryset = queryset.filter(peca__icontains=peca_param)

        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(page_number)

        pecas = []
        for po in page_obj.object_list:
            ordem_display = po.ordem.ordem if po.ordem and po.ordem.ordem is not None else (po.ordem.ordem_duplicada if po.ordem else None)
            pecas.append({
                'id': po.id,
                'ordem_id': po.ordem_id,
                'ordem_numero': ordem_display,
                'grupo_maquina': po.ordem.get_grupo_maquina_display() if po.ordem else None,
                'peca': po.peca,
                'qtd_planejada': po.qtd_planejada,
                'qtd_boa': po.qtd_boa,
                'qtd_morta': po.qtd_morta,
                'data': po.data.strftime('%d/%m/%Y %H:%M') if po.data else None,
            })

        return JsonResponse({
            'results': pecas,
            'page': page_obj.number,
            'page_size': page_obj.paginator.per_page,
            'total_pages': paginator.num_pages,
            'total_items': paginator.count,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
        })

    if request.method == 'PATCH':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'JSON inválido.'}, status=400)

        pecas_id = data.get('id')
        if not pecas_id:
            return JsonResponse({'error': 'ID da peça não informado.'}, status=400)

        peca_ordem = get_object_or_404(
            PecasOrdemCorte.objects.select_related('ordem'),
            id=pecas_id,
            ordem__grupo_maquina__in=corte_grupos
        )
            
        # qtd_total = float(data.get('qtd_boa')) + float(data.get('qtd_morta'))
        # if not qtd_total == peca_ordem.qtd_planejada:
        #     return JsonResponse({'error': 'Quantidade total precisa ser igual a quantidade planejada.'}, status=400)

        campos_para_atualizar = {}
        for campo in ['qtd_boa', 'qtd_morta']:
            if campo in data:
                try:
                    campos_para_atualizar[campo] = float(data[campo])
                except (TypeError, ValueError):
                    return JsonResponse({'error': f'{campo} inválido.'}, status=400)

        if not campos_para_atualizar:
            return JsonResponse({'error': 'Nenhum campo válido para atualizar.'}, status=400)

        for campo, valor in campos_para_atualizar.items():
            setattr(peca_ordem, campo, valor)

        peca_ordem.save(update_fields=list(campos_para_atualizar.keys()))

        return JsonResponse({
            'success': 'Peça atualizada com sucesso.',
            'peca': {
                'id': peca_ordem.id,
                'qtd_boa': peca_ordem.qtd_boa,
                'qtd_morta': peca_ordem.qtd_morta,
            }
        })

    return JsonResponse({'error': 'Método não permitido.'}, status=405)

class CustomLoginView(LoginView):
    template_name = 'login/login.html'

    def form_valid(self, form):
        start_time = time.time()

        user = authenticate(
            self.request,
            username=form.cleaned_data["username"],
            password=form.cleaned_data["password"]
        )
        if user:
            login(self.request, user)

        end_time = time.time()
        print(f"Tempo de login: {end_time - start_time:.2f} segundos")  # Log de tempo de login

        return super().form_valid(form)

    def form_invalid(self, form):
        # Mensagem de erro 
        messages.error(self.request, "Usuário ou senha incorretos.",extra_tags='danger')

        return super().form_invalid(form)
        
def home(request):
    return render(request, 'home/home.html')  

def versao(request):
    # Busca todas as versões ordenadas pela data mais recente
    versoes = Versao.objects.order_by('data_lancamento')

    return render(request, 'home/versao.html', {'versoes': versoes})

@login_required
def propriedades_ordem(request):
    return render(
        request,
        'core/propriedades_ordem.html',
        {
            'tipos_chapa': PropriedadesOrdem.TIPO_CHAPA_CHOICES
        }
    )

@csrf_exempt
@require_http_methods(["PATCH"])  # So PATCH é permitido
def retornar_maquina(request):

    """
    
    Para retornar uma maquina:

    {
        "maquina": 30
    }
    
    """


    try:
        data = json.loads(request.body)
        maquina_nome = data.get('maquina')

        if not maquina_nome:
            return JsonResponse({'error': 'Nome da máquina não fornecido'}, status=400)

        # Busca a máquina que está parada e ainda não tem data_fim definida
        maquina = MaquinaParada.objects.get(maquina=maquina_nome, data_fim__isnull=True)

        # Atualiza o status para funcionamento
        maquina.data_fim = now()
        maquina.save()

        return JsonResponse({'success': 'Máquina retornada à produção com sucesso.'}, status=200)
    
    except ObjectDoesNotExist:
        return JsonResponse({'error': 'Máquina não encontrada ou já está em operação.'}, status=404)
    
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Formato JSON inválido'}, status=400)

    except Exception as e:
        return JsonResponse({'error': f'Erro inesperado: {str(e)}'}, status=500)

@csrf_exempt
def parar_maquina(request):

    """

    Para parar uma máquina:

    {
        "setor": "montagem",
        "maquina": 30,
        "motivo": "Manutenção"
    }

    """

    setor = request.GET.get('setor', '')

    if request.method == 'PATCH':
        try:
            with transaction.atomic():
                # Decodifica o corpo da requisição
                data = json.loads(request.body)
                maquina = get_object_or_404(Maquina, pk=data.get('maquina')) 
                motivo = data.get('motivo')
                
                # Validação básica de dados
                if not maquina or not motivo:
                    return JsonResponse({'error': 'Dados inválidos: maquina ou motivo ausente.'}, status=400)

                # Verifica se a máquina ja está parada
                if MaquinaParada.objects.filter(maquina=maquina, data_fim__isnull=True).exists():
                    return JsonResponse({'error': 'Máquina já está parada.'}, status=400)

                # Busca o motivo específico no banco de dados
                try:
                    motivo_instance = MotivoMaquinaParada.objects.get(nome=motivo)
                except MotivoMaquinaParada.DoesNotExist:
                    return JsonResponse({'error': 'Motivo não encontrado para o setor especificado.'}, status=404)

                # Cria o registro de máquina parada
                MaquinaParada.objects.create(
                    maquina=maquina,
                    motivo=motivo_instance
                )

                # Busca todas as ordens em processo que ainda não foram finalizadas para essa máquina
                ordens_em_processo = OrdemProcesso.objects.filter(data_fim__isnull=True, status='iniciada', ordem__maquina=maquina)

                if ordens_em_processo.exists():  # Apenas executa se houver ordens iniciadas

                    motivo_interrupcao = MotivoInterrupcao.objects.get(nome='Máquina parada')

                    for ordem_processo in ordens_em_processo:
                        # Finaliza a ordem em processo atual
                        ordem_processo.data_fim = now()
                        ordem_processo.save()

                        # Cria um novo processo com status "interrompido"
                        novo_processo = OrdemProcesso.objects.create(
                            ordem=ordem_processo.ordem,
                            status='interrompida',
                            data_inicio=now(),
                            motivo_interrupcao=motivo_interrupcao
                        )
                        novo_processo.save()

                        # Atualiza o status da ordem associada
                        ordem = ordem_processo.ordem
                        ordem.status_prioridade = 2
                        ordem.status_atual = 'interrompida'
                        ordem.save()

                return JsonResponse({'success': 'Máquina parada com sucesso.'}, status=201)

        except MotivoInterrupcao.DoesNotExist:
            return JsonResponse({'error': 'Motivo de interrupção não encontrado.'}, status=404)
        except Exception as e:
            print(f"Erro: {str(e)}")
            return JsonResponse({'error': 'Erro interno no servidor.'}, status=500)
        
    # Resposta padrão para métodos não permitidos
    return JsonResponse({'error': 'Método não permitido.'}, status=405)

def get_ultimas_pecas_produzidas(request):
    setor = request.GET.get('setor', '')  # Captura o setor da URL

    if setor == 'corte':
        ultimas_ordens = Ordem.objects.filter(status_atual='finalizada').prefetch_related(
            'ordem_pecas_corte'  # Apenas busca as peças diretamente
        ).order_by('-ultima_atualizacao')[:10]
    else:
        # Filtra as ordens finalizadas e carrega as peças associadas ao setor informado
        ultimas_ordens = Ordem.objects.filter(status_atual='finalizada').prefetch_related(
            Prefetch(f'ordem_pecas_{setor}__peca', queryset=Pecas.objects.all())
        ).order_by('-ultima_atualizacao')[:10]  # Ordena pelas mais recentes e limita a 10

    # Prepara a lista de peças para o retorno JSON
    pecas = []
    for ordem in ultimas_ordens:
        ordem_pecas = getattr(ordem, f'ordem_pecas_{setor}', None)  # Obtém o atributo dinamicamente
        
        if ordem_pecas:  # Verifica se existe a relação
            for ordem_peca in ordem_pecas.all():
                peca = ordem_peca.peca
                if setor == 'corte':
                    peca_dict = {
                        'nome': f'{peca[:30] + "..." if peca and len(peca) > 30 else (peca if peca else "Sem descrição")}',
                        'data_producao': ordem.ultima_atualizacao.strftime('%Y-%m-%d %H:%M:%S'),
                    }
                else:
                    peca_dict = {
                        'nome': f'{peca.codigo} - {peca.descricao[:30] + "..." if peca.descricao and len(peca.descricao) > 30 else (peca.descricao if peca.descricao else "Sem descrição")}',
                        'data_producao': ordem.ultima_atualizacao.strftime('%Y-%m-%d %H:%M:%S'),
                    }

                # Adiciona 'quantidade' apenas se qtd_boa for diferente de 0
                if ordem_peca.qtd_boa != 0:
                    peca_dict['quantidade'] = ordem_peca.qtd_boa
                    pecas.append(peca_dict)

    # Retorna os dados como JSON
    return JsonResponse({'pecas': pecas})

def get_contagem_status_ordem(request):

    setor = request.GET.get('setor', '')  # Captura o setor da URL

    if setor == 'corte':
        contagem_status = Ordem.objects.filter(grupo_maquina__in=('laser_1','laser_2','laser_3','plasma'), excluida=False).values('status_atual').annotate(total=Count('id')).order_by('status_atual')
    else:
        contagem_status = Ordem.objects.filter(grupo_maquina=setor, excluida=False).values('status_atual').annotate(total=Count('id')).order_by('status_atual')

    # Consulta os dados agrupados por status

    # Total de ordens
    total_ordens = sum(item['total'] for item in contagem_status)

    # Calcula as porcentagens e prepara os dados para o frontend
    status_data = []
    for item in contagem_status:
        porcentagem = (item['total'] / total_ordens * 100) if total_ordens > 0 else 0
        status_data.append({
            'status': item['status_atual'],
            'total': item['total'],
            'porcentagem': round(porcentagem, 2)  # Trunca a porcentagem para 2 casas decimais
        })

    return JsonResponse({'status_contagem': status_data})

def get_status_maquinas(request):
    setor = request.GET.get('setor', '')

    # Máquinas a excluir da contagem
    maquinas_excluidas = [
        'PLAT. TANQUE. CAÇAM. 2',
        'QUALIDADE',
        'FORJARIA',
        'ESTAMPARIA',
        'Carpintaria',
        'FEIXE DE MOLAS',
        'SERRALHERIA',
        'ROÇADEIRA'
    ]


    if setor:    
        maquinas = Maquina.objects.filter(setor__nome=setor, tipo='maquina').exclude(nome__in=maquinas_excluidas).values_list('id', 'nome')
    else:
        return JsonResponse({'error': 'Setor inválido'}, status=400)

    status_data = []
    
    for maquina_id, maquina_nome in maquinas:
        # Verifica se já existe uma parada ativa para essa máquina
        paradas = MaquinaParada.objects.filter(maquina_id=maquina_id, data_fim__isnull=True)
        
        # Verifica o status da máquina
        em_producao = OrdemProcesso.objects.filter(
            ordem__maquina_id=maquina_id, status='iniciada', data_fim__isnull=True
        ).exists()
        
        interrompida = OrdemProcesso.objects.filter(
            ordem__maquina_id=maquina_id, status='interrompida', data_fim__isnull=True
        ).exists()

        # Determina o status da máquina
        if paradas.exists():
            status = 'Parada'
        elif em_producao:
            status = 'Em produção'
        elif interrompida:
            status = 'Livre'
        else:
            status = 'Livre'

        status_data.append({
            'maquina_id': maquina_id,
            'maquina': maquina_nome,
            'status': status,
            'motivo_parada': paradas.last().motivo.nome if paradas.exists() else None
        })

    return JsonResponse({'status': status_data})

def get_maquinas_disponiveis(request):

    setor = request.GET.get('setor', '')

    if setor:    
        maquinas = Maquina.objects.filter(setor__nome=setor, tipo='maquina').values_list('id', 'nome')
    else:
        return JsonResponse({'error': 'Setor inválido'}, status=400)

    # Obtem todas as máquinas que estão ativas em `OrdemProcesso` ou `MaquinaParada`
    maquinas_em_processo = OrdemProcesso.objects.filter(data_fim__isnull=True).values_list('maquina', flat=True).exclude(status='iniciada')
    maquinas_paradas = MaquinaParada.objects.filter(data_fim__isnull=True).values_list('maquina', flat=True)

    # Converte os resultados para conjuntos para evitar duplicação
    maquinas_ocupadas = set(maquinas_em_processo).union(set(maquinas_paradas))

    # Filtra as máquinas disponíveis com alias e nome
    maquinas_disponiveis = [
        {'alias': maquina[0], 'nome': maquina[1]}
        for maquina in maquinas
        if maquina[0] not in maquinas_ocupadas
    ]

    return JsonResponse({'maquinas_disponiveis': maquinas_disponiveis})

@login_required
def acessos(request):

    return render(request, 'acessos/acessos.html')

def api_listar_usuarios(request):
    users = Profile.objects.select_related("user").prefetch_related("permissoes").all()

    usuarios_json = [
        {
            "id": user.user.id,
            "username": user.user.username,
            "tipo_acesso": user.tipo_acesso,
            "permissoes": list(user.permissoes.values_list("nome", flat=True)),
        }
        for user in users
    ]
    return JsonResponse(usuarios_json, safe=False)

def api_listar_acessos(request, user_id):
    try:
        # Obtém todas as permissões cadastradas no sistema
        todas_as_rotas = RotaAcesso.objects.all()

        # Obtém o perfil do usuário
        profile = Profile.objects.get(user_id=user_id)

        # Obtém os IDs das permissões que o usuário já possui
        permissoes_usuario = set(profile.permissoes.all().values_list("id", flat=True))

        # Estrutura a resposta JSON
        acessos = [
            {
                "id": rota.id, 
                "nome": rota.nome, 
                "descricao": rota.descricao, 
                "ativo": rota.id in permissoes_usuario,  # Verifica se o usuário tem essa permissão
                "app": rota.get_app_display()
            }
            for rota in todas_as_rotas
        ]

        return JsonResponse(acessos, safe=False)

    except Profile.DoesNotExist:
        return JsonResponse({"error": "Perfil não encontrado!"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

def api_usuario_acessos(request, user_id):
    user = get_object_or_404(User, id=user_id)
    
    # Se o usuário não tiver um Profile, cria um automaticamente
    profile, created = Profile.objects.get_or_create(user=user)

    acessos = [{"id": setor[0], "nome": setor[1], "ativo": setor[0] in (profile.setores_permitidos or [])} for setor in Profile.SETOR_CHOICES]

    return JsonResponse({"acessos": acessos})

@csrf_exempt
def api_atualizar_acessos(request, user_id):
    if request.method != "POST":
        return JsonResponse({"error": "Método não permitido!"}, status=405)

    try:
        data = json.loads(request.body)
        profile = Profile.objects.get(user_id=user_id)

        # Converte os IDs para inteiros
        permissoes_ids = list(map(int, data.get("permissoes", [])))

        # Busca as permissões pelo ID corretamente
        permissoes_novas = RotaAcesso.objects.filter(id__in=permissoes_ids)

        # Atualiza as permissões do perfil
        profile.permissoes.set(permissoes_novas)

        profile.save()
        return JsonResponse({"message": "Acessos atualizados com sucesso!"})

    except Profile.DoesNotExist:
        return JsonResponse({"error": "Perfil não encontrado!"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

def retornar_processo(request):
    if request.method != 'POST':
        return JsonResponse(
            {'status': 'error', 'message': 'Método não permitido'}, 
            status=405
        )

    try:
        data = json.loads(request.body)
        ordem_id = data.get('ordemId')
        
        if not ordem_id:
            return JsonResponse(
                {'status': 'error', 'message': 'ordemId não fornecido'}, 
                status=400
            )

        with transaction.atomic():
            deleted_count, _ = OrdemProcesso.objects.filter(ordem_id=ordem_id).delete()
            
            updated_count = Ordem.objects.filter(id=ordem_id).update(
                maquina=None,
                status_atual='aguardando_iniciar'
            )
            
            if updated_count == 0:
                raise Ordem.DoesNotExist(f"Ordem com id {ordem_id} não encontrada")

        return JsonResponse({
            'status': 'success', 
            'message': 'Processo retornado com sucesso'
        })

    except json.JSONDecodeError:
        return JsonResponse(
            {'status': 'error', 'message': 'JSON inválido'}, 
            status=400
        )
    except Ordem.DoesNotExist:
        return JsonResponse(
            {'status': 'error', 'message': 'Ordem não encontrada'}, 
            status=404
        )
    except Exception as e:
        return JsonResponse(
            {'status': 'error', 'message': str(e)}, 
            status=500
        )

#Consultas de peças

def consulta_pecas(request):
    
    "Redirecionar para a tela de consultas de peça"

    return render(request, 'home/consulta-peca.html')

@require_GET
def consulta_carretas(request):
    """
    Retorna sugestões de carretas com base em um caractere digitado.
    Exemplo de uso: /api/consulta-carreta/?q=car
    """

    termo = request.GET.get('q', '').strip()

    if not termo:
        return JsonResponse({'carretas': []})

    carretas = (
        CarretasExplodidas.objects
        .filter(carreta__icontains=termo)
        .values_list('carreta', flat=True)
        .distinct()
    )

    return JsonResponse({'carretas': list(carretas)})

@require_GET
def consulta_conjunto(request):
    """
    Retorna sugestões de conjuntos com base na carreta selecionada e nos caracteres digitados.
    Exemplo de uso: /api/consulta-conjuntos/?carreta=F4&q=PLAT
    """

    caractere = request.GET.get('q', '').strip()
    carreta = request.GET.get('carreta', '').strip()

    if not carreta:
        return JsonResponse({'conjuntos': []})

    queryset = CarretasExplodidas.objects.filter(carreta=carreta)

    if caractere:
        queryset = queryset.filter(conjunto_peca__icontains=caractere)

    conjuntos = (
        queryset
        .values_list('conjunto_peca', flat=True)
        .distinct()
    )

    return JsonResponse({'conjuntos': list(conjuntos)})

@require_GET
def mostrar_pecas_completa(request):
    
    """
    Retorna as peças completas de uma carreta e conjunto específicos.
    Exemplo de uso: /api/pecas-completa/?carreta=carreta1&conjunto=conjunto1
    """

    conjunto = request.GET.get('conjunto', '').strip()
    carreta = request.GET.get('carreta', '').strip()

    if not carreta or not conjunto:
        return JsonResponse({'error': 'Carreta ou conjunto não fornecido'}, status=400)

    pecas = (
        CarretasExplodidas.objects
        .filter(carreta=carreta, conjunto_peca=conjunto)
        .values('descricao_peca','mp_peca','total_peca','conjunto_peca','primeiro_processo','segundo_processo')
    )

    return JsonResponse({'pecas': list(pecas)})

@require_GET
def base_explodida_innovaro(request):
    
    """
    Retorna as peças completas de uma carreta e conjunto específicos.
    Exemplo de uso: 
    """

    conjunto = request.GET.get('conjunto', '').strip()
    carreta = request.GET.get('carreta', '').strip()
    primeiro_processo = request.GET.get('primeiro_processo', '').strip()
    segundo_processo = request.GET.get('segundo_processo', '').strip()
    codigo_peca = request.GET.get('codigo_peca', '').strip()
    mp_peca = request.GET.get('mp_peca', '').strip()
    conjunto_peca = request.GET.get('conjunto_peca', '').strip()
    skip_raw = request.GET.get('skip', '0').strip()
    limit_raw = request.GET.get('limit', '100').strip()

    def _parse_list(v):
        if not v:
            return []
        return [p.strip() for p in v.split(',') if p.strip()]

    def _like_q(field, pattern):
        raw = (pattern or '').strip()
        if not raw:
            return Q()
        starts = raw.startswith('%')
        ends = raw.endswith('%')
        core = raw.strip('%')
        if not core:
            return Q()
        if starts and ends:
            return Q(**{f"{field}__icontains": core})
        if starts:
            return Q(**{f"{field}__iendswith": core})
        if ends:
            return Q(**{f"{field}__istartswith": core})
        return Q(**{f"{field}__iexact": raw})

    filtros = Q()

    if '%' in carreta:
        filtros &= _like_q('carreta', carreta)
    else:
        carreta_list = _parse_list(carreta)
        if carreta_list:
            filtros &= Q(carreta__in=carreta_list)

    conjunto_list_req = _parse_list(conjunto)
    if conjunto_list_req:
        filtros &= Q(conjunto_peca__in=conjunto_list_req)

    primeiro_list = _parse_list(primeiro_processo)
    if primeiro_list:
        filtros &= Q(primeiro_processo__in=primeiro_list)

    segundo_list = _parse_list(segundo_processo)
    if segundo_list:
        filtros &= Q(segundo_processo__in=segundo_list)

    codigo_list = _parse_list(codigo_peca)
    if codigo_list:
        filtros &= Q(codigo_peca__in=codigo_list)

    mp_list = _parse_list(mp_peca)
    if mp_list:
        filtros &= Q(mp_peca__in=mp_list)

    conjunto_list = _parse_list(conjunto_peca)
    if conjunto_list:
        filtros &= Q(conjunto_peca__in=conjunto_list)

    try:
        skip = max(int(skip_raw), 0)
    except ValueError:
        skip = 0

    try:
        limit = max(int(limit_raw), 1)
    except ValueError:
        limit = 100

    pecas = (
        CarretasExplodidas.objects
        .filter(filtros)
        .values(
            'codigo_peca',
            'descricao_peca',
            'mp_peca',
            'total_peca',
            'conjunto_peca',
            'primeiro_processo',
            'segundo_processo',
            'carreta',
            'grupo',
            'grupo1',
            'grupo2',
        )
        [skip:skip + limit]
    )

    return JsonResponse({'pecas': list(pecas)})

login_required
def notificacoes_pagina(request):
    """
    View para renderizar o 'shell' da página de notificações.
    Os dados serão carregados via API pelo JavaScript.
    """
    # A view agora só precisa renderizar o template, sem contexto extra.
    return render(request, 'notifications.html')


@login_required
def notificacoes_api(request):
    """
    API que retorna uma página de notificações e a contagem total de não lidas de forma otimizada.
    """
    page_number = request.GET.get('page', 1)

    try:
        profile = request.user.profile
    except Profile.DoesNotExist:
        return JsonResponse({'error': 'Perfil de usuário não encontrado.'}, status=404)

    # Define a queryset base
    if profile.tipo_acesso != 'admin':
        notificacoes_qs = Notificacao.objects.filter(profile=profile)
    else:
        # Admin vê todas as notificações
        notificacoes_qs = Notificacao.objects.all()

    # Otimização com select_related já garante que profile e user sejam carregados
    notificacoes_qs = notificacoes_qs.select_related('profile__user').order_by('-criado_em')

    # Contagem de não lidas
    unread_count = notificacoes_qs.filter(lido=False).count()

    # Paginação
    paginator = Paginator(notificacoes_qs, 8)
    page_obj = paginator.get_page(page_number)

    # --- MODIFICAÇÃO AQUI ---
    # Adicionamos o campo 'profile_nome' na serialização.
    # O acesso a `n.profile.user.username` é performático graças ao select_related.
    notificacoes_json = [
        {
            'id': n.id,
            'titulo': n.titulo,
            'mensagem': n.mensagem,
            'rota_acesso': n.rota_acesso,
            'tipo': n.tipo,
            'lido': n.lido,
            'tempo_atras': f"há {timesince(n.criado_em, now()).split(',')[0]}",
            'profile_nome': n.profile.user.username, # <-- CAMPO ADICIONADO
        }
        for n in page_obj.object_list
    ]

    data = {
        'notificacoes': notificacoes_json,
        'has_next': page_obj.has_next(),
        'unread_count': unread_count,
        'user_tipo_acesso': profile.tipo_acesso,
    }
    return JsonResponse(data)


@login_required
@require_POST
def marcar_notificacoes_como_lidas(request):
    try:
        data = json.loads(request.body)
        notification_ids = data.get('ids')

        if not isinstance(notification_ids, list):
            return HttpResponseBadRequest("O corpo da requisição deve conter uma lista de 'ids'.")

        notificacoes_para_marcar = Notificacao.objects.filter(
            profile=request.user.profile, 
            id__in=notification_ids,
            lido=False
        )
        
        count = 0
        # **A MUDANÇA ESSENCIAL ESTÁ AQUI**
        # Em vez de .update(), iteramos sobre a queryset.
        for notificacao in notificacoes_para_marcar:
            notificacao.lido = True
            # .save() DISPARA o sinal post_save para esta instância.
            notificacao.save(update_fields=['lido']) # Opcional: otimiza o SQL gerado
            count += 1

        return JsonResponse({
            'status': 'success', 
            'message': f'{count} notificações foram marcadas como lidas.'
        })

    except json.JSONDecodeError:
        return HttpResponseBadRequest("JSON inválido.")

@csrf_exempt
@login_required
def propriedades_ordem_api(request):
    """
    GET: lista PropriedadesOrdem paginadas.
    PATCH: atualiza campos editáveis (descricao_mp, tamanho, espessura, quantidade, tipo_chapa).
    """
    if request.method == 'GET':
        page_number = request.GET.get('page', 1)
        page_size = request.GET.get('page_size', 50)

        try:
            page_number = int(page_number)
            page_size = int(page_size)
        except ValueError:
            return JsonResponse({'error': 'Parâmetros de paginação inválidos.'}, status=400)

        queryset = (
            PropriedadesOrdem.objects
            .select_related('ordem', 'mp_codigo', 'nova_mp')
            .order_by('id')
        )
        
        # Filtros
        ordem_param = request.GET.get('ordem')
        if ordem_param:
            ordem_param = ordem_param.strip()
            try:
                ordem_num = int(ordem_param)
                queryset = queryset.filter(
                    Q(ordem__ordem=ordem_num) |
                    Q(ordem__ordem_duplicada__iexact=ordem_param)
                )
            except ValueError:
                queryset = queryset.filter(ordem__ordem_duplicada__icontains=ordem_param)

        mp_codigo_param = request.GET.get('mp_codigo')
        if mp_codigo_param:
            queryset = queryset.filter(mp_codigo_id=mp_codigo_param)

        descricao_param = request.GET.get('descricao_mp')
        if descricao_param:
            queryset = queryset.filter(descricao_mp__icontains=descricao_param)

        tipo_chapa_param = request.GET.get('tipo_chapa')
        if tipo_chapa_param:
            queryset = queryset.filter(tipo_chapa=tipo_chapa_param)

        retalho_param = request.GET.get('retalho')
        if retalho_param in ['true', 'false']:
            queryset = queryset.filter(retalho=(retalho_param == 'true'))

        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(page_number)

        propriedades = []
        for prop in page_obj.object_list:
            propriedades.append({
                'id': prop.id,
                'ordem_id': prop.ordem_id,
                'ordem_numero': prop.ordem.ordem if prop.ordem.ordem else prop.ordem.ordem_duplicada,
                'grupo_maquina': prop.ordem.grupo_maquina if prop.ordem else None,
                'grupo_maquina_display': prop.ordem.get_grupo_maquina_display() if prop.ordem else None,
                'mp_codigo_id': prop.mp_codigo_id,
                'descricao_mp': prop.descricao_mp,
                'tamanho': prop.tamanho,
                'espessura': prop.espessura,
                'quantidade': prop.quantidade,
                'aproveitamento': prop.aproveitamento,
                'tipo_chapa': prop.tipo_chapa,
                'retalho': prop.retalho,
                'nova_mp_id': prop.nova_mp_id,
            })

        print(propriedades)

        return JsonResponse({
            'results': propriedades,
            'page': page_obj.number,
            'page_size': page_obj.paginator.per_page,
            'total_pages': paginator.num_pages,
            'total_items': paginator.count,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
        })

    if request.method == 'PATCH':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'JSON inválido.'}, status=400)

        prop_id = data.get('id')
        if not prop_id:
            return JsonResponse({'error': 'ID da propriedade não informado.'}, status=400)

        propriedade = get_object_or_404(PropriedadesOrdem, id=prop_id)

        campos_editaveis = ['descricao_mp', 'tamanho', 'espessura', 'quantidade', 'tipo_chapa']
        campos_para_atualizar = {}

        for campo in campos_editaveis:
            if campo in data:
                campos_para_atualizar[campo] = data[campo]

        if not campos_para_atualizar:
            return JsonResponse({'error': 'Nenhum campo válido para atualizar.'}, status=400)

        for campo, valor in campos_para_atualizar.items():
            setattr(propriedade, campo, valor)

        propriedade.save(update_fields=list(campos_para_atualizar.keys()))

        return JsonResponse({
            'success': 'Propriedade atualizada com sucesso.',
            'propriedade': {
                'id': propriedade.id,
                'descricao_mp': propriedade.descricao_mp,
                'tamanho': propriedade.tamanho,
                'espessura': propriedade.espessura,
                'quantidade': propriedade.quantidade,
                'tipo_chapa': propriedade.tipo_chapa,
            }
        })

    return JsonResponse({'error': 'Método não permitido.'}, status=405)
