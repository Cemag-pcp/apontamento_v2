"""
Conferência de pedido: verifica se o código do ERP contempla o que o
representante pediu na observação (cor, mola/freio, pneu, mangueiras maiores).

Fluxo:
  1. A IA apenas LÊ a observação e extrai as características pedidas por item.
  2. O item do ERP é localizado no catálogo do Innovaro (atributos estruturados).
  3. Aplica-se as características pedidas sobre os atributos do item e busca-se
     no catálogo o produto com essa combinação → código correto.
  4. Compara-se código correto × ERP × CRM de forma determinística.
"""
import difflib
import os
import re
import time
import unicodedata

import anthropic
import requests

_CATALOGO_URL = 'https://cemag.innovaro.com.br/api/publica/v1/tabelas/listarProdutos'
_CATALOGO_CACHE = {'data': None, 'ts': 0.0}
_CATALOGO_TTL = 3600

_CORES = ('Laranja', 'Vermelha', 'Azul', 'Verde', 'Amarela', 'Cinza')
_MANG_MAIORES = 'MANG. MAIORES'
# atributos que a observação não altera: o produto correto tem de mantê-los
_ATRIBUTOS_FIXOS = ('modelo', 'classe', 'descGenerica', 'rodado', 'eixo', 'tamanho')


_SIGLAS_COR = {'AN': 'Azul', 'CO': 'Cinza', 'CE': 'Cinza', 'VM': 'Vermelha', 'VJ': 'Verde', 'AV': 'Amarela', 'LJ': 'Laranja'}
_RE_PNEU = re.compile(r'^P(\d+(?:\.\d+)?)(\(I\)|IMP|\(R\))?$')


def _corrigir_atributos(produto: dict) -> dict:
    """
    O cadastro do Innovaro tem campos inconsistentes com o código (ex.: código
    P750(I) com pneu='750(R)', sufixo AN com cor='Laranja'). O código é o que vai
    para a produção, então os segmentos dele prevalecem sobre os campos.
    """
    p = dict(produto)
    tokens = str(p['codigo']).upper().split()

    cor = next((_SIGLAS_COR[t] for t in tokens if t in _SIGLAS_COR), None)
    if cor:
        p['cor'] = cor
    elif p.get('cor'):
        p['cor'] = 'Laranja'  # sem sigla = cor padrão

    for t in tokens:
        m = _RE_PNEU.match(t)
        if not m:
            continue
        numero, tipo = m.group(1), {'(I)': '(I)', 'IMP': '(I)', '(R)': '(R)'}.get(m.group(2) or '', '')
        atual = p.get('pneu') or ''
        if not (atual.startswith(numero) and (not tipo or atual.endswith(tipo))):
            p['pneu'] = numero + tipo
        break

    mola_freio = next((t for t in tokens if t in ('SS', 'SC', 'CS', 'CC')), None)
    if mola_freio:
        p['molaFreio'] = mola_freio

    if 'MM' in tokens and _MANG_MAIORES not in _funcionalidades(p):
        p['funcionalidade'] = ' + '.join(sorted(_funcionalidades(p) | {_MANG_MAIORES}))
    return p


def _buscar_catalogo() -> list[dict]:
    now = time.time()
    if _CATALOGO_CACHE['data'] is None or now - _CATALOGO_CACHE['ts'] > _CATALOGO_TTL:
        resp = requests.get(_CATALOGO_URL, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict):
            data = data.get('produtos') or data.get('results') or data.get('data') or []
        _CATALOGO_CACHE['data'] = [
            _corrigir_atributos(p) for p in data if isinstance(p, dict) and p.get('codigo')
        ]
        _CATALOGO_CACHE['ts'] = now
    return _CATALOGO_CACHE['data']


def _normalizar_codigo(codigo) -> str:
    return re.sub(r'[-/_\s]+', '', str(codigo or '').strip().upper())


def _sem_acento(texto: str) -> str:
    return unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode().lower()


def _cor_canonica(valor) -> str | None:
    """'VERMELHA', 'vermelho', 'Vermelha' → 'Vermelha'. 'Sem cor'/'padrão' → 'Laranja' (cor padrão, sem sigla)."""
    v = _sem_acento(str(valor or '').strip())
    if not v:
        return None
    if v.startswith(('sem cor', 's/ cor', 's/cor', 'padrao', 'cor padrao')):
        return 'Laranja'
    for cor in _CORES:
        if v[:4] == _sem_acento(cor)[:4]:
            return cor
    return None


