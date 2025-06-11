from django.shortcuts import render
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth import authenticate, login
from django.contrib.auth.views import LoginView
from django.contrib.auth.decorators import login_required, permission_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.exceptions import ObjectDoesNotExist
from django.utils.timezone import now
from django.db import transaction
from django.db.models import Prefetch, Count
from django.contrib.auth.models import User
from django.contrib import messages

from .models import Ordem, Versao
from cadastro.models import MotivoExclusao,MotivoMaquinaParada,MotivoInterrupcao,Pecas,Maquina
from core.models import Ordem,MaquinaParada,OrdemProcesso,Profile,RotaAcesso

import json
import time

@login_required  # Garante que apenas usuários autenticados possam acessar a view
def excluir_ordem(request):
    # Verifica se o usuário tem o tipo de acesso "pcp"
    if not hasattr(request.user, 'profile') or request.user.profile.tipo_acesso not in ['pcp','supervisor']:
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
                if setor in ['laser_1','laser_2','plasma']:
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
            else:
                return JsonResponse({'error': 'Finalize a ordem para excluí-la.'}, status=400)

        except Exception as e:
            print(f"Erro ao excluir ordem: {str(e)}")
            return JsonResponse({'error': 'Erro interno no servidor.'}, status=500)

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
        contagem_status = Ordem.objects.filter(grupo_maquina__in=('laser_1','laser_2','plasma'), excluida=False).values('status_atual').annotate(total=Count('id')).order_by('status_atual')
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
