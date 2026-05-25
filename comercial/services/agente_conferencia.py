import os
import re
import time

import anthropic
import requests

_CATALOGO_CACHE = {'data': None, 'ts': 0.0}
_CATALOGO_TTL = 3600  # 1 hora

MAX_FAMILIA = 300   # máximo de produtos da família enviados ao agente
MAX_FALLBACK = 100  # se não achar família, envia os primeiros N


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
    1. Produtos da família dos itens do pedido (lista)
    2. Dicionário de siglas únicas por posição do código (de todo o catálogo)
    """
    familia = _filtrar_familia(catalogo_completo, codigos_pedido)
    siglas = _extrair_siglas(catalogo_completo)

    # formata a lista de produtos da família
    linhas_familia = []
    for item in familia:
        cod = _codigo_campo(item)
        desc = ''
        for campo in ('descricao', 'description', 'nome', 'name', 'recurso_nome'):
            v = item.get(campo)
            if v:
                desc = str(v).strip()
                break
        linhas_familia.append(f"  {cod}" + (f" — {desc}" if desc else ''))

    familia_txt = '\n'.join(linhas_familia) or '  (nenhum produto da família encontrado)'

    # formata o dicionário de siglas
    siglas_linhas = []
    for pos in sorted(siglas):
        valores = sorted(siglas[pos])
        # pula posições com muitos valores (provavelmente números de série / IDs)
        if len(valores) > 80:
            continue
        siglas_linhas.append(f"  Posição {pos}: {', '.join(valores)}")

    siglas_txt = '\n'.join(siglas_linhas) or '  (não foi possível extrair siglas)'

    return (
        f"--- Produtos da família do pedido ({len(familia)} de {len(catalogo_completo)} total) ---\n"
        f"{familia_txt}\n\n"
        f"--- Dicionário de segmentos/siglas por posição no código ---\n"
        f"{siglas_txt}"
    )


SYSTEM_PROMPT = (
    "Você é um assistente especializado em conferência de pedidos industriais da empresa Cemag. "
    "Sua função é analisar os itens de um pedido junto com a observação do representante de vendas "
    "e identificar possíveis divergências ou correções necessárias nos códigos de produtos.\n\n"
    "REGRAS ABSOLUTAS:\n"
    "1. NUNCA invente, sugira ou mencione códigos que não estejam no catálogo de produtos fornecido.\n"
    "2. Cada segmento do código representa uma característica (cor, modelo, tamanho, etc.). "
    "Use apenas siglas e valores que existem no catálogo.\n"
    "3. Se a observação mencionar uma característica que conflita com o produto selecionado "
    "(ex: produto laranja mas observação diz vermelho), aponte o código correto APENAS se ele "
    "existir no catálogo. Caso contrário, informe que não encontrou.\n"
    "4. Responda em português brasileiro, de forma objetiva.\n"
    "5. Se não houver divergências, informe que o pedido está consistente."
)


def _montar_prompt(
    itens_innovaro: list,
    itens_ploomes: list,
    observacoes: list,
    catalogo_resumo: str,
) -> str:
    linhas_innovaro = '\n'.join(
        f"  {i+1}. Código: {item.get('recurso_codigo', 'N/D')} | "
        f"Nome: {item.get('recurso_nome', 'N/D')} | "
        f"Série: {item.get('numero_serie', '') or 'sem série'}"
        for i, item in enumerate(itens_innovaro)
    ) or '  Nenhum item Innovaro informado.'

    linhas_ploomes = '\n'.join(
        f"  {i+1}. Código Produto: {item.get('codigo_produto', 'N/D')} | "
        f"Cor: {item.get('cor', 'N/D')}"
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
        f"Com base no catálogo acima:\n"
        f"1. Verifique divergências entre os itens selecionados e a observação do representante.\n"
        f"2. Se houver divergência, aponte o código correto (somente se existir no catálogo).\n"
        f"3. Explique as siglas relevantes do código.\n"
        f"4. Estruture a resposta em: Análise, Divergências (se houver) e Sugestão de código correto."
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
        max_tokens=1200,
        system=SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': prompt}],
    )
    return msg.content[0].text
