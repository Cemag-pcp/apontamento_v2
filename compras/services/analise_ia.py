import hashlib
import json
import os
from datetime import datetime

import anthropic
from django.utils import timezone

from compras.models import AnaliseIA

CAMPOS_HASH = [
    'estoque_atual', 'estoque_minimo', 'consumo_diario',
    'dias_ressupr', 'dias_ate_data_compra', 'ped_compras',
    'pedidos_pendentes_count', 'chegadas_previstas',
    'media_3m', 'cons_mes_anterior', 'simulado_pend_vendas',
    'dee_dias_em_est', 'estoque_total', 'fornecedores_pedidos',
]


def _hash_projecao(projecao: dict) -> str:
    payload = {}
    for k in CAMPOS_HASH:
        v = projecao.get(k)
        # Normaliza listas para ordenação determinística
        if isinstance(v, list):
            v = sorted(v, key=lambda x: json.dumps(x, sort_keys=True, default=str))
        payload[k] = v
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode()
    ).hexdigest()


def _serializar_registro(registro):
    criado_local = timezone.localtime(registro.criado_em)
    return {
        'analise': registro.analise,
        'from_cache': True,
        'criado_em': criado_local.strftime('%d/%m/%Y %H:%M'),
    }


def check_cache(codigo: str, projecao: dict):
    h = _hash_projecao(projecao)
    cached = AnaliseIA.objects.filter(codigo=codigo, dados_hash=h).first()
    if cached:
        return _serializar_registro(cached)
    return None


def get_or_create_analise(codigo: str, projecao: dict, force: bool = False) -> dict:
    h = _hash_projecao(projecao)
    if not force:
        cached = AnaliseIA.objects.filter(codigo=codigo, dados_hash=h).first()
        if cached:
            return _serializar_registro(cached)

    analise_texto = _chamar_claude(codigo, projecao)
    registro = AnaliseIA.objects.create(codigo=codigo, dados_hash=h, analise=analise_texto)
    criado_local = timezone.localtime(registro.criado_em)
    return {
        'analise': analise_texto,
        'from_cache': False,
        'criado_em': criado_local.strftime('%d/%m/%Y %H:%M'),
    }


SYSTEM_PROMPT = (
    "Você é um assistente especializado em compras industriais. "
    "Sua única fonte de verdade são os dados fornecidos pelo usuário. "
    "REGRA ABSOLUTA: nunca invente, estime ou infira datas, quantidades ou situações "
    "que não estejam explicitamente nos dados recebidos. "
    "Se uma informação não constar nos dados, diga que não há dados suficientes para essa conclusão. "
    "Sua análise será usada para tomadas de decisão reais de compra."
)


def _chamar_claude(codigo: str, projecao: dict) -> str:
    client = anthropic.Anthropic(api_key=os.environ['ANTHROPIC_API_KEY'])
    msg = client.messages.create(
        model='claude-haiku-4-5-20251001',
        max_tokens=500,
        system=SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': _montar_prompt(codigo, projecao)}],
    )
    return msg.content[0].text


