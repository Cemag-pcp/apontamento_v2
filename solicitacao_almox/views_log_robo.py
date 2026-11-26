"""Tela "Log do robô" do almoxarifado.

Cruza o log do robô que lança as requisições no ERP (schema
``log_requisicao``: execucao / tentativa / evento) com as requisições do
cmgprod (``solicitacao_almox_solicitacaorequisicao``).

O schema de log fica no mesmo banco, sem chave estrangeira para as tabelas do
sistema; a ligação é ``log_requisicao.tentativa.solicitacao_id = requisicao.id``.
As tabelas do sistema são referenciadas sem schema, então seguem o
``search_path`` da conexão (BASE_PROD ou BASE_TESTE). Tudo aqui é só leitura.
"""

from datetime import date, datetime, timedelta

from django.contrib.auth.decorators import login_required
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render

from cadastro_almox.models import Cc, Funcionario, ItensSolicitacao
from cadastro_almox.models import ClasseRequisicao
from .models import SolicitacaoRequisicao

LOG_SCHEMA = "log_requisicao"
TZ_LOCAL = "America/Sao_Paulo"
POR_PAGINA = 50
MAX_DIAS = 180

SITUACOES = {
    "lancada": "Lançada no ERP",
    "manual": "OK manual (sem chave)",
    "erro": "Erro",
    "pendente": "Pendente (sem retorno)",
}


def _t(model):
    return connection.ops.quote_name(model._meta.db_table)