def _funcionalidades(produto: dict) -> frozenset:
    return frozenset(
        p.strip() for p in str(produto.get('funcionalidade') or '').split('+') if p.strip()
    )


def _parse_qtd(valor) -> float:
    try:
        return float(valor or 0)
    except (TypeError, ValueError):
        return 0.0


def _agregar(itens: list, campo_codigo: str) -> list[dict]:
    """Agrupa itens pelo código somando a quantidade."""
    agrupado: dict[str, dict] = {}
    for item in itens:
        cod = str(item.get(campo_codigo) or '').strip()
        if not cod:
            continue
        chave = _normalizar_codigo(cod)
        if chave not in agrupado:
            agrupado[chave] = {**item, 'codigo': cod, 'quantidade': 0.0}
        agrupado[chave]['quantidade'] += _parse_qtd(item.get('quantidade'))
    return list(agrupado.values())


# ──────────────────────────────────────────────────────────────────────────────
# Extração das características pedidas (IA)
# ──────────────────────────────────────────────────────────────────────────────
_TOOL_NAME = 'registrar_caracteristicas'

_TOOL_EXTRACAO = {
    'name': _TOOL_NAME,
    'description': 'Registra as características de produto pedidas na observação, por item do pedido.',
    'input_schema': {
        'type': 'object',
        'properties': {
            'itens': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'codigo': {
                            'type': 'string',
                            'description': 'código do item do pedido, exatamente como listado',
                        },
                        'cor': {'type': ['string', 'null'], 'enum': [*_CORES, None]},
                        'mola': {'type': ['boolean', 'null'], 'description': 'true=com mola, false=sem mola'},
                        'freio': {'type': ['boolean', 'null'], 'description': 'true=com freio, false=sem freio'},
                        'pneu': {'type': ['boolean', 'null'], 'description': 'true=com pneus, false=sem pneus'},
                        'mangueiras_maiores': {'type': ['boolean', 'null']},
                        'trecho': {'type': 'string', 'description': 'trecho da observação que justifica'},
                    },
                    'required': ['codigo', 'cor', 'mola', 'freio', 'pneu', 'mangueiras_maiores', 'trecho'],
                },
            },
        },
        'required': ['itens'],
    },
}

SYSTEM_PROMPT = """\
Você lê a observação que o representante de vendas da Cemag escreveu no pedido e \
identifica quais características de produto ele pediu para cada item.

Para cada item do pedido, preencha:
- cor: Laranja, Vermelha, Azul, Verde, Amarela ou Cinza ("vermelho"→Vermelha, "amarelo"→Amarela).
  Laranja é a cor padrão: "sem cor", "s/ cor", "cor padrão" ou "laranja" → Laranja.
- mola: true se pediu "com mola"/"c/ mola", false se "sem mola"/"s/ mola".
- freio: true se pediu "com freio"/"c/ freio", false se "sem freio"/"s/ freio".
- pneu: true se pediu "com pneus"/"c/ pneus", false se "sem pneus"/"s/ pneus".
- mangueiras_maiores: true se pediu "mangueiras maiores", "mang. maiores" ou "MM".

Use null para tudo que NÃO foi mencionado — nunca deduza um valor padrão.
Ignore condições comerciais (pagamento, frete, prazo, desconto).
Se a observação não indicar a qual item se refere, aplique a todos os itens compatíveis.\
"""


# SS/SC/CS/CC soltos na observação; ignora UF ("Joinville/SC", "Itajaí - SC")
_RE_SIGLA_MOLA_FREIO = re.compile(r'(?<![/\w])(?<!-\s)(?<!-)\b(SS|SC|CS|CC)\b(?!\s*/)', re.IGNORECASE)


def _sigla_mola_freio(observacoes: list[str]) -> str | None:
    """
    Sigla de mola/freio escrita pelo representante (1ª letra = mola, 2ª = freio;
    C=com, S=sem). Detectada por regra: a IA confunde com a sigla do código do item.
    Só vale se houver uma única sigla distinta na observação.
    """
    siglas = {m.group(1).upper() for o in observacoes for m in _RE_SIGLA_MOLA_FREIO.finditer(o)}
    return siglas.pop() if len(siglas) == 1 else None


