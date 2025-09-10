from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt

from cargas.utils import get_data_from_sheets,tratando_dados
from .models import Carga,ItemPacote,Pacote,VerificacaoPacote, CarretaCarga, ImagemPacote
from .utils import chamar_impressora

import json
import boto3

def planejamento(request):

    return render(request, 'apontamento_exped/planejamento.html')

# =========== utils ==============

def cor_recurso(recurso):
    if 'VM' in recurso:
        return 'vermelho'
    elif 'AN' in recurso:
        return 'azul'
    elif 'VJ' in recurso:
        return 'verde'
    elif 'LJ' in recurso:
        return 'laranja'
    elif 'AV' in recurso:
        return 'amarelo'
    elif 'CO' in recurso:
        return 'cinza'
    else:
        return 'laranja'

# ============ apis ===============

def cargas(request):
    data_carga = request.GET.get('data_carga')

    base_carretas, base_carga = get_data_from_sheets()
    base_carretas, base_carga = tratando_dados(base_carretas, base_carga, data_carga)

    cargas = base_carga['Carga'].unique().tolist()

    return JsonResponse(cargas, safe=False)

def clientes(request):
    data_carga = request.GET.get('data_carga')
    carga = request.GET.get('carga')

    base_carretas, base_carga = get_data_from_sheets()
    base_carretas, base_carga = tratando_dados(
        base_carretas, base_carga, data_carga,cliente=None,carga=carga
    )
    
    clientes = base_carga['PED_PESSOA.CODIGO'].unique().tolist()

    return JsonResponse(clientes, safe=False)

def carretas(request):
    cliente = request.GET.get('cliente')
    data_carga = request.GET.get('data_carga')

    base_carretas, base_carga = get_data_from_sheets()
    base_carretas, base_carga = tratando_dados(base_carretas, base_carga, data_carga, cliente)

    # criar coluna de cor
    # procurar na coluna recurso as siglas
    # VM=VERMELHO,AN=AZUL,VJ=VERDE,LJ=LARANJA,AM=AMARELO,CO=CINZA

    base_carga['cor'] = base_carga['Recurso'].apply(cor_recurso)

    # Mostrar recurso e quantidade
    carretas = base_carga[['Recurso', 'Qtde', 'PED_NUMEROSERIE','cor']].to_dict(orient='records')
    
    return JsonResponse(carretas, safe=False)

@csrf_exempt
def criar_caixa(request):
    if request.method != 'POST':
        return JsonResponse({'erro': 'Método não permitido'}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'erro': 'JSON inválido'}, status=400)

    # Extrai dados do pacote
    data_carga = data.get('data_carga')
    carga_nome = data.get('carga_nome')
    cliente_codigo = data.get('cliente_codigo')
    observacoes = data.get('observacoes')
    itens = data.get('itens', [])

    if not itens:
        return JsonResponse({'erro': 'Nenhum item informado'}, status=400)

    print(data_carga)
    print(carga_nome)
    print(cliente_codigo)
    print(observacoes)
    print(itens)

    # Aqui você pode salvar no banco se quiser

    hora_atual = timezone.now().strftime("%H%M%S")
    
    # criar no models carga e CarretaCarga
    carga = Carga.objects.create(
        nome=f"{carga_nome}_{cliente_codigo}_{data_carga.replace('-', '')}"+"_"+hora_atual,
        carga=carga_nome,
        data_carga=data_carga,
        cliente=cliente_codigo,
        obs_pacote=observacoes
    )

    #loop para salvar dentro de CarretaCarga os itens
    for item in itens:
        CarretaCarga.objects.create(
            carga=carga,
            carreta=item['codigo_peca'],  # ou parsear de item['descricao']
            quantidade=item['quantidade'],
            cor=item['cor']
        )

    # resposta de sucesso
    return JsonResponse({
        'mensagem': 'Caixa criada com sucesso!',
    }, status=201)

