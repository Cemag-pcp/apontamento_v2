import json
import os
import re
import time

import anthropic
import requests

_CATALOGO_CACHE = {'data': None, 'ts': 0.0}
_CATALOGO_TTL = 3600

MAX_AMOSTRA = 18   # códigos enviados ao agente como exemplos
MAX_FALLBACK = 30  # fallback se família não encontrada

_COLOR_SUFFIXES = frozenset({'AN', 'CO', 'VM', 'VJ', 'AV'})
_SENTINELAS_IA = frozenset({'NÃO ENCONTRADO', 'NÃO ENCONTRADO NO CATÁLOGO', '—', '-'})

# ──────────────────────────────────────────────────────────────────────────────
# ANATOMIA DOS CÓDIGOS — enviada ao agente; define a ordem obrigatória dos
# segmentos e o significado de cada sigla.
# ──────────────────────────────────────────────────────────────────────────────
ANATOMIA_CODIGOS = """\
ANATOMIA DOS CÓDIGOS DE PRODUTO CEMAG
======================================
Segmentos separados por hífen (-), sempre nesta ordem:

  [1] FAMÍLIA   (obrigatório) — 2-4 letras iniciais; identifica a linha do produto.
                Ex: CA, CAG, CAP, MB

  [2] MODELO    (obrigatório) — número ou dimensão do modelo.
                Ex: 100, 250, 400, 1000

  [3] VARIANTE  (opcional) — combinação mola + freio, vem ANTES de MM e COR:
                SS = Sem mola / Sem freio
                CS = Com mola / Sem freio
                SC = Sem mola / Com freio
                CC = Com mola / Com freio

  [4] OPÇÃO MM  (opcional) — vem DEPOIS da variante e ANTES da cor:
                MM = Mangueiras Maiores (mangueiras de comprimento estendido)
                Palavras como "mangueiras maiores", "mang. maiores", "c/ MM"
                na observação indicam que MM deve ser inserido aqui.

  [5] COR       (opcional, SEMPRE o ÚLTIMO segmento):
                AN=Azul  CO=Cinza  VM=Vermelho  VJ=Verde  AV=Amarelo
                Ausência de cor = Laranja (cor padrão, sem sigla)

Fórmula: FAMÍLIA-MODELO[-VARIANTE][-MM][-COR]

Exemplos de montagem:
  CA-250           → Carreta 250, Laranja
  CA-250-CS        → Carreta 250, Com mola/Sem freio, Laranja
  CA-250-CS-AN     → Carreta 250, Com mola/Sem freio, Azul
  CA-250-CS-MM     → Carreta 250, Com mola/Sem freio, Mangueiras Maiores, Laranja
  CA-250-CS-MM-AN  → Carreta 250, Com mola/Sem freio, Mangueiras Maiores, Azul
"""


def _buscar_catalogo() -> list:
    now = time.time()
    if _CATALOGO_CACHE['data'] is None or now - _CATALOGO_CACHE['ts'] > _CATALOGO_TTL:
        resp = requests.get(
            'https://cemag.innovaro.com.br/api/publica/v1/tabelas/listarProdutos',
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict):
            data = data.get('results') or data.get('data') or data.get('produtos') or []
        _CATALOGO_CACHE['data'] = data if isinstance(data, list) else []
        _CATALOGO_CACHE['ts'] = now
    return _CATALOGO_CACHE['data']


def _codigo_campo(item: dict) -> str:
    for campo in ('codigo', 'code', 'recurso_codigo', 'produto_codigo', 'id'):
        v = item.get(campo)
        if v:
            return str(v).strip().upper()
    for v in item.values():
        if isinstance(v, str) and re.match(r'^[A-Z0-9]', v.strip().upper()):
            return v.strip().upper()
    return ''


