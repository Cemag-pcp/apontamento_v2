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




def _descrever_atributos(produto: dict) -> dict[str, str]:
    """Atributos do produto em linguagem de chão de fábrica, para comparar ERP × esperado."""
    mola_freio = produto.get('molaFreio') or ''
    pneu = produto.get('pneu') or ''
    funcs = _funcionalidades(produto)
    desc = {
        'Modelo': produto.get('modelo') or '',
        'Tipo': produto.get('descGenerica') or '',
        'Rodado': produto.get('rodado') or '',
        'Eixo': produto.get('eixo') or '',
        'Tamanho': produto.get('tamanho') or '',
        'Pneus': f"com pneus {pneu}" if pneu else 'sem pneus',
        'Mangueiras maiores': 'sim' if _MANG_MAIORES in funcs else 'não',
        'Outros opcionais': ' + '.join(sorted(funcs - {_MANG_MAIORES})) or 'nenhum',
        'Cor': (produto.get('cor') or '').lower(),
    }
    if len(mola_freio) == 2:
        desc['Mola'] = 'com mola' if mola_freio[0] == 'C' else 'sem mola'
        desc['Freio'] = 'com freio' if mola_freio[1] == 'C' else 'sem freio'
    return desc


_ORDEM_ATRIBUTOS = ('Modelo', 'Tipo', 'Rodado', 'Eixo', 'Tamanho', 'Mola', 'Freio', 'Pneus',
                    'Mangueiras maiores', 'Outros opcionais', 'Cor')


def _correcoes(prod_erp: dict, prod_esperado: dict) -> list[dict]:
    """Lista o que precisa mudar no item do ERP: [{campo, erp, esperado}]."""
    a, b = _descrever_atributos(prod_erp), _descrever_atributos(prod_esperado)
    return [
        {'campo': campo, 'erp': a.get(campo) or '—', 'esperado': b.get(campo) or '—'}
        for campo in _ORDEM_ATRIBUTOS
        if (a.get(campo) or '') != (b.get(campo) or '')
    ]


def analisar_pedido(
    itens_innovaro: list,
    itens_ploomes: list,
    observacoes: list,
) -> dict:
    """
    Referência = item do CRM (código + campo de cor) + observação do representante.
    Conferido  = item lançado no ERP.

    Cada item volta com:
      situacao   'ok' (ERP correto) | 'corrigir' (ERP diferente do vendido)
                 | 'verificar' (não dá para concluir sozinho)
      erp/crm    {codigo, qtd[, cor]} ou None
      esperado   código que deveria estar no ERP (ou None)
      correcoes  [{campo, erp, esperado}] — o que mudar no ERP
      pedido_vendedor  trecho da observação que pediu algo
      avisos     mensagens que pedem atenção humana
      obs_complementa  a observação pede algo que o CRM (código + cor) não traz (informativo)
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

    itens = []
    for (erp, crm), referencia in zip(pares, referencias):
        base = indice.get(_normalizar_codigo(referencia['codigo']))
        pedido = dict(pedidos.get(_normalizar_codigo(referencia['codigo'])) or {})
        if not any(pedido.get(k) is not None for k in ('cor', 'mola', 'freio', 'pneu', 'mangueiras_maiores')):
            pedido.pop('trecho', None)

        # o CRM é código + campo de cor: a cor do campo faz parte do que foi vendido
        cor_crm = _cor_canonica(crm.get('cor')) if crm else None
        if cor_crm and not _cor_canonica(pedido.get('cor')):
            pedido['cor'] = cor_crm

        avisos: list[str] = []
        correcoes: list[dict] = []
        esperado = None
        obs_complementa = False
        situacao = 'ok'

        if base is None:
            origem = 'CRM' if crm else 'ERP'
            avisos.append(f"O código do {origem} ({referencia['codigo']}) não existe no catálogo do Innovaro.")
            situacao = 'verificar'
        else:
            esperado, notas = _resolver_codigo(base, pedido, catalogo, erp['codigo'] if erp else '')
            avisos.extend(f"{n[0].upper()}{n[1:]}." for n in notas if n.startswith('tipo de pneu'))
            if esperado is None:
                avisos.append(
                    "O que foi pedido não existe no catálogo (nenhum produto com essa combinação). "
                    "Confirmar com o comercial."
                )
                situacao = 'verificar'
            if crm:
                # o que o CRM sozinho (código + cor) já define, sem a observação
                so_crm, _ = _resolver_codigo(base, {'cor': cor_crm}, catalogo)
                obs_complementa = bool(
                    esperado and so_crm and _normalizar_codigo(esperado) != _normalizar_codigo(so_crm)
                )

        if erp is None:
            avisos.append("Item vendido (CRM) que não foi lançado no ERP.")
            situacao = 'corrigir'
        elif crm is None:
            avisos.append("Item lançado no ERP que não aparece no CRM.")
            situacao = 'verificar'
        else:
            if esperado and _normalizar_codigo(esperado) != _normalizar_codigo(erp['codigo']):
                situacao = 'corrigir'
                prod_erp = indice.get(_normalizar_codigo(erp['codigo']))
                if prod_erp is None:
                    avisos.append(f"O código do ERP ({erp['codigo']}) não existe no catálogo do Innovaro.")
                else:
                    correcoes = _correcoes(prod_erp, indice[_normalizar_codigo(esperado)])
            if erp['quantidade'] != crm['quantidade']:
                situacao = 'corrigir'
                correcoes.append({
                    'campo': 'Quantidade',
                    'erp': _fmt_qtd(erp['quantidade']),
                    'esperado': _fmt_qtd(crm['quantidade']),
                })

        itens.append({
            'situacao': situacao,
            'erp': {'codigo': erp['codigo'], 'qtd': _fmt_qtd(erp['quantidade'])} if erp else None,
            'crm': (
                {'codigo': crm['codigo'], 'cor': (cor_crm or crm.get('cor') or '').lower(),
                 'qtd': _fmt_qtd(crm['quantidade'])}
                if crm else None
            ),
            'esperado': esperado,
            'correcoes': correcoes,
            'pedido_vendedor': pedido.get('trecho') or '',
            'avisos': avisos,
            'obs_complementa': obs_complementa,
        })

    n_corrigir = sum(1 for i in itens if i['situacao'] == 'corrigir')
    n_verificar = sum(1 for i in itens if i['situacao'] == 'verificar')
    if n_corrigir:
        status = 'CORRIGIR'
        resumo = f"{n_corrigir} de {len(itens)} item(ns) precisa(m) ser corrigido(s) no ERP antes de conferir."
        if n_verificar:
            resumo += f" {n_verificar} precisa(m) de verificação manual."
    elif n_verificar:
        status = 'VERIFICAR'
        resumo = f"{n_verificar} de {len(itens)} item(ns) precisa(m) de verificação manual."
    else:
        status = 'OK'
        resumo = "Tudo certo: o ERP condiz com o que foi vendido."

    return {'itens': itens, 'status': status, 'resumo': resumo}