def buscar_cargas(request):

    cargas = Carga.objects.all().values('id', 'nome', 'carga', 'data_carga', 'cliente', 'obs_pacote', 'stage', 'data_criacao')

    # verifica se todos os pacotes dessa carga contém foto
    for carga in cargas:
        pacotes = Pacote.objects.filter(carga_id=carga['id'])
        total_pacotes = pacotes.count()
        pacotes_com_foto_verificacao = ImagemPacote.objects.filter(pacote__in=pacotes, stage='verificacao').values('pacote').distinct().count()
        pacotes_com_foto_despachado = ImagemPacote.objects.filter(pacote__in=pacotes, stage='despachado').values('pacote').distinct().count()
        
        carga['todos_pacotes_tem_foto_verificacao'] = (total_pacotes > 0 and total_pacotes == pacotes_com_foto_verificacao)
        carga['todos_pacotes_tem_foto_despachado'] = (total_pacotes > 0 and total_pacotes == pacotes_com_foto_despachado)
        

    print(list(cargas))

    return JsonResponse(list(cargas), safe=False)

@csrf_exempt
def guardar_pacotes(request):

    if request.method != 'POST':
        return JsonResponse({'erro': 'Método não permitido'}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'erro': 'JSON inválido'}, status=400)

    # Extrai dados do pacote
    id_carga = data.get('idCargaPacote')
    nome_pacote = data.get('nomePacote')
    itens = data.get('itens', [])

    if not itens:
        return JsonResponse({'erro': 'O campo de itens precisa ser preenchido.'}, status=400)

    print(id_carga)
    print(nome_pacote)
    print(itens)

    # criar pacotes
    pacote = Pacote.objects.create(
        nome=nome_pacote,
        carga=get_object_or_404(Carga, id=id_carga),
    )

    # adicionar itens dentro do pacote
    for item in itens:
        itens_pacote = ItemPacote.objects.create(
            pacote=pacote,
            codigo_peca=item['descricao'],
            descricao=None,
            cor=None,
            quantidade=int(item['quantidade'])
        )

    # resposta de sucesso
    return JsonResponse({
        'mensagem': 'Caixa criada com sucesso!',
    }, status=201)

def buscar_pacotes_carga(request, id):

    carga = get_object_or_404(Carga, id=id)
    pacotes = Pacote.objects.filter(carga=carga).prefetch_related('itens')

    dados = []

    for pacote in pacotes:
        itens = []
        for item in pacote.itens.all():
            itens.append({
                'id': item.id,
                'codigo_peca': item.codigo_peca,
                'descricao': item.descricao,
                'cor': item.cor,
                'quantidade': item.quantidade,
            })

        # Verifica se o pacote tem foto
        tem_foto = ImagemPacote.objects.filter(pacote=pacote).exists()

        dados.append({
            'id': pacote.id,
            'nome': pacote.nome,
            'status_expedicao': pacote.status_confirmacao_expedicao,
            'status_qualidade': pacote.status_confirmacao_qualidade,
            'data_criacao': pacote.data_criacao.strftime('%Y-%m-%d %H:%M'),
            'itens': itens,
            'cliente': carga.cliente,
            'data_carga': carga.data_carga,
            'tem_foto': tem_foto
        })

    return JsonResponse({'pacotes': dados, 'status_carga': carga.stage,
                        'cliente_carga': carga.cliente, 'data_carga': carga.data_carga,
                        'carga':carga.carga})

@csrf_exempt
def alterar_stage(request, id):
    if request.method != 'POST':
        return JsonResponse({'erro': 'Método não permitido'}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'erro': 'JSON inválido.'}, status=400)

    novo_stage = data.get('stage', None)
    carga = get_object_or_404(Carga, id=id)
    stage_atual = carga.stage

    # Regras de avanço de estágio
    if stage_atual == 'planejamento':
        pacotes = Pacote.objects.filter(carga_id=id).count()
        
        if pacotes == 0:
            return JsonResponse(
                {'erro': 'Você precisa criar ao menos 1 pacote antes de avançar para Apontamento.'},
                status=400
            )

    if stage_atual == 'apontamento':
        # VERIFICA SE TODOS PACOTES FORAM CONFIRMADOS
        total = Pacote.objects.filter(carga_id=id).count()
        confirmados = Pacote.objects.filter(carga_id=id, status_confirmacao_expedicao='ok').count()
        if total == 0 or confirmados < total:
            return JsonResponse(
                {'erro': 'Todos os pacotes precisam estar confirmados para avançar para Verificação.'},
                status=400
            )

    # Atualização do estágio
    if not novo_stage:
        if stage_atual == 'planejamento':
            carga.stage = 'apontamento'
        elif stage_atual == 'apontamento':
            carga.stage = 'verificacao'
        elif stage_atual == 'verificacao':
            carga.stage = 'despachado'
        else:
            return JsonResponse({'erro': 'Estágio atual inválido para avanço automático.'}, status=400)
    else:
        carga.stage = novo_stage

    carga.save()

    return JsonResponse({
        'mensagem': 'Estágio alterado com sucesso!',
        'novo_stage': carga.stage
    }, status=200)

