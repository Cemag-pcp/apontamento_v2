
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.urls import reverse
from django.db.models.functions import Coalesce, Now
from django.db import models, transaction
from django.db.models import Sum,Q,CharField,Count,OuterRef, Subquery, F, Value, Avg, Max, Prefetch
from django.utils.dateparse import parse_date
from django.views.decorators.csrf import csrf_exempt
from django.utils.timezone import now, localtime
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.views.decorators.http import require_POST, require_GET
from django.db.models import Func, FloatField, ExpressionWrapper
from django.contrib.auth.decorators import login_required

from apontamento_pintura.models import PecasOrdem as POPintura
from apontamento_montagem.models import PecasOrdem as POMontagem
from apontamento_solda.models import PecasOrdem as POSolda

from django.core.mail import send_mail
from django.conf import settings as django_settings

from core.models import Ordem
from cargas.models import CargaLiberada, CargaLiberadaVersao, CargaLiberadaItem, CargaLiberadaAlteracao, LinkAcompanhamento, EmailNotificacaoCarga
from cargas.services import (
    atualizar_datas_sugeridas_planejamento,
    consolidar_ordens_planejamento,
    liberar_cargas_periodo,
    listar_cargas_liberadas_para_planejamento,
    listar_cargas_liberadas_periodo,
    montar_preview_planejamento_montagem,
)
from cargas.utils import consultar_carretas, consultar_carretas_detalhado, gerar_sequenciamento, gerar_arquivos, criar_array_datas, get_base_carreta, normalizar_codigo_recurso_serie
from cadastro.models import Maquina
from cargas.utils import processar_ordens_montagem, processar_ordens_pintura, processar_ordens_solda, imprimir_ordens_montagem, imprimir_ordens_montagem_unitaria, imprimir_ordens_pintura, imprimir_ordens_pcp_qualidade
from apontamento_pintura.models import CambaoPecas, Retrabalho
from apontamento_pintura.views import ordens_criadas as ordens_criadas_pintura
from apontamento_montagem.views import ordens_criadas as ordens_criadas_montagem
from inspecao.models import DadosExecucaoInspecao, CausasNaoConformidade, Inspecao
from apontamento_exped.models import Carga as CargaExpedicao

import pandas as pd
import os
import io
import zipfile
import threading
from datetime import datetime, date
import requests
import json
from datetime import timedelta
import django
from collections import defaultdict
import logging

django.setup()
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "apontamento_v2.settings")
logger = logging.getLogger(__name__)


def _enviar_email_carga_liberada(resultado, data_inicio, data_fim, usuario):
    destinatarios = list(EmailNotificacaoCarga.objects.values_list("email", flat=True))
    if not destinatarios:
        return

    cargas = resultado.get("cargas", [])
    total = resultado.get("total_cargas_liberadas", 0)

    fmt = lambda d: datetime.strptime(d, "%Y-%m-%d").strftime("%d/%m/%Y")

    linhas = "\n".join(
        f"  • {fmt(c['data_carga'])} — {c['carga']} (v{c['versao']})"
        for c in cargas
    )

    assunto = f"[PCP] {total} carga(s) liberada(s) — {fmt(data_inicio)} a {fmt(data_fim)}"
    corpo = (
        f"Olá,\n\n"
        f"O usuário {usuario} liberou {total} carga(s) no período de {fmt(data_inicio)} a {fmt(data_fim)}:\n\n"
        f"{linhas}\n\n"
        f"As cargas acima já estão disponíveis para serem planejadas para produção.\n\n"
        f"Este é um aviso automático do sistema de apontamento.\n"
    )

    try:
        send_mail(
            subject=assunto,
            message=corpo,
            from_email=django_settings.DEFAULT_FROM_EMAIL,
            recipient_list=destinatarios,
            fail_silently=False,
        )
    except Exception:
        logger.exception("Falha ao enviar e-mail de notificação de carga liberada")


@csrf_exempt
@login_required
def api_emails_notificacao(request):
    if request.method == "GET":
        emails = list(EmailNotificacaoCarga.objects.values("id", "email"))
        return JsonResponse({"emails": emails})

    if request.method == "POST":
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "JSON inválido."}, status=400)

        email = data.get("email", "").strip().lower()
        if not email:
            return JsonResponse({"error": "E-mail obrigatório."}, status=400)

        obj, created = EmailNotificacaoCarga.objects.get_or_create(email=email)
        if not created:
            return JsonResponse({"error": "E-mail já cadastrado."}, status=400)

        return JsonResponse({"id": obj.id, "email": obj.email}, status=201)

    if request.method == "DELETE":
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "JSON inválido."}, status=400)

        email_id = data.get("id")
        if not email_id:
            return JsonResponse({"error": "ID obrigatório."}, status=400)

        deleted, _ = EmailNotificacaoCarga.objects.filter(id=email_id).delete()
        if not deleted:
            return JsonResponse({"error": "E-mail não encontrado."}, status=404)

        return JsonResponse({"message": "E-mail removido."})

    return JsonResponse({"error": "Método não permitido."}, status=405)


def _normalizar_sugestoes_datas(payload_bruto):
    if not payload_bruto:
        return {}

    try:
        payload = json.loads(payload_bruto)
    except (TypeError, json.JSONDecodeError):
        raise ValueError("Formato inválido para sugestoes_datas.")

    if not isinstance(payload, dict):
        raise ValueError("Formato inválido para sugestoes_datas.")

    sugestoes = {}
    for data_original, data_sugerida in payload.items():
        try:
            data_original_obj = datetime.strptime(data_original, "%Y-%m-%d").date()
        except (TypeError, ValueError):
            raise ValueError("As chaves de sugestoes_datas devem estar no formato YYYY-MM-DD.")

        if data_sugerida in ("", None):
            sugestoes[data_original_obj] = None
            continue

        try:
            sugestoes[data_original_obj] = datetime.strptime(data_sugerida, "%Y-%m-%d").date()
        except (TypeError, ValueError):
            raise ValueError("Os valores de sugestoes_datas devem estar no formato YYYY-MM-DD.")

    return sugestoes


def _calcular_data_programacao_por_setor(setor, data_carga):
    if setor == 'montagem':
        data_programacao = data_carga - timedelta(days=3)
    elif setor == 'solda':
        data_programacao = data_carga - timedelta(days=2)
    elif setor == 'pintura':
        data_programacao = data_carga - timedelta(days=1)
    else:
        return None

    while data_programacao.weekday() in [5, 6]:
        data_programacao -= timedelta(days=1)

    return data_programacao


def _construir_ordens_planejamento(cargas_liberadas, setor, datas_finais_por_carga):
    ordens = []

    for carga_liberada in cargas_liberadas:
        data_carga_original = carga_liberada["data_carga"]
        data_carga_planejada = datas_finais_por_carga[carga_liberada["carga_liberada_id"]]
        tabela_carga = gerar_sequenciamento(
            data_carga_original.isoformat(),
            data_carga_original.isoformat(),
            setor,
            carga_liberada["carga"],
        )

        if tabela_carga.empty:
            continue

        if setor == 'pintura':
            colunas_grupo = ['Código', 'Peca', 'Célula', 'Datas', 'Recurso_cor', 'cor']
            if 'Carga' in tabela_carga.columns:
                colunas_grupo.append('Carga')
            tabela_carga = tabela_carga.groupby(colunas_grupo).agg({'Qtde_total': 'sum'}).reset_index()
            tabela_carga.drop_duplicates(
                subset=['Código', 'Datas', 'cor', 'Carga'] if 'Carga' in tabela_carga.columns else ['Código', 'Datas', 'cor'],
                inplace=True,
            )
        else:
            tabela_carga.drop_duplicates(
                subset=['Código', 'Datas', 'Célula', 'Carga'] if 'Carga' in tabela_carga.columns else ['Código', 'Datas', 'Célula'],
                inplace=True,
            )

        for _, row in tabela_carga.iterrows():
            ordens.append({
                "grupo_maquina": setor.lower(),
                "cor": row["cor"] if setor == 'pintura' else '',
                "obs": "Ordem gerada automaticamente",
                "peca_nome": str(row["Código"]) + " - " + row["Peca"],
                "qtd_planejada": int(row["Qtde_total"]),
                "data_carga": data_carga_planejada.isoformat(),
                "setor_conjunto": row["Célula"],
                "carga_liberada_id": carga_liberada["carga_liberada_id"],
                "carga_liberada_versao_id": carga_liberada["carga_liberada_versao_id"],
            })

    return consolidar_ordens_planejamento(ordens)


MAPA_CORES_PINTURA = {
    "AM": "Amarelo", "AN": "Azul", "VJ": "Verde", "LJ": "Laranja Jacto",
    "LC": "Laranja", "VM": "Vermelho", "AV": "Amarelo", "CO": "Cinza", "CE": "Cinza escuro",
}


def _construir_ordens_planejamento_from_items(cargas_liberadas, setor, datas_finais_por_carga):
    """
    Gera ordens planejadas cruzando CargaLiberadaItem (banco) × Base_Carretas (Sheets).
    Substitui gerar_sequenciamento (que lia de Carga_Vendas no Sheets) para garantir
    que novos itens liberados no banco sejam incluídos no planejamento.
    """
    base_carretas = get_base_carreta()
    base_carretas['Recurso'] = base_carretas['Recurso'].astype(str)
    base_carretas['Recurso'] = normalizar_codigo_recurso_serie(base_carretas['Recurso'])
    base_carretas['Recurso'] = base_carretas['Recurso'].apply(
        lambda x: '0' + x if len(str(x)) == 5 else str(x)
    )
    base_carretas['Qtde'] = pd.to_numeric(base_carretas['Qtde'], errors='coerce').fillna(0)

    if setor == 'pintura':
        if 'Etapa2' in base_carretas.columns:
            base_carretas = base_carretas[
                base_carretas['Etapa2'].fillna('') == 'Pintura'
            ].copy()
        colunas_carretas = ['Recurso', 'Código', 'Peca', 'Qtde', 'Célula', 'Etapa5']
    elif setor == 'solda':
        if 'Etapa3' in base_carretas.columns:
            base_carretas = base_carretas[base_carretas['Etapa3'].fillna('') != ''].copy()
        colunas_carretas = ['Recurso', 'Código', 'Peca', 'Qtde', 'Célula']
    else:  # montagem
        if 'Etapa' in base_carretas.columns:
            base_carretas = base_carretas[base_carretas['Etapa'].fillna('') != ''].copy()
        colunas_carretas = ['Recurso', 'Código', 'Peca', 'Qtde', 'Célula']

    colunas_carretas = [c for c in colunas_carretas if c in base_carretas.columns]

    # Remove apenas linhas EXATAMENTE iguais em (Recurso, Código, Peca, Célula).
    # Não usar só (Recurso, Célula) pois a mesma máquina pode produzir peças
    # diferentes na mesma célula — removeria linhas válidas.
    cols_dedup = [c for c in ['Recurso', 'Código', 'Peca', 'Célula'] if c in base_carretas.columns]
    antes_dedup = len(base_carretas)
    base_carretas = base_carretas.drop_duplicates(subset=cols_dedup).reset_index(drop=True)
    removidas_carreta = antes_dedup - len(base_carretas)
    if removidas_carreta:
        logger.warning(
            "[from_items] base_carretas | %d linhas exatamente duplicadas removidas (Recurso+Código+Peca+Célula)",
            removidas_carreta,
        )

    origens = {}  # chave: (peca_nome, celula, cor) → lista de itens que geraram a quantidade

    logger.info(
        "[from_items] setor=%s | base_carretas carregada | linhas=%d | colunas=%s",
        setor, len(base_carretas), list(base_carretas.columns),
    )
    for row in base_carretas.itertuples(index=False):
        recurso   = getattr(row, 'Recurso',  '')
        codigo    = getattr(row, 'C_digo',   getattr(row, 'Código',  ''))  # pandas renomeia acentos em itertuples
        peca      = getattr(row, 'Peca',     '')
        qtde      = getattr(row, 'Qtde',     '')
        celula    = getattr(row, 'C_lula',   getattr(row, 'Célula',  ''))
        logger.info(
            "[from_items] carreta | recurso=%s | codigo=%s | peca=%s | qtde_por_unidade=%s | celula=%s",
            recurso, codigo, peca, qtde, celula,
        )

    ordens = []

    for carga_liberada in cargas_liberadas:
        data_carga_planejada = datas_finais_por_carga[carga_liberada["carga_liberada_id"]]

        # Sempre usa a versão mais alta da carga, garantindo que versões
        # antigas não sejam incluídas mesmo se o dict estiver desatualizado.
        ultima_versao_id_qs = (
            CargaLiberadaVersao.objects
            .filter(carga_liberada_id=carga_liberada["carga_liberada_id"])
            .order_by('-versao')
            .values('id')[:1]
        )
        itens_qs = CargaLiberadaItem.objects.filter(
            carga_versao_id__in=ultima_versao_id_qs
        ).values('codigo_recurso', 'quantidade', 'numero_serie')

        logger.info(
            "[from_items] carga=%s | carga_liberada_id=%s | versao_id_usado=%s",
            carga_liberada.get("carga"),
            carga_liberada.get("carga_liberada_id"),
            list(ultima_versao_id_qs.values_list('id', flat=True)),
        )

        if not itens_qs.exists():
            logger.info("[from_items] carga=%s sem itens no banco", carga_liberada.get("carga"))
            continue

        df_itens = pd.DataFrame(list(itens_qs))

        # Deduplica por numero_serie para evitar dupla contagem caso múltiplas versões
        # sejam lidas acidentalmente (mesmo serial na versão 1 e versão 2).
        tem_serie = df_itens['numero_serie'].astype(str).str.strip().ne('')
        if tem_serie.any():
            antes = len(df_itens)
            df_itens = df_itens.drop_duplicates(subset=['codigo_recurso', 'numero_serie'])
            removidos = antes - len(df_itens)
            if removidos:
                logger.warning(
                    "[from_items] carga=%s | %d duplicatas removidas por numero_serie",
                    carga_liberada.get("carga"), removidos,
                )

        logger.info(
            "[from_items] carga=%s | itens_banco=%d | recursos únicos=%d",
            carga_liberada.get("carga"), len(df_itens), df_itens['codigo_recurso'].nunique(),
        )
        for _, row in df_itens.iterrows():
            logger.info(
                "[from_items] item_banco | recurso=%s | quantidade=%s | numero_serie=%s",
                row['codigo_recurso'], row['quantidade'], row.get('numero_serie', ''),
            )

        df_itens['Recurso_original'] = df_itens['codigo_recurso'].astype(str).str.strip()

        if setor == 'pintura':
            df_itens['Recurso_cor_sigla'] = df_itens['Recurso_original'].str[-2:].str.strip()
            df_itens['Recurso_cor_sigla'] = df_itens['Recurso_cor_sigla'].where(
                df_itens['Recurso_cor_sigla'].isin(MAPA_CORES_PINTURA.keys()), 'LC'
            )
            df_itens['cor'] = df_itens['Recurso_cor_sigla'].map(MAPA_CORES_PINTURA)

        df_itens['Recurso'] = normalizar_codigo_recurso_serie(df_itens['Recurso_original'])
        df_itens['Recurso'] = df_itens['Recurso'].apply(lambda x: '0' + x if len(x) == 5 else x)

        df_merged = pd.merge(df_itens, base_carretas[colunas_carretas], on='Recurso', how='left')

        logger.info(
            "[from_items] carga=%s | linhas_apos_merge=%d (antes dropna)",
            carga_liberada.get("carga"), len(df_merged),
        )

        df_merged = df_merged.dropna(subset=['Código', 'Peca', 'Célula']).copy()

        if df_merged.empty:
            logger.warning("[from_items] carga=%s | merge vazio apos dropna", carga_liberada.get("carga"))
            continue

        df_merged['Qtde_total'] = (
            pd.to_numeric(df_merged['quantidade'], errors='coerce').fillna(0).astype(int) *
            pd.to_numeric(df_merged['Qtde'], errors='coerce').fillna(0).astype(int)
        )

        logger.info("[from_items] carga=%s | linhas_apos_qtde_total (antes filtro >0)=%d", carga_liberada.get("carga"), len(df_merged))
        for _, row in df_merged.iterrows():
            logger.info(
                "[from_items] merged_row | recurso=%s | qtd_item=%s | qtde_carreta=%s | qtde_total=%s | celula=%s",
                row.get('Recurso', ''), row.get('quantidade', ''), row.get('Qtde', ''), row.get('Qtde_total', ''), row.get('Célula', ''),
            )

        df_merged = df_merged[df_merged['Qtde_total'] > 0].copy()

        df_merged['Código'] = (
            df_merged['Código'].fillna('').astype(str).str.strip()
            .str.replace(r'\.0$', '', regex=True)
        )
        df_merged['Código'] = df_merged['Código'].apply(
            lambda x: '0' + x if len(x) == 5 else (x[:6] if len(x) == 8 else x)
        )

        # Coleta origens ANTES do groupby: cada linha do merge mostra
        # qual recurso do banco (codigo_recurso + quantidade) gerou qual subtotal
        for _, mrow in df_merged.iterrows():
            codigo_norm = (
                mrow['Código'].fillna('') if hasattr(mrow['Código'], 'fillna')
                else str(mrow.get('Código', '') or '')
            ).strip().replace(r'\.0$', '')
            peca_nome_orig = str(mrow.get('Código', '')).strip() + " - " + str(mrow.get('Peca', '')).strip()
            celula_orig = str(mrow.get('Célula', '')).strip()
            cor_orig = str(mrow.get('cor', '')).strip() if setor == 'pintura' else ''
            chave_orig = (peca_nome_orig, celula_orig, cor_orig)
            if chave_orig not in origens:
                origens[chave_orig] = []
            origens[chave_orig].append({
                "recurso": str(mrow.get('codigo_recurso', mrow.get('Recurso', ''))),
                "quantidade_item": int(pd.to_numeric(mrow.get('quantidade', 0), errors='coerce') or 0),
                "qtde_por_unidade": int(pd.to_numeric(mrow.get('Qtde', 0), errors='coerce') or 0),
                "subtotal": int(mrow.get('Qtde_total', 0)),
                "carga": carga_liberada.get("carga", ""),
            })

        if setor == 'pintura':
            if 'Etapa5' in df_merged.columns:
                etapa5 = df_merged['Etapa5'].fillna('').str.upper()
                df_merged.loc[etapa5.str.contains('CINZA'), 'cor'] = 'Cinza'
                df_merged.loc[etapa5.str.contains('PRETO'), 'cor'] = 'Preto'

            df_final = (
                df_merged.groupby(['Código', 'Peca', 'Célula', 'cor'], as_index=False)['Qtde_total'].sum()
            )
            df_final.drop_duplicates(subset=['Código', 'cor'], inplace=True)
        else:
            df_final = (
                df_merged.groupby(['Código', 'Peca', 'Célula'], as_index=False)['Qtde_total'].sum()
            )
            df_final.drop_duplicates(subset=['Código', 'Célula'], inplace=True)

        logger.info("[from_items] carga=%s | itens_finais_apos_groupby=%d", carga_liberada.get("carga"), len(df_final))
        for _, row in df_final.iterrows():
            logger.info(
                "[from_items] item_final | codigo=%s | peca=%s | celula=%s | qtde_total=%s",
                row.get('Código', ''), row.get('Peca', ''), row.get('Célula', ''), row.get('Qtde_total', ''),
            )

        for _, row in df_final.iterrows():
            ordens.append({
                "grupo_maquina": setor.lower(),
                "cor": row.get("cor", '') if setor == 'pintura' else '',
                "obs": "Ordem gerada automaticamente",
                "peca_nome": str(row["Código"]) + " - " + row["Peca"],
                "qtd_planejada": int(row["Qtde_total"]),
                "data_carga": data_carga_planejada.isoformat(),
                "setor_conjunto": row["Célula"],
                "carga_liberada_id": carga_liberada["carga_liberada_id"],
                "carga_liberada_versao_id": carga_liberada["carga_liberada_versao_id"],
            })

    return consolidar_ordens_planejamento(ordens), origens