def _montar_prompt(codigo: str, projecao: dict) -> str:
    hoje = datetime.now().strftime('%d/%m/%Y')

    # Pedidos com datas e status
    pedidos = projecao.get('pedidos_pendentes_detalhes') or []
    if pedidos:
        linhas_pedidos = '\n'.join(
            f"  • {p.get('data', '-')} — {p.get('quantidade', 0):.0f} unid [{p.get('status', '')}]"
            for p in pedidos
        )
    else:
        linhas_pedidos = '  Nenhum pedido cadastrado'

    # Chegadas previstas dentro do horizonte do gráfico
    chegadas = projecao.get('chegadas_previstas') or []
    if chegadas:
        linhas_chegadas = '\n'.join(
            f"  • {c.get('data', '-')} — {c.get('quantidade', 0):.0f} unid "
            f"(estoque após chegada: {c.get('estoque_apos_chegada', 0):.0f} unid)"
            for c in chegadas
        )
    else:
        linhas_chegadas = '  Nenhuma chegada prevista'

    # Fornecedores com pedidos e seus prazos
    fornecedores = projecao.get('fornecedores_pedidos') or []
    if fornecedores:
        linhas_forn = '\n'.join(
            f"  • {f.get('fornecedor', '-')} — entrega: {f.get('data_entrega', '-')} "
            f"({f.get('quantidade', 0):.0f} unid)"
            for f in fornecedores
        )
    else:
        linhas_forn = '  Nenhum fornecedor com pedido cadastrado'

    return (
        f"Hoje é {hoje}. Você é um assistente de compras industriais.\n"
        f"Analise a situação do material {codigo} — {projecao.get('descricao', '')} "
        f"(grupo: {projecao.get('grupo', 'N/A')}) com base nos dados abaixo:\n\n"

        f"=== ESTOQUE ===\n"
        f"- Est. almoxarifado atual: {projecao.get('estoque_atual')} unid\n"
        f"- Est. total (inclui produção): {projecao.get('estoque_total')} unid\n"
        f"- Estoque mínimo configurado: {projecao.get('estoque_minimo')} unid\n"
        f"- DEE (dias em estoque): {projecao.get('dee_dias_em_est')} dias\n\n"

        f"=== CONSUMO ===\n"
        f"- Média de consumo 3 meses: {projecao.get('media_3m')} unid/mês\n"
        f"- Consumo mês anterior: {projecao.get('cons_mes_anterior')} unid\n"
        f"- Simulado pendente de vendas: {projecao.get('simulado_pend_vendas')} unid\n"
        f"- Consumo diário calculado: {projecao.get('consumo_diario')} unid/dia\n\n"

        f"=== PROJEÇÃO ===\n"
        f"- Prazo de ressuprimento: {projecao.get('dias_ressupr')} dias úteis\n"
        f"- Data limite para solicitar compra: {projecao.get('data_compra', 'N/A')} "
        f"({projecao.get('dias_ate_data_compra', 'N/A')} dias úteis a partir de hoje)\n"
        f"- Data prevista de atingir estoque mínimo: {projecao.get('data_estoque_minimo', 'N/A')}\n"
        f"- Data prevista de estoque zero: {projecao.get('data_estoque_zero', 'N/A')}\n"
        f"- Flag de urgência: {projecao.get('flag_urgencia', 'N/A')}\n\n"

        f"=== PEDIDOS DE COMPRA PENDENTES "
        f"({projecao.get('pedidos_pendentes_count', 0)} pedidos, "
        f"{projecao.get('pedidos_atrasados_count', 0)} atrasados, "
        f"{projecao.get('pedidos_previstos_count', 0)} a receber) ===\n"
        f"{linhas_pedidos}\n\n"

        f"=== CHEGADAS PREVISTAS NO HORIZONTE DO GRÁFICO ===\n"
        f"{linhas_chegadas}\n\n"

        f"=== FORNECEDORES COM PEDIDOS ABERTOS ===\n"
        f"(Prazo de ressuprimento configurado: {projecao.get('dias_ressupr')} dias úteis)\n"
        f"{linhas_forn}\n\n"

        f"INSTRUÇÕES OBRIGATÓRIAS:\n"
        f"1. Use APENAS os dados fornecidos acima. Não invente datas, quantidades, cenários ou previsões.\n"
        f"2. Se um campo estiver como 'N/A' ou ausente, não faça suposições sobre ele.\n"
        f"3. Escreva em 3-4 frases curtas em português.\n"
        f"4. Informe: qual o risco real com base nos dados, o que já está planejado (pedidos/chegadas) "
        f"e qual a ação mais urgente a tomar hoje ({datetime.now().strftime('%d/%m/%Y')})."
    )