@csrf_exempt
def confirmar_pacote(request, id):
    
    data = json.loads(request.body)

    obs = data.get('observacao')

    pacote = get_object_or_404(Pacote, id=id)

    # identificar em qual estage está esse pacote
    stage = pacote.carga.stage

    # verifica se o pacote ja tem imagem
    # if stage == 'apontamento':
    #     imagens = ImagemPacote.objects.filter(pacote=pacote, stage=stage)
    if stage == 'verificacao':
        imagens = ImagemPacote.objects.filter(pacote=pacote, stage=stage)

        if not imagens.exists():
            return JsonResponse({'erro': 'É necessário anexar ao menos uma foto antes de confirmar o pacote.'}, status=400)


    if stage == 'apontamento':
        pacote.status_confirmacao_expedicao = 'ok'
        pacote.data_confirmacao_expedicao = timezone.now()
        pacote.obs_expedicao = obs
    elif stage == 'verificacao':
        pacote.status_confirmacao_qualidade = 'ok'
        pacote.data_confirmacao_qualidade = timezone.now()
        pacote.obs_qualidade = obs
    
    pacote.save()    

    return JsonResponse({
        'mensagem': 'Pacote confirmado com sucesso!',
    }, status=200)

def mover_item(request):
    
    data = json.loads(request.body)

    item_id = data.get('item_id')
    pacote_destino_id = data.get('pacote_destino_id')

    item_pacote_atual = get_object_or_404(ItemPacote, id=item_id)
    item_pacote_atual.pacote_id = pacote_destino_id
    item_pacote_atual.save()

    return JsonResponse({
        'mensagem': 'Pacote alterado com sucesso.',
    }, status=200)

def impressao_pacote(request):

    data = json.loads(request.body)

    id_pacote = data.get('pacote_id')
    cliente = data.get('cliente')
    data_carga = data.get('data_carga')
    nome_pacote = data.get('nome_pacote')

    # buscar observações do pacote
    pacote = get_object_or_404(Pacote, id=id_pacote)
    obs_qualidade = pacote.obs_qualidade
    obs_expedicao = pacote.obs_expedicao


    # juntar observações
    if obs_qualidade and obs_expedicao:
        obs_completa = f"Expedição: {obs_expedicao} | Qualidade: {obs_qualidade}"
    elif obs_qualidade:
        obs_completa = f"Qualidade: {obs_qualidade}"
    elif obs_expedicao:
        obs_completa = f"Expedição: {obs_expedicao}"
    else:
        obs_completa = "Sem observações"

    chamar_impressora(cliente, data_carga, nome_pacote, obs_completa)

    return JsonResponse({'status': 'ok'})

@csrf_exempt
def salvar_foto(request):
    if request.method == 'POST' and request.FILES.get('foto'):

        foto = request.FILES['foto']
        pacote_id = request.POST.get('pacote')

        pacote_object = get_object_or_404(Pacote, id=pacote_id)

        # stage atual do pacote
        stage = pacote_object.carga.stage

        # Gera nome customizado
        extensao = foto.name.split('.')[-1]  # preserva extensão original
        nome_arquivo = f"fotos_pacotes/pacote_{pacote_id}_{timezone.now().strftime('%Y%m%d%H%M%S')}.{extensao}"

        # Sobrescreve o nome do arquivo
        foto.name = nome_arquivo

        imagem = ImagemPacote.objects.create(
            pacote=pacote_object,
            arquivo=foto,
            stage=stage
        )

        return JsonResponse({'status': 'ok', 'url': imagem.arquivo.url})

    return JsonResponse({'erro': 'Foto não recebida'}, status=400)

def buscar_fotos(request, pacote_id):
    if request.method == 'GET':
        imagens = ImagemPacote.objects.filter(pacote_id=pacote_id)
        fotos = [{'url': img.arquivo.url, 'etapa': img.stage} for img in imagens]
        return JsonResponse({'fotos': fotos})
    return JsonResponse({'erro': 'Método não permitido'}, status=405)