def _extrair_apenas_codigos(catalogo: list) -> list[str]:
    """Extrai somente os códigos únicos do JSON do catálogo, descartando metadados."""
    vistos: set[str] = set()
    codigos: list[str] = []
    for item in catalogo:
        cod = _codigo_campo(item)
        if cod and cod not in vistos:
            codigos.append(cod)
            vistos.add(cod)
    return codigos


def _normalizar_codigo(codigo: str) -> str:
    return re.sub(r'[-/_\s]+', '', str(codigo).strip().upper())


def _prefixos(codigo: str) -> list[str]:
    partes = re.split(r'[-/_\s]+', codigo)
    prefixos = []
    acum = ''
    for p in partes:
        acum = f"{acum}-{p}" if acum else p
        prefixos.append(acum)
    return prefixos


def _filtrar_familia_codigos(todos_codigos: list[str], codigos_pedido: list[str]) -> list[str]:
    """Filtra para os códigos da mesma família dos itens do pedido."""
    if not codigos_pedido:
        return todos_codigos[:MAX_FALLBACK]

    bases: set[str] = set()
    for cod in codigos_pedido:
        prefs = _prefixos(cod)
        bases.update(prefs[:2])

    familia = [c for c in todos_codigos if any(c.startswith(base) for base in bases)]
    return familia if familia else todos_codigos[:MAX_FALLBACK]


def _selecionar_amostra(codigos_familia: list[str], codigos_pedido: list[str]) -> list[str]:
    """
    Seleciona até MAX_AMOSTRA códigos representativos para enviar ao agente.
    Prioridade:
      1. Códigos idênticos aos do pedido
      2. Variantes da mesma base (diferentes cores)
      3. Exemplos com MM
      4. Um exemplo de cada sufixo de cor
      5. Exemplos base sem cor (complemento)
    """
    amostra: list[str] = []
    pedido_norm = {_normalizar_codigo(c) for c in codigos_pedido}

    def _add(cod: str):
        if cod not in amostra and len(amostra) < MAX_AMOSTRA:
            amostra.append(cod)

    # 1. Códigos do próprio pedido
    for cod in codigos_familia:
        if _normalizar_codigo(cod) in pedido_norm:
            _add(cod)

    # 2. Variantes da mesma base (remove sufixo de cor e compara)
    for pedido_cod in codigos_pedido:
        base = re.sub(r'[-/_\s]+(?:AN|CO|VM|VJ|AV)$', '', pedido_cod.strip().upper())
        for cod in codigos_familia:
            if base and cod.startswith(base):
                _add(cod)

    # 3. Exemplos com MM
    for cod in codigos_familia:
        if 'MM' in re.split(r'[-/_\s]+', cod):
            _add(cod)

    # 4. Um exemplo de cada cor disponível
    cores_vistas: set[str] = set()
    for cod in codigos_familia:
        partes = re.split(r'[-/_\s]+', cod)
        cor = partes[-1] if partes else ''
        if cor in _COLOR_SUFFIXES and cor not in cores_vistas:
            _add(cod)
            cores_vistas.add(cor)

    # 5. Exemplos base sem sufixo de cor (até completar MAX_AMOSTRA)
    for cod in codigos_familia:
        partes = re.split(r'[-/_\s]+', cod)
        if not partes or partes[-1] not in _COLOR_SUFFIXES:
            _add(cod)

    return amostra


def _set_codigos_catalogo(todos_codigos: list[str]) -> set[str]:
    s = {_normalizar_codigo(c) for c in todos_codigos}
    s.discard('')
    return s


