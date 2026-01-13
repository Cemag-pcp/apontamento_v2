from cachetools import LRUCache
from datetime import datetime, timedelta
from core.models import ConsultaSaldoInnovaro

# Cache aumentado para 5000 entradas
cache = LRUCache(maxsize=5000)

def busca_saldo_recurso_central(codigos):
    """
    Busca saldo de recursos do almoxarifado central da tabela ConsultaSaldoInnovaro.
    
    Args:
        codigos: List ou Set de códigos dos itens
        
    Returns:
        Tuple: (dict com saldos, data do último saldo)
        
    Otimizações:
    - Cache de 5000 entradas
    - Busca direta no banco de dados (sem API externa)
    - Dict direto em vez de DataFrame
    """
    
    # Converter para tupla para usar como chave de cache
    codigos_tupla = tuple(sorted(set(codigos)))
    
    # Verificar cache
    if codigos_tupla in cache:
        print(f'✓ Cache hit: {len(codigos)} códigos')
        return cache[codigos_tupla]
    
    print(f'⚠ Cache miss: buscando {len(codigos)} códigos do banco de dados')
    
    try:
        # Normalizar códigos para busca (remover espaços)
        codigos_set = set(str(cod).strip() for cod in codigos)
        
        # Buscar dados da tabela ConsultaSaldoInnovaro
        registros = ConsultaSaldoInnovaro.objects.filter(
            codigo__in=codigos_set
        ).values('codigo', 'saldo', 'data_ultimo_saldo')
        
        # Construir dicionário de saldos
        saldo_dict = {}
        codigos_encontrados = []
        data_ultimo_saldo = "N/A"
        
        print(f"\n{'='*80}")
        print(f"📋 BUSCANDO NA TABELA ConsultaSaldoInnovaro:")
        print(f"   Total de códigos a buscar: {len(codigos_set)}")
        
        for registro in registros:
            codigo = str(registro['codigo']).strip()
            saldo = registro['saldo']
            
            if registro['data_ultimo_saldo']:
                data_ultimo_saldo = registro['data_ultimo_saldo']
            
            saldo_dict[codigo] = saldo
            codigos_encontrados.append(codigo)
            
            # Debug: mostrar primeiros 10 resultados
            if len(codigos_encontrados) <= 10:
                print(f"   ✓ {codigo}: {saldo}")
        
        codigos_nao_encontrados = [cod for cod in codigos_set if cod not in codigos_encontrados]
        print(f"{'='*80}\n")
        
        print(f"✓ Saldo recuperado para {len(saldo_dict)} itens, {len(codigos_nao_encontrados)} não encontrados")
        if codigos_nao_encontrados and len(codigos_nao_encontrados) <= 5:
            print(f"   Códigos não encontrados: {codigos_nao_encontrados}")
        
        # Armazenar no cache e retornar
        resultado = (saldo_dict, data_ultimo_saldo)
        cache[codigos_tupla] = resultado
        
        return resultado
        
    except Exception as exc:
        print(f"❌ Erro ao buscar saldo: {str(exc)}")
        import traceback
        traceback.print_exc()
        return {}, "Erro ao conectar"
 