def _listar_cargas_planejamento_para_atualizacao(data_planejada, setor):
    versoes_prefetch = Prefetch(
        "versoes",
        queryset=CargaLiberadaVersao.objects.order_by("-versao"),
        to_attr="versoes_ordenadas",
    )

    cargas = (
        CargaLiberada.objects.filter(
            Q(data_carga=data_planejada) | Q(data_sugerida_planejamento=data_planejada),
            ativo=True,
        )
        .prefetch_related(versoes_prefetch)
        .order_by("data_carga", "carga_nome")
    )

    resultado = []
    for carga in cargas:
        versoes_ordenadas = getattr(carga, "versoes_ordenadas", [])
        if not versoes_ordenadas:
            continue

        ultima_versao = versoes_ordenadas[0]
        resultado.append(
            {
                "carga_liberada_id": carga.id,
                "carga_liberada_versao_id": ultima_versao.id,
                "carga_uuid": str(carga.carga_uuid),
                "versao_uuid": str(ultima_versao.versao_uuid),
                "data_carga": carga.data_carga,
                "data_sugerida_planejamento": carga.data_sugerida_planejamento,
                "carga": carga.carga_nome,
                "versao": ultima_versao.versao,
            }
        )

    return resultado


def _chave_ordem_planejada(setor, ordem):
    setor_conjunto = ordem.get("setor_conjunto", "") or ""
    if setor == "pintura":
        setor_conjunto = ""

    base = (
        ordem["grupo_maquina"],
        str(ordem["data_carga"]),
        setor_conjunto,
        ordem["peca_nome"],
    )
    if setor == "pintura":
        return base + (ordem.get("cor", ""),)
    return base


def _chave_ordem_existente(setor, ordem):
    if setor == "montagem":
        peca_nome = ordem.ordem_pecas_montagem.values_list("peca", flat=True).first() or ""
        return (
            ordem.grupo_maquina,
            ordem.data_carga.isoformat() if ordem.data_carga else "",
            ordem.maquina.nome if ordem.maquina else "",
            peca_nome,
        )
    if setor == "pintura":
        peca_nome = ordem.ordem_pecas_pintura.values_list("peca", flat=True).first() or ""
        return (
            ordem.grupo_maquina,
            ordem.data_carga.isoformat() if ordem.data_carga else "",
            ordem.maquina.nome if ordem.maquina else "",
            peca_nome,
            ordem.cor or "",
        )
    peca_nome = ordem.ordem_pecas_solda.values_list("peca", flat=True).first() or ""
    return (
        ordem.grupo_maquina,
        ordem.data_carga.isoformat() if ordem.data_carga else "",
        ordem.maquina.nome if ordem.maquina else "",
        peca_nome,
    )

@login_required
def home(request):

    return render(request, "cargas/home.html")

@login_required
def liberacao(request):

    return render(request, "cargas/liberacao.html")


def _marcar_selecao_versao_anterior(itens_sem_numero_serie):
    if not itens_sem_numero_serie:
        return

    cargas_consultadas = {
        (item.get("data_carga"), item.get("carga"))
        for item in itens_sem_numero_serie
        if item.get("data_carga") and item.get("carga")
    }
    if not cargas_consultadas:
        return

    datas = {data_carga for data_carga, _ in cargas_consultadas}
    nomes = {carga_nome for _, carga_nome in cargas_consultadas}
    ultima_versao = (
        CargaLiberadaVersao.objects.filter(carga_liberada=OuterRef("pk"))
        .order_by("-versao")
        .values("pk")[:1]
    )
    cargas = (
        CargaLiberada.objects.filter(data_carga__in=datas, carga_nome__in=nomes)
        .annotate(ultima_versao_id=Subquery(ultima_versao))
        .exclude(ultima_versao_id__isnull=True)
    )
    versoes_por_carga = {
        (carga.data_carga.isoformat(), carga.carga_nome): carga.ultima_versao_id
        for carga in cargas
        if (carga.data_carga.isoformat(), carga.carga_nome) in cargas_consultadas
    }

    itens_selecionados = defaultdict(set)
    for item in CargaLiberadaItem.objects.filter(
        carga_versao_id__in=versoes_por_carga.values(),
        numero_serie="",
    ).values(
        "carga_versao_id",
        "codigo_recurso",
        "cliente_codigo",
    ):
        itens_selecionados[item["carga_versao_id"]].add(
            (
                str(item["codigo_recurso"]).strip(),
                str(item["cliente_codigo"] or "").strip(),
            )
        )

    for item in itens_sem_numero_serie:
        versao_id = versoes_por_carga.get(
            (item.get("data_carga"), item.get("carga"))
        )
        chave_item = (
            str(item.get("codigo_recurso", "")).strip(),
            str(item.get("cliente_codigo", "") or "").strip(),
        )
        item["selecionado_versao_anterior"] = (
            chave_item in itens_selecionados.get(versao_id, set())
        )


def buscar_dados_carreta_planilha(request):
    data_inicio = request.GET.get('data_inicio')
    data_final = request.GET.get('data_fim')

    # Converte as datas de string para datetime (garante que None não cause erro)
    if data_inicio:
        data_inicio = pd.to_datetime(data_inicio, errors='coerce')

    if data_final:
        data_final = pd.to_datetime(data_final, errors='coerce')

    # Verifica se as datas foram convertidas corretamente
    if pd.isna(data_inicio) or pd.isna(data_final):
        return JsonResponse({'error': 'Datas inválidas'}, status=400)

    # Retorna o detalhado direto da planilha, sem a agregação final por data/recurso/carga.
    cargas = consultar_carretas_detalhado(data_inicio, data_final)
    _marcar_selecao_versao_anterior(
        cargas.get("itens_sem_numero_serie", [])
    )

    return JsonResponse({'cargas': cargas})


def buscar_cargas_liberadas(request):
    data_inicio = request.GET.get("data_inicio")
    data_final = request.GET.get("data_fim")

    try:
        data_inicio_obj = datetime.strptime(data_inicio, "%Y-%m-%d").date() if data_inicio else None
        data_final_obj = datetime.strptime(data_final, "%Y-%m-%d").date() if data_final else None
    except ValueError:
        return JsonResponse({"error": "Formato de data inválido. Use YYYY-MM-DD."}, status=400)

    if not data_inicio_obj or not data_final_obj:
        return JsonResponse({"error": "data_inicio e data_fim são obrigatórios."}, status=400)

    if data_inicio_obj > data_final_obj:
        return JsonResponse({"error": "A data início deve ser menor ou igual à data fim."}, status=400)

    try:
        cargas = listar_cargas_liberadas_periodo(data_inicio_obj, data_final_obj)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    return JsonResponse({"cargas": cargas})