def _extrair_caracteristicas(observacoes: list[str], itens_base: list[dict]) -> dict[str, dict]:
    """Retorna {codigo_normalizado: {cor, mola, freio, pneu, mangueiras_maiores, trecho}}."""
    if not observacoes or not itens_base:
        return {}

    linhas_itens = '\n'.join(
        f"  - {item['codigo']} | {item.get('nome') or ''}" for item in itens_base
    )
    linhas_obs = '\n'.join(f"  - {o}" for o in observacoes)
    prompt = (
        f"=== OBSERVAÇÃO DO REPRESENTANTE ===\n{linhas_obs}\n\n"
        f"=== ITENS DO PEDIDO ===\n{linhas_itens}\n\n"
        f"Registre as características com a ferramenta '{_TOOL_NAME}', uma entrada por item."
    )

    client = anthropic.Anthropic(api_key=os.environ['ANTHROPIC_API_KEY'], timeout=60)
    try:
        msg = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            tools=[_TOOL_EXTRACAO],
            tool_choice={'type': 'tool', 'name': _TOOL_NAME},
            messages=[{'role': 'user', 'content': prompt}],
        )
    except anthropic.APIError as exc:
        raise RuntimeError(f"Falha ao consultar a IA: {exc}") from exc

    if msg.stop_reason == 'max_tokens':
        raise RuntimeError("A resposta da IA foi cortada (pedido muito grande). Tente novamente.")

    entrada = next(
        (b.input for b in msg.content if b.type == 'tool_use' and b.name == _TOOL_NAME),
        None,
    )
    if not isinstance(entrada, dict) or not isinstance(entrada.get('itens'), list):
        raise RuntimeError("A IA retornou uma resposta em formato inesperado. Tente novamente.")

    sigla = _sigla_mola_freio(observacoes)
    resultado = {}
    for item in entrada['itens']:
        if isinstance(item, dict):
            if sigla and item.get('mola') is None and item.get('freio') is None:
                item['mola'] = sigla[0] == 'C'
                item['freio'] = sigla[1] == 'C'
            resultado[_normalizar_codigo(item.get('codigo'))] = item
    # um único item: a observação vale para ele mesmo se a IA errar o código
    if len(itens_base) == 1 and len(resultado) == 1:
        resultado = {_normalizar_codigo(itens_base[0]['codigo']): next(iter(resultado.values()))}
    return resultado


# ──────────────────────────────────────────────────────────────────────────────
# Resolução do código correto (determinística, sobre o catálogo)
# ──────────────────────────────────────────────────────────────────────────────
def _resolver_codigo(
    base: dict, pedido: dict, catalogo: list[dict], preferido: str = '',
) -> tuple[str | None, list[str]]:
    """
    Aplica as características pedidas sobre os atributos do produto base e
    procura no catálogo o produto com essa combinação.
    Se `preferido` (código do ERP) atende ao pedido, é ele o escolhido — ex.: obs
    "com pneus" aceita qualquer pneu, e P750(I) × P750IMP são equivalentes.
    Retorna (código correto ou None se a combinação não existe, observações).
    """
    notas: list[str] = []

    mola_freio = base.get('molaFreio') or ''
    if mola_freio and (pedido.get('mola') is not None or pedido.get('freio') is not None):
        mola = mola_freio[0] if pedido.get('mola') is None else ('C' if pedido['mola'] else 'S')
        freio = mola_freio[1] if pedido.get('freio') is None else ('C' if pedido['freio'] else 'S')
        if mola + freio != mola_freio:
            notas.append(f"mola/freio {mola_freio} → {mola + freio}")
        mola_freio = mola + freio

    cor = base.get('cor') or ''
    cor_pedida = _cor_canonica(pedido.get('cor'))
    if cor and cor_pedida and cor_pedida != cor:
        notas.append(f"cor {cor} → {cor_pedida}")
        cor = cor_pedida

    pneu_base = base.get('pneu') or ''
    pneu_pedido = pedido.get('pneu')
    if pneu_pedido is True and not pneu_base:
        notas.append("pneus incluídos")
        aceita_pneu = lambda p: bool(p)  # noqa: E731
    elif pneu_pedido is False and pneu_base:
        notas.append("sem pneus")
        aceita_pneu = lambda p: not p  # noqa: E731
    else:
        aceita_pneu = lambda p: p == pneu_base  # noqa: E731

    funcs = set(_funcionalidades(base))
    if pedido.get('mangueiras_maiores') is True and _MANG_MAIORES not in funcs:
        notas.append("mangueiras maiores")
        funcs.add(_MANG_MAIORES)
    elif pedido.get('mangueiras_maiores') is False and _MANG_MAIORES in funcs:
        notas.append("sem mangueiras maiores")
        funcs.discard(_MANG_MAIORES)

    candidatos = [
        p for p in catalogo
        if all((p.get(k) or '') == (base.get(k) or '') for k in _ATRIBUTOS_FIXOS)
        and (p.get('molaFreio') or '') == mola_freio
        and (p.get('cor') or '') == cor
        and aceita_pneu(p.get('pneu') or '')
        and _funcionalidades(p) == funcs
    ]
    if not candidatos:
        return None, notas

    if preferido:
        aceito = next(
            (p for p in candidatos if _normalizar_codigo(p['codigo']) == _normalizar_codigo(preferido)),
            None,
        )
        if aceito:
            return aceito['codigo'], notas

    pneus = sorted({p.get('pneu') for p in candidatos})
    if pneu_pedido is True and not pneu_base and len(pneus) > 1:
        notas.append(f"tipo de pneu não informado (opções: {', '.join(pneus)})")

    # entre equivalentes (ex.: P750(I) × P750IMP), o mais parecido com o código atual
    escolhido = max(
        candidatos,
        key=lambda p: difflib.SequenceMatcher(None, base['codigo'], p['codigo']).ratio(),
    )
    return escolhido['codigo'], notas


