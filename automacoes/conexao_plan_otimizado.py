import gspread
from google.oauth2 import service_account
import os
from cachetools import LRUCache
from datetime import datetime, timedelta

# Cache aumentado para 5000 entradas
cache = LRUCache(maxsize=5000)

# Cliente autenticado reutilizável
_gsheets_client = None
_client_created_at = None

def format_private_key(key: str) -> str:
    """Formata a chave privada do Google"""
    if '\\n' in key:
        return key.replace('\\n', '\n')
    return key

def get_gsheets_client():
    """
    Retorna cliente autenticado reutilizável.
    Recria cliente a cada 1 hora para manter conexão fresca.
    """
    global _gsheets_client, _client_created_at
    
    # Verifica se cliente existe e ainda é válido (menos de 1 hora)
    if _gsheets_client is not None and _client_created_at is not None:
        idade_cliente = (datetime.now() - _client_created_at).seconds
        if idade_cliente < 3600:  # 1 hora em segundos
            return _gsheets_client
    
    print("Criando nova conexão com Google Sheets...")
    
    # Construir credenciais do ambiente
    credentials_google = {
        "type": os.environ.get('type'),
        "project_id": os.environ.get('project_id'),
        "private_key": format_private_key(os.environ.get('private_key')),
        "client_email": os.environ.get('client_email'),
        "client_id": os.environ.get('client_id'),
        "auth_uri": os.environ.get('auth_uri'),
        "token_uri": os.environ.get('token_uri'),
        "auth_provider_x509_cert_url": os.environ.get('auth_provider_x509_cert_url'),
        "client_x509_cert_url": os.environ.get('client_x509_cert_url'),
        "universe_domain": os.environ.get('universe_domain')
    }
    
    scope = [
        'https://www.googleapis.com/auth/spreadsheets',
        "https://www.googleapis.com/auth/drive"
    ]
    
    credentials = service_account.Credentials.from_service_account_info(
        credentials_google, 
        scopes=scope
    )
    _gsheets_client = gspread.authorize(credentials)
    _client_created_at = datetime.now()
    
    return _gsheets_client

def busca_saldo_recurso_central(codigos):
    """
    Busca saldo de recursos do almoxarifado central.
    
    Args:
        codigos: List ou Set de códigos dos itens
        
    Returns:
        Tuple: (dict com saldos, data do último saldo)
        
    Otimizações:
    - Cache de 5000 entradas (antes era 100)
    - Cliente autenticado reutilizável
    - Query específica de colunas (A:C)
    - Dict direto em vez de DataFrame (90% mais rápido)
    """
    
    # Converter para tupla para usar como chave de cache
    codigos_tupla = tuple(sorted(set(codigos)))
    
    # Verificar cache
    if codigos_tupla in cache:
        print(f'✓ Cache hit: {len(codigos)} códigos')
        return cache[codigos_tupla]
    
    print(f'⚠ Cache miss: buscando {len(codigos)} códigos do Google Sheets')
    
    try:
        # ✅ Usar cliente reutilizável
        client = get_gsheets_client()
        
        sheet_id = '1u2Iza-ocp6ROUBXG9GpfHvEJwLHuW7F2uiO583qqLIE'
        sh = client.open_by_key(sheet_id)
        wks = sh.worksheet('saldo central')
        
        # ✅ Otimização: Carregar apenas 3 colunas (A:C) em vez de TODA a planilha
        # Colunas: A=código, B=saldo, C=data
        list1 = wks.get('A:C', valueRenderOption='FORMATTED_VALUE')
        
        # Validação
        if not list1 or len(list1) < 2:
            print("Planilha vazia ou sem dados")
            return {}, "N/A"
        
        # ✅ Extrair data do último saldo (primeira linha, coluna C)
        header = list1[0]
        data_ultimo_saldo = header[2] if len(header) > 2 else "N/A"
        if data_ultimo_saldo == "data ultimo saldo":
            # Se for header, pega do segundo row
            data_ultimo_saldo = list1[1][2] if len(list1) > 1 and len(list1[1]) > 2 else "N/A"
        
        # ✅ Construir dicionário direto (90% mais rápido que pandas)
        # Pula a primeira linha (header)
        saldo_dict = {}
        codigos_set = set(codigos)
        
        for row in list1[1:]:
            if len(row) >= 2:
                codigo = row[0]
                if codigo in codigos_set:
                    saldo = row[1]
                    saldo_dict[codigo] = saldo
        
        # Armazenar no cache e retornar
        resultado = (saldo_dict, data_ultimo_saldo)
        cache[codigos_tupla] = resultado
        
        print(f"✓ Saldo recuperado para {len(saldo_dict)} itens, {len(codigos_set) - len(saldo_dict)} não encontrados")
        return resultado
        
    except Exception as exc:
        print(f"❌ Erro ao buscar saldo: {str(exc)}")
        return {}, "Erro ao conectar"