def _validar_codigo_ia(codigo_ia: str, codigos_catalogo: set[str]) -> str:
    """
    Valida o código sugerido pelo agente contra o catálogo completo.
    Aceita: sentinelas conhecidas, código exato, e base+cor quando a base existe.
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
        base = _normalizar_codigo('-'.join(partes[:-1]))
        if base and base in codigos_catalogo:
            return cod
    return 'NÃO ENCONTRADO'


def _montar_contexto_catalogo(todos_codigos: list[str], codigos_pedido: list[str]) -> str:
    """
    Monta o contexto do catálogo para o agente:
    anatomia dos segmentos + amostra representativa de códigos da família.
    O agente usa a anatomia para MONTAR o código; a validação usa o catálogo completo.
    """
    familia = _filtrar_familia_codigos(todos_codigos, codigos_pedido)
    amostra = _selecionar_amostra(familia, codigos_pedido)

    linhas_amostra = '\n'.join(f"  {c}" for c in amostra)

    return (
        f"{ANATOMIA_CODIGOS}\n"
        f"AMOSTRA DA FAMÍLIA RELEVANTE — {len(amostra)} de {len(familia)} na família "
        f"({len(todos_codigos)} códigos no catálogo total):\n"
        f"{linhas_amostra}\n\n"
        f"ATENÇÃO: Esta amostra ilustra o padrão. Seu código sugerido no campo 'ia' será "
        f"validado automaticamente contra os {len(todos_codigos)} códigos reais do catálogo. "
        f"Monte o código seguindo a ANATOMIA acima — não se limite à amostra."
    )


SYSTEM_PROMPT = """\
Você é um assistente especializado em conferência de pedidos industriais da empresa Cemag.

OBJETIVO PRINCIPAL:
O representante de vendas pode informar na observação características do produto \
(cor, mangueiras maiores, variante mola/freio, etc.) que DEVERIAM estar no código, \
mas foram omitidas ou erradas ao lançar no ERP/CRM. \
Para o ERP, o código deve ir COMPLETO — qualquer característica ausente causa erro de produção.

Sua função: ler a observação + códigos atuais → determinar o código CORRETO → \
comparar com o ERP → informar se o ERP precisa ou não ser corrigido.

FLUXO OBRIGATÓRIO:

PASSO 1 — Decodifique a observação:
  Liste as características mencionadas e suas siglas.
  Ex: "mangueiras maiores"→MM | "azul"→AN | "com mola/sem freio"→CS
  Ignore frases que não alteram código ("conforme pedido", "frete CIF", etc.).

PASSO 2 — Monte o código CORRETO com base na observação + código existente:
  Use a ANATOMIA DOS CÓDIGOS. Ordem obrigatória: FAMÍLIA→MODELO→VARIANTE→MM→COR.

PASSO 3 — Compare código CORRETO com o código ERP:
  ├─ ERP já tem o código correto? → divergencia=false  (ERP está OK)
  └─ ERP está errado/incompleto?  → divergencia=true   (ERP precisa ser corrigido)

PASSO 4 — Compare código CORRETO com o código CRM (independente do ERP):
  ├─ CRM tem o código correto? → crm_divergencia=false
  └─ CRM está errado?          → crm_divergencia=true  (apenas informativo)

CRITÉRIO DE STATUS:
  status='DIVERGÊNCIA'  → algum item tem divergencia=true  (ERP precisa ser corrigido)
  status='CONSISTENTE'  → todos os itens têm divergencia=false (ERP está correto em tudo)
  ATENÇÃO: CRM errado com ERP certo NÃO gera status=DIVERGÊNCIA.

REGRAS:
1. Nunca invente siglas fora da ANATOMIA fornecida.
2. COR vai SEMPRE no último segmento: AN=Azul CO=Cinza VM=Vermelho VJ=Verde AV=Amarelo \
   (sem sufixo = Laranja).
3. O código em 'ia' será validado automaticamente. \
   Escreva 'NÃO ENCONTRADO' só se não for possível montar um código válido.
4. Quantidades: compare pela Qtd total do ERP (já somada). \
   divergencia=true por quantidade só quando Qtd ERP ≠ Qtd CRM E o ERP está errado.