@csrf_exempt
@require_POST
def liberar_cargas(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Usuário não autenticado."}, status=401)

    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON inválido."}, status=400)

    data_inicio = data.get("data_inicio")
    data_fim = data.get("data_fim")
    itens_sem_numero_serie_selecionados = data.get("itens_sem_numero_serie_selecionados", [])

    if not data_inicio or not data_fim:
        return JsonResponse(
            {"error": "Os campos data_inicio e data_fim são obrigatórios."},
            status=400,
        )

    try:
        data_inicio_obj = datetime.strptime(data_inicio, "%Y-%m-%d").date()
        data_fim_obj = datetime.strptime(data_fim, "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({"error": "Formato de data inválido. Use YYYY-MM-DD."}, status=400)

    if data_inicio_obj > data_fim_obj:
        return JsonResponse(
            {"error": "A data início deve ser menor ou igual à data fim."},
            status=400,
        )

    try:
        resultado = liberar_cargas_periodo(
            usuario=request.user,
            data_inicio=data_inicio_obj,
            data_fim=data_fim_obj,
            incluir_sheet_rows_sem_numero_serie=itens_sem_numero_serie_selecionados,
        )
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except Exception as exc:
        logger.exception("Falha ao liberar cargas")
        return JsonResponse({"error": f"Erro ao liberar cargas: {exc}"}, status=500)

    threading.Thread(
        target=_enviar_email_carga_liberada,
        args=(resultado, data_inicio, data_fim, request.user.username),
        daemon=True,
    ).start()

    return JsonResponse(
        {
            "message": "Cargas liberadas com sucesso.",
            **resultado,
        },
        status=201,
    )

def gerar_arquivos_sequenciamento(request):
    """
    Gera arquivos Excel do sequenciamento, compacta em ZIP e chama a API 'criar_ordem'.
    """
    data_inicio = request.GET.get('data_inicio')
    data_final = request.GET.get('data_fim')
    setor = request.GET.get('setor')

    if not data_inicio or not data_final or not setor:
        return HttpResponse("Erro: Parâmetros obrigatórios ausentes.", status=400)

    # Gerar os arquivos e a tabela completa
    arquivos_gerados = gerar_arquivos(data_inicio, data_final, setor)

    if not arquivos_gerados:
        return HttpResponse("Nenhum arquivo foi gerado.", status=500)

    # Criar ZIP na memória
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for filename in arquivos_gerados:
            with open(filename, "rb") as f:
                zip_file.writestr(os.path.basename(filename), f.read())

    zip_buffer.seek(0)

    # Retornar ZIP para download
    response = HttpResponse(zip_buffer, content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="sequenciamento_{datetime.now().strftime("%Y%m%d")}.zip"'

    # Remover arquivos temporários
    for filename in arquivos_gerados:
        os.remove(filename)

    return response
    
def gerar_dados_sequenciamento(request):
    data_inicio = request.GET.get('data_inicio')
    data_final = request.GET.get('data_fim')
    setor = request.GET.get('setor')
    sugestoes_brutas = request.GET.get('sugestoes_datas')

    if not data_inicio or not data_final or not setor:
        return HttpResponse("Erro: Parâmetros obrigatórios ausentes.", status=400)

    try:
        data_inicio_obj = datetime.strptime(data_inicio, "%Y-%m-%d").date()
        data_final_obj = datetime.strptime(data_final, "%Y-%m-%d").date()
        sugestoes_datas = _normalizar_sugestoes_datas(sugestoes_brutas)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    try:
        cargas_liberadas = listar_cargas_liberadas_para_planejamento(
            data_inicio_obj,
            data_final_obj,
        )
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    if not cargas_liberadas:
        return JsonResponse(
            {"error": "Não existem cargas liberadas no período selecionado."},
            status=400,
        )

    conflitos_datas = defaultdict(list)
    datas_finais_por_carga = {}
    atualizacoes_sugeridas = {}

    for carga_liberada in cargas_liberadas:
        data_original = carga_liberada["data_carga"]
        data_sugerida = sugestoes_datas.get(data_original)
        data_final_carga = data_sugerida or data_original

        conflitos_datas[data_final_carga.isoformat()].append(data_original.isoformat())
        datas_finais_por_carga[carga_liberada["carga_liberada_id"]] = data_final_carga
        atualizacoes_sugeridas[carga_liberada["carga_liberada_id"]] = data_sugerida

    conflitos = {
        data_final_str: datas_origem
        for data_final_str, datas_origem in conflitos_datas.items()
        if len(set(datas_origem)) > 1
    }
    if conflitos:
        conflitos_texto = ", ".join(
            f"{data_final_str} <= {', '.join(sorted(set(datas_origem)))}"
            for data_final_str, datas_origem in sorted(conflitos.items())
        )
        return JsonResponse(
            {"error": f"Conflito de sugestão de datas: {conflitos_texto}"},
            status=400,
        )

    datas_finais = sorted({data.isoformat() for data in datas_finais_por_carga.values()})
    if Ordem.objects.filter(grupo_maquina=setor, data_carga__in=datas_finais).exists():
        return JsonResponse(
            {'error': 'Já existe uma carga programada para a data sugerida selecionada'},
            status=400,
        )

    ordens, _ = _construir_ordens_planejamento_from_items(
        cargas_liberadas,
        setor,
        datas_finais_por_carga,
    )

    if not ordens:
        return JsonResponse(
            {"error": "Nenhuma ordem foi gerada a partir das cargas liberadas selecionadas."},
            status=400,
        )

    if setor.lower() == 'montagem':
        resultado = processar_ordens_montagem(request, ordens, grupo_maquina=setor.lower())
    elif setor.lower() == 'pintura':
        resultado = processar_ordens_pintura(ordens, grupo_maquina=setor.lower())
    else:
        resultado = processar_ordens_solda(ordens, grupo_maquina=setor.lower())

    if "error" in resultado:
        logger.warning(
            "gerar_dados_sequenciamento falhou | setor=%s | data_inicio=%s | data_fim=%s | erro=%s | ordens=%s",
            setor,
            data_inicio,
            data_final,
            resultado.get("error"),
            ordens
        )
        return JsonResponse({"error": resultado["error"]}, status=resultado.get("status", 400))

    atualizar_datas_sugeridas_planejamento(atualizacoes_sugeridas)
    return JsonResponse({"message": "Sequenciamento gerado com sucesso!", "detalhes": "resultado"})


@require_GET
def verificar_planejamento_montagem(request):
    data_inicio = request.GET.get("data_inicio")
    data_final = request.GET.get("data_fim")
    sugestoes_brutas = request.GET.get("sugestoes_datas")

    if not data_inicio or not data_final:
        return JsonResponse(
            {"error": "Parâmetros 'data_inicio' e 'data_fim' são obrigatórios."},
            status=400,
        )

    try:
        data_inicio_obj = datetime.strptime(data_inicio, "%Y-%m-%d").date()
        data_final_obj = datetime.strptime(data_final, "%Y-%m-%d").date()
        sugestoes_datas = _normalizar_sugestoes_datas(sugestoes_brutas)
        preview = montar_preview_planejamento_montagem(
            data_inicio_obj,
            data_final_obj,
            sugestoes_datas=sugestoes_datas,
            validar_datas_existentes=False,
        )
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    ordens = [
        {
            **ordem,
            "data_carga": ordem["data_carga"].isoformat(),
        }
        for ordem in preview["ordens"]
    ]

    cargas = [
        {
            **carga,
            "data_carga_original": carga["data_carga_original"].isoformat(),
            "data_carga_planejada": carga["data_carga_planejada"].isoformat(),
        }
        for carga in preview["cargas"]
    ]

    resumo_por_data = defaultdict(int)
    resumo_por_carga = defaultdict(int)
    for ordem in ordens:
        resumo_por_data[ordem["data_carga"]] += 1
        resumo_por_carga[str(ordem["carga_liberada_id"])] += 1

    return JsonResponse(
        {
            "setor": "montagem",
            "datas_finais": [data.isoformat() for data in preview["datas_finais"]],
            "maquinas_nao_cadastradas": preview["maquinas_nao_cadastradas"],
            "total_cargas": len(cargas),
            "total_ordens": len(ordens),
            "cargas": cargas,
            "ordens": ordens,
            "resumo_por_data": resumo_por_data,
            "resumo_por_carga_liberada": resumo_por_carga,
        }
    )

    # Gerar os arquivos e a tabela completa
    tabela_completa = gerar_sequenciamento(data_inicio, data_final, setor)

    # tabela_completa['cor'].unique()

    if setor == 'pintura':
        tabela_completa = tabela_completa.groupby(['Código', 'Peca', 'Célula', 'Datas','Recurso_cor','cor']).agg({'Qtde_total': 'sum'}).reset_index()
        tabela_completa.drop_duplicates(subset=['Código','Datas','cor'], inplace=True)
    else:
        tabela_completa.drop_duplicates(subset=['Código','Datas','Célula'], inplace=True)

    # Criar a carga para a API de criar ordem
    ordens = []
    for _, row in tabela_completa.iterrows():
        ordens.append({
            "grupo_maquina": setor.lower(),
            "cor": row["cor"] if setor == 'pintura' else '',
            "obs": "Ordem gerada automaticamente",
            "peca_nome": str(row["Código"]) + " - " + row["Peca"],
            "qtd_planejada": int(row["Qtde_total"]),
            "data_carga": str(row["Datas"].date()) if setor in ['montagem', 'solda'] else row["Datas"],
            "setor_conjunto" : row["Célula"]
        })

    if setor.lower() == 'montagem':
        resultado = processar_ordens_montagem(request, ordens, grupo_maquina=setor.lower())
    elif setor.lower() == 'pintura':
        resultado = processar_ordens_pintura(ordens, grupo_maquina=setor.lower())
    else:
        resultado = processar_ordens_solda(ordens, grupo_maquina=setor.lower())

    if "error" in resultado:
        logger.warning(
            "gerar_dados_sequenciamento falhou | setor=%s | data_inicio=%s | data_fim=%s | erro=%s | ordens=%s",
            setor,
            data_inicio,
            data_final,
            resultado.get("error"),
            ordens
        )
        return JsonResponse({"error": resultado["error"]}, status=resultado.get("status", 400))

    return JsonResponse({"message": "Sequenciamento gerado com sucesso!", "detalhes": "resultado"})

@csrf_exempt
def atualizar_ordem_existente_planejamento(request):
    """
    Atualiza as ordens de um dia usando o mesmo fluxo do planejamento gerado
    a partir das cargas liberadas e reconcilia as ordens existentes.
    """

    data_inicio = request.GET.get('data_inicio')
    setor = request.GET.get('setor')

    if not data_inicio or not setor:
        return HttpResponse("Erro: ParÃ¢metros obrigatÃ³rios ausentes.", status=400)

    try:
        data_planejada = datetime.strptime(data_inicio, "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({"error": "Formato de data invÃ¡lido. Use YYYY-MM-DD."}, status=400)

    ordens_existentes_qs = Ordem.objects.filter(
        data_carga=data_planejada,
        grupo_maquina=setor,
    )

    STATUS_PROTEGIDOS = ['iniciada', 'finalizada', 'interrompida']

    if setor == 'montagem':
        ordens_com_apontamentos = ordens_existentes_qs.filter(
            Q(status_atual__in=STATUS_PROTEGIDOS) |
            Q(ordem_pecas_montagem__qtd_boa__gt=0)
        ).distinct()
    elif setor == 'pintura':
        ordens_com_apontamentos = ordens_existentes_qs.filter(
            Q(status_atual__in=STATUS_PROTEGIDOS) |
            Q(ordem_pecas_pintura__qtd_boa__gt=0)
        ).distinct()
    else:
        ordens_com_apontamentos = ordens_existentes_qs.filter(
            Q(status_atual__in=STATUS_PROTEGIDOS) |
            Q(ordem_pecas_solda__qtd_boa__gt=0)
        ).distinct()

    ordens_com_apontamentos_ids = set(ordens_com_apontamentos.values_list('id', flat=True))

    cargas_liberadas = _listar_cargas_planejamento_para_atualizacao(data_planejada, setor)
    if not cargas_liberadas:
        return JsonResponse(
            {"error": "NÃ£o existem cargas liberadas vinculadas a esse planejamento."},
            status=400,
        )

    datas_finais_por_carga = {
        carga_liberada["carga_liberada_id"]: data_planejada
        for carga_liberada in cargas_liberadas
    }
    ordens_planejadas, origens_planejamento = _construir_ordens_planejamento_from_items(
        cargas_liberadas,
        setor,
        datas_finais_por_carga,
    )

    logger.info(
        "[atualizar-planejamento] data=%s setor=%s total_itens_planejados=%d",
        data_inicio, setor, len(ordens_planejadas),
    )
    for op in ordens_planejadas:
        logger.info(
            "[atualizar-planejamento] item | peca=%s | qtd_planejada=%s | setor_conjunto=%s | cor=%s",
            op.get("peca_nome"), op.get("qtd_planejada"), op.get("setor_conjunto", ""), op.get("cor", ""),
        )

    # Monta dict das ordens existentes indexado por peca_nome (+ cor para pintura).
    # Isso evita queries por maquina__nome que falham quando o nome da célula no
    # Sheets não bate exatamente com Maquina.nome no banco.
    # Chave inclui (peca_nome, celula/maquina) para diferenciar o mesmo item em células distintas.
    # Ex: "037567G - CILINDRO CAF" em CILINDRO e em QUALIDADE são duas ordens separadas.
    map_existentes = {}
    for ordem in ordens_existentes_qs.prefetch_related(
        'ordem_pecas_montagem', 'ordem_pecas_pintura', 'ordem_pecas_solda'
    ).select_related('maquina'):
        maquina_nome = ordem.maquina.nome if ordem.maquina else ''
        if setor == 'montagem':
            peca = ordem.ordem_pecas_montagem.values_list('peca', flat=True).first() or ''
            chave = (peca, maquina_nome)
        elif setor == 'pintura':
            peca = ordem.ordem_pecas_pintura.values_list('peca', flat=True).first() or ''
            chave = (peca, ordem.cor or '')
        else:
            peca = ordem.ordem_pecas_solda.values_list('peca', flat=True).first() or ''
            chave = (peca, maquina_nome)
        if chave not in map_existentes:
            map_existentes[chave] = ordem

    # Monta dict das ordens planejadas indexado pela mesma chave
    map_planejadas = {}
    for op in ordens_planejadas:
        if setor == 'pintura':
            chave = (op['peca_nome'], op.get('cor', ''))
        else:
            chave = (op['peca_nome'], op.get('setor_conjunto', ''))
        map_planejadas[chave] = op

    # Exclui ordens que saíram do planejamento (e não são protegidas)
    ids_para_excluir = [
        ordem.id
        for chave, ordem in map_existentes.items()
        if chave not in map_planejadas and ordem.id not in ordens_com_apontamentos_ids
    ]
    if ids_para_excluir:
        Ordem.objects.filter(id__in=ids_para_excluir).delete()

    ordens_a_criar = []
    for chave, op in map_planejadas.items():
        ordem_existente = map_existentes.get(chave)

        if ordem_existente:
            fields_to_update = []
            if ordem_existente.carga_liberada_id != op.get("carga_liberada_id"):
                ordem_existente.carga_liberada_id = op.get("carga_liberada_id")
                fields_to_update.append("carga_liberada_id")
            if ordem_existente.carga_liberada_versao_id != op.get("carga_liberada_versao_id"):
                ordem_existente.carga_liberada_versao_id = op.get("carga_liberada_versao_id")
                fields_to_update.append("carga_liberada_versao_id")
            if fields_to_update:
                ordem_existente.save(update_fields=fields_to_update)

            # Não atualiza quantidade de ordens já iniciadas/finalizadas ou com produção registrada
            if ordem_existente.id not in ordens_com_apontamentos_ids:
                nova_qtd = int(op["qtd_planejada"])
                if setor == 'montagem':
                    qs = ordem_existente.ordem_pecas_montagem
                    if not qs.filter(peca=op["peca_nome"]).update(qtd_planejada=nova_qtd):
                        qs.update(qtd_planejada=nova_qtd)
                elif setor == 'pintura':
                    qs = ordem_existente.ordem_pecas_pintura
                    if not qs.filter(peca=op["peca_nome"]).update(qtd_planejada=nova_qtd):
                        qs.update(qtd_planejada=nova_qtd)
                else:
                    qs = ordem_existente.ordem_pecas_solda
                    if not qs.filter(peca=op["peca_nome"]).update(qtd_planejada=nova_qtd):
                        qs.update(qtd_planejada=nova_qtd)
        else:
            ordens_a_criar.append(op)

    resultado = {"message": "Ordens atualizadas com sucesso."}
    if ordens_a_criar:
        if setor == 'montagem':
            resultado = processar_ordens_montagem(request, ordens_a_criar, atualizacao_ordem=True, grupo_maquina=setor.lower())
        elif setor == 'pintura':
            resultado = processar_ordens_pintura(ordens_a_criar, atualizacao_ordem=True, grupo_maquina=setor.lower())
        else:
            resultado = processar_ordens_solda(ordens_a_criar, atualizacao_ordem=True, grupo_maquina=setor.lower())

        if "error" in resultado:
            return JsonResponse({"error": resultado["error"]}, status=resultado.get("status", 400))

    ordens_protegidas = []
    for ordem in ordens_com_apontamentos.select_related('maquina'):
        if setor == 'montagem':
            peca = ordem.ordem_pecas_montagem.values_list('peca', flat=True).first() or ''
        elif setor == 'pintura':
            peca = ordem.ordem_pecas_pintura.values_list('peca', flat=True).first() or ''
        else:
            peca = ordem.ordem_pecas_solda.values_list('peca', flat=True).first() or ''
        ordens_protegidas.append({
            'id': ordem.id,
            'data_carga': ordem.data_carga.isoformat() if ordem.data_carga else '',
            'grupo_maquina': ordem.grupo_maquina,
            'status_atual': ordem.status_atual,
            'peca': peca,
        })

    def _agrupar_origens(lista):
        """Agrupa origens pelo mesmo recurso+qtde_por_unidade+carga, somando quantidade_item."""
        agrupado = {}
        for o in lista:
            chave = (o["recurso"], o["qtde_por_unidade"], o["carga"])
            if chave not in agrupado:
                agrupado[chave] = {**o}
            else:
                agrupado[chave]["quantidade_item"] += o["quantidade_item"]
                agrupado[chave]["subtotal"] += o["subtotal"]
        return list(agrupado.values())

    itens_planejados = [
        {
            "peca": op["peca_nome"],
            "qtd_planejada": int(op["qtd_planejada"]),
            "setor_conjunto": op.get("setor_conjunto", ""),
            "cor": op.get("cor", ""),
            "nova": op in ordens_a_criar,
            "origem": _agrupar_origens(
                origens_planejamento.get(
                    (op["peca_nome"], op.get("setor_conjunto", ""), op.get("cor", "")), []
                )
            ),
        }
        for op in ordens_planejadas
    ]

    return JsonResponse({
        "message": "Ordens atualizadas com sucesso!",
        "ordens_com_apontamentos": ordens_protegidas,
        "novas_ordens_criadas": len(ordens_a_criar),
        "itens_planejados": itens_planejados,
    })


@csrf_exempt
def atualizar_ordem_existente(request):
    """
    Atualiza as ordens de um dia específico:
    - Remove ordens sem apontamento que foram retiradas do sequenciamento
    - Mantém ordens que já têm apontamentos
    - Atualiza `qtd_planejada` de ordens já existentes
    - Cria novas ordens para itens adicionados
    - Retorna as ordens que não puderam ser removidas
    """

    data_inicio = request.GET.get('data_inicio')
    setor = request.GET.get('setor')
    # data_inicio = '2025-06-26'
    # setor = 'pintura'

    if not data_inicio or not setor:
        return HttpResponse("Erro: Parâmetros obrigatórios ausentes.", status=400)

    intervalo_datas_formatado = [
        datetime.strptime(data_inicio, "%Y-%m-%d").strftime("%Y-%m-%d")
    ]

    # Filtra ordens existentes do dia
    ordens_existentes_qs = Ordem.objects.filter(
        data_carga__in=intervalo_datas_formatado,
        grupo_maquina=setor
    )

    # Separar ordens que já têm apontamentos
    if setor == 'montagem':
        ordens_com_apontamentos = ordens_existentes_qs.annotate(
            total_produzido=Sum('ordem_pecas_montagem__qtd_boa')
        ).filter(total_produzido__gt=0)
    elif setor == 'pintura':
        ordens_com_apontamentos = ordens_existentes_qs.annotate(
            total_produzido=Sum('ordem_pecas_pintura__qtd_boa')
        ).filter(total_produzido__gt=0)
    else:
        ordens_com_apontamentos = ordens_existentes_qs.annotate(
            total_produzido=Sum('ordem_pecas_solda__qtd_boa')
        ).filter(total_produzido__gt=0)

    ordens_com_apontamentos_ids = set(ordens_com_apontamentos.values_list('id', flat=True))

    # Gerar a tabela completa
    tabela_completa = gerar_sequenciamento(data_inicio, data_inicio, setor)
    
    # print(tabela_completa[tabela_completa['cor'] == 'Amarelo'])

    if setor == 'pintura':
        tabela_completa = tabela_completa.groupby(['Código', 'Peca', 'Célula', 'Datas','Recurso_cor','cor']).agg({'Qtde_total': 'sum'}).reset_index()
        tabela_completa.drop_duplicates(subset=['Código', 'Datas', 'cor'], inplace=True)
        # tabela_completa["Datas"] = pd.to_datetime(tabela_completa["Datas"], format="%d/%m/%Y", errors="coerce").dt.strftime("%Y-%m-%d")
    else:
        tabela_completa.drop_duplicates(subset=['Código', 'Datas', 'Célula'], inplace=True)
        # tabela_completa["Datas"] = pd.to_datetime(tabela_completa["Datas"], format="%Y-%d-%m", errors="coerce").dt.strftime("%Y-%m-%d")

    # Conjunto de peças atuais
    if setor == 'pintura':
        pecas_atualizadas = set(
            (f"{str(row['Código'])} - {row['Peca']}", row['cor']) for _, row in tabela_completa.iterrows()
        )
    else:
        pecas_atualizadas = set(
            f"{str(row['Código'])} - {row['Peca']}" for _, row in tabela_completa.iterrows()
        )

    # Identificar ordens sem apontamento que não existem mais no sequenciamento
    if setor == 'montagem':
        ordens_sem_apontamento = ordens_existentes_qs.exclude(id__in=ordens_com_apontamentos_ids).filter(
            ~Q(ordem_pecas_montagem__peca__in=pecas_atualizadas)
        )
    elif setor == 'pintura':
        # ordens_sem_apontamento = ordens_existentes_qs.exclude(id__in=ordens_com_apontamentos_ids).filter(
        #     ~Q(ordem_pecas_pintura__peca__in=pecas_atualizadas)
        # )
        condicao = Q()
        for peca, cor in pecas_atualizadas:
            condicao |= Q(ordem_pecas_pintura__peca=peca, cor=cor)

        ordens_sem_apontamento = ordens_existentes_qs.exclude(id__in=ordens_com_apontamentos_ids).exclude(condicao)
    else:
        ordens_sem_apontamento = ordens_existentes_qs.exclude(id__in=ordens_com_apontamentos_ids).filter(
            ~Q(ordem_pecas_solda__peca__in=pecas_atualizadas)
        )

    # Remove essas ordens
    ordens_sem_apontamento.delete()

    # Preparar lista para criar novas ordens
    ordens_a_criar = []

    # tabela_completa = tabela_completa.iloc[31:32]
    # tabela_completa.reset_index(drop=True)

    for _, row in tabela_completa.iterrows():
        peca_nome = f"{str(row['Código'])} - {row['Peca']}"
        data_carga = row["Datas"]

        if setor == 'montagem':
            ordem_existente = Ordem.objects.filter(
                grupo_maquina=setor,
                data_carga=data_carga,
                ordem_pecas_montagem__peca=peca_nome
            ).first()
        elif setor == 'pintura':
            ordem_existente = Ordem.objects.filter(
                grupo_maquina=setor,
                data_carga=data_carga,
                ordem_pecas_pintura__peca=peca_nome,
                cor=row['cor']
            ).first()
        else:
            ordem_existente = Ordem.objects.filter(
                grupo_maquina=setor,
                data_carga=data_carga,
                ordem_pecas_solda__peca=peca_nome
            ).first()

        if ordem_existente:
            # Atualizar qtd_planejada na peça vinculada
            if setor == 'montagem':
                ordem_existente.ordem_pecas_montagem.filter(peca=peca_nome).update(qtd_planejada=int(row["Qtde_total"]))
            elif setor == 'pintura':
                ordem_existente.ordem_pecas_pintura.filter(peca=peca_nome).update(qtd_planejada=int(row["Qtde_total"]))
            else:
                ordem_existente.ordem_pecas_solda.filter(peca=peca_nome).update(qtd_planejada=int(row["Qtde_total"]))
        else:
            # Criar nova ordem
            ordens_a_criar.append({
                "grupo_maquina": setor.lower(),
                "cor": row["cor"] if setor == 'pintura' else '',
                "obs": "Ordem gerada automaticamente",
                "peca_nome": peca_nome,
                "qtd_planejada": int(row["Qtde_total"]),
                "data_carga": data_carga,
                "setor_conjunto": row["Célula"]
            })

    # Processar novas ordens
    if setor == 'montagem':
        resultado = processar_ordens_montagem(request, ordens_a_criar, atualizacao_ordem=True, grupo_maquina=setor.lower())
    elif setor == 'pintura':
        resultado = processar_ordens_pintura(ordens_a_criar, atualizacao_ordem=True, grupo_maquina=setor.lower())
    else:
        resultado = processar_ordens_solda(ordens_a_criar, atualizacao_ordem=True, grupo_maquina=setor.lower())

    if "error" in resultado:
        return JsonResponse({"error": resultado["error"]}, status=resultado.get("status", 400))

    # Retorno final
    return JsonResponse({
        "message": "Ordens atualizadas com sucesso!",
        "ordens_com_apontamentos": list(ordens_com_apontamentos.values('id', 'data_carga', 'grupo_maquina')),
        "novas_ordens_criadas": len(ordens_a_criar),
    })

@csrf_exempt
def remanejar_carga(request):
    """ Remaneja cargas cuja data_carga é igual à data antiga e move para a nova data. """

    if request.method == 'POST':
        try:
            data = json.loads(request.body)

            setor = data.get('setor')  # "montagem" ou "pintura"
            data_atual = data.get('dataAtual')  # Data da carga que será movida
            data_remaneja = data.get('dataRemanejar')  # Nova data

            if not setor or not data_atual or not data_remaneja:
                return JsonResponse({'error': 'Setor, data atual e nova data são obrigatórios'}, status=400)

            # Converte as datas para o formato correto
            data_atual = datetime.strptime(data_atual, "%Y-%m-%d").date()
            data_remaneja = datetime.strptime(data_remaneja, "%Y-%m-%d").date()

            # Filtra apenas as ordens do setor cuja `data_carga` é igual à `data_atual`
            ordens_atualizadas = Ordem.objects.filter(
                grupo_maquina=setor,
                data_carga=data_atual
            )

            if not ordens_atualizadas.exists():
                return JsonResponse({'error': 'Nenhuma carga encontrada para essa data'}, status=404)

            # Verifica se já existe uma carga na nova data
            if Ordem.objects.filter(grupo_maquina=setor, data_carga=data_remaneja).exists():
                return JsonResponse({'error': 'Já existe uma carga programada para essa data'}, status=400)

            # **Recalcula `data_programacao` apenas uma vez, pois todas as ordens seguem a mesma lógica**
            if setor == 'montagem':
                data_programacao = data_remaneja - timedelta(days=3)
            elif setor == 'solda':
                data_programacao = data_remaneja - timedelta(days=2)
            elif setor == 'pintura':
                data_programacao = data_remaneja - timedelta(days=1)

            # Ajusta `data_programacao` para sexta-feira se cair no fim de semana
            while data_programacao.weekday() in [5, 6]:  # 5 = Sábado, 6 = Domingo
                data_programacao -= timedelta(days=1)

            # Atualiza todas as ordens filtradas em um único comando SQL
            ordens_atualizadas.update(data_carga=data_remaneja, data_programacao=data_programacao)

            return JsonResponse({'message': 'Carga remanejada com sucesso!'})

        except json.JSONDecodeError:
            return JsonResponse({'error': 'JSON inválido'}, status=400)

    return JsonResponse({'error': 'Método não permitido'}, status=405)

def parse_iso_date(date_str):
    """ Converte datas ISO do FullCalendar ('YYYY-MM-DDTHH:mm:ssZ') para 'YYYY-MM-DD' """
    try:
        return datetime.strptime(date_str[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


@login_required
@require_GET
def datas_historico_liberacoes(request):
    start_date = parse_iso_date(request.GET.get("start"))
    end_date = parse_iso_date(request.GET.get("end"))

    if not start_date or not end_date:
        return JsonResponse(
            {"error": "Parâmetros 'start' e 'end' são obrigatórios e devem ser datas válidas."},
            status=400,
        )
    if start_date >= end_date:
        return JsonResponse(
            {"error": "A data inicial deve ser anterior à data final."},
            status=400,
        )

    datas = list(
        CargaLiberada.objects
        .filter(data_carga__gte=start_date, data_carga__lt=end_date)
        .order_by("data_carga")
        .values_list("data_carga", flat=True)
        .distinct()
    )
    return JsonResponse({
        "datas": [data.isoformat() for data in datas],
    })


@login_required
@require_GET
def historico_liberacoes_dia(request):
    data_carga = parse_date(request.GET.get("data", ""))
    if data_carga is None:
        return JsonResponse(
            {"error": "O parâmetro 'data' é obrigatório e deve estar no formato YYYY-MM-DD."},
            status=400,
        )

    cargas = (
        CargaLiberada.objects
        .filter(data_carga=data_carga)
        .prefetch_related(
            Prefetch(
                "versoes",
                queryset=(
                    CargaLiberadaVersao.objects
                    .select_related("liberado_por")
                    .prefetch_related("alteracoes_destino")
                    .order_by("-versao")
                ),
            ),
        )
        .order_by("carga_nome")
    )

    cargas_serializadas = []
    for carga in cargas:
        versoes = []
        for versao in carga.versoes.all():
            alteracoes = []
            for alteracao in versao.alteracoes_destino.all():
                detalhes = alteracao.detalhes or {}
                alteracoes.append({
                    "tipo": alteracao.tipo_alteracao,
                    "tipo_display": alteracao.get_tipo_alteracao_display(),
                    "codigo_recurso": alteracao.codigo_recurso,
                    "cliente_codigo": detalhes.get("cliente_codigo", ""),
                    "numero_serie": detalhes.get("numero_serie", ""),
                    "quantidade_anterior": alteracao.quantidade_anterior,
                    "quantidade_nova": alteracao.quantidade_nova,
                    "motivo": detalhes.get("motivo") or detalhes.get("mensagem", ""),
                    "criado_em": localtime(alteracao.criado_em).strftime("%d/%m/%Y %H:%M"),
                })

            versoes.append({
                "versao": versao.versao,
                "liberado_em": localtime(versao.liberado_em).strftime("%d/%m/%Y %H:%M"),
                "liberado_por": versao.liberado_por.username,
                "data_inicio_pesquisa": versao.data_inicio_pesquisa.strftime("%d/%m/%Y"),
                "data_fim_pesquisa": versao.data_fim_pesquisa.strftime("%d/%m/%Y"),
                "alteracoes": alteracoes,
            })

        cargas_serializadas.append({
            "carga_uuid": str(carga.carga_uuid),
            "carga": carga.carga_nome,
            "ativo": carga.ativo,
            "versoes": versoes,
        })

    return JsonResponse({
        "data": data_carga.isoformat(),
        "data_formatada": data_carga.strftime("%d/%m/%Y"),
        "cargas": cargas_serializadas,
    })


def andamento_liberacoes(request):
    start_date = parse_iso_date(request.GET.get("start"))
    end_date = parse_iso_date(request.GET.get("end"))

    if not start_date or not end_date:
        return JsonResponse({"error": "Parâmetros 'start' e 'end' são obrigatórios"}, status=400)

    liberacoes = (
        CargaLiberada.objects.filter(
            data_carga__gte=start_date,
            data_carga__lt=end_date,
            ativo=True,
        )
        .annotate(
            ultima_versao=Max("versoes__versao"),
            ultimo_liberado_em=Subquery(
                CargaLiberadaVersao.objects.filter(
                    carga_liberada=OuterRef("pk")
                )
                .order_by("-versao")
                .values("liberado_em")[:1]
            ),
        )
        .order_by("data_carga", "carga_nome")
    )

    eventos = [
        {
            "id": f"liberacao-{liberacao.carga_uuid}",
            "title": f"{liberacao.carga_nome} v{liberacao.ultima_versao or 1}",
            "start": liberacao.data_carga.strftime("%Y-%m-%d"),
            "allDay": True,
            "backgroundColor": "#dc3545" if liberacao.data_sugerida_planejamento else "#198754",
            "borderColor": "#dc3545" if liberacao.data_sugerida_planejamento else "#198754",
            "extendedProps": {
                "tipo": "liberacao",
                "carga_uuid": str(liberacao.carga_uuid),
                "versao": liberacao.ultima_versao or 1,
                "liberado_em": (
                    localtime(liberacao.ultimo_liberado_em).strftime("%d/%m/%Y %H:%M")
                    if liberacao.ultimo_liberado_em
                    else ""
                ),
                "data_carga": liberacao.data_carga.strftime("%d/%m/%Y"),
                "data_sugerida_planejamento": (
                    liberacao.data_sugerida_planejamento.strftime("%d/%m/%Y")
                    if liberacao.data_sugerida_planejamento
                    else ""
                ),
            },
        }
        for liberacao in liberacoes
    ]

    return JsonResponse(eventos, safe=False)

def detalhes_liberacao(request, carga_uuid):
    carga = get_object_or_404(CargaLiberada, carga_uuid=carga_uuid)
    ultima_versao = (
        carga.versoes.select_related("liberado_por")
        .prefetch_related("itens")
        .order_by("-versao")
        .first()
    )

    if ultima_versao is None:
        return JsonResponse({"error": "Nenhuma versão encontrada para esta carga."}, status=404)

    return JsonResponse(
        {
            "carga_uuid": str(carga.carga_uuid),
            "carga": carga.carga_nome,
            "data_carga": carga.data_carga.strftime("%Y-%m-%d"),
            "data_carga_formatada": carga.data_carga.strftime("%d/%m/%Y"),
            "data_sugerida_planejamento": (
                carga.data_sugerida_planejamento.strftime("%Y-%m-%d")
                if carga.data_sugerida_planejamento
                else ""
            ),
            "data_sugerida_planejamento_formatada": (
                carga.data_sugerida_planejamento.strftime("%d/%m/%Y")
                if carga.data_sugerida_planejamento
                else ""
            ),
            "tem_data_sugerida": bool(carga.data_sugerida_planejamento),
            "ativo": carga.ativo,
            "inativada_em": (
                localtime(carga.inativada_em).strftime("%d/%m/%Y %H:%M")
                if carga.inativada_em
                else ""
            ),
            "total_ordens_vinculadas": carga.ordens_sequenciadas.count(),
            "pode_excluir": not carga.ordens_sequenciadas.exists(),
            "versao": ultima_versao.versao,
            "liberado_em": localtime(ultima_versao.liberado_em).strftime("%d/%m/%Y %H:%M"),
            "liberado_por": ultima_versao.liberado_por.username,
            "itens": [
                {
                    "cliente": item.cliente or item.cliente_codigo,
                    "codigo_recurso": item.codigo_recurso,
                    "quantidade": item.quantidade,
                    "presente_no_carreta": item.presente_no_carreta,
                }
                for item in ultima_versao.itens.all().order_by("cliente", "cliente_codigo", "codigo_recurso")
            ],
        }
    )


@csrf_exempt
@require_POST
def excluir_liberacao(request, carga_uuid):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Usuário não autenticado."}, status=401)

    with transaction.atomic():
        carga = (
            CargaLiberada.objects.select_for_update()
            .prefetch_related("ordens_sequenciadas")
            .filter(carga_uuid=carga_uuid)
            .first()
        )

        if carga is None:
            return JsonResponse({"error": "Carga não encontrada."}, status=404)

        total_ordens_vinculadas = carga.ordens_sequenciadas.count()
        if total_ordens_vinculadas:
            return JsonResponse(
                {
                    "error": (
                        "Não é possível excluir esta carga porque ela já possui "
                        f"{total_ordens_vinculadas} ordem(ns) vinculada(s)."
                    )
                },
                status=409,
            )

        ultima_versao = carga.versoes.order_by("-versao").first()
        carga_nome = carga.carga_nome
        data_carga = carga.data_carga.strftime("%d/%m/%Y")
        carga.ativo = False
        carga.inativada_em = now()
        carga.save(update_fields=["ativo", "inativada_em", "atualizado_em"])

        if ultima_versao is not None:
            CargaLiberadaAlteracao.objects.create(
                carga_liberada=carga,
                versao_origem=ultima_versao,
                versao_destino=ultima_versao,
                tipo_alteracao="carga_inativada",
                detalhes={"motivo": "Carga inativada manualmente pelo usuário."},
            )

    return JsonResponse(
        {
            "message": f"Carga {carga_nome} de {data_carga} inativada com sucesso.",
        }
    )


@csrf_exempt
@require_POST
def aplicar_data_sugerida_liberacao(request, carga_uuid):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Usuário não autenticado."}, status=401)

    with transaction.atomic():
        carga = (
            CargaLiberada.objects.select_for_update()
            .prefetch_related("versoes__itens", "ordens_sequenciadas")
            .filter(carga_uuid=carga_uuid)
            .first()
        )

        if carga is None:
            return JsonResponse({"error": "Carga não encontrada."}, status=404)

        if not carga.data_sugerida_planejamento:
            return JsonResponse({"error": "Esta carga não possui data sugerida para aplicar."}, status=400)

        data_atual = carga.data_carga
        data_destino = carga.data_sugerida_planejamento

        conflito = CargaLiberada.objects.filter(
            data_carga=data_destino,
            carga_nome=carga.carga_nome,
            ativo=True,
        ).exclude(pk=carga.pk)
        if conflito.exists():
            return JsonResponse(
                {"error": "Já existe uma carga com esse nome na data sugerida."},
                status=400,
            )

        ultima_versao = carga.versoes.order_by("-versao").first()
        clientes = set()
        if ultima_versao is not None:
            clientes = {
                item.cliente or item.cliente_codigo
                for item in ultima_versao.itens.all()
                if item.cliente or item.cliente_codigo
            }

        for ordem in carga.ordens_sequenciadas.all():
            ordem.data_carga = data_destino
            ordem.data_programacao = _calcular_data_programacao_por_setor(
                ordem.grupo_maquina,
                data_destino,
            )
            ordem.save(update_fields=["data_carga", "data_programacao"])

        for cliente in clientes:
            link_atual = LinkAcompanhamento.objects.filter(
                data_carga=data_atual,
                cliente=cliente,
            ).first()
            link_destino = LinkAcompanhamento.objects.filter(
                data_carga=data_destino,
                cliente=cliente,
            ).first()

            if link_destino:
                if link_atual and link_atual.pk != link_destino.pk:
                    link_atual.delete()
            elif link_atual:
                link_atual.data_carga = data_destino
                link_atual.save(update_fields=["data_carga"])
            else:
                LinkAcompanhamento.objects.create(
                    data_carga=data_destino,
                    cliente=cliente,
                )

        carga.data_carga = data_destino
        carga.data_sugerida_planejamento = None
        carga.save(update_fields=["data_carga", "data_sugerida_planejamento", "atualizado_em"])

    return JsonResponse(
        {
            "message": "Data sugerida aplicada com sucesso.",
            "carga_uuid": str(carga.carga_uuid),
            "data_carga": carga.data_carga.strftime("%Y-%m-%d"),
        }
    )


@require_GET
def status_carga_por_data(request):
    data_carga = request.GET.get("data_carga")
    cliente = (request.GET.get("cliente") or "").strip()

    if not data_carga:
        return JsonResponse({"error": "O parâmetro data_carga é obrigatório."}, status=400)
    if not cliente:
        return JsonResponse({"error": "O parâmetro cliente é obrigatório."}, status=400)

    try:
        data_carga_obj = datetime.strptime(data_carga, "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({"error": "Formato de data inválido. Use YYYY-MM-DD."}, status=400)

    liberacoes = (
        CargaLiberadaVersao.objects.filter(
            carga_liberada__data_carga=data_carga_obj,
            carga_liberada__ativo=True,
        ).filter(
            Q(carga_liberada__versoes__itens__cliente=cliente)
            | Q(carga_liberada__versoes__itens__cliente_codigo=cliente)
        )
        .distinct()
        .order_by("liberado_em")
    )
    primeira_liberacao = liberacoes.first()
    cargas_liberadas_ids = list(
        liberacoes.values_list("carga_liberada_id", flat=True).distinct()
    )

    if primeira_liberacao is None:
        return JsonResponse(
            {
                "data_carga": data_carga_obj.strftime("%Y-%m-%d"),
                "cliente": cliente,
                "status": "aguardando_liberacao",
                "descricao": "Aguardando liberação",
                "historico": [],
            }
        )

    primeira_expedicao = (
        CargaExpedicao.objects.filter(data_carga=data_carga_obj, cliente=cliente)
        .order_by("data_criacao")
        .first()
    )
    primeira_montagem = (
        Ordem.objects.filter(
            grupo_maquina="montagem",
            data_carga=data_carga_obj,
            carga_liberada_id__in=cargas_liberadas_ids,
        )
        .distinct()
        .order_by("data_criacao")
        .first()
    )
    primeira_expedida = (
        CargaExpedicao.objects.filter(
            data_carga=data_carga_obj,
            cliente=cliente,
            stage="despachado",
            data_despachado__isnull=False,
        )
        .order_by("data_despachado")
        .first()
    )

    historico = [
        {
            "status": "liberado",
            "descricao": "Liberado",
            "data": localtime(primeira_liberacao.liberado_em).strftime("%d/%m/%Y"),
        }
    ]

    if primeira_montagem is not None:
        historico.append(
            {
                "status": "em_fabricacao",
                "descricao": "Em fabricação",
                "data": localtime(primeira_montagem.data_criacao).strftime("%d/%m/%Y"),
            }
        )

    if primeira_expedicao is not None:
        historico.append(
            {
                "status": "liberado_expedicao",
                "descricao": "Liberado para expedição",
                "data": localtime(primeira_expedicao.data_criacao).strftime("%d/%m/%Y"),
            }
        )

    if primeira_expedida is not None:
        historico.append(
            {
                "status": "expedida",
                "descricao": "Expedida",
                "data": localtime(primeira_expedida.data_despachado).strftime("%d/%m/%Y"),
            }
        )

    if primeira_expedida is not None:
        return JsonResponse(
            {
                "data_carga": data_carga_obj.strftime("%Y-%m-%d"),
                "cliente": cliente,
                "status": "expedida",
                "descricao": "Expedida",
                "historico": historico,
            }
        )

    return JsonResponse(
        {
            "data_carga": data_carga_obj.strftime("%Y-%m-%d"),
            "cliente": cliente,
            "status": "em_fabricacao" if primeira_montagem is not None else "liberado",
            "descricao": "Em fabricação" if primeira_montagem is not None else "Liberado",
            "historico": historico,
        }
    )

def andamento_cargas(request):
    """ Retorna as cargas de um setor dentro do intervalo solicitado pelo FullCalendar """

    # Algumas máquinas que não precisam está na contagem de montagem
    maquinas_excluidas = [
        'PLAT. TANQUE. CAÇAM. 2',
        'QUALIDADE',
        'FORJARIA',
        'ESTAMPARIA',
        'Carpintaria',
        'FEIXE DE MOLAS',
        'SERRALHERIA',
        'ROÇADEIRA'
    ]

    maquinas_excluidas_ids = Maquina.objects.filter(nome__in=maquinas_excluidas).values_list('id', flat=True)

    # Obtém os parâmetros da requisição
    start_date = request.GET.get('start')
    end_date = request.GET.get('end')

    # Converte as datas corretamente
    start_date = parse_iso_date(start_date)
    end_date = parse_iso_date(end_date)

    if not start_date or not end_date:
        return JsonResponse({"error": "Parâmetros 'start' e 'end' são obrigatórios"}, status=400)
    
    setores = ["pintura", "montagem", "solda"]
    andamento_cargas = []

    for setor in setores:

        # Define as cores e modelos conforme o setor
        if setor == "pintura":
            modelo = POPintura
        elif setor == "montagem":
            modelo = POMontagem
        else:
            modelo = POSolda
        
        if setor == "pintura":
            cor = "#28a745"
        elif setor == "montagem":
            cor = "#007bff"
        else:
            cor = "#ffc107" 

        # Filtra apenas as ordens dentro do intervalo solicitado
        cargas = Ordem.objects.filter(
            grupo_maquina=setor,
            data_carga__range=[start_date, end_date],
            ordem_pai__isnull=True
        ).order_by('data_carga').values_list('data_carga', flat=True).distinct()
        
        for data in cargas:
            total_planejado = modelo.objects.filter(
                ordem__data_carga=data,
                ordem__grupo_maquina=setor
            ).exclude(ordem__maquina__id__in=maquinas_excluidas_ids) \
            .values('ordem', 'peca').distinct().aggregate(
                total_planejado=Coalesce(Sum('qtd_planejada', output_field=models.FloatField()), Value(0.0))
            )["total_planejado"]

            total_finalizado = modelo.objects.filter(
                ordem__data_carga=data,
                ordem__grupo_maquina=setor
            ).exclude(ordem__maquina__id__in=maquinas_excluidas_ids) \
            .aggregate(
                total_finalizado=Coalesce(Sum('qtd_boa', output_field=models.FloatField()), Value(0.0))
            )["total_finalizado"]

            percentual_concluido = (total_finalizado / total_planejado * 100) if total_planejado > 0 else 0.0

            andamento_cargas.append({
                "id": f"{setor}-{data.strftime('%Y-%m-%d')}",  # Gera um ID único baseado no setor e data
                "title": f"{setor.capitalize()} - {round(percentual_concluido, 2)}%",
                "start": data.strftime("%Y-%m-%d"),  # Formato correto para FullCalendar
                "allDay": True,
                "backgroundColor": cor,  # Cor baseada no setor
                "borderColor": cor,
                "extendedProps": {"setor": setor, "data_atual": data.strftime("%Y-%m-%d")}  # Propriedade personalizada
            })

    return JsonResponse(andamento_cargas, safe=False)  # Retorna um ARRAY direto

@login_required
@require_POST
@csrf_exempt
def gerar_link_acompanhamento(request):
    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON inválido."}, status=400)

    data_carga = data.get("data_carga")
    cliente = (data.get("cliente") or "").strip()

    if not data_carga or not cliente:
        return JsonResponse({"error": "data_carga e cliente são obrigatórios."}, status=400)

    try:
        data_carga_obj = datetime.strptime(data_carga, "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({"error": "Formato de data inválido. Use YYYY-MM-DD."}, status=400)

    link, _ = LinkAcompanhamento.objects.get_or_create(
        data_carga=data_carga_obj,
        cliente=cliente,
    )

    url = request.build_absolute_uri(
        reverse("cargas:acompanhamento_cliente", args=[str(link.token)])
    )
    return JsonResponse({"url": url, "token": str(link.token)})


def acompanhamento_cliente(request, token):
    link = get_object_or_404(LinkAcompanhamento, token=token)
    return render(request, "cargas/acompanhamento.html", {
        "data_carga": link.data_carga.strftime("%Y-%m-%d"),
        "cliente": link.cliente,
        "data_carga_formatada": link.data_carga.strftime("%d/%m/%Y"),
    })


def historico_cargas(request):

    return render(request, "cargas/historico.html")

def historico_ordens_montagem(request):
    """
    View que agrega os dados de PecasOrdem (por ordem) e junta com a model Ordem,
    trazendo algumas colunas da Ordem e calculando o saldo:
        saldo = soma(qtd_planejada) - soma(qtd_boa)
    
    Parâmetros esperados na URL (via GET):
      - data_carga: data da carga (default: hoje)
      - maquina: nome da máquina (opcional)
      - status: status da ordem (opcional)
      - page: número da página
      - limit: quantidade de itens por página

    """

    data_carga = request.GET.get('data_carga')
    maquina_param = request.GET.get('setor', None) # Chassi, Içamento...
    status_param = request.GET.get('status', None)
    ordem_param = request.GET.get('ordem', None)
    conjunto_param = request.GET.get('conjunto', '')

    # Paginação
    page = request.GET.get('page', 1)
    limit = request.GET.get('limit', 10)  # Default: 10 itens por página

    try:
        limit = int(limit)
        page = int(page)
    except ValueError:
        return JsonResponse({"error": "Parâmetros de paginação inválidos."}, status=400)

    # Monta os filtros para a model Ordem
    filtros_ordem = {
        'grupo_maquina': 'montagem'
    }

    if data_carga:
        try:
            data_carga = datetime.strptime(data_carga, "%Y-%m-%d").date()
            filtros_ordem['data_carga'] = data_carga  # Removida a vírgula extra
        except ValueError:
            return JsonResponse({"error": "Formato de data inválido. Use YYYY-MM-DD."}, status=400)
    if maquina_param:
        maquina = get_object_or_404(Maquina, pk=maquina_param)
        filtros_ordem['maquina'] = maquina
    if status_param:
        filtros_ordem['status_atual'] = status_param
    if ordem_param:
        filtros_ordem['id'] = ordem_param
    if conjunto_param:
        filtros_ordem['ordem_pecas_montagem__peca__icontains'] = conjunto_param

    # Recupera os IDs das ordens que atendem aos filtros
    ordem_ids = Ordem.objects.filter(**filtros_ordem).values_list('id', flat=True)

    # Consulta na PecasOrdem filtrando pelas ordens identificadas,
    # trazendo alguns campos da Ordem (usando a notação "ordem__<campo>"),
    # e agrupando para calcular as somas e o saldo.
    pecas_ordem_agg = POMontagem.objects.filter(ordem_id__in=ordem_ids).values(
        'ordem',                    # id da ordem (chave para o agrupamento)
        'ordem__data_carga',        # data da carga da ordem
        'ordem__data_programacao',  # data da programação da ordem
        'ordem__maquina__nome',     # nome da máquina (ajuste se necessário)
        'ordem__status_atual',      # status atual da ordem
        'peca',                     # nome da peça
    ).annotate(
        total_planejada=Coalesce(
            Avg('qtd_planejada'), Value(0.0, output_field=models.FloatField())
        ),
        total_produzido=Coalesce(
            Sum('qtd_boa'), Value(0.0, output_field=models.FloatField())
        )
    )

    # Aplicando a paginação
    paginator = Paginator(pecas_ordem_agg, limit)
    
    try:
        ordens_paginadas = paginator.page(page)
    except PageNotAnInteger:
        ordens_paginadas = paginator.page(1)
    except EmptyPage:
        ordens_paginadas = []

    maquinas = Ordem.objects.filter(id__in=ordem_ids).values('maquina__nome', 'maquina__id').distinct()

    return JsonResponse({
        "ordens": list(ordens_paginadas),
        "maquinas": list(maquinas),
        "total_ordens": paginator.count,
        "total_paginas": paginator.num_pages,
        "pagina_atual": page
    })

def historico_ordens_pintura(request):
    """
    View que agrega os dados de PecasOrdem (por ordem) e junta com a model Ordem,
    trazendo algumas colunas da Ordem e calculando o saldo:
        saldo = soma(qtd_planejada) - soma(qtd_boa)
    
    Parâmetros esperados na URL (via GET):
      - data_carga: data da carga (default: hoje)
      - maquina: nome da máquina (opcional)
      - status: status da ordem (opcional)
      - page: número da página
      - limit: quantidade de itens por página

    """

    data_carga = request.GET.get('data_carga')
    cor = request.GET.get('cor', '') # Chassi, Içamento...
    status_param = request.GET.get('status', '')
    ordem_param = request.GET.get('ordem', '')
    conjunto_param = request.GET.get('conjunto', '')

    # Paginação
    page = request.GET.get('page', 1)
    limit = request.GET.get('limit', 10)  # Default: 10 itens por página

    try:
        limit = int(limit)
        page = int(page)
    except ValueError:
        return JsonResponse({"error": "Parâmetros de paginação inválidos."}, status=400)

    # Monta os filtros para a model Ordem
    filtros_ordem = {
        'grupo_maquina': 'pintura'
    }

    if data_carga:
        try:
            data_carga = datetime.strptime(data_carga, "%Y-%m-%d").date()
            filtros_ordem['data_carga'] = data_carga
        except ValueError:
            return JsonResponse({"error": "Formato de data inválido. Use YYYY-MM-DD."}, status=400)
    if cor:
        filtros_ordem['cor'] = cor
    if status_param:
        filtros_ordem['status_atual'] = status_param
    if ordem_param:
        filtros_ordem['id'] = ordem_param
    if conjunto_param:
        filtros_ordem['ordem_pecas_pintura__peca__icontains'] = conjunto_param

    # Recupera os IDs das ordens que atendem aos filtros
    ordem_ids = Ordem.objects.filter(**filtros_ordem).values_list('id', flat=True)

    # Consulta na PecasOrdem filtrando pelas ordens identificadas,
    # trazendo alguns campos da Ordem (usando a notação "ordem__<campo>"),
    # e agrupando para calcular as somas e o saldo.
    pecas_ordem_agg = POPintura.objects.filter(ordem_id__in=ordem_ids).values(
        'ordem',                    # id da ordem (chave para o agrupamento)
        'ordem__data_carga',        # data da carga da ordem
        'ordem__data_programacao',  # data da programação da ordem
        'ordem__cor',               # cor
        'ordem__status_atual',      # status atual da ordem
        'peca',                     # nome da peça
    ).annotate(
        total_planejada=Coalesce(
            Avg('qtd_planejada'), Value(0.0, output_field=models.FloatField())
        ),
        total_produzido=Coalesce(
            Sum('qtd_boa'), Value(0.0, output_field=models.FloatField())
        )

    )

    # Aplicando a paginação
    paginator = Paginator(pecas_ordem_agg, limit)
    
    try:
        ordens_paginadas = paginator.page(page)
    except PageNotAnInteger:
        ordens_paginadas = paginator.page(1)
    except EmptyPage:
        ordens_paginadas = []

    return JsonResponse({
        "ordens": list(ordens_paginadas),
        "total_ordens": paginator.count,
        "total_paginas": paginator.num_pages,
        "pagina_atual": page
    })

def historico_ordens_solda(request):
    """
    View que agrega os dados de PecasOrdem (por ordem) e junta com a model Ordem,
    trazendo algumas colunas da Ordem e calculando o saldo:
        saldo = soma(qtd_planejada) - soma(qtd_boa)
    
    Parâmetros esperados na URL (via GET):
      - data_carga: data da carga (default: hoje)
      - maquina: nome da máquina (opcional)
      - status: status da ordem (opcional)
      - page: número da página
      - limit: quantidade de itens por página

    """

    data_carga = request.GET.get('data_carga')
    maquina_param = request.GET.get('setor', None) # Chassi, Içamento...
    status_param = request.GET.get('status', None)
    ordem_param = request.GET.get('ordem', None)
    conjunto_param = request.GET.get('conjunto', '')

    # Paginação
    page = request.GET.get('page', 1)
    limit = request.GET.get('limit', 10)  # Default: 10 itens por página

    try:
        limit = int(limit)
        page = int(page)
    except ValueError:
        return JsonResponse({"error": "Parâmetros de paginação inválidos."}, status=400)

    # Monta os filtros para a model Ordem
    filtros_ordem = {
        'grupo_maquina': 'solda'
    }

    if data_carga:
        try:
            data_carga = datetime.strptime(data_carga, "%Y-%m-%d").date()
            filtros_ordem['data_carga'] = data_carga  # Removida a vírgula extra
        except ValueError:
            return JsonResponse({"error": "Formato de data inválido. Use YYYY-MM-DD."}, status=400)
    if maquina_param:
        maquina = get_object_or_404(Maquina, pk=maquina_param)
        filtros_ordem['maquina'] = maquina
    if status_param:
        filtros_ordem['status_atual'] = status_param
    if ordem_param:
        filtros_ordem['id'] = ordem_param
    if conjunto_param:
        filtros_ordem['ordem_pecas_solda__peca__icontains'] = conjunto_param

    # Recupera os IDs das ordens que atendem aos filtros
    ordem_ids = Ordem.objects.filter(**filtros_ordem).values_list('id', flat=True)

    # Consulta na PecasOrdem filtrando pelas ordens identificadas,
    # trazendo alguns campos da Ordem (usando a notação "ordem__<campo>"),
    # e agrupando para calcular as somas e o saldo.
    pecas_ordem_agg = POSolda.objects.filter(ordem_id__in=ordem_ids).values(
        'ordem',                    # id da ordem (chave para o agrupamento)
        'ordem__data_carga',        # data da carga da ordem
        'ordem__data_programacao',  # data da programação da ordem
        'ordem__maquina__nome',     # nome da máquina (ajuste se necessário)
        'ordem__status_atual',      # status atual da ordem
        'peca',                     # nome da peça
    ).annotate(
        total_planejada=Coalesce(
            Avg('qtd_planejada'), Value(0.0, output_field=models.FloatField())
        ),
        total_produzido=Coalesce(
            Sum('qtd_boa'), Value(0.0, output_field=models.FloatField())
        )
    )

    # Aplicando a paginação
    paginator = Paginator(pecas_ordem_agg, limit)
    
    try:
        ordens_paginadas = paginator.page(page)
    except PageNotAnInteger:
        ordens_paginadas = paginator.page(1)
    except EmptyPage:
        ordens_paginadas = []

    maquinas = Ordem.objects.filter(id__in=ordem_ids).values('maquina__nome', 'maquina__id').distinct()

    return JsonResponse({
        "ordens": list(ordens_paginadas),
        "maquinas": list(maquinas),
        "total_ordens": paginator.count,
        "total_paginas": paginator.num_pages,
        "pagina_atual": page
    })

@csrf_exempt
def editar_planejamento(request):
    if request.method != "POST":
        return JsonResponse({"erro": "Método não permitido. Use POST!"}, status=405)

    try:
        # Carregar dados do corpo da requisição
        data = json.loads(request.body)

        nova_data_carga = data.get('novaDataCarga')
        qt_planejada = data.get('novaQtdPlan')
        ordem_id = data.get('ordemId')
        setor = data.get('setor')
        qtd_produzida = data.get('qtd_produzida')

        # Validação de campos obrigatórios
        if not ordem_id or not setor:
            return JsonResponse({"erro": "Os campos 'setor' e 'ordem_id' são obrigatórios!"}, status=400)

        # Buscar a ordem
        ordem = get_object_or_404(Ordem, pk=ordem_id)

        # Determinar o modelo correto com base no setor
        if setor == 'montagem':
            atualizar_ordens = POMontagem.objects.filter(ordem=ordem)
        elif setor == 'solda':
            atualizar_ordens = POSolda.objects.filter(ordem=ordem)
        else:
            atualizar_ordens = POPintura.objects.filter(ordem=ordem)

        if nova_data_carga:
            try:
                nova_data_carga = datetime.strptime(nova_data_carga, "%Y-%m-%d").date()
            except ValueError:
                return JsonResponse({"erro": "Formato de data inválido. Use YYYY-MM-DD."}, status=400)

            pecas_ordem = atualizar_ordens.values_list('peca', flat=True)

            if setor == 'montagem':
                conflito = Ordem.objects.filter(
                    data_carga=nova_data_carga,
                    ordem_pecas_montagem__peca__in=pecas_ordem,
                    maquina=ordem.maquina
                ).exclude(id=ordem_id).exists()
            elif setor == 'solda':
                conflito = Ordem.objects.filter(
                    data_carga=nova_data_carga,
                    ordem_pecas_solda__peca__in=pecas_ordem,
                    maquina=ordem.maquina
                ).exclude(id=ordem_id).exists()
            else:  # pintura
                conflito = Ordem.objects.filter(
                    data_carga=nova_data_carga,
                    ordem_pecas_pintura__peca__in=pecas_ordem,
                    cor=ordem.cor
                ).exclude(id=ordem_id).exists()

            if conflito:
                return JsonResponse({"erro": "Já existe uma ordem com o mesmo conjunto para essa data!"}, status=400)

            ordem.data_carga = nova_data_carga
            ordem.save()

        # Atualiza a quantidade planejada, se necessário
        if qt_planejada:
            atualizar_ordens.update(qtd_planejada=qt_planejada)

        # Atualiza a quantidade produzida, se enviada
        if qtd_produzida is not None:
            try:
                qtd_produzida = float(qtd_produzida)
            except (TypeError, ValueError):
                return JsonResponse({"erro": "Quantidade produzida inválida."}, status=400)
            if qtd_produzida < 0:
                return JsonResponse({"erro": "Quantidade produzida não pode ser negativa."}, status=400)

            if setor == 'montagem':
                soma_atual = atualizar_ordens.aggregate(total=Coalesce(Sum('qtd_boa'), Value(0.0)))['total'] or 0.0
                delta = qtd_produzida - float(soma_atual)
                ultima_execucao = atualizar_ordens.order_by('-data', '-id').first()
                if not ultima_execucao:
                    return JsonResponse({"erro": "Nenhuma execução encontrada para ajustar a produção."}, status=400)

                if delta < 0:
                    reduzir = abs(delta)
                    if reduzir > (ultima_execucao.qtd_boa or 0):
                        return JsonResponse({"erro": f"Redução maior que a última execução ({ultima_execucao.qtd_boa})."}, status=400)
                    ultima_execucao.qtd_boa = (ultima_execucao.qtd_boa or 0) - reduzir
                elif delta > 0:
                    ultima_execucao.qtd_boa = (ultima_execucao.qtd_boa or 0) + delta
                # se delta == 0 não altera
                if delta != 0:
                    ultima_execucao.save(update_fields=['qtd_boa'])
            elif setor == 'pintura':
                soma_atual = atualizar_ordens.aggregate(total=Coalesce(Sum('qtd_boa'), Value(0.0)))['total'] or 0.0
                delta = qtd_produzida - float(soma_atual)
                ultima_execucao = atualizar_ordens.order_by('-data', '-id').first()
                if not ultima_execucao:
                    return JsonResponse({"erro": "Nenhuma execução encontrada para ajustar a produção."}, status=400)

                if delta < 0:
                    reduzir = abs(delta)
                    if reduzir > (ultima_execucao.qtd_boa or 0):
                        return JsonResponse({"erro": f"Redução maior que a última execução ({ultima_execucao.qtd_boa})."}, status=400)
                    ultima_execucao.qtd_boa = (ultima_execucao.qtd_boa or 0) - reduzir
                elif delta > 0:
                    ultima_execucao.qtd_boa = (ultima_execucao.qtd_boa or 0) + delta

                if delta != 0:
                    ultima_execucao.save(update_fields=['qtd_boa'])
                    # Ajusta o último cambão vinculado à mesma peça/ordem
                    try:
                        from apontamento_pintura.models import CambaoPecas
                        cambao = (CambaoPecas.objects
                                  .filter(peca_ordem=ultima_execucao)
                                  .order_by('-data_pendura', '-id')
                                  .first())
                        if not cambao:
                            return JsonResponse({"erro": "Nenhum registro de cambão encontrado para esta peça/ordem."}, status=400)
                        if cambao:
                            if delta < 0 and cambao.quantidade_pendurada < abs(delta):
                                return JsonResponse({"erro": "Quantidade a reduzir maior que a última pendurada."}, status=400)
                            cambao.quantidade_pendurada = (cambao.quantidade_pendurada or 0) + delta
                            cambao.save(update_fields=['quantidade_pendurada'])
                    except Exception as e:
                        return JsonResponse({"erro": f"Falha ao ajustar cambão: {e}"}, status=400)
            else:
                atualizar_ordens.update(qtd_boa=qtd_produzida)

        return JsonResponse({"mensagem": "Planejamento atualizado com sucesso!"}, status=200)

    except json.JSONDecodeError:
        return JsonResponse({"erro": "Erro ao processar JSON. Verifique o formato da requisição!"}, status=400)

    except Exception as e:
        return JsonResponse({"erro": f"Ocorreu um erro: {str(e)}"}, status=500)    

@csrf_exempt
@require_POST
def excluir_ordens_dia_setor(request):
    """
    Exclui ordens de um dia e setor específicos via POST,
    somente se não houver apontamentos associados.
    
    Espera JSON no corpo da requisição com:
    {
        "data": "2025-06-03",
        "setor": "montagem"  # ou "pintura"
    }
    """

    try:
        payload = json.loads(request.body)
        data = payload.get('data')
        setor = payload.get('setor')
    except Exception:
        return JsonResponse({"error": "Erro ao ler o corpo da requisição. Envie JSON válido."}, status=400)

    if not data or not setor:
        return JsonResponse({"error": "Campos 'data' e 'setor' são obrigatórios."}, status=400)

    try:
        data_formatada = datetime.strptime(data, "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({"error": "Formato de data inválido. Use 'yyyy-mm-dd'."}, status=400)

    ordens_qs = Ordem.objects.filter(data_carga=data_formatada, grupo_maquina=setor)

    if setor == 'montagem':
        ordens_com_apontamentos = ordens_qs.annotate(
            total_apontado=Sum('ordem_pecas_montagem__qtd_boa')
        ).filter(total_apontado__gt=0)
    elif setor == 'pintura':
        ordens_com_apontamentos = ordens_qs.annotate(
            total_apontado=Sum('ordem_pecas_pintura__qtd_boa')
        ).filter(total_apontado__gt=0)
    elif setor == 'solda':
        ordens_com_apontamentos = ordens_qs.annotate(
            total_apontado=Sum('ordem_pecas_solda__qtd_boa')
        ).filter(total_apontado__gt=0)
    else:
        return JsonResponse({"error": "Setor inválido. Use 'montagem' ou 'pintura'."}, status=400)

    ordens_bloqueadas_ids = set(ordens_com_apontamentos.values_list('id', flat=True))

    if ordens_bloqueadas_ids:
        return JsonResponse({
            "error": "Existe ordens ja apontadas, retire elas dessa data."
        })   

    ordens_para_excluir = ordens_qs.exclude(id__in=ordens_bloqueadas_ids)
    total_excluidas = ordens_para_excluir.count()

    ordens_para_excluir.delete()

    return JsonResponse({
        "message": f"{total_excluidas} ordens excluídas com sucesso.",
        "ordens_bloqueadas": list(ordens_com_apontamentos.values("id", "data_carga", "grupo_maquina")),
    })    

@require_GET
def enviar_etiqueta_impressora(request):
    data_carga = request.GET.get('data_carga')

    payload_status = imprimir_ordens_montagem(data_carga)
    # aceita tanto (dict, status) quanto apenas dict
    if isinstance(payload_status, tuple):
        payload, status = payload_status
    else:
        payload, status = payload_status, 200

    return JsonResponse(payload, status=status)

@csrf_exempt
@require_POST
def enviar_etiqueta_impressora_montagem(request):
    payload = json.loads(request.body)
    cargas_payload = payload.get('cargas', [])

    if not cargas_payload:
        return JsonResponse({"error": "Nenhuma carga informada."}, status=400)

    def normalizar_recurso(valor):
        serie = pd.Series([str(valor).strip()], dtype="string")
        serie = normalizar_codigo_recurso_serie(serie)
        recurso = str(serie.iloc[0]).strip()
        return ('0' + recurso) if len(recurso) == 5 else recurso

    # Filtro de célula por carga: { 'CARGA 04': ['CELULA A', ...] }
    filtros_celula = {}
    filtros_recurso = {}
    for item in cargas_payload:
        nome = str(item.get('nome', '')).strip().upper()
        if nome:
            filtros_celula[nome] = [c.strip().upper() for c in (item.get('celulas') or []) if c.strip()]
            recursos_item = [
                str(recurso).strip()
                for recurso in (item.get('recursos') or [])
                if str(recurso).strip()
            ]
            if recursos_item:
                filtros_recurso[nome] = {
                    normalizar_recurso(recurso)
                    for recurso in recursos_item
                }

    # 1. Busca itens do banco para as cargas selecionadas
    linhas = []
    for item_carga in cargas_payload:
        nome_carga = str(item_carga.get('nome', '')).strip()
        data_carga_str = item_carga.get('data_carga', '')

        try:
            data_carga_obj = date.fromisoformat(data_carga_str) if data_carga_str else None
        except ValueError:
            data_carga_obj = None

        if not nome_carga or not data_carga_obj:
            continue

        try:
            carga_lib = CargaLiberada.objects.prefetch_related('versoes__itens').get(
                carga_nome=nome_carga,
                data_carga=data_carga_obj,
            )
        except CargaLiberada.DoesNotExist:
            logger.warning("[etiquetas_montagem] carga não encontrada no banco | nome=%s data=%s", nome_carga, data_carga_str)
            continue

        ultima_versao = carga_lib.versoes.order_by('-versao').first()
        if not ultima_versao:
            continue

        for item in ultima_versao.itens.all():
            recurso = str(item.codigo_recurso).strip()
            recurso_normalizado = normalizar_recurso(recurso)
            recursos_selecionados = filtros_recurso.get(carga_lib.carga_nome.strip().upper())
            if recursos_selecionados is not None and recurso_normalizado not in recursos_selecionados:
                continue

            linhas.append({
                'Recurso': recurso,
                'Qtde_pedido': float(item.quantidade),
                'Carga': carga_lib.carga_nome.strip().upper(),
                'Datas': carga_lib.data_carga.isoformat(),
            })

    logger.info("[etiquetas_montagem] itens coletados do banco | total=%d", len(linhas))
    print(f"[etiquetas_montagem] itens coletados do banco | total={len(linhas)}")

    if not linhas:
        logger.warning("[etiquetas_montagem] nenhum item encontrado no banco para as cargas")
        return JsonResponse(
            {"error": "Nenhum item encontrado no banco para as cargas selecionadas."},
            status=400,
        )

    try:
        # 2. Carrega aba de referência das carretas (dados estáticos de Código/Peca/Célula/Qtde)
        base_carretas = get_base_carreta()
        base_carretas['Recurso'] = base_carretas['Recurso'].astype(str)
        base_carretas['Recurso'] = normalizar_codigo_recurso_serie(base_carretas['Recurso'])
        base_carretas['Recurso'] = base_carretas['Recurso'].apply(
            lambda x: '0' + x if len(x) == 5 else x
        )
        if 'Etapa' in base_carretas.columns:
            base_carretas = base_carretas[base_carretas['Etapa'].fillna('') != ''].copy()
        base_carretas = base_carretas.reset_index(drop=True)

        # converte Qtde tolerando strings vazias ou inválidas
        base_carretas['Qtde'] = pd.to_numeric(base_carretas['Qtde'], errors='coerce').fillna(0)

        logger.info("[etiquetas_montagem] base_carretas carregada | linhas=%d", len(base_carretas))
        print(f"[etiquetas_montagem] base_carretas carregada | linhas={len(base_carretas)}")

        # 3. Normaliza Recurso dos itens do banco e faz merge
        df_itens = pd.DataFrame(linhas)
        df_itens['Recurso'] = normalizar_codigo_recurso_serie(df_itens['Recurso'])
        df_itens['Recurso'] = df_itens['Recurso'].apply(lambda x: '0' + x if len(x) == 5 else x)

        logger.info("[etiquetas_montagem] amostra recurso itens | %s", df_itens['Recurso'].head(5).tolist())
        print(f"[etiquetas_montagem] amostra recurso itens | {df_itens['Recurso'].head(5).tolist()}")

        df_merged = pd.merge(
            df_itens,
            base_carretas[['Recurso', 'Código', 'Peca', 'Qtde', 'Célula']],
            on='Recurso',
            how='left',
        )

        total_antes = len(df_merged)
        df_merged = df_merged.dropna(subset=['Código', 'Peca', 'Célula']).copy()
        logger.info("[etiquetas_montagem] merge | antes_dropna=%d depois_dropna=%d", total_antes, len(df_merged))
        print(f"[etiquetas_montagem] merge | antes_dropna={total_antes} depois_dropna={len(df_merged)}")

        if df_merged.empty:
            return JsonResponse(
                {"error": "Nenhum item das cargas selecionadas está na base de carretas de montagem."},
                status=400,
            )

        # 4. Calcula Qtde_total e normaliza Código
        df_merged['Qtde_pedido'] = pd.to_numeric(df_merged['Qtde_pedido'], errors='coerce').fillna(0)
        df_merged['Qtde'] = pd.to_numeric(df_merged['Qtde'], errors='coerce').fillna(0)
        df_merged['Qtde_total'] = (df_merged['Qtde_pedido'].astype(int) * df_merged['Qtde'].astype(int))
        df_merged = df_merged[df_merged['Qtde_total'] > 0].copy()

        logger.info("[etiquetas_montagem] após filtro qtd>0 | linhas=%d", len(df_merged))
        print(f"[etiquetas_montagem] após filtro qtd>0 | linhas={len(df_merged)}")

        df_merged['Código'] = (
            df_merged['Código'].fillna('').astype(str).str.strip()
            .str.replace(r'\.0$', '', regex=True)
        )
        df_merged['Código'] = df_merged['Código'].apply(
            lambda x: '0' + x if len(x) == 5 else (x[:6] if len(x) == 8 else x)
        )
        df_merged['Célula'] = df_merged['Célula'].astype(str).str.strip().str.upper()

        # 5. Aplica filtro de célula por carga (se especificado)
        def celula_ok(row):
            filtro = filtros_celula.get(row['Carga'], [])
            return not filtro or row['Célula'] in filtro

        df_merged = df_merged[df_merged.apply(celula_ok, axis=1)].copy()

        if df_merged.empty:
            return JsonResponse(
                {"error": "Nenhum item corresponde aos filtros de célula informados."},
                status=400,
            )

        # 6. Agrupa e imprime
        df_final = (
            df_merged.groupby(['Código', 'Peca', 'Célula', 'Datas', 'Carga'], as_index=False)['Qtde_total']
            .sum()
            .sort_values(['Célula', 'Datas'])
            .reset_index(drop=True)
        )

        logger.info("[etiquetas_montagem] df_final para impressão | linhas=%d", len(df_final))
        print(f"[etiquetas_montagem] df_final para impressão | linhas={len(df_final)}")
        print(df_final[['Código', 'Peca', 'Célula', 'Carga', 'Qtde_total']].to_string())

        imprimir_ordens_montagem(df_final)

    except Exception as exc:
        logger.exception("[etiquetas_montagem] erro inesperado")
        return JsonResponse({"error": f"Erro interno ao processar etiquetas: {exc}"}, status=500)

    return JsonResponse({"payload": f"Processadas {len(cargas_payload)} cargas"})

@csrf_exempt
@require_POST
def enviar_etiqueta_impressora_pintura(request):
    data = json.loads(request.body)

    data_carga = data.get('data_inicio')
    carga = data.get('carga')
    celulas = data.get('celulas', [])

    itens = gerar_sequenciamento(data_carga,data_carga,'pintura',carga)

    colunas_grupo = [
        "Código", "Peca", "Célula", "Datas", 
        "Recurso_cor", "cor", "Carga", "Etapa5", "Etapa6"
    ]

    itens_agrupado = (
        itens.groupby(colunas_grupo, as_index=False)["Qtde_total"]
        .sum()
    )

    # filtrando celulas caso esteja marcada
    if celulas:
        itens_agrupado = itens_agrupado[itens_agrupado['Célula'].isin(celulas)]

    # reitrando celulas
    itens_agrupado = itens_agrupado[
        ~itens_agrupado['Célula'].isin(['CONJ INTERMED'])
    ]
    
    substituicoes = {
        'PLAT.': 'PL.',
        'TANQUE.': 'TA.',
        'CAÇAM.': 'CA.',
        'IÇAMENTO': 'ICAMENTO'
    }

    # filtrando apenas células específicas
    # itens_agrupado = itens_agrupado[
    #     itens_agrupado['Célula'].isin(['CHASSI'])
    # ]

    # filtrando apenas células específicas
    # itens_agrupado = itens_agrupado[
    #     (itens_agrupado['Código'].isin(['460382'])) &
    #     (itens_agrupado['cor'] == 'Amarelo')
    # ]

    # Aplica as substituições
    itens_agrupado['Célula'] = itens_agrupado['Célula'].replace(substituicoes, regex=True)

    # payload_status = imprimir_ordens_pintura(data_carga, carga, itens_agrupado)
    # print(itens_agrupado)
    print(itens_agrupado)
    payload = imprimir_ordens_pcp_qualidade(data_carga, carga, itens_agrupado)

    return JsonResponse({"payload": "payload"})
    # return JsonResponse({"payload": payload})
    
@require_GET
def enviar_etiqueta_unitaria_impressora(request):
    ordem_id = request.GET.get('ordem_id')

    payload_status = imprimir_ordens_montagem_unitaria(ordem_id)
    # aceita tanto (dict, status) quanto apenas dict
    if isinstance(payload_status, tuple):
        payload, status = payload_status
    else:
        payload, status = payload_status, 200

    return JsonResponse(payload, status=status)

# API para consulta no google sheets
class AtTimeZone(Func):
    function = ''
    template = "%(expressions)s AT TIME ZONE '%(timezone)s'"
    output_field = CharField()

    def __init__(self, expression, timezone, **extra):
        super().__init__(expression, timezone=timezone, **extra)

class ToChar(Func):
    function = 'to_char'
    output_field = CharField()

def ordens_em_andamento_finalizada_pintura(request):
    """"
    traz as ordens aguardando inicio, em andamento e finalizadas na pintura
    """
    
    data_inicio_str = request.GET.get('data_inicio')
    data_fim_str = request.GET.get('data_fim')

    from pytz import timezone as pytz_timezone
    br_tz = pytz_timezone('America/Sao_Paulo')
    hoje_br = now().astimezone(br_tz).date()
    ultima_data_carga = (
        Ordem.objects
        .filter(grupo_maquina='pintura', data_carga__isnull=False)
        .aggregate(ultima_data=Max('data_carga'))['ultima_data']
    )
    data_fim_padrao = ultima_data_carga or hoje_br
    data_inicio_padrao = data_fim_padrao - timedelta(days=30)

    try:
        data_inicio = parse_date(data_inicio_str) if data_inicio_str else data_inicio_padrao
        data_fim = parse_date(data_fim_str) if data_fim_str else data_fim_padrao
    except (ValueError, TypeError):
        return JsonResponse({'erro': 'Formato de data inválido. Use YYYY-MM-DD.'}, status=400)

    if data_inicio is None or data_fim is None:
        return JsonResponse({'erro': 'Formato de data inválido. Use YYYY-MM-DD.'}, status=400)

    request_mutable = request.GET.copy()
    request_mutable['data_inicio'] = data_inicio.isoformat()
    request_mutable['data_fim'] = data_fim.isoformat()
    request.GET = request_mutable

    resultado = ordens_criadas_pintura(request)

    resultado_json_ordens_criadas = json.loads(resultado.content)

    ordens_aguardando_iniciar = []

    data_hora_atual = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    for ordem in resultado_json_ordens_criadas['ordens']:
        data_carga_datetime = datetime.strptime(ordem['data_carga'], "%Y-%m-%d").date()
        if not (data_inicio <= data_carga_datetime <= data_fim):
            continue

        #adicionar que a ordem aguardando_iniciar criando do mês atual
        ordens_aguardando_iniciar.append({
            'status': ordem['status_atual'],
            'quantidade_pendurada': 0,
            'id_ordem': ordem['id'],
            'ordem': ordem['ordem'],
            'peca': ordem['peca_codigo'],
            'qtd_planejada': ordem['peca_qt_planejada'],
            'cor': ordem['cor'],
            'data_criacao_fmt': formatar_data_str(ordem['data_criacao']) if ordem['data_criacao'] else '',
            'data_carga_fmt': formatar_data_str(ordem['data_carga']) if ordem['data_carga'] else '',
            'data_pendura_fmt': '',
            'data_derruba_fmt': '',
            'tipo': '',
            'cambao_nome': '',
            'data_ultima_atualizacao': data_hora_atual,
        })


    qs = (
        CambaoPecas.objects
        .filter(
            peca_ordem__ordem__grupo_maquina='pintura',
            status__isnull=False,
        )
        .select_related('peca_ordem', 'peca_ordem__ordem', 'cambao')
        .annotate(
            id_ordem=F('peca_ordem__ordem__id'),
            ordem=F('peca_ordem__ordem__ordem'),
            peca=F('peca_ordem__peca'),
            qtd_planejada=F('peca_ordem__qtd_planejada'),
            cor=F('peca_ordem__ordem__cor'),

            # use nomes sem colidir com fields reais
            data_criacao_fmt=ToChar(F('peca_ordem__ordem__data_criacao'), Value('DD/MM/YYYY')),
            data_carga_fmt=ToChar(F('peca_ordem__ordem__data_carga'), Value('DD/MM/YYYY')),
            data_pendura_fmt=ToChar(
                AtTimeZone(F('data_pendura'), 'America/Sao_Paulo'),
                Value('DD/MM/YYYY HH24:MI:SS')
            ),
            data_derruba_fmt=ToChar(
                AtTimeZone(F('data_fim'), 'America/Sao_Paulo'),
                Value('DD/MM/YYYY HH24:MI:SS')
            ),

            tipo=F('cambao__tipo'),
            cambao_nome=F('cambao__nome'),
            data_ultima_atualizacao=Value(data_hora_atual, output_field=CharField()) # já vem string
        )
        .filter(peca_ordem__ordem__data_carga__range=[data_inicio, data_fim])
        .values(
            'id_ordem',
            'ordem',
            'peca',
            'qtd_planejada',
            'cor',
            'status',
            'quantidade_pendurada',

            # valores formatados
            'data_criacao_fmt',
            'data_carga_fmt',
            'data_pendura_fmt',
            'data_derruba_fmt',
            
            'tipo',
            'cambao_nome',
            'data_ultima_atualizacao',
        )
        .order_by('-data_fim')
    )

    data = list(qs)[::-1]

    resultado_final_concat = ordens_aguardando_iniciar + data

    resultado_final_concat = sorted(
        resultado_final_concat,
        key=lambda x: parse_data_fmt(x.get('data_derruba_fmt', ''))
    )

    return JsonResponse(resultado_final_concat, safe=False)

def verificar_cargas_geradas(request):

    qs = (
        Ordem.objects
        .filter(grupo_maquina__in=['pintura', 'montagem', 'solda'])
        .order_by('data_carga', 'grupo_maquina', 'data_criacao')  # precisa começar pelos do distinct
        .distinct('data_carga', 'grupo_maquina')                  # DISTINCT ON (data_carga, grupo_maquina)
        .annotate(
            data_criacao_fmt=ToChar(F('data_criacao'), Value('DD/MM/YYYY')),
            data_carga_fmt=ToChar(F('data_carga'), Value('DD/MM/YYYY'))

        )
        .values('data_criacao_fmt', 'data_carga_fmt', 'grupo_maquina')
    )
    return JsonResponse(list(qs), safe=False)

def formatar_data_str(data_str):
    """
    Recebe uma string de data (ex: '2025-10-07' ou '2025-10-07T00:00:00')
    e retorna no formato 'DD/MM/YYYY'.
    Se não conseguir converter, retorna a string original ou vazio.
    """
    if not data_str:
        return ''
    try:
        # Trata ISO completo ou só data
        if 'T' in data_str:
            data_obj = datetime.strptime(data_str[:10], "%Y-%m-%d")
        else:
            data_obj = datetime.strptime(data_str, "%Y-%m-%d")
        return data_obj.strftime('%d/%m/%Y')
    except Exception:
        return data_str

def parse_data_fmt(data_str):
    try:
        return datetime.strptime(data_str, "%d/%m/%Y")
    except Exception:
        return datetime.min  # Garante que datas inválidas fiquem no início


def obter_skip_limit(request, default_limit=200, max_limit=500):
    skip_str = request.GET.get('skip', '0')
    limit_str = request.GET.get('limit', str(default_limit))

    try:
        skip = int(skip_str)
        limit = int(limit_str)
    except (TypeError, ValueError):
        raise ValueError('Par?metros skip e limit devem ser inteiros.')

    if skip < 0:
        raise ValueError('O par?metro skip deve ser maior ou igual a zero.')
    if limit <= 0:
        raise ValueError('O par?metro limit deve ser maior que zero.')

    return skip, min(limit, max_limit) 


def ordens_status_montagem(request):
    """
        traz as ordens aguardando inicio, em andamento e finalizadas na montagem
    """

    data_inicio_str = request.GET.get('data_inicio')
    data_fim_str = request.GET.get('data_fim')

    hoje = now().date()
    ultima_data_carga = (
        Ordem.objects
        .filter(grupo_maquina='montagem', data_carga__isnull=False)
        .aggregate(ultima_data=Max('data_carga'))['ultima_data']
    )
    data_fim_padrao = ultima_data_carga or hoje
    data_inicio_padrao = data_fim_padrao - timedelta(days=30)

    try:
        data_inicio = parse_date(data_inicio_str) if data_inicio_str else data_inicio_padrao
        data_fim = parse_date(data_fim_str) if data_fim_str else data_fim_padrao
    except (ValueError, TypeError):
        return JsonResponse({'erro': 'Formato de data inválido. Use YYYY-MM-DD.'}, status=400)

    if data_inicio is None or data_fim is None:
        return JsonResponse({'erro': 'Formato de data inválido. Use YYYY-MM-DD.'}, status=400)

    try:
        skip, limit = obter_skip_limit(request)
    except ValueError as exc:
        return JsonResponse({'erro': str(exc)}, status=400)

    # Monta os filtros para a model Ordem
    filtros_ordem = {
        'grupo_maquina': 'montagem',
        'data_carga__gte': data_inicio,
        'data_carga__lte': data_fim,
    }

    # Máquinas a excluir da contagem / retorno
    maquinas_excluidas = [
        'PLAT. TANQUE. CAÇAM. 2',
        'QUALIDADE',
        'FORJARIA',
        'ESTAMPARIA',
        'Carpintaria',
        'FEIXE DE MOLAS',
        'ROÇADEIRA'
    ]

    # Recupera os IDs das ordens que atendem aos filtros (ainda sem excluir máquinas, pois o filtro de máquina pode vir por parâmetro)
    ordem_ids = Ordem.objects.filter(**filtros_ordem).values_list('id', flat=True)

    # Consulta em PecasOrdem filtrando pelas ordens e EXCLUINDO as máquinas definidas em maquinas_excluidas
    pecas_ordem_queryset = POMontagem.objects.filter(ordem_id__in=ordem_ids).exclude(
        ordem__maquina__nome__in=maquinas_excluidas
    )

    data_hora_atual = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    pecas_ordem_agg = pecas_ordem_queryset.values(
        'ordem',                            # id da ordem (chave para o agrupamento)
        'peca',                              # nome da peça
        'ordem__maquina__nome',              # nome da máquina   
        'ordem__status_atual',               # status atual da ordem
    ).annotate(
        total_boa=Coalesce(
            Sum('qtd_boa'), Value(0.0, output_field=FloatField())
        ),
        total_planejada=Coalesce(
            Avg('qtd_planejada'), Value(0.0, output_field=FloatField())
        ),
        data_ultima_atualizacao_ordem=ToChar(AtTimeZone(Max('ordem__ultima_atualizacao'), 'America/Sao_Paulo'),Value('DD/MM/YYYY HH24:MI:SS')),
        data_carga_fmt=ToChar(Max('ordem__data_carga'), Value('DD/MM/YYYY')),                                       
        data_ultima_chamada=Value(data_hora_atual, output_field=CharField()),

    ).annotate(
        restante=ExpressionWrapper(
            F('total_planejada') - F('total_boa'), output_field=FloatField()
        )
    ).order_by('ordem__ultima_atualizacao')[skip:skip + limit]

    resultado_final = list(pecas_ordem_agg)


    return JsonResponse(resultado_final, safe=False)

def ordens_status_solda(request):
    """"
        traz as ordens aguardando inicio, em andamento e finalizadas na solda
    """

    try:
        skip, limit = obter_skip_limit(request)
    except ValueError as exc:
        return JsonResponse({'erro': str(exc)}, status=400)
     
     
    # Monta os filtros para a model Ordem
    filtros_ordem = {
        'grupo_maquina': 'solda',
        'ordem_pai__isnull': True
    }

    # Recupera os IDs das ordens que atendem aos filtros
    ordem_ids = Ordem.objects.filter(**filtros_ordem).values_list('id', flat=True)

    # Consulta na PecasOrdem filtrando pelas ordens identificadas,
    # trazendo alguns campos da Ordem (usando a notação "ordem__<campo>"),
    # e agrupando para calcular as somas e o saldo.

    data_hora_atual = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    
    pecas_ordem_queryset = POSolda.objects.filter(ordem_id__in=ordem_ids)

    pecas_ordem_agg = pecas_ordem_queryset.values(
        'ordem',                            # id da ordem (chave para o agrupamento)
        'peca',                              # nome da peça
        'ordem__maquina__nome',              # nome da máquina   
        'ordem__status_atual',               # status atual da ordem
    ).annotate(
        total_boa=Coalesce(
            Sum('qtd_boa'), Value(0.0, output_field=FloatField())
        ),
        total_planejada=Coalesce(
            Avg('qtd_planejada'), Value(0.0, output_field=FloatField())
        ),
        data_ultima_atualizacao_ordem=ToChar(AtTimeZone(Max('ordem__ultima_atualizacao'), 'America/Sao_Paulo'),Value('DD/MM/YYYY HH24:MI:SS')),
        data_carga_fmt=ToChar(Max('ordem__data_carga'), Value('DD/MM/YYYY')),                                      
        data_ultima_chamada=Value(data_hora_atual, output_field=CharField()),

    ).annotate(
        restante=ExpressionWrapper(
            F('total_planejada') - F('total_boa'), output_field=FloatField()
        )
    ).order_by('-ordem__ultima_atualizacao')[skip:skip + limit]

    resultado_final = list(pecas_ordem_agg)


    return JsonResponse(resultado_final, safe=False)

def pecas_status_retrabalho_pintura(request):
    """
        Puxar as ordens que estão em retrabalho na pintura, aguardando retrabalho, aguardando inspeção e retrabalhados
    """
    # Puxar as ordens que estão em retrabalho ou aguardando retrabalho na pintura

    mes_atual = datetime.now().date().month
    ano_atual = datetime.now().date().year

    mes_prev = mes_atual -1 if mes_atual > 1 else 12
    mes_prox = mes_atual +1 if mes_atual <12 else 1

    meses = [mes_prev, mes_atual, mes_prox]

    data_hora_atual = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    retrabalho_qs = (
        Retrabalho.objects
        .annotate(
            dados_execucao_inspecao=Subquery(
                DadosExecucaoInspecao.objects
                .filter(inspecao=OuterRef('reinspecao__inspecao__id'))
                .order_by('-id')  # ou '-num_execucao' conforme seu modelo
                .values_list('id', flat=True)[:1]
            ),
            data_carga_fmt=ToChar(F('reinspecao__inspecao__pecas_ordem_pintura__ordem__data_carga'), Value('DD/MM/YYYY')),
            data_inicio_fmt=ToChar(
                AtTimeZone(F('data_inicio'), 'America/Sao_Paulo'),
                Value('DD/MM/YYYY HH24:MI:SS')
            ),
            data_fim_fmt=ToChar(
                AtTimeZone(F('data_fim'), 'America/Sao_Paulo'),
                Value('DD/MM/YYYY HH24:MI:SS')
            ),
            data_ultima_atualizacao_fmt=Value(data_hora_atual, output_field=CharField()) # já vem string
        )
        .filter(reinspecao__inspecao__pecas_ordem_pintura__ordem__data_carga__month__in=meses,
                reinspecao__inspecao__pecas_ordem_pintura__ordem__data_carga__year=ano_atual
        )
        .values(
            'id',
            'status',
            'data_inicio_fmt',
            'data_fim_fmt',

            'reinspecao__inspecao__pecas_ordem_pintura__ordem__id',
            'reinspecao__inspecao__pecas_ordem_pintura__ordem__ordem',
            'data_carga_fmt',
            'reinspecao__inspecao__pecas_ordem_pintura__peca',
        
            'reinspecao__inspecao__id',
            'reinspecao__id',
            'dados_execucao_inspecao',

            'data_ultima_atualizacao_fmt',

        )
    )

    retr_list = list(retrabalho_qs)

    # 2) buscar causas para os dados_execucao_ids coletados (uma query)
    dados_ids = {r['dados_execucao_inspecao'] for r in retr_list if r.get('dados_execucao_inspecao')}
    causas_map = defaultdict(list)
    if dados_ids:
        causas_qs = CausasNaoConformidade.objects.filter(dados_execucao__id__in=dados_ids).prefetch_related('causa').values(
            'id',
            'dados_execucao__id',
            'causa__id',
            'causa__nome'  # ajuste conforme campo de descrição'
        )
        for c in causas_qs:
            causas_map[c['dados_execucao__id']].append({
                'causa_nao_conformidade_id': c['id'],
                'causa_id': c['causa__id'],
                'causa_nome': c.get('causa__nome'),
            })

    # 3) produzir lista PLANA: cada item de retr_list ganha a chave 'causas_nao_conformidade'
    flat = []
    for r in retr_list:
        causas = causas_map.get(r.get('dados_execucao_inspecao')) or []
        flat.append({
            'ordem_id': r.get('reinspecao__inspecao__pecas_ordem_pintura__ordem__id'),
            'ordem': r.get('reinspecao__inspecao__pecas_ordem_pintura__ordem__ordem'),
            'data_carga': r.get('data_carga_fmt'),
            'peca': r.get('reinspecao__inspecao__pecas_ordem_pintura__peca'),
            'retrabalho_id': r.get('id'),
            'retrabalho_status': r.get('status'),
            'retrabalho_data_inicio': r.get('data_inicio_fmt'),
            'retrabalho_data_fim': r.get('data_fim_fmt'),
            'causa_nao_conformidade': causas[0].get('causa_nome') if causas else None,
            'inspecao_id': r.get('reinspecao__inspecao__id'),
            'reinspecao_id': r.get('reinspecao__id'),
            'dados_execucao_inspecao': r.get('dados_execucao_inspecao'),
            'data_ultima_atualizacao': r.get('data_ultima_atualizacao_fmt'),
        })

    
    # 4) buscar inspeções que ainda aguardam inspeção
    inspecoes_ids = set(
        DadosExecucaoInspecao.objects.values_list("inspecao", flat=True)
    )

    # Filtra os dados
    datas = Inspecao.objects.filter(pecas_ordem_pintura__isnull=False).exclude(
        id__in=inspecoes_ids
    )

    datas = datas.select_related(
        "pecas_ordem_pintura",
        "pecas_ordem_pintura__ordem",
        "pecas_ordem_pintura__operador_fim",
    ).order_by("-id")


    for inspecao in datas:
        flat.append({
            'ordem_id': inspecao.pecas_ordem_pintura.ordem.id,
            'ordem': inspecao.pecas_ordem_pintura.ordem.ordem,
            'data_carga': inspecao.pecas_ordem_pintura.ordem.data_carga.strftime('%d/%m/%Y') if inspecao.pecas_ordem_pintura.ordem.data_carga else '',
            'peca': inspecao.pecas_ordem_pintura.peca,
            'retrabalho_id': '',
            'retrabalho_status': 'aguardando_inspecao',
            'retrabalho_data_inicio': '',
            'retrabalho_data_fim': '',
            'causa_nao_conformidade': '',
            'inspecao_id': inspecao.id,
            'reinspecao_id': '',
            'dados_execucao_inspecao': '',
            'data_ultima_atualizacao': data_hora_atual,
        })

    # ordenando por data da carga
    flat = sorted(
        flat,
        key=lambda x: parse_data_fmt(x.get('data_carga', ''))
    )

    
    return JsonResponse(flat, safe=False, json_dumps_params={'default': str})


def ordens_finalizadas_pintura_inicio_ano(request):
    """
    Traz as ordens finalizadas da pintura filtradas por data_derruba (data_fim).
    Padrão: ontem e hoje (America/Sao_Paulo).
    Aceita parâmetros opcionais: data_inicio e data_fim (formato YYYY-MM-DD).
    """
    from zoneinfo import ZoneInfo

    tz = ZoneInfo('America/Sao_Paulo')
    hoje = datetime.now(tz).date()
    ontem = hoje - timedelta(days=1)

    data_inicio_str = request.GET.get('data_inicio', '')
    data_fim_str    = request.GET.get('data_fim', '')

    data_inicio = parse_date(data_inicio_str) if data_inicio_str else ontem
    data_fim    = parse_date(data_fim_str)    if data_fim_str    else hoje

    data_hora_atual = datetime.now(tz).strftime("%d/%m/%Y %H:%M:%S")

    qs = (
        CambaoPecas.objects
        .filter(
            peca_ordem__ordem__grupo_maquina='pintura',
            status='finalizada',
            data_fim__date__gte=data_inicio,
            data_fim__date__lte=data_fim,
        )
        .select_related('peca_ordem', 'peca_ordem__ordem', 'cambao')
        .annotate(
            id_ordem=F('peca_ordem__ordem__id'),
            ordem=F('peca_ordem__ordem__ordem'),
            peca=F('peca_ordem__peca'),
            qtd_planejada=F('peca_ordem__qtd_planejada'),
            cor=F('peca_ordem__ordem__cor'),

            data_criacao_fmt=ToChar(F('peca_ordem__ordem__data_criacao'), Value('DD/MM/YYYY')),
            data_carga_fmt=ToChar(F('peca_ordem__ordem__data_carga'), Value('DD/MM/YYYY')),
            data_pendura_fmt=ToChar(
                AtTimeZone(F('data_pendura'), 'America/Sao_Paulo'),
                Value('DD/MM/YYYY HH24:MI:SS')
            ),
            data_derruba_fmt=ToChar(
                AtTimeZone(F('data_fim'), 'America/Sao_Paulo'),
                Value('DD/MM/YYYY HH24:MI:SS')
            ),

            tipo=F('cambao__tipo'),
            cambao_nome=F('cambao__nome'),
            data_ultima_atualizacao=Value(data_hora_atual, output_field=CharField()),
        )
        .values(
            'id_ordem',
            'ordem',
            'peca',
            'qtd_planejada',
            'cor',
            'status',
            'quantidade_pendurada',
            'data_criacao_fmt',
            'data_carga_fmt',
            'data_pendura_fmt',
            'data_derruba_fmt',
            'tipo',
            'cambao_nome',
            'data_ultima_atualizacao',
        )
        .order_by('data_fim')
    )

    resultado_final_concat = sorted(
        list(qs),
        key=lambda x: parse_data_fmt(x.get('data_derruba_fmt', ''))
    )

    return JsonResponse(resultado_final_concat, safe=False)