def _parear_crm(itens_erp: list[dict], itens_crm: list[dict], indice: dict) -> list[tuple]:
    """Emparelha cada item do ERP com o item do CRM do mesmo modelo/código mais parecido."""
    livres = list(itens_crm)
    pares = []
    for erp in itens_erp:
        prod_erp = indice.get(_normalizar_codigo(erp['codigo']))
        modelo = (prod_erp or {}).get('modelo') or erp['codigo'].split()[0]

        def _score(crm):
            prod_crm = indice.get(_normalizar_codigo(crm['codigo']))
            modelo_crm = (prod_crm or {}).get('modelo') or crm['codigo'].split()[0]
            if modelo_crm.upper() != modelo.upper():
                return -1
            return difflib.SequenceMatcher(None, erp['codigo'], crm['codigo']).ratio()

        melhor = max(livres, key=_score, default=None)
        if melhor is not None and _score(melhor) >= 0:
            livres.remove(melhor)
            pares.append((erp, melhor))
        else:
            pares.append((erp, None))
    pares.extend((None, crm) for crm in livres)
    return pares


def _fmt_qtd(q: float) -> str:
    return f"{q:.0f}" if q == int(q) else f"{q:g}"




_ROTULOS_ATRIBUTOS = (
    ('modelo', 'modelo'),
    ('descGenerica', 'tipo'),
    ('molaFreio', 'mola/freio'),
    ('rodado', 'rodado'),
    ('eixo', 'eixo'),
    ('tamanho', 'tamanho'),
    ('pneu', 'pneu'),
    ('funcionalidade', 'opcionais'),
    ('cor', 'cor'),
)


def _diferencas(prod_erp: dict, prod_esperado: dict) -> list[str]:
    """Descreve em que atributos o produto do ERP difere do esperado."""
    difs = []
    for campo, rotulo in _ROTULOS_ATRIBUTOS:
        if campo == 'funcionalidade':
            a, b = _funcionalidades(prod_erp), _funcionalidades(prod_esperado)
            va, vb = ' + '.join(sorted(a)) or 'nenhum', ' + '.join(sorted(b)) or 'nenhum'
        else:
            a = va = prod_erp.get(campo) or ''
            b = vb = prod_esperado.get(campo) or ''
            va, vb = va or 'nenhum', vb or 'nenhum'
        if a != b:
            difs.append(f"{rotulo} {va} (esperado {vb})")
    return difs