def _parse_data(valor, padrao):
    try:
        return datetime.strptime(valor, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return padrao


def _filtros(request):
    """Monta o WHERE comum (sobre a requisição + última tentativa)."""
    hoje = date.today()
    data_fim = _parse_data(request.GET.get("data_fim"), hoje)
    data_ini = _parse_data(request.GET.get("data_ini"), data_fim - timedelta(days=6))
    if data_ini > data_fim:
        data_ini, data_fim = data_fim, data_ini
    if (data_fim - data_ini).days > MAX_DIAS:
        data_ini = data_fim - timedelta(days=MAX_DIAS)

    where = [
        "sr.data_entrega IS NOT NULL",
        f"(sr.data_entrega AT TIME ZONE '{TZ_LOCAL}')::date BETWEEN %s AND %s",
    ]
    params = [data_ini, data_fim]

    situacao = request.GET.get("situacao") or ""
    if situacao in SITUACOES:
        where.append("situacao = %s")
        params.append(situacao)

    resultado = request.GET.get("resultado") or ""
    if resultado == "sem_tentativa":
        where.append("ut.id IS NULL")
    elif resultado:
        where.append("ut.resultado = %s")
        params.append(resultado)

    etapa = request.GET.get("etapa") or ""
    if etapa:
        where.append("ut.etapa_falha = %s")
        params.append(etapa)

    busca = (request.GET.get("busca") or "").strip()
    if busca:
        like = f"%{busca}%"
        cond = ["i.codigo ILIKE %s", "i.nome ILIKE %s", "f.matricula ILIKE %s",
                "f.nome ILIKE %s", "sr.chave_innovaro ILIKE %s", "ut.mensagem_erro ILIKE %s"]
        params_busca = [like] * len(cond)
        if busca.isdigit():
            cond.append("sr.id = %s")
            params_busca.append(int(busca))
        where.append("(" + " OR ".join(cond) + ")")
        params.extend(params_busca)

    return where, params, data_ini, data_fim


def _base_sql():
    """Requisição + dados de cadastro + agregados do log (CTE ``base``)."""
    return f"""
        WITH base AS (
            SELECT sr.id, sr.quantidade, sr.data_solicitacao, sr.data_entrega,
                   sr.rpa, sr.chave_innovaro,
                   i.codigo AS item_codigo, i.nome AS item_nome,
                   f.matricula, f.nome AS funcionario_nome,
                   cc.nome AS cc_nome, cr.nome AS classe_nome,
                   CASE
                       WHEN sr.rpa = 'OK' AND COALESCE(sr.chave_innovaro, '') <> '' THEN 'lancada'
                       WHEN sr.rpa = 'OK' THEN 'manual'
                       WHEN sr.rpa IS NULL OR sr.rpa = '' THEN 'pendente'
                       ELSE 'erro'
                   END AS situacao,
                   ut.id AS ut_id, ut.resultado AS ut_resultado, ut.etapa_falha AS ut_etapa,
                   ut.mensagem_erro AS ut_mensagem, ut.iniciado_em AS ut_iniciado_em,
                   ut.chave_erp AS ut_chave_erp, ut.duracao_ms AS ut_duracao_ms,
                   COALESCE(agg.qtd_tentativas, 0) AS qtd_tentativas,
                   COALESCE(agg.qtd_erros, 0) AS qtd_erros,
                   agg.primeira_tentativa
            FROM {_t(SolicitacaoRequisicao)} sr
            JOIN {_t(ItensSolicitacao)} i ON i.id = sr.item_id
            JOIN {_t(Funcionario)} f ON f.id = sr.funcionario_id
            JOIN {_t(Cc)} cc ON cc.id = sr.cc_id
            JOIN {_t(ClasseRequisicao)} cr ON cr.id = sr.classe_requisicao_id
            LEFT JOIN LATERAL (
                SELECT t.* FROM {LOG_SCHEMA}.tentativa t
                WHERE t.solicitacao_id = sr.id
                ORDER BY t.id DESC LIMIT 1
            ) ut ON true
            LEFT JOIN LATERAL (
                SELECT COUNT(*) AS qtd_tentativas,
                       COUNT(*) FILTER (WHERE t.resultado <> 'OK') AS qtd_erros,
                       MIN(t.iniciado_em) AS primeira_tentativa
                FROM {LOG_SCHEMA}.tentativa t
                WHERE t.solicitacao_id = sr.id
            ) agg ON true
            WHERE {{where}}
        )
    """


def _where_sql(where):
    # "situacao" é calculada na CTE; o filtro dela vai para fora.
    dentro, fora = [], []
    for w in where:
        (fora if w.startswith("situacao") else dentro).append(w)
    return " AND ".join(dentro) or "TRUE", " AND ".join(fora) or "TRUE"


def _split_params(where, params):
    """Separa os parâmetros do filtro de situação (aplicado fora da CTE)."""
    dentro, fora = [], []
    idx = 0
    for w in where:
        n = w.count("%s")
        alvo = fora if w.startswith("situacao") else dentro
        alvo.extend(params[idx:idx + n])
        idx += n
    return dentro, fora


def _executar(sql, params):
    with connection.cursor() as cur:
        cur.execute(sql, params)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def _fmt_dt(valor):
    if not valor:
        return ""
    from django.utils import timezone
    return timezone.localtime(valor).strftime("%d/%m/%Y %H:%M")


def _resumir_erro(msg):
    if not msg:
        return ""
    msg = " ".join(str(msg).split())
    return msg[:220] + ("…" if len(msg) > 220 else "")


@login_required
def log_robo(request):
    return render(request, "log_robo.html", {"situacoes": SITUACOES})


@login_required
def api_log_robo_resumo(request):
    where, params, data_ini, data_fim = _filtros(request)
    w_in, w_out = _where_sql(where)
    p_in, p_out = _split_params(where, params)
    base = _base_sql().replace("{where}", w_in)

    por_situacao = _executar(
        base + f"SELECT situacao, COUNT(*) AS qtd FROM base WHERE {w_out} GROUP BY situacao",
        p_in + p_out,
    )
    totais = _executar(
        base + f"""
        SELECT COUNT(*) AS solicitacoes,
               COALESCE(SUM(qtd_tentativas), 0) AS tentativas,
               COALESCE(SUM(qtd_erros), 0) AS tentativas_erro,
               COUNT(*) FILTER (WHERE qtd_tentativas = 0) AS sem_tentativa,
               COUNT(*) FILTER (WHERE qtd_tentativas > 1) AS com_retentativa
        FROM base WHERE {w_out}
        """,
        p_in + p_out,
    )[0]
    top_erros = _executar(
        base + f"""
        SELECT COALESCE(ut_etapa, '-') AS etapa,
               CASE WHEN ut_mensagem ILIKE '%%saldo insuficiente%%' THEN 'Saldo insuficiente'
                    WHEN ut_mensagem ILIKE '%%regra cont%%' THEN 'Regra contábil não encontrada'
                    WHEN ut_mensagem ILIKE '%%timeout%%' THEN 'Timeout na tela do ERP'
                    WHEN ut_mensagem ILIKE '%%has been closed%%' THEN 'Navegador do robô fechado'
                    WHEN ut_mensagem ILIKE '%%não foi aprovada%%' THEN 'Requisição não aprovada no ERP'
                    ELSE LEFT(REGEXP_REPLACE(COALESCE(ut_mensagem, ''), '\\s+', ' ', 'g'), 80)
               END AS motivo,
               COUNT(*) AS qtd
        FROM base
        WHERE {w_out} AND situacao = 'erro'
        GROUP BY 1, 2 ORDER BY qtd DESC LIMIT 8
        """,
        p_in + p_out,
    )
    top_itens = _executar(
        base + f"""
        SELECT item_codigo, item_nome, COUNT(*) AS qtd
        FROM base
        WHERE {w_out} AND situacao = 'erro'
        GROUP BY 1, 2 ORDER BY qtd DESC LIMIT 8
        """,
        p_in + p_out,
    )
    etapas = _executar(
        f"SELECT DISTINCT etapa_falha FROM {LOG_SCHEMA}.tentativa "
        "WHERE etapa_falha IS NOT NULL ORDER BY 1",
        [],
    )
    execucoes = _executar(
        f"""SELECT id, maquina, versao, status, motivo_fim, iniciado_em, finalizado_em
            FROM {LOG_SCHEMA}.execucao ORDER BY id DESC LIMIT 5""",
        [],
    )

    return JsonResponse({
        "periodo": {"data_ini": data_ini.isoformat(), "data_fim": data_fim.isoformat()},
        "por_situacao": {r["situacao"]: r["qtd"] for r in por_situacao},
        "totais": {k: int(v or 0) for k, v in totais.items()},
        "top_erros": top_erros,
        "top_itens": top_itens,
        "etapas": [r["etapa_falha"] for r in etapas],
        "execucoes": [
            {**e, "iniciado_em": _fmt_dt(e["iniciado_em"]), "finalizado_em": _fmt_dt(e["finalizado_em"])}
            for e in execucoes
        ],
    })


@login_required
def api_log_robo_solicitacoes(request):
    where, params, _, _ = _filtros(request)
    w_in, w_out = _where_sql(where)
    p_in, p_out = _split_params(where, params)
    base = _base_sql().replace("{where}", w_in)

    try:
        pagina = max(1, int(request.GET.get("pagina", 1)))
    except ValueError:
        pagina = 1
    offset = (pagina - 1) * POR_PAGINA

    total = _executar(base + f"SELECT COUNT(*) AS n FROM base WHERE {w_out}", p_in + p_out)[0]["n"]
    linhas = _executar(
        base + f"""
        SELECT * FROM base WHERE {w_out}
        ORDER BY data_entrega DESC, id DESC
        LIMIT %s OFFSET %s
        """,
        p_in + p_out + [POR_PAGINA, offset],
    )

    dados = [
        {
            "id": r["id"],
            "item": f"{r['item_codigo']} - {r['item_nome']}",
            "quantidade": float(r["quantidade"]) if r["quantidade"] is not None else None,
            "solicitante": f"{r['matricula']} - {r['funcionario_nome']}",
            "cc": r["cc_nome"],
            "classe": r["classe_nome"],
            "data_entrega": _fmt_dt(r["data_entrega"]),
            "situacao": r["situacao"],
            "situacao_display": SITUACOES.get(r["situacao"], r["situacao"]),
            "chave": r["chave_innovaro"] or "",
            "rpa": _resumir_erro(r["rpa"]),
            "qtd_tentativas": r["qtd_tentativas"],
            "qtd_erros": r["qtd_erros"],
            "ultimo_resultado": r["ut_resultado"] or "",
            "ultima_etapa": r["ut_etapa"] or "",
            "ultima_mensagem": _resumir_erro(r["ut_mensagem"]),
            "ultima_tentativa": _fmt_dt(r["ut_iniciado_em"]),
        }
        for r in linhas
    ]
    return JsonResponse({
        "total": total,
        "pagina": pagina,
        "por_pagina": POR_PAGINA,
        "paginas": max(1, -(-total // POR_PAGINA)),
        "dados": dados,
    })


@login_required
def api_log_robo_tentativas(request, solicitacao_id):
    tentativas = _executar(
        f"""
        SELECT t.id, t.execucao_id, t.item, t.quantidade, t.classe, t.matricula, t.cc,
               t.chave_erp, t.iniciado_em, t.finalizado_em, t.duracao_ms, t.resultado,
               t.etapa_falha, t.mensagem_erro, t.texto_modal, t.screenshot,
               e.maquina, e.versao
        FROM {LOG_SCHEMA}.tentativa t
        LEFT JOIN {LOG_SCHEMA}.execucao e ON e.id = t.execucao_id
        WHERE t.solicitacao_id = %s
        ORDER BY t.id DESC
        """,
        [solicitacao_id],
    )
    ids = [t["id"] for t in tentativas]
    eventos_por_tentativa = {}
    if ids:
        for ev in _executar(
            f"""SELECT tentativa_id, criado_em, nivel, mensagem, detalhe
                FROM {LOG_SCHEMA}.evento
                WHERE tentativa_id = ANY(%s)
                ORDER BY criado_em, id""",
            [ids],
        ):
            eventos_por_tentativa.setdefault(ev["tentativa_id"], []).append({
                "criado_em": timezone_hms(ev["criado_em"]),
                "nivel": ev["nivel"],
                "mensagem": ev["mensagem"],
                "detalhe": ev["detalhe"] or "",
            })

    return JsonResponse({
        "solicitacao_id": solicitacao_id,
        "tentativas": [
            {
                **{k: t[k] for k in ("id", "execucao_id", "item", "classe", "matricula", "cc",
                                     "chave_erp", "duracao_ms", "resultado", "etapa_falha",
                                     "mensagem_erro", "texto_modal", "screenshot", "maquina", "versao")},
                "quantidade": float(t["quantidade"]) if t["quantidade"] is not None else None,
                "iniciado_em": _fmt_dt(t["iniciado_em"]),
                "finalizado_em": _fmt_dt(t["finalizado_em"]),
                "eventos": eventos_por_tentativa.get(t["id"], []),
            }
            for t in tentativas
        ],
    })


def timezone_hms(valor):
    if not valor:
        return ""
    from django.utils import timezone
    return timezone.localtime(valor).strftime("%d/%m %H:%M:%S")
