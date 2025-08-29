from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.shortcuts import get_object_or_404

from cargas.utils import get_data_from_sheets,tratando_dados
from .models import Carga,ItemPacote,Pacote,VerificacaoPacote, CarretaCarga

import json

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

    cargas = Carga.objects.all().values('id', 'nome', 'carga', 'data_carga', 'cliente', 'obs_pacote', 'status', 'data_criacao')
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

        dados.append({
            'id': pacote.id,
            'nome': pacote.nome,
            'status': pacote.status_confirmacao,
            'data_criacao': pacote.data_criacao.strftime('%Y-%m-%d %H:%M'),
            'itens': itens,
        })

    return JsonResponse({'pacotes': dados})