def analisar_pedido(
    itens_innovaro: list,
    itens_ploomes: list,
    observacoes: list,
) -> dict:
    """
    Referência = item do CRM + observação do representante (o que foi vendido).
    Conferido  = item lançado no ERP.
    """
    try:
        catalogo = _buscar_catalogo()
    except Exception as exc:
        raise RuntimeError(f"Falha ao buscar catálogo de produtos: {exc}") from exc
    indice = {_normalizar_codigo(p['codigo']): p for p in catalogo}

    itens_erp = _agregar(itens_innovaro, 'recurso_codigo')
    for item in itens_erp:
        item['nome'] = item.get('recurso_nome') or ''
    itens_crm = _agregar(itens_ploomes, 'codigo_produto')
    for item in itens_crm:
        item['nome'] = (indice.get(_normalizar_codigo(item['codigo'])) or {}).get('nome') or ''

    pares = _parear_crm(itens_erp, itens_crm, indice)

    obs_unicas = list(dict.fromkeys(str(o).strip() for o in observacoes if str(o).strip()))
    # a observação é aplicada sobre o item de referência (CRM; ERP só quando não há CRM)
    referencias = [crm or erp for erp, crm in pares]
    pedidos = _extrair_caracteristicas(obs_unicas, referencias)

    linhas = []
    for (erp, crm), referencia in zip(pares, referencias):
        base = indice.get(_normalizar_codigo(referencia['codigo']))
        pedido = dict(pedidos.get(_normalizar_codigo(referencia['codigo'])) or {})
        if not any(pedido.get(k) is not None for k in ('cor', 'mola', 'freio', 'pneu', 'mangueiras_maiores')):
            pedido.pop('trecho', None)
        if crm and not _cor_canonica(pedido.get('cor')) and _cor_canonica(crm.get('cor')):
            pedido['cor'] = crm.get('cor')  # cor informada no campo do CRM

        motivos: list[str] = []
        esperado = None
        notas: list[str] = []
        if base is None:
            origem = 'CRM' if crm else 'ERP'
            motivos.append(f"código do {origem} {referencia['codigo']} não existe no catálogo")
        else:
            esperado, notas = _resolver_codigo(base, pedido, catalogo, erp['codigo'] if erp else '')
            if notas:
                motivos.append(f"obs. pede: {', '.join(notas)}")
            if esperado is None:
                motivos.append("combinação pedida não existe no catálogo — verificar com o comercial")

        if erp is None:
            divergencia = True
            motivos.append("item do CRM não lançado no ERP")
        elif crm is None:
            divergencia = True
            motivos.append("item do ERP sem correspondente no CRM")
        else:
            divergencia = esperado is None or _normalizar_codigo(esperado) != _normalizar_codigo(erp['codigo'])
            if divergencia and esperado:
                prod_erp = indice.get(_normalizar_codigo(erp['codigo']))
                if prod_erp is None:
                    motivos.append(f"código do ERP {erp['codigo']} não existe no catálogo")
                else:
                    difs = _diferencas(prod_erp, indice[_normalizar_codigo(esperado)])
                    motivos.append(
                        f"ERP com {'; '.join(difs)}" if difs else f"ERP deveria ser {esperado}"
                    )
            if erp['quantidade'] != crm['quantidade']:
                divergencia = True
                motivos.append(
                    f"quantidade ERP {_fmt_qtd(erp['quantidade'])} ≠ CRM {_fmt_qtd(crm['quantidade'])}"
                )

        # informativo: o código no CRM não reflete sozinho o que a observação pede
        crm_divergencia = bool(crm and notas)
        if pedido.get('trecho') and motivos:
            motivos.insert(0, f"obs.: \"{pedido['trecho']}\"")

        linhas.append({
            'erp': f"{erp['codigo']} | Qtd: {_fmt_qtd(erp['quantidade'])}" if erp else '—',
            'crm': (
                f"{crm['codigo']} | {crm.get('cor') or 'N/D'} | Qtd: {_fmt_qtd(crm['quantidade'])}"
                if crm else '—'
            ),
            'ia': esperado or 'NÃO ENCONTRADO',
            'motivo': '; '.join(motivos) or '—',
            'divergencia': divergencia,
            'crm_divergencia': crm_divergencia,
        })

    n_div = sum(1 for linha in linhas if linha['divergencia'])
    n_crm = sum(1 for linha in linhas if linha['crm_divergencia'])
    if n_div:
        resumo = f"{n_div} item(ns) do ERP não condizem com o CRM + observação."
    else:
        resumo = "ERP condiz com o CRM + observação."
    if n_crm:
        resumo += f" Em {n_crm} item(ns) o código do CRM está incompleto (a observação complementa)."

    return {
        'itens': linhas,
        'status': 'DIVERGÊNCIA' if n_div else 'CONSISTENTE',
        'resumo': resumo,
    }
