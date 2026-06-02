import json
import os
import re
import time

import anthropic
import requests

_CATALOGO_CACHE = {'data': None, 'ts': 0.0}
_CATALOGO_TTL = 3600  # 1 hora

MAX_FAMILIA = 60   # máximo de produtos da família enviados ao agente
MAX_FALLBACK = 30  # se não achar família, envia os primeiros N


def _buscar_catalogo() -> list:
    now = time.time()
    if _CATALOGO_CACHE['data'] is None or now - _CATALOGO_CACHE['ts'] > _CATALOGO_TTL:
        resp = requests.get(
            'https://cemag.innovaro.com.br/api/publica/v1/tabelas/listarProdutos',
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        # aceita tanto lista direta quanto {"results": [...]} ou {"data": [...]}
        if isinstance(data, dict):
            data = data.get('results') or data.get('data') or data.get('produtos') or []
        _CATALOGO_CACHE['data'] = data if isinstance(data, list) else []
        _CATALOGO_CACHE['ts'] = now
    return _CATALOGO_CACHE['data']


def _codigo_campo(item: dict) -> str:
    """Retorna o código do produto independente do nome do campo."""
    for campo in ('codigo', 'code', 'recurso_codigo', 'produto_codigo', 'id'):
        v = item.get(campo)
        if v:
            return str(v).strip().upper()
    # pega o primeiro campo que pareça um código
    for v in item.values():
        if isinstance(v, str) and re.match(r'^[A-Z0-9]', v.strip().upper()):
            return v.strip().upper()
    return ''


def _prefixos(codigo: str) -> list[str]:
    """
    Gera prefixos progressivos do código para busca por família.
    Ex: 'AB-123-LA' → ['AB', 'AB-123', 'AB-123-LA']
    Funciona com separadores -, /, _ ou espaço.
    """
    partes = re.split(r'[-/_\s]+', codigo)
    prefixos = []
    acum = ''
    for p in partes:
        acum = f"{acum}-{p}" if acum else p
        prefixos.append(acum)
    return prefixos


def _filtrar_familia(catalogo: list, codigos_pedido: list[str]) -> list:
    """Filtra o catálogo aos produtos da mesma família dos itens do pedido."""
    if not codigos_pedido:
        return catalogo[:MAX_FALLBACK]

    # usa os 2 primeiros segmentos de cada código do pedido como base da família
    bases: set[str] = set()
    for cod in codigos_pedido:
        prefs = _prefixos(cod)
        # pega até os 2 primeiros segmentos
        bases.update(prefs[:2])

    familia = [
        item for item in catalogo
        if any(_codigo_campo(item).startswith(base) for base in bases)
    ]

    if not familia:
        return catalogo[:MAX_FALLBACK]

    return familia[:MAX_FAMILIA]


_COLOR_SUFFIXES = frozenset({'AN', 'CO', 'VM', 'VJ', 'AV'})
_SENTINELAS_IA = frozenset({'NÃO ENCONTRADO', 'NÃO ENCONTRADO NO CATÁLOGO', '—', '-'})


def _normalizar_codigo(codigo: str) -> str:
    """Remove separadores e normaliza para comparação: 'AB-123 AN' → 'AB123AN'."""
    return re.sub(r'[-/_\s]+', '', str(codigo).strip().upper())


def _set_codigos_catalogo(catalogo: list) -> set[str]:
    s = {_normalizar_codigo(_codigo_campo(item)) for item in catalogo if _codigo_campo(item)}
    s.discard('')
    return s


def _validar_codigo_ia(codigo_ia: str, codigos_catalogo: set[str]) -> str:
    """
    Garante que o código sugerido pela IA exista no catálogo.
    Aceita:
      - sentinelas conhecidas (NÃO ENCONTRADO, —, etc.)
      - código normalizado presente no catálogo
      - código sem sufixo de cor presente no catálogo (variante cromática válida)
    Qualquer outra coisa → 'NÃO ENCONTRADO'.
    """
    if not codigo_ia:
        return '—'
    cod = codigo_ia.strip()
    if cod.upper() in _SENTINELAS_IA:
        return cod
    normalizado = _normalizar_codigo(cod)
    if not normalizado:
        return '—'
    if normalizado in codigos_catalogo:
        return cod
    # aceita variante cromática: base sem sufixo de cor deve existir no catálogo
    partes = re.split(r'[-/_\s]+', cod.strip().upper())
    if len(partes) > 1 and partes[-1] in _COLOR_SUFFIXES:
        base = _normalizar_codigo(' '.join(partes[:-1]))
        if base and base in codigos_catalogo:
            return cod
    return 'NÃO ENCONTRADO'


def _extrair_siglas(catalogo: list) -> dict[str, set]:
    """
    Constrói um dicionário de segmentos únicos por posição a partir de todos os
    códigos do catálogo. Ex: {0: {'AB', 'CD'}, 1: {'123', '456'}, 2: {'LA', 'VM'}}
    """
    por_posicao: dict[int, set] = {}
    for item in catalogo:
        cod = _codigo_campo(item)
        if not cod:
            continue
        partes = re.split(r'[-/_\s]+', cod)
        for pos, parte in enumerate(partes):
            por_posicao.setdefault(pos, set()).add(parte)
    return por_posicao


def _resumir_catalogo(catalogo_completo: list, codigos_pedido: list[str]) -> str:
    """
    Retorna uma representação compacta:
    1. Códigos da família (sem descrição para economizar tokens)
    2. Siglas por posição extraídas apenas da família (≤8 valores únicos por posição)
    """
    familia = _filtrar_familia(catalogo_completo, codigos_pedido)

    # apenas os códigos, sem descrição
    linhas_familia = [f"  {_codigo_campo(item)}" for item in familia if _codigo_campo(item)]
    familia_txt = '\n'.join(linhas_familia) or '  (nenhum produto da família encontrado)'

    # siglas só da família e apenas posições com poucos valores (sufixos de cor/variante)
    siglas = _extrair_siglas(familia)
    siglas_linhas = [
        f"  Posição {pos}: {', '.join(sorted(vals))}"
        for pos, vals in sorted(siglas.items())
        if len(vals) <= 8
    ]
    siglas_txt = '\n'.join(siglas_linhas) or '  (não foi possível extrair siglas)'

    return (
        f"--- Códigos da família ({len(familia)} de {len(catalogo_completo)} total) ---\n"
        f"{familia_txt}\n\n"
        f"--- Siglas por posição (apenas sufixos com ≤8 variantes) ---\n"
        f"{siglas_txt}"
    )


SYSTEM_PROMPT = (
    "Você é um assistente especializado em conferência de pedidos industriais da empresa Cemag. "
    "Sua função é analisar os itens de um pedido junto com a observação do representante de vendas "
    "e identificar divergências E correções necessárias nos códigos de produtos.\n\n"
    "REGRAS ABSOLUTAS:\n"
    "1. NUNCA invente, sugira ou mencione códigos que não estejam no catálogo de produtos fornecido.\n"
    "2. Cada segmento do código representa uma característica (cor, modelo, tamanho, etc.). "
    "Use apenas siglas e valores que existem no catálogo.\n"
    "3. OBSERVAÇÃO É FONTE DE CORREÇÃO: leia atentamente a observação do representante. "
    "Se ela mencionar uma característica ausente no código ERP/CRM (ex: 'mangueiras maiores', 'MM', "
    "'cor azul', etc.), isso indica que o código precisa ser corrigido. "
    "Aplique a correção no campo 'ia' SE o código resultante existir no catálogo. "
    "Caso contrário, escreva 'NÃO ENCONTRADO'. "
    "Marque divergencia=true para o item afetado e use status DIVERGÊNCIA.\n"
    "4. Responda em português brasileiro, de forma objetiva.\n"
    "5. Use status CONSISTENTE somente quando ERP e CRM batem E a observação não indica nenhuma "
    "modificação a ser aplicada nos códigos.\n"
    "6. TABELA DE CORES — use SEMPRE este mapeamento:\n"
    "   AN = Azul | CO = Cinza | VM = Vermelho | VJ = Verde | AV = Amarelo\n"
    "   Sem sigla de cor no final do código = Laranja (cor padrão).\n"
    "7. SIGLAS TÉCNICAS DE CARRETAS:\n"
    "   Mola/Freio (posições internas): SS = Sem mola/Sem freio | CS = Com mola/Sem freio | "
    "SC = Sem mola/Com freio | CC = Com mola/Com freio.\n"
    "   MM = Mangueiras Maiores (mangueiras de comprimento maior, sigla inserida no código). "
    "Palavras como 'mangueiras maiores', 'mang. maiores', 'c/ MM' na observação indicam uso de MM.\n"
    "8. COMPARE as quantidades usando a QUANTIDADE TOTAL por código: "
    "o ERP já envia a soma de todas as linhas do mesmo produto (campo 'Qtd total'). "
    "Divergência de quantidade só existe quando a Qtd total do ERP for DIFERENTE da Qtd do CRM.\n"
    "9. DIVERGÊNCIA existe quando: (a) código, cor ou quantidade diferem entre CRM e ERP; "
    "OU (b) a observação indica uma modificação (MM, cor, modelo, etc.) ausente no código ERP/CRM. "
    "Em ambos os casos marque divergencia=true e sugira o código corrigido no campo 'ia'."
)


def _agregar_erp(itens: list) -> list[dict]:
    """Agrupa itens do ERP pelo código, somando quantidades.
    O ERP costuma criar uma linha por unidade; o CRM agrupa tudo em uma linha.
    """
    agrupado: dict[str, dict] = {}
    for item in itens:
        cod = str(item.get('recurso_codigo') or 'N/D').strip()
        nome = str(item.get('recurso_nome') or 'N/D').strip()
        try:
            qtd = float(item.get('quantidade') or 0)
        except (TypeError, ValueError):
            qtd = 0.0
        if cod not in agrupado:
            agrupado[cod] = {'nome': nome, 'qtd': 0.0}
        agrupado[cod]['qtd'] += qtd
    return [{'recurso_codigo': cod, 'recurso_nome': info['nome'], 'quantidade': info['qtd']}
            for cod, info in agrupado.items()]


def _montar_prompt(
    itens_innovaro: list,
    itens_ploomes: list,
    observacoes: list,
    catalogo_resumo: str,
) -> str:
    erp_agregado = _agregar_erp(itens_innovaro)
    linhas_innovaro = '\n'.join(
        f"  {i+1}. Código: {item['recurso_codigo']} | "
        f"Nome: {item['recurso_nome']} | "
        f"Qtd total: {item['quantidade']:.0f}"
        for i, item in enumerate(erp_agregado)
    ) or '  Nenhum item Innovaro informado.'

    linhas_ploomes = '\n'.join(
        f"  {i+1}. Código: {item.get('codigo_produto', 'N/D')} | "
        f"Cor: {item.get('cor', 'N/D')} | "
        f"Qtd: {item.get('quantidade') if item.get('quantidade') is not None else 'N/D'}"
        for i, item in enumerate(itens_ploomes)
    ) or '  Nenhum item Ploomes informado.'

    obs_unicas = list(dict.fromkeys(
        str(o).strip() for o in observacoes if str(o).strip()
    ))
    linhas_obs = '\n'.join(f"  - {o}" for o in obs_unicas) or '  Sem observação.'

    return (
        f"=== CATÁLOGO DE PRODUTOS (use APENAS estes códigos e siglas) ===\n"
        f"{catalogo_resumo}\n\n"
        f"=== ITENS DO PEDIDO NO ERP (Innovaro) ===\n"
        f"{linhas_innovaro}\n\n"
        f"=== ITENS DO PEDIDO NO CRM (Ploomes) ===\n"
        f"{linhas_ploomes}\n\n"
        f"=== OBSERVAÇÃO DO REPRESENTANTE DE VENDAS ===\n"
        f"{linhas_obs}\n\n"
        f"Retorne APENAS um objeto JSON válido, sem markdown, sem texto antes ou depois:\n"
        f"{{\n"
        f"  \"itens\": [\n"
        f"    {{\n"
        f"      \"erp\": \"código ERP | Qtd: X  (use '—' se não houver item)\",\n"
        f"      \"crm\": \"código CRM | COR | Qtd: X  (use '—' se não houver item)\",\n"
        f"      \"ia\": \"código corrigido com sigla de cor aplicada\",\n"
        f"      \"divergencia\": false\n"
        f"    }}\n"
        f"  ],\n"
        f"  \"status\": \"CONSISTENTE\",\n"
        f"  \"resumo\": \"explicação breve em uma linha\"\n"
        f"}}\n\n"
        f"Regras obrigatórias para o campo 'ia':\n"
        f"- SEMPRE escreva um código — se não há divergência, reescreva o código com a cor aplicada.\n"
        f"- Aplique sigla de cor ao FINAL do código: AZUL→AN, CINZA→CO, VERMELHO→VM, VERDE→VJ, AMARELO→AV, LARANJA→sem sigla.\n"
        f"- Emparelhe itens ERP e CRM na mesma linha quando correspondem ao mesmo produto.\n"
        f"- Se código corrigido não existe no catálogo, escreva 'NÃO ENCONTRADO'.\n"
        f"- Marque divergencia=true somente quando código, quantidade ou cor diferem entre ERP e CRM.\n"
        f"- status deve ser 'CONSISTENTE' ou 'DIVERGÊNCIA'."
    )


def analisar_pedido(
    itens_innovaro: list,
    itens_ploomes: list,
    observacoes: list,
) -> str:
    try:
        catalogo = _buscar_catalogo()
    except Exception as exc:
        raise RuntimeError(f"Falha ao buscar catálogo de produtos: {exc}") from exc

    codigos_pedido = []
    for item in itens_innovaro:
        cod = str(item.get('recurso_codigo') or '').strip().upper()
        if cod:
            codigos_pedido.append(cod)
    for item in itens_ploomes:
        cod = str(item.get('codigo_produto') or '').strip().upper()
        if cod:
            codigos_pedido.append(cod)

    catalogo_resumo = _resumir_catalogo(catalogo, codigos_pedido)

    client = anthropic.Anthropic(api_key=os.environ['ANTHROPIC_API_KEY'])
    prompt = _montar_prompt(itens_innovaro, itens_ploomes, observacoes, catalogo_resumo)

    msg = client.messages.create(
        model='claude-haiku-4-5-20251001',
        max_tokens=600,
        system=SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': prompt}],
    )
    text = msg.content[0].text.strip()

    # remove markdown code fences if present
    text = re.sub(r'^```[a-z]*\n?', '', text)
    text = re.sub(r'\n?```$', '', text.strip())

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict) and isinstance(parsed.get('itens'), list):
            codigos_set = _set_codigos_catalogo(catalogo)
            for item in parsed['itens']:
                if isinstance(item, dict) and item.get('ia'):
                    item['ia'] = _validar_codigo_ia(str(item['ia']), codigos_set)
            return parsed
    except (json.JSONDecodeError, ValueError):
        pass

    return {'analise': text, 'status': 'ERRO'}
