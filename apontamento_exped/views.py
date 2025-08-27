from django.shortcuts import render
from django.http import JsonResponse

from cargas.utils import get_data_from_sheets,tratando_dados
from .models import Carga,ItemPacote,Pacote,VerificacaoPacote

def planejamento(request):

    return render(request, 'apontamento_exped/planejamento.html')

# ============ apis ===============

# fluxo:
# 1. Escolhe data
# 2. Mostra clientes disponíveis
# 3. Escolhe cliente
# 4. Mostra carretas disponíveis
# 5. Escolhe carreta

# criar cache para n ficar carregando toda hora

def clientes(request):
    data_carga = request.GET.get('data_carga')

    base_carretas, base_carga = get_data_from_sheets()
    base_carretas, base_carga = tratando_dados(base_carretas, base_carga, data_carga)

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
    def cor_recurso(recurso):
        if 'VM' in recurso:
            return 'vermelho'
        elif 'AN' in recurso:
            return 'azul'
        elif 'VJ' in recurso:
            return 'verde'
        elif 'LJ' in recurso:
            return 'laranja'
        elif 'AM' in recurso:
            return 'amarelo'
        elif 'CO' in recurso:
            return 'cinza'
        else:
            return 'laranja'

    base_carga['cor'] = base_carga['Recurso'].apply(cor_recurso)

    # Mostrar recurso e quantidade
    carretas = base_carga[['Recurso', 'Qtde', 'PED_NUMEROSERIE','cor']].to_dict(orient='records')
    
    return JsonResponse(carretas, safe=False)

# def escolher_carretas(request):


