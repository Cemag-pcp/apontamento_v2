from django.shortcuts import render
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth import authenticate, login
from django.contrib.auth.views import LoginView
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.exceptions import ObjectDoesNotExist
from django.utils.timezone import now
from django.db import transaction
from django.db.models import Prefetch, Count

from .models import Ordem, Versao
from cadastro.models import MotivoExclusao,MotivoMaquinaParada,MotivoInterrupcao,Pecas
from core.models import Ordem,MaquinaParada,OrdemProcesso

import json
import time

@login_required  # Garante que apenas usuários autenticados possam acessar a view
def excluir_ordem(request):
    # Verifica se o usuário tem o tipo de acesso "pcp"
    if not hasattr(request.user, 'profile') or request.user.profile.tipo_acesso != 'pcp':
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
            ordem = get_object_or_404(Ordem, ordem=ordem_id, grupo_maquina=setor)

            # Verifica o status atual da ordem antes de permitir a exclusão
            if ordem.status_atual in ['aguardando_iniciar', 'finalizada']:
                ordem.excluida = True
                ordem.motivo_exclusao = motivo_exclusao
                ordem.save()
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

def home(request):
    return render(request, 'home/home.html')  

def versao(request):
    # Busca todas as versões ordenadas pela data mais recente
    versoes = Versao.objects.order_by('data_lancamento')

    return render(request, 'home/versao.html', {'versoes': versoes})

@csrf_exempt
@require_http_methods(["PATCH"])  # So PATCH é permitido
def retornar_maquina(request):
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

def parar_maquina(request):

    setor = request.GET.get('setor', '')

    if request.method == 'PATCH':
        try:
            with transaction.atomic():
                # Decodifica o corpo da requisição
                data = json.loads(request.body)
                maquina = data.get('maquina')
                motivo = data.get('motivo')

                # Validação básica de dados
                if not maquina or not motivo:
                    return JsonResponse({'error': 'Dados inválidos: maquina ou motivo ausente.'}, status=400)

                # Verifica se a máquina ja está parada
                if MaquinaParada.objects.filter(maquina=maquina, data_fim__isnull=True).exists():
                    return JsonResponse({'error': 'Máquina já está parada.'}, status=400)

                # Busca o motivo específico no banco de dados
                try:
                    motivo_instance = MotivoMaquinaParada.objects.get(nome=motivo, setor__nome=setor)
                except MotivoMaquinaParada.DoesNotExist:
                    return JsonResponse({'error': 'Motivo não encontrado para o setor especificado.'}, status=404)

                # Cria o registro de máquina parada
                MaquinaParada.objects.create(
                    maquina=maquina,
                    motivo=motivo_instance
                )

                # Verifica se existe alguma ordem em processo associada à máquina
                ordem_em_processo = OrdemProcesso.objects.filter(data_fim__isnull=True, status='iniciada', ordem__maquina=maquina).first()

                if ordem_em_processo:

                    ordem_em_processo.data_fim=now()
                    ordem_em_processo.save()

                    # Cria um novo processo com status "interrompido"
                    novo_processo = OrdemProcesso.objects.create(
                        ordem=ordem_em_processo.ordem,
                        status='interrompida',
                        data_inicio=now(),
                        motivo_interrupcao=MotivoInterrupcao.objects.get(nome='Máquina parada')
                    )
                    novo_processo.save()

                    # Atualiza a ordem associada
                    ordem=ordem_em_processo.ordem
                    ordem.status_prioridade=2
                    ordem.status_atual='interrompida'
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

    # Consulta os dados agrupados por status
    contagem_status = Ordem.objects.filter(grupo_maquina=setor, excluida=False).values('status_atual').annotate(total=Count('id')).order_by('status_atual')

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

    if setor == 'serra':    
        maquinas = [
            ('serra_1', 'Serra 1'),
            ('serra_2','Serra 2'),
            ('serra_3', 'Serra 3')
        ]
    elif setor == 'estamparia':
        maquinas = [
            ('viradeira_1','Viradeira 1'),
            ('viradeira_2','Viradeira 2'),
            ('viradeira_3','Viradeira 3'),
            ('viradeira_4','Viradeira 4'),
            ('viradeira_5','Viradeira 5'),
            ('prensa','Prensa')
        ]

    status_data = []
    for maquina in maquinas:
        # Verifica se ja tem uma parada ativa dessa máquina
        paradas = MaquinaParada.objects.filter(
            maquina=maquina[0],
            data_fim__isnull=True
        )

        # Verifica o último status
        em_producao = OrdemProcesso.objects.filter(
            ordem__maquina=maquina[0],
            status='iniciada',
            data_fim__isnull=True
        ).exists()

        interrompida = OrdemProcesso.objects.filter(
            ordem__maquina=maquina[0],
            status='interrompida',
            data_fim__isnull=True
        ).exists()

        if em_producao and paradas.exists():
            status = 'Parada'
        elif interrompida and paradas.exists():
            status = 'Parada'
        elif paradas.exists():
            status = 'Parada'
        elif interrompida and em_producao:
            status = 'Em produção'
        elif interrompida and not paradas.exists():
            status = 'Livre'
        elif em_producao:
            status = 'Em produção'
        else: 
            status = 'Livre'

        status_data.append({
            'maquina_id': maquina[0],
            'maquina': maquina[1],
            'status': status,
            'motivo_parada': paradas.last().motivo.nome if paradas.exists() else None
        })

    return JsonResponse({'status': status_data})

def get_maquinas_disponiveis(request):

    setor = request.GET.get('setor', '')

    if setor == 'serra':    
        maquinas = [
            ('serra_1', 'Serra 1'),
            ('serra_2','Serra 2'),
            ('serra_3', 'Serra 3')
        ]
    elif setor == 'estamparia':
        maquinas = [
            ('viradeira_1','Viradeira 1'),
            ('viradeira_2','Viradeira 2'),
            ('viradeira_3','Viradeira 3'),
            ('viradeira_4','Viradeira 4'),
            ('viradeira_5','Viradeira 5'),
            ('prensa','Prensa')
        ]

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
