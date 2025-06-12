from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET
import gspread
from cargas.utils import google_credentials_json, scope
from google.oauth2 import service_account
from datetime import datetime
from collections import defaultdict

def sucata(request):

    return render(request, 'sucata.html')

def filtrar_sucata(request):
    # Obter parâmetros da query string
    data_inicial = request.GET.get('data_inicial', None)
    data_final = request.GET.get('data_final', None)
    codigo_chapa = request.GET.get('codigo_chapa', None)
    
    google_credentials_json["private_key"] = google_credentials_json["private_key"].replace("\\n", "\n")
    credentials = service_account.Credentials.from_service_account_info(
        google_credentials_json, 
        scopes=scope
    )
    
    sa = gspread.authorize(credentials)

    name_sheet = 'CENTRAL CORTE CHAPAS'
    worksheet1 = 'RQ PCP-003-000 (Transferencia Corte)'

    sh = sa.open(name_sheet)
    wks1 = sh.worksheet(worksheet1)

    all_data = wks1.get_all_values()
    
    # Filtrar as linhas de dados
    data_rows = all_data[5:]
    
    # Dicionários para agrupamento
    agrupados_por_data_codigo = defaultdict(lambda: {
        'aproveitamentos': [],
        'peso_total': 0,
        'count': 0
    })
    
    agrupados_por_data = defaultdict(lambda: {
        'peso_total': 0,
        'aproveitamentos': []
    })
    
    agrupados_por_codigo = defaultdict(float)
    
    for row in data_rows:
        # Verificar filtro de data
        if data_inicial and data_final:
            try:
                data_row = datetime.strptime(row[0], '%d/%m/%Y').date()
                data_inicial_dt = datetime.strptime(data_inicial, '%Y-%m-%d').date()
                data_final_dt = datetime.strptime(data_final, '%Y-%m-%d').date()
                
                if not (data_inicial_dt <= data_row <= data_final_dt):
                    continue
            except ValueError:
                continue
                
        # Verificar filtro de código de chapa
        if codigo_chapa and row[12] != codigo_chapa:
            continue
        
        # Obter valores das colunas
        data = row[0]
        codigo = row[12]
        try:
            aproveitamento = float(row[4].replace(',', '.'))
            peso = float(row[10].replace(',', '.'))
        except (ValueError, AttributeError):
            continue
        
        # Agrupar para dados detalhados
        chave = (data, codigo)
        agrupados_por_data_codigo[chave]['aproveitamentos'].append(aproveitamento)
        agrupados_por_data_codigo[chave]['peso_total'] += peso
        
        # Agrupar para o gráfico
        agrupados_por_data[data]['peso_total'] += peso
        agrupados_por_data[data]['aproveitamentos'].append(aproveitamento)
        
        # Agrupar para a tabela
        agrupados_por_codigo[codigo] += peso
    
    # Preparar dados para o gráfico
    grafico_data = {
        'datas': [],
        'pesos': [],
        'aproveitamentos': []
    }
    
    for data in sorted(agrupados_por_data.keys(), key=lambda x: datetime.strptime(x, '%d/%m/%Y')):
        grafico_data['datas'].append(data)
        grafico_data['pesos'].append(agrupados_por_data[data]['peso_total'])
        
        # Calcular média de aproveitamento para o dia
        aproveitamentos = agrupados_por_data[data]['aproveitamentos']
        media_aproveitamento = (sum(aproveitamentos)/len(aproveitamentos)) * 100 if aproveitamentos else 0
        grafico_data['aproveitamentos'].append(media_aproveitamento)

    # Preparar dados para a tabela (ordenados por código)
    tabela_codigos = [
        {'codigo': codigo, 'peso': f"{peso:.2f}".replace('.', ',')}
        for codigo, peso in sorted(agrupados_por_codigo.items())
    ]
    
    # Preparar dados detalhados (opcional, se ainda necessário)
    table_data = []
    for (data, codigo), valores in agrupados_por_data_codigo.items():
        media_aproveitamento = sum(valores['aproveitamentos']) / len(valores['aproveitamentos']) if valores['aproveitamentos'] else 0
        
        table_data.append({
            'Data': data,
            'Aproveitamento': f"{media_aproveitamento:.4f}".replace('.', ','),
            'Sucata': f"{valores['peso_total']:.2f}".replace('.', ','),
            'Codigo_Chapa': codigo
        })

    response_data = {
        'success': True,
        'grafico': grafico_data,
        'tabela': tabela_codigos,
        'filters': {
            'data_inicial': data_inicial,
            'data_final': data_final,
            'codigo_chapa': codigo_chapa
        }
    }
    
    return JsonResponse(response_data)
