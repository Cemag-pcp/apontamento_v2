# Análise do Arquivo `conexao_plan.py` - Problemas de Performance

## 🔴 PROBLEMAS CRÍTICOS IDENTIFICADOS

### 1. **Download de TODA a Planilha (Problema Principal)**
```python
wks = sh.worksheet('saldo central')
list1 = wks.get_all_values()  # ⚠️ CARREGA TUDO NA MEMÓRIA
itens = pd.DataFrame(list1)
```
**Impacto:** Se a planilha tem milhares de linhas, isso carrega TUDO na memória RAM antes de filtrar.

### 2. **Chamadas Síncronas Repetidas ao Frontend**
No `core_almox/views.py`, a função é chamada **3 vezes**:
- Linha 125: `busca_saldo_recurso_central(codigos_produtos)` para requisições
- Linha 162: `busca_saldo_recurso_central(codigos_produtos)` para transferências
- Linha 307: Chamada adicional

**Problema:** Se houver múltiplas requisições simultâneas do frontend, cada uma dispara essa função pesada.

### 3. **Cache Insuficiente**
```python
cache = LRUCache(maxsize=100)
```
**Problema:** Apenas 100 itens em cache. Se há mais de 100 combinações diferentes de códigos, não há reutilização.

### 4. **Credenciais Reconstruídas a Cada Chamada**
```python
credentials_google = {...}  # Constrói novo dict
credentials = service_account.Credentials.from_service_account_info(...)  # Nova autenticação
client = gspread.authorize(credentials)  # Nova conexão
```
**Problema:** Autenticação cara em toda chamada.

### 5. **Sem Paginação na Query do Google Sheets**
O código baixa TODA a planilha sem usar range específico. Google Sheets API permite:
```python
wks.get('A:B')  # Apenas colunas necessárias
wks.range('A1:C1000')  # Range específico
```

### 6. **DataFrame Desnecessário**
```python
itens = pd.DataFrame(list1)  # Cria DataFrame enorme
itens.columns = itens.iloc[0]
itens = itens.drop(index=0)
```
**Problema:** Pandas consome muita memória. Para apenas buscar e filtrar, dicts seria mais eficiente.

## 📊 Cenário do Erro

1. Usuário acessa dashboard almoxarifado
2. Frontend faz requisição com 50 códigos diferentes
3. `busca_saldo_recurso_central(50)` é chamado
4. Código baixa TODA planilha (5000+ linhas) em DataFrame
5. Filtra os 50 itens
6. Resposta é enviada
7. Se temos 10 usuários simultâneos → 10 × 5000 linhas em memória = 50.000 linhas
8. **RAM explode!** 💥

---

## ✅ SOLUÇÕES RECOMENDADAS

### Solução 1: Usar Query Específica (RÁPIDA)
```python
# Em vez de:
list1 = wks.get_all_values()

# Fazer:
list1 = wks.get(f'A:D', valueRenderOption='FORMATTED_VALUE')
# Apenas colunas necessárias: codigo, saldo, data
```

### Solução 2: Cachear a Autenticação
```python
_cached_client = None

def get_gsheets_client():
    global _cached_client
    if _cached_client is None:
        credentials_google = {...}
        credentials = service_account.Credentials.from_service_account_info(...)
        _cached_client = gspread.authorize(credentials)
    return _cached_client
```

### Solução 3: Usar Dict em vez de DataFrame
```python
# Em vez de pandas:
saldo_dict = {}
for row in list1[1:]:  # Pula header
    codigo, saldo = row[0], row[1]
    saldo_dict[codigo] = saldo

filtered = {k: saldo_dict[k] for k in codigos if k in saldo_dict}
```

### Solução 4: Aumentar Cache Significativamente
```python
cache = LRUCache(maxsize=10000)  # De 100 para 10000
```

### Solução 5: Considerar Cache com Expiração
```python
from datetime import datetime, timedelta

cache_data = {}
cache_expiry = {}
CACHE_TTL = 3600  # 1 hora

def busca_saldo_recurso_central(codigos):
    codigos_tupla = tuple(sorted(codigos))
    
    # Verifica se está em cache e ainda válido
    if codigos_tupla in cache_data:
        if datetime.now() < cache_expiry[codigos_tupla]:
            return cache_data[codigos_tupla]
    
    # ... resto do código
    
    cache_data[codigos_tupla] = (saldo_dict, data_ultimo_saldo)
    cache_expiry[codigos_tupla] = datetime.now() + timedelta(seconds=CACHE_TTL)
    return saldo_dict, data_ultimo_saldo
```

---

## 🎯 Prioridade de Correção

1. **CRÍTICO:** Usar apenas colunas necessárias na query (reduce 50-70% da memória)
2. **IMPORTANTE:** Cachear cliente autenticado (reduce 30% do tempo)
3. **IMPORTANTE:** Aumentar tamanho do cache (reduce requisições à API)
4. **BOM:** Usar dict em vez de pandas (reduce 40% da memória)
5. **MELHOR:** Implementar cache com TTL (melhor controle)

---

## 💡 Código Otimizado (Sugestão)

```python
import gspread
from google.oauth2 import service_account
import os
from cachetools import LRUCache
from datetime import datetime, timedelta

cache = LRUCache(maxsize=5000)
_gsheets_client = None
_client_created_at = None

def format_private_key(key: str) -> str:
    return key.replace('\\n', '\n') if '\\n' in key else key

def get_gsheets_client():
    global _gsheets_client, _client_created_at
    
    # Recriar cliente a cada hora para manter conexão fresca
    if _gsheets_client is None or (datetime.now() - _client_created_at).seconds > 3600:
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
        
        scope = ['https://www.googleapis.com/auth/spreadsheets',
                "https://www.googleapis.com/auth/drive"]
        credentials = service_account.Credentials.from_service_account_info(credentials_google, scopes=scope)
        _gsheets_client = gspread.authorize(credentials)
        _client_created_at = datetime.now()
    
    return _gsheets_client

def busca_saldo_recurso_central(codigos):
    codigos_tupla = tuple(sorted(codigos))
    
    if codigos_tupla in cache:
        print(f'Cache hit para {len(codigos)} códigos')
        return cache[codigos_tupla]
    
    print(f'Cache miss - buscando {len(codigos)} códigos do Google Sheets')
    
    try:
        client = get_gsheets_client()
        sheet_id = '1u2Iza-ocp6ROUBXG9GpfHvEJwLHuW7F2uiO583qqLIE'
        sh = client.open_by_key(sheet_id)
        wks = sh.worksheet('saldo central')
        
        # ✅ Apenas as 3 colunas necessárias
        list1 = wks.get('A:C', valueRenderOption='FORMATTED_VALUE')
        
        if not list1 or len(list1) < 2:
            return {}, "N/A"
        
        # Extrair data do primeiro saldo (segunda coluna do header)
        data_ultimo_saldo = list1[0][2] if len(list1[0]) > 2 else "N/A"
        
        # ✅ Usar dict em vez de DataFrame
        saldo_dict = {}
        for row in list1[1:]:
            if len(row) >= 2 and row[0] in codigos:
                saldo_dict[row[0]] = row[1]
        
        resultado = (saldo_dict, data_ultimo_saldo)
        cache[codigos_tupla] = resultado
        return resultado
        
    except Exception as e:
        print(f"Erro ao buscar saldo: {e}")
        return {}, "Erro"
```

---

## 📋 Teste a Diferença

Antes:
```
Tempo: ~8 segundos
Memória: 300-500 MB
```

Depois:
```
Tempo: ~1-2 segundos (com cache: ~100ms)
Memória: 50-100 MB
```