5. Responda em português brasileiro.\
"""


def _agregar_erp(itens: list) -> list[dict]:
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
    contexto_catalogo: str,
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
        f"=== OBSERVAÇÃO DO REPRESENTANTE DE VENDAS (leia primeiro) ===\n"
        f"{linhas_obs}\n\n"
        f"=== GUIA DE CÓDIGOS DE PRODUTO ===\n"
        f"{contexto_catalogo}\n\n"
        f"=== ITENS DO PEDIDO NO ERP (Innovaro) ===\n"
        f"{linhas_innovaro}\n\n"
        f"=== ITENS DO PEDIDO NO CRM (Ploomes) ===\n"
        f"{linhas_ploomes}\n\n"
        f"Siga o FLUXO OBRIGATÓRIO e retorne APENAS um objeto JSON válido,\n"
        f"sem markdown, sem texto antes ou depois:\n"
        f"{{\n"
        f"  \"itens\": [\n"
        f"    {{\n"
        f"      \"erp\": \"código ERP | Qtd: X  (use '—' se não houver)\",\n"
        f"      \"crm\": \"código CRM | COR | Qtd: X  (use '—' se não houver)\",\n"
        f"      \"ia\": \"código CORRETO montado: FAMÍLIA-MODELO-[VARIANTE]-[MM]-[COR]\",\n"
        f"      \"motivo\": \"o que foi detectado na observação e/ou diferença CRM; '—' se tudo OK\",\n"
        f"      \"divergencia\": false,\n"
        f"      \"crm_divergencia\": false\n"
        f"    }}\n"
        f"  ],\n"
        f"  \"status\": \"CONSISTENTE\",\n"
        f"  \"resumo\": \"resumo geral em uma linha\"\n"
        f"}}\n\n"
        f"Regras para os campos booleanos:\n"
        f"- divergencia=true → o ERP está ERRADO (ERP ≠ código correto). ERP precisa ser corrigido.\n"
        f"- divergencia=false → o ERP está CORRETO (ERP = código correto). Não precisa ser corrigido.\n"
        f"- crm_divergencia=true → o CRM difere do código correto (apenas informativo, não gera status DIVERGÊNCIA).\n"
        f"- status='DIVERGÊNCIA' somente quando algum item tiver divergencia=true.\n"
        f"- 'ia' sempre presente: se sem divergência, escreva o código ERP atual.\n"
        f"- Emparelhe ERP e CRM na mesma linha quando se referem ao mesmo produto."
    )


def analisar_pedido(
    itens_innovaro: list,
    itens_ploomes: list,
    observacoes: list,
) -> dict:
    try:
        catalogo = _buscar_catalogo()
    except Exception as exc:
        raise RuntimeError(f"Falha ao buscar catálogo de produtos: {exc}") from exc

    todos_codigos = _extrair_apenas_codigos(catalogo)

    codigos_pedido: list[str] = []
    for item in itens_innovaro:
        cod = str(item.get('recurso_codigo') or '').strip().upper()
        if cod:
            codigos_pedido.append(cod)
    for item in itens_ploomes:
        cod = str(item.get('codigo_produto') or '').strip().upper()
        if cod:
            codigos_pedido.append(cod)

    contexto_catalogo = _montar_contexto_catalogo(todos_codigos, codigos_pedido)

    client = anthropic.Anthropic(api_key=os.environ['ANTHROPIC_API_KEY'])
    prompt = _montar_prompt(itens_innovaro, itens_ploomes, observacoes, contexto_catalogo)

    msg = client.messages.create(
        model='claude-haiku-4-5-20251001',
        max_tokens=600,
        system=SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': prompt}],
    )
    text = msg.content[0].text.strip()

    text = re.sub(r'^```[a-z]*\n?', '', text)
    text = re.sub(r'\n?```$', '', text.strip())

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict) and isinstance(parsed.get('itens'), list):
            codigos_set = _set_codigos_catalogo(todos_codigos)
            for item in parsed['itens']:
                if isinstance(item, dict) and item.get('ia'):
                    item['ia'] = _validar_codigo_ia(str(item['ia']), codigos_set)
            return parsed
    except (json.JSONDecodeError, ValueError):
        pass

    return {'analise': text, 'status': 'ERRO'}
