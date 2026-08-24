import hashlib
import json
import logging
import os
import re
import time
from io import BytesIO
from datetime import datetime
from html import escape

import gspread
from boto3.s3.transfer import TransferConfig
from django.core.paginator import Paginator
from django.db import connection, transaction
from django.db.models import Count, Q, TextField, Value
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Cast, Coalesce
from django.http import FileResponse, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.timezone import localtime
from storages.backends.s3boto3 import S3Boto3Storage

from core.models import Profile
from core.utils import get_google_credentials
from ..models import InspecaoRecebimento, InspecaoRecebimentoItem

# Uploads de imagem/video da inspecao de recebimento usam upload sequencial
# (sem threads). O upload multipart concorrente padrao do boto3 le o mesmo
# file-like object do Django em offsets diferentes a partir de varias
# threads, corrompendo o arquivo quando ele excede o limite de multipart.
# Isolado nesta storage especifica para nao afetar os demais uploads do
# sistema (que nao tem esse problema e se beneficiam do upload paralelo).
_storage_midia_recebimento = S3Boto3Storage(transfer_config=TransferConfig(use_threads=False))

SHEET_ID = os.environ.get(
    "RECEBIMENTO_SHEET_ID",
    "1mLuw4jM5WpD0pgxXREio15Ju8MZZ7QMJHb3vapz94Ac",
)
SHEET_TAB = os.environ.get(
    "RECEBIMENTO_SHEET_TAB",
    "Base controle de entrada",
)

logger = logging.getLogger(__name__)

DEFAULT_CUT_OFF_DATE = "2026-05-01"
COLUNA_STATUS_IDX = 7  # Coluna H (0-based)
COLUNAS_EXIBIR = [0, 1, 2, 3, 4, 5, 6, 8, 9, 10]  # A,B,C,D,E,F,G,I,J,K


def _salvar_imagem_inspecao_recebimento(uploaded_file, sheet_hash, material_idx, unidade_idx):
    extensao = os.path.splitext(getattr(uploaded_file, "name", "") or "")[1].lower() or ".jpg"
    caminho = (
        f"inspecao_recebimento/{datetime.now().strftime('%Y/%m')}/"
        f"{sheet_hash}_m{material_idx}_u{unidade_idx}{extensao}"
    )
    caminho_salvo = _storage_midia_recebimento.save(caminho, uploaded_file)

    try:
        url = _storage_midia_recebimento.url(caminho_salvo)
    except Exception:
        url = ""

    return {
        "arquivo": caminho_salvo,
        "url": url,
        "nome": getattr(uploaded_file, "name", ""),
    }


def _salvar_video_inspecao_recebimento(uploaded_file, sheet_hash, material_idx, unidade_idx):
    extensao = os.path.splitext(getattr(uploaded_file, "name", "") or "")[1].lower() or ".mp4"
    caminho = (
        f"inspecao_recebimento/{datetime.now().strftime('%Y/%m')}/"
        f"{sheet_hash}_m{material_idx}_u{unidade_idx}_video{extensao}"
    )
    caminho_salvo = _storage_midia_recebimento.save(caminho, uploaded_file)

    try:
        url = _storage_midia_recebimento.url(caminho_salvo)
    except Exception:
        url = ""

    return {
        "arquivo": caminho_salvo,
        "url": url,
        "nome": getattr(uploaded_file, "name", ""),
    }


def inspecao_recebimento(request):
    user_profile = Profile.objects.filter(user=request.user).first() if request.user.is_authenticated else None
    if (
        user_profile
        and user_profile.tipo_acesso == "inspetor"
        and user_profile.permissoes.filter(nome="inspecao/recebimento").exists()
    ):
        inspetor_logado = {"nome_usuario": request.user.username, "id": request.user.id}
    else:
        inspetor_logado = None

    return render(
        request,
        "inspecao_recebimento.html",
        {
            "inspetor_logado": inspetor_logado,
        },
    )


def _make_unique_headers(headers):
    counts = {}
    unique = []
    for index, header in enumerate(headers, start=1):
        name = (header or "").strip()
        if not name:
            name = f"Coluna {index}"
        if name in counts:
            counts[name] += 1
            name = f"{name} ({counts[name]})"
        else:
            counts[name] = 1
        unique.append(name)
    return unique


def _row_hash(row_data):
    payload = json.dumps(row_data, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _load_recebimento_sheet():
    credentials = get_google_credentials()
    if credentials is None:
        return None, "Credenciais do Google Sheets não encontradas."

    try:
        gc = gspread.service_account_from_dict(credentials)
        sheet = gc.open_by_key(SHEET_ID)
        worksheet = sheet.worksheet(SHEET_TAB)
        values = worksheet.get_all_values()
        return values, None
    except Exception as exc:
        return None, str(exc)


def _parse_br_date(value):
    if not value:
        return None
    texto = str(value).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(texto, fmt).date()
        except ValueError:
            continue
    return None


def _get_classe_inspecao(data):
    if not isinstance(data, dict):
        return ""
    return str(
        data.get("Classe de inspeção")
        or data.get("Classe de Inspeção")
        or ""
    ).strip()


def _normalizar_classe_inspecao(valor):
    texto = str(valor or "").strip().lower()
    substituicoes = str.maketrans(
        {
            "á": "a",
            "à": "a",
            "â": "a",
            "ã": "a",
            "ä": "a",
            "é": "e",
            "è": "e",
            "ê": "e",
            "ë": "e",
            "í": "i",
            "ì": "i",
            "î": "i",
            "ï": "i",
            "ó": "o",
            "ò": "o",
            "ô": "o",
            "õ": "o",
            "ö": "o",
            "ú": "u",
            "ù": "u",
            "û": "u",
            "ü": "u",
            "ç": "c",
        }
    )
    return texto.translate(substituicoes)


def _row_hash_from_list(row_values):
    payload = json.dumps(row_values, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _is_filled(value):
    return str(value or "").strip() != ""


def _merge_sheet_data(existing_data, incoming_data):
    merged = dict(existing_data or {})
    for key, value in (incoming_data or {}).items():
        if _is_filled(value) or key not in merged:
            merged[key] = value
    return merged


IDENTITY_IGNORE_FIELDS = {"CNPJ", "Fornecedor"}


def _identity_payload(dados):
    payload = {}
    for key, value in (dados or {}).items():
        if key in IDENTITY_IGNORE_FIELDS:
            continue
        payload[key] = str(value or "").strip()
    return payload


def _find_recebimento_item_by_identity(dados, data_coluna_a):
    identity_payload = _identity_payload(dados)
    candidates = InspecaoRecebimentoItem.objects.filter(
        planilha_id=SHEET_ID,
        aba_nome=SHEET_TAB,
        data_referencia=data_coluna_a,
    ).order_by("id")

    for candidate in candidates:
        if _identity_payload(candidate.dados) == identity_payload:
            return candidate
    return None


BUSINESS_KEY_FIELDS = ("CNPJ", "Ch. de Pedido", "Nº Nota fiscal")


def _business_key_payload(dados):
    payload = {}
    for key in BUSINESS_KEY_FIELDS:
        payload[key] = str((dados or {}).get(key) or "").strip()
    return payload


def _find_recebimento_item_by_business_key(dados, data_coluna_a):
    business_key = _business_key_payload(dados)
    if not any(business_key.values()):
        return None

    candidates = InspecaoRecebimentoItem.objects.filter(
        planilha_id=SHEET_ID,
        aba_nome=SHEET_TAB,
        data_referencia=data_coluna_a,
    ).order_by("id")

    for candidate in candidates:
        if _business_key_payload(candidate.dados) == business_key:
            return candidate
    return None


def _sync_recebimento_inspecao_ativa(primary_item, merged_dados, row_index, sheet_hash):
    registros = list(
        InspecaoRecebimento.objects.filter(item=primary_item).order_by(
            "excluido", "-data_inspecao", "-id"
        )
    )
    if not registros:
        return

    registro_ativo = next((registro for registro in registros if registro.sheet_hash == sheet_hash), None)
    if registro_ativo is None:
        registro_ativo = next((registro for registro in registros if not registro.excluido), registros[0])

    update_fields = []
    if registro_ativo.item_id != primary_item.id:
        registro_ativo.item = primary_item
        update_fields.append("item")
    if registro_ativo.dados != merged_dados:
        registro_ativo.dados = merged_dados
        update_fields.append("dados")
    if registro_ativo.linha_planilha != row_index:
        registro_ativo.linha_planilha = row_index
        update_fields.append("linha_planilha")
    if registro_ativo.sheet_hash != sheet_hash:
        registro_ativo.sheet_hash = sheet_hash
        update_fields.append("sheet_hash")

    if update_fields:
        registro_ativo.save(update_fields=update_fields)


def _reconcile_recebimento_items(items, incoming_dados, row_index, sheet_hash, data_coluna_a):
    unique_items = []
    seen_ids = set()
    for item in items:
        if item and item.id not in seen_ids:
            unique_items.append(item)
            seen_ids.add(item.id)

    primary_item = next((item for item in unique_items if item.inspecionado), None)
    if primary_item is None:
        primary_item = unique_items[0]

    merged_dados = {}
    any_inspecionado = False
    for item in unique_items:
        merged_dados = _merge_sheet_data(merged_dados, item.dados)
        any_inspecionado = any_inspecionado or item.inspecionado
    merged_dados = _merge_sheet_data(merged_dados, incoming_dados)

    with transaction.atomic():
        for duplicate_item in unique_items:
            if duplicate_item.id == primary_item.id:
                continue
            InspecaoRecebimento.objects.filter(item=duplicate_item).update(item=primary_item)
            duplicate_item.delete()

        primary_item.dados = merged_dados
        primary_item.data_referencia = data_coluna_a
        primary_item.status_h = True
        primary_item.sheet_hash = sheet_hash
        primary_item.linha_planilha = row_index
        primary_item.inspecionado = any_inspecionado
        primary_item.save(
            update_fields=[
                "dados",
                "data_referencia",
                "status_h",
                "sheet_hash",
                "linha_planilha",
                "inspecionado",
            ]
        )

        if primary_item.inspecionado:
            _sync_recebimento_inspecao_ativa(
                primary_item=primary_item,
                merged_dados=primary_item.dados,
                row_index=row_index,
                sheet_hash=sheet_hash,
            )

    return primary_item


# Orcamento de tempo por request: a sincronizacao roda linha a linha, de
# forma sincrona, dentro do worker do Daphne. Uma planilha grande podia
# manter isso rodando por minutos, prendendo o worker e derrubando a
# instancia inteira (Render matava a task e reiniciava o servico). Agora
# cada chamada processa no maximo esse tempo e devolve "concluido: false"
# com o ponto pra continuar; o front chama de novo automaticamente ate
# terminar, sem nenhuma request individual ficar longa o suficiente pra
# travar o processo.
TEMPO_LIMITE_SYNC_SEGUNDOS = 12


def sincronizar_recebimento(request):
    if request.method != "POST":
        return JsonResponse({"error": "MÃ©todo não permitido"}, status=405)

    values, error = _load_recebimento_sheet()
    if error:
        return JsonResponse({"error": error}, status=500)

    if not values or len(values) < 2:
        return JsonResponse({"novos": 0, "total": 0, "concluido": True}, status=200)

    header_row_index = 5
    header_row = values[header_row_index - 1] if len(values) >= header_row_index else []
    selected_headers = _make_unique_headers(
        [header_row[i] if i < len(header_row) else "" for i in COLUNAS_EXIBIR]
    )
    data_rows = values[header_row_index:]

    cutoff = _parse_br_date(DEFAULT_CUT_OFF_DATE)
    if cutoff is None:
        return JsonResponse({"error": "Data de corte invÃ¡lida"}, status=500)

    try:
        start_offset = max(int(request.GET.get("start_offset", 0) or 0), 0)
    except (TypeError, ValueError):
        start_offset = 0

    novos = 0
    total = 0
    proximo_offset = None
    inicio = time.monotonic()

    for offset, row in enumerate(data_rows[start_offset:], start=start_offset):
        if time.monotonic() - inicio > TEMPO_LIMITE_SYNC_SEGUNDOS:
            proximo_offset = offset
            break

        row_index = header_row_index + 1 + offset
        row_values = list(row)
        if not row_values:
            continue
        if len(row_values) <= COLUNA_STATUS_IDX:
            continue

        data_coluna_a = _parse_br_date(row_values[0])
        if data_coluna_a is None or data_coluna_a < cutoff:
            continue

        status_val = str(row_values[COLUNA_STATUS_IDX] or "").strip().upper()
        if status_val != "TRUE":
            continue

        total += 1
        sheet_hash = _row_hash_from_list(row_values)

        dados = {
            selected_headers[idx]: (
                row_values[col_idx] if col_idx < len(row_values) else ""
            )
            for idx, col_idx in enumerate(COLUNAS_EXIBIR)
        }

        try:
            existing_by_line = InspecaoRecebimentoItem.objects.filter(
                planilha_id=SHEET_ID,
                aba_nome=SHEET_TAB,
                linha_planilha=row_index,
            ).first()
            existing_by_hash = InspecaoRecebimentoItem.objects.filter(sheet_hash=sheet_hash).first()
            existing_by_identity = _find_recebimento_item_by_identity(dados, data_coluna_a)
            existing_by_business_key = _find_recebimento_item_by_business_key(dados, data_coluna_a)

            existing_item = (
                existing_by_line
                or existing_by_hash
                or existing_by_business_key
                or existing_by_identity
            )
            if existing_item:
                _reconcile_recebimento_items(
                    items=[
                        existing_by_line,
                        existing_by_hash,
                        existing_by_business_key,
                        existing_by_identity,
                    ],
                    incoming_dados=dados,
                    row_index=row_index,
                    sheet_hash=sheet_hash,
                    data_coluna_a=data_coluna_a,
                )
                continue

            InspecaoRecebimentoItem.objects.create(
                planilha_id=SHEET_ID,
                aba_nome=SHEET_TAB,
                linha_planilha=row_index,
                sheet_hash=sheet_hash,
                dados=dados,
                data_referencia=data_coluna_a,
                status_h=True,
            )
            novos += 1
        except Exception:
            logger.exception(
                "Falha ao sincronizar linha %s da planilha de recebimento (sheet_hash=%s). Linha ignorada.",
                row_index,
                sheet_hash,
            )
            continue

    return JsonResponse(
        {
            "novos": novos,
            "total": total,
            "concluido": proximo_offset is None,
            "proximo_offset": proximo_offset,
            "linha_atual": (proximo_offset if proximo_offset is not None else len(data_rows)) + header_row_index,
            "total_linhas": len(data_rows) + header_row_index,
        },
        status=200,
    )


COLUNAS_PENDENCIAS = [
    "Data",
    "CNPJ",
    "Fornecedor",
    "Ch. de Pedido",
    "Nº Nota fiscal",
    "Tipo de material",
    "Classe de Inspeção",
]


def recebimento_pendencias(request):
    if request.method != "GET":
        return JsonResponse({"error": "Método não permitido"}, status=405)

    itens = InspecaoRecebimentoItem.objects.filter(inspecionado=False, excluido=False).order_by("-id")
    rows = []

    for item in itens:
        data = item.dados or {}
        data_filtrada = {col: data.get(col, "") for col in COLUNAS_PENDENCIAS}
        rows.append(
            {
                "row_index": item.linha_planilha,
                "hash": item.sheet_hash,
                "data": data_filtrada,
                "item_id": item.id,
                "data_completa": data,
            }
        )

    return JsonResponse(
        {
            "columns": COLUNAS_PENDENCIAS,
            "rows": rows,
            "total": len(rows),
            "pode_editar": _tem_acesso_edicao(request),
        },
        status=200,
    )


COLUNAS_OCULTAS_INSPECIONADOS = {"Situação do frete"}


def _classe_inspecao_annotation():
    return Coalesce(
        KeyTextTransform("Classe de Inspeção", "dados"),
        KeyTextTransform("Classe de inspeção", "dados"),
        Value("", output_field=TextField()),
        output_field=TextField(),
    )


def _aplicar_busca_inspecionados(queryset, busca):
    if not busca:
        return queryset
    return queryset.annotate(
        busca_dados=Cast("dados", output_field=TextField()),
        busca_dados_inspecao=Cast("dados_inspecao", output_field=TextField()),
    ).filter(
        Q(busca_dados__icontains=busca)
        | Q(busca_dados_inspecao__icontains=busca)
        | Q(observacao__icontains=busca)
        | Q(inspetor__user__username__icontains=busca)
        | Q(inspetor__user__first_name__icontains=busca)
        | Q(inspetor__user__last_name__icontains=busca)
    )


def recebimento_inspecionados(request):
    if request.method != "GET":
        return JsonResponse({"error": "Método não permitido"}, status=405)

    page = max(int(request.GET.get("page", 1) or 1), 1)
    limit = min(max(int(request.GET.get("limit", 50) or 50), 10), 200)
    busca = request.GET.get("q", "").strip()
    classe_filtro = request.GET.get("classe", "").strip()

    base_queryset = (
        InspecaoRecebimento.objects.filter(excluido=False)
        .annotate(classe_inspecao=_classe_inspecao_annotation())
    )
    base_queryset = _aplicar_busca_inspecionados(base_queryset, busca)

    classes_resumo = [
        {"classe": item["classe_inspecao"] or "Sem classe", "total": item["total"]}
        for item in (
            base_queryset.values("classe_inspecao")
            .annotate(total=Count("id"))
            .order_by("classe_inspecao")
        )
    ]

    registros = base_queryset.select_related("inspetor__user").order_by("-data_inspecao")
    if classe_filtro:
        if classe_filtro == "Sem classe":
            registros = registros.filter(Q(classe_inspecao="") | Q(classe_inspecao__isnull=True))
        else:
            registros = registros.filter(classe_inspecao=classe_filtro)

    paginator = Paginator(registros, limit)
    pagina = paginator.get_page(page)

    headers = []
    rows = []
    for registro in pagina.object_list:
        data = registro.dados or {}
        for key in data.keys():
            if key not in headers and key not in COLUNAS_OCULTAS_INSPECIONADOS:
                headers.append(key)

        meta = {
            "id": registro.id,
            "data_inspecao": localtime(registro.data_inspecao).strftime("%d/%m/%Y %H:%M"),
            "inspetor": (
                registro.inspetor.user.username
                if registro.inspetor and registro.inspetor.user
                else ""
            ),
            "resultado": registro.get_resultado_display(),
            "observacao": registro.observacao or "",
        }
        display = {
            "Data inspeção": meta["data_inspecao"],
            "Inspetor": meta["inspetor"],
            "Resultado": meta["resultado"],
            "Observação": meta["observacao"],
        }
        for header in headers:
            display[header] = data.get(header, "")
        rows.append(
            {
                "data": display,
                "meta": meta,
                "dados_inspecao": registro.dados_inspecao or {},
            }
        )

    columns = ["Data inspeção", "Inspetor", "Resultado", "Observação"] + headers

    return JsonResponse(
        {
            "columns": columns,
            "rows": rows,
            "total": paginator.count,
            "total_geral": InspecaoRecebimento.objects.filter(excluido=False).count(),
            "page": pagina.number,
            "total_pages": paginator.num_pages,
            "has_next": pagina.has_next(),
            "has_previous": pagina.has_previous(),
            "classes_resumo": classes_resumo,
            "pode_editar": _tem_acesso_edicao(request),
        },
        status=200,
    )


def _rotulo_ficha_recebimento(chave):
    if chave == "video":
        return "Video Link"
    return re.sub(r"\s+", " ", str(chave or "").replace("_", " ")).strip().title()


def _valor_campo_unidade_recebimento(coluna, unidade):
    campos = unidade.get("campos") or {}
    if coluna == "unidade":
        return unidade.get("unidade") or "-"
    if coluna == "resultado":
        return unidade.get("resultado") or "-"
    if coluna == "observacao":
        return unidade.get("observacao") or "-"
    if coluna == "imagem":
        imagem = unidade.get("imagem") or {}
        return imagem.get("url") or imagem.get("arquivo") or "Imagem anexada"
    if coluna == "video":
        video = unidade.get("video") or {}
        return video.get("url") or video.get("arquivo") or "-"
    return campos.get(coluna) or "-"


def _dados_unidades_recebimento_pdf(registro):
    dados_inspecao = registro.dados_inspecao or {}
    materiais = dados_inspecao.get("materiais") or []
    unidades = dados_inspecao.get("unidades") or []
    unidades_com_material = (
        [
            {
                **unidade,
                "__material_nome": material.get("nome_material")
                or f"Material {material.get('material') or ''}".strip(),
            }
            for material in materiais
            for unidade in (material.get("unidades") or [])
        ]
        if materiais
        else unidades
    )

    campos_ocultos = re.compile(r"^devolucao_peca_\d+_(codigo|quantidade)$")
    campos_extras = []
    possui_imagem = False
    possui_video = False

    for unidade in unidades_com_material:
        imagem = unidade.get("imagem") or {}
        video = unidade.get("video") or {}
        possui_imagem = possui_imagem or bool(imagem.get("url") or imagem.get("arquivo"))
        possui_video = possui_video or bool(video.get("url") or video.get("arquivo"))
        for campo in (unidade.get("campos") or {}).keys():
            if campos_ocultos.match(campo):
                continue
            if campo not in campos_extras:
                campos_extras.append(campo)

    colunas = ["unidade", "resultado", "observacao"]
    if possui_video:
        colunas.append("video")
    if possui_imagem:
        colunas.append("imagem")
    colunas.extend(campos_extras)

    linhas = []
    if materiais:
        for material in materiais:
            unidades_material = material.get("unidades") or []
            if not unidades_material:
                continue
            linhas.append(
                {
                    "tipo": "material",
                    "nome": material.get("nome_material")
                    or f"Material {material.get('material') or ''}".strip(),
                }
            )
            for unidade in unidades_material:
                linhas.append({"tipo": "unidade", "unidade": unidade})
    else:
        linhas = [{"tipo": "unidade", "unidade": unidade} for unidade in unidades_com_material]

    return unidades_com_material, colunas, linhas


def _extrair_pecas_devolucao_pdf(campos):
    pecas = []
    campos = campos or {}
    for chave, codigo in campos.items():
        match = re.match(r"^devolucao_peca_(\d+)_codigo$", chave)
        if not match or not str(codigo or "").strip():
            continue
        idx = match.group(1)
        pecas.append(
            {
                "codigo": codigo,
                "quantidade": campos.get(f"devolucao_peca_{idx}_quantidade") or "-",
            }
        )
    return pecas


def exportar_ficha_recebimento_pdf(request, registro_id):
    if request.method != "GET":
        return JsonResponse({"error": "Metodo nao permitido"}, status=405)

    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_RIGHT
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError:
        return HttpResponse(
            "A biblioteca reportlab nao esta instalada. Rode: pip install reportlab",
            status=500,
            content_type="text/plain; charset=utf-8",
        )

    registro = get_object_or_404(
        InspecaoRecebimento.objects.select_related("inspetor__user"),
        pk=registro_id,
        excluido=False,
    )

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=10 * mm,
        leftMargin=10 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
        title=f"Ficha de Inspecao de Recebimento #{registro.id}",
    )

    base_styles = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle(
            "FichaTitle",
            parent=base_styles["Title"],
            alignment=TA_CENTER,
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=18,
            textColor=colors.HexColor("#1e293b"),
            spaceAfter=2,
        ),
        "subtitle": ParagraphStyle(
            "FichaSubtitle",
            parent=base_styles["BodyText"],
            alignment=TA_CENTER,
            fontName="Helvetica",
            fontSize=9,
            leading=11,
            textColor=colors.HexColor("#64748b"),
        ),
        "right": ParagraphStyle(
            "FichaRight",
            parent=base_styles["BodyText"],
            alignment=TA_RIGHT,
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#64748b"),
        ),
        "section": ParagraphStyle(
            "FichaSection",
            parent=base_styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#64748b"),
            uppercase=True,
            spaceBefore=8,
            spaceAfter=4,
        ),
        "cell": ParagraphStyle(
            "FichaCell",
            parent=base_styles["BodyText"],
            fontName="Helvetica",
            fontSize=7,
            leading=8,
            wordWrap="CJK",
        ),
        "cell_bold": ParagraphStyle(
            "FichaCellBold",
            parent=base_styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=7,
            leading=8,
            wordWrap="CJK",
        ),
        "label": ParagraphStyle(
            "FichaLabel",
            parent=base_styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=6,
            leading=7,
            textColor=colors.HexColor("#64748b"),
            wordWrap="CJK",
        ),
    }

    def p(valor, style="cell"):
        return Paragraph(escape(str(valor if valor not in (None, "") else "-")), styles[style])

    def section(titulo):
        return Paragraph(escape(titulo.upper()), styles["section"])

    def fields_table(campos):
        cells = []
        for label, value in campos:
            cells.append(
                Paragraph(
                    f"<b>{escape(str(label))}</b><br/>{escape(str(value if value not in (None, '') else '-'))}",
                    styles["cell"],
                )
            )
        while len(cells) % 4:
            cells.append("")
        rows = [cells[i : i + 4] for i in range(0, len(cells), 4)]
        table = Table(rows, colWidths=[doc.width / 4] * 4, hAlign="LEFT")
        table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 2),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        return table

    def split_columns(columns, max_columns=8):
        if len(columns) <= max_columns:
            return [columns]
        first = columns[0]
        chunks = []
        for index in range(1, len(columns), max_columns - 1):
            chunks.append([first, *columns[index : index + max_columns - 1]])
        return chunks

    def dynamic_table(title, columns, rows):
        story_items = []
        if not columns or not rows:
            return story_items

        chunks = split_columns(columns)
        for chunk_index, chunk in enumerate(chunks, start=1):
            table_title = title if len(chunks) == 1 else f"{title} - parte {chunk_index}"
            story_items.append(section(table_title))

            data = [[p(_rotulo_ficha_recebimento(col), "cell_bold") for col in chunk]]
            spans = []
            for row in rows:
                if row.get("tipo") == "material":
                    data.append([p(row.get("nome") or "Material", "cell_bold"), *[""] * (len(chunk) - 1)])
                    spans.append(("SPAN", (0, len(data) - 1), (len(chunk) - 1, len(data) - 1)))
                    continue
                unidade = row.get("unidade") or {}
                data.append([p(_valor_campo_unidade_recebimento(col, unidade)) for col in chunk])

            table = Table(data, colWidths=[doc.width / len(chunk)] * len(chunk), repeatRows=1, hAlign="LEFT")
            style_commands = [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
            for span in spans:
                style_commands.append(span)
                style_commands.append(("BACKGROUND", span[1], span[2], colors.HexColor("#e2e8f0")))
            table.setStyle(TableStyle(style_commands))
            story_items.extend([table, Spacer(1, 6)])
            if chunk_index < len(chunks):
                story_items.append(PageBreak())
        return story_items

    def unidade_cards(title, columns, rows):
        story_items = []
        if not columns or not rows:
            return story_items

        story_items.append(section(title))
        material_atual = ""
        campos_card = [col for col in columns if col != "unidade"]
        card_gap = 10
        row_gap = 10
        card_width = (doc.width - (card_gap * 2)) / 3
        cards_linha = []

        def flush_cards():
            nonlocal cards_linha
            if not cards_linha:
                return
            while len(cards_linha) < 3:
                cards_linha.append("")
            linha = Table(
                [[cards_linha[0], "", cards_linha[1], "", cards_linha[2]]],
                colWidths=[card_width, card_gap, card_width, card_gap, card_width],
                hAlign="LEFT",
            )
            linha.setStyle(
                TableStyle(
                    [
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 0),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                        ("TOPPADDING", (0, 0), (-1, -1), 0),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), row_gap),
                    ]
                )
            )
            story_items.append(linha)
            cards_linha = []

        for row in rows:
            if row.get("tipo") == "material":
                material_atual = row.get("nome") or "Material"
                continue

            unidade = row.get("unidade") or {}
            unidade_nome = _valor_campo_unidade_recebimento("unidade", unidade)
            resultado = _valor_campo_unidade_recebimento("resultado", unidade)
            titulo_card = f"Unidade {unidade_nome}"
            if material_atual:
                titulo_card = f"{titulo_card} - {material_atual}"

            header = Table(
                [[p(titulo_card, "cell_bold")], [p(f"Resultado: {resultado}", "cell_bold")]],
                colWidths=[card_width],
            )
            header.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#e2e8f0")),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 6),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                        ("TOPPADDING", (0, 0), (-1, -1), 5),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ]
                )
            )

            campos = []
            for coluna in campos_card:
                if coluna == "resultado":
                    continue
                campos.append(
                    Paragraph(
                        f"<b>{escape(_rotulo_ficha_recebimento(coluna))}</b><br/>"
                        f"{escape(str(_valor_campo_unidade_recebimento(coluna, unidade)))}",
                        styles["cell"],
                    )
                )

            if not campos:
                campos.append(p("-", "cell"))
            while len(campos) % 2:
                campos.append("")

            linhas_campos = [campos[i : i + 2] for i in range(0, len(campos), 2)]
            body = Table(linhas_campos, colWidths=[card_width / 2] * 2)
            body.setStyle(
                TableStyle(
                    [
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 6),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                        ("TOPPADDING", (0, 0), (-1, -1), 5),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ]
                )
            )

            card = Table([[header], [body]], colWidths=[card_width])
            card.setStyle(
                TableStyle(
                    [
                        ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor("#cbd5e1")),
                        ("BACKGROUND", (0, 1), (0, 1), colors.HexColor("#f8fafc")),
                        ("LEFTPADDING", (0, 0), (-1, -1), 0),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                        ("TOPPADDING", (0, 0), (-1, -1), 0),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                    ]
                )
            )
            cards_linha.append(card)
            if len(cards_linha) == 3:
                flush_cards()

        flush_cards()
        return story_items

    dados = registro.dados or {}
    inspetor = (
        registro.inspetor.user.username
        if registro.inspetor and registro.inspetor.user
        else ""
    )
    data_inspecao = localtime(registro.data_inspecao).strftime("%d/%m/%Y %H:%M")
    emitido_em = localtime(timezone.now()).strftime("%d/%m/%Y %H:%M:%S")
    campos_principais = ["Data", "Fornecedor", "CNPJ", "Nº Nota fiscal", "Tipo de material", "Classe de Inspeção"]
    campos_recebimento = [
        (campo, dados.get(campo, ""))
        for campo in campos_principais
        if campo in dados
    ]
    campos_recebimento.extend(
        (campo, valor)
        for campo, valor in dados.items()
        if campo not in campos_principais
    )

    story = [
        Paragraph("Ficha de Inspeção de Recebimento", styles["title"]),
        Paragraph("Controle de qualidade - material recebido", styles["subtitle"]),
        Table(
            [
                [
                    "",
                    Paragraph(f"<b>#{registro.id}</b><br/>Emitido em {emitido_em}", styles["right"]),
                ]
            ],
            colWidths=[doc.width * 0.72, doc.width * 0.28],
        ),
        Spacer(1, 8),
        section("Dados do recebimento"),
        fields_table(
            [
                *campos_recebimento,
                ("Data inspeção", data_inspecao),
                ("Inspetor", inspetor),
                ("Resultado", registro.get_resultado_display()),
                ("Observação", registro.observacao or ""),
            ]
        ),
        section("Resultado da inspeção"),
        fields_table(
            [
                ("Resultado", registro.get_resultado_display()),
                ("Data da inspeção", data_inspecao),
                ("Inspetor", inspetor),
                ("Observação", registro.observacao or ""),
            ]
        ),
    ]

    unidades_com_material, colunas, linhas = _dados_unidades_recebimento_pdf(registro)
    story.extend(unidade_cards("Dados por unidade inspecionada", colunas, linhas))

    linhas_pecas = []
    for unidade in unidades_com_material:
        chamado = (unidade.get("campos") or {}).get("chamado_garantia") or "-"
        for peca in _extrair_pecas_devolucao_pdf(unidade.get("campos")):
            linhas_pecas.append(
                {
                    "tipo": "unidade",
                    "unidade": {
                        "unidade": unidade.get("unidade"),
                        "resultado": chamado,
                        "observacao": peca.get("codigo"),
                        "campos": {"quantidade": peca.get("quantidade")},
                    },
                }
            )
    story.extend(dynamic_table("Peças utilizadas na devolução", ["unidade", "resultado", "observacao", "quantidade"], linhas_pecas))

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#94a3b8"))
        canvas.drawString(document.leftMargin, 7 * mm, "Inspeção de Recebimento - sistema de qualidade")
        canvas.drawRightString(document.pagesize[0] - document.rightMargin, 7 * mm, f"Registro #{registro.id} - pagina {document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    buffer.seek(0)
    filename = f"ficha-inspecao-recebimento-{registro.id}.pdf"
    return FileResponse(buffer, as_attachment=True, filename=filename, content_type="application/pdf")


def inspecionar_recebimento(request):
    if request.method != "POST":
        return JsonResponse({"error": "Metodo nao permitido"}, status=405)

    if request.content_type and "multipart/form-data" in request.content_type:
        try:
            payload = json.loads(request.POST.get("payload", "{}") or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"error": "JSON invalido"}, status=400)
    else:
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"error": "JSON invalido"}, status=400)

    row_data = payload.get("data")
    if not isinstance(row_data, dict) or not row_data:
        return JsonResponse({"error": "Dados da linha nao informados"}, status=400)

    resultado = payload.get("resultado")
    if resultado not in {"conforme", "nao_conforme"}:
        return JsonResponse({"error": "Resultado invalido"}, status=400)

    observacao = (payload.get("observacao") or "").strip()
    dados_inspecao = payload.get("dados_inspecao") or None
    row_index = payload.get("row_index")
    item_id = payload.get("item_id")
    sheet_hash = _row_hash(row_data)
    classe_inspecao = _get_classe_inspecao(row_data)

    materiais_inspecao = []
    if isinstance(dados_inspecao, dict):
        materiais_val = dados_inspecao.get("materiais")
        if isinstance(materiais_val, list):
            materiais_inspecao = materiais_val

    classe_inspecao_normalizada = _normalizar_classe_inspecao(classe_inspecao)

    if classe_inspecao_normalizada == "adaptadores e terminais":
        if materiais_inspecao:
            conjuntos_unidades = [m.get("unidades") for m in materiais_inspecao if isinstance(m, dict)]
            if not any(isinstance(unidades, list) and unidades for unidades in conjuntos_unidades):
                return JsonResponse(
                    {"error": "Informe o teste de rosqueamento para as unidades inspecionadas."},
                    status=400,
                )
            unidades_iteracao = []
            for unidades in conjuntos_unidades:
                if isinstance(unidades, list):
                    unidades_iteracao.extend(unidades)
        else:
            unidades = dados_inspecao.get("unidades") if isinstance(dados_inspecao, dict) else None
            if not isinstance(unidades, list) or not unidades:
                return JsonResponse(
                    {"error": "Informe o teste de rosqueamento para as unidades inspecionadas."},
                    status=400,
                )
            unidades_iteracao = unidades

        for unidade in unidades_iteracao:
            campos = unidade.get("campos") if isinstance(unidade, dict) else None
            teste_rosqueamento = ""
            if isinstance(campos, dict):
                teste_rosqueamento = str(campos.get("teste_rosqueamento") or "").strip()
            if teste_rosqueamento not in {"conforme", "nao_conforme"}:
                return JsonResponse(
                    {"error": "Informe o teste de rosqueamento como conforme ou nao conforme."},
                    status=400,
                )

    if classe_inspecao_normalizada == "mangueiras hidraulicas":
        campos_obrigatorios = {
            "teste_rosqueamento": "teste de rosqueamento",
            "teste_estanqueidade": "teste de estanqueidade",
            "dimensional": "dimensional",
        }

        if materiais_inspecao:
            conjuntos_unidades = [m.get("unidades") for m in materiais_inspecao if isinstance(m, dict)]
            unidades_iteracao = []
            for unidades in conjuntos_unidades:
                if isinstance(unidades, list):
                    unidades_iteracao.extend(unidades)
        else:
            unidades = dados_inspecao.get("unidades") if isinstance(dados_inspecao, dict) else None
            unidades_iteracao = unidades if isinstance(unidades, list) else []

        if not unidades_iteracao:
            return JsonResponse(
                {"error": "Informe os campos de inspeção para as unidades inspecionadas."},
                status=400,
            )

        for unidade in unidades_iteracao:
            campos = unidade.get("campos") if isinstance(unidade, dict) else None
            campos = campos if isinstance(campos, dict) else {}

            for chave, rotulo in campos_obrigatorios.items():
                valor = str(campos.get(chave) or "").strip()
                if valor not in {"conforme", "nao_conforme"}:
                    return JsonResponse(
                        {"error": f"Informe {rotulo} como conforme ou nao conforme."},
                        status=400,
                    )

    if classe_inspecao_normalizada == "devolucao":
        if materiais_inspecao:
            conjuntos_unidades = [m.get("unidades") for m in materiais_inspecao if isinstance(m, dict)]
            unidades_iteracao = []
            for unidades in conjuntos_unidades:
                if isinstance(unidades, list):
                    unidades_iteracao.extend(unidades)
        else:
            unidades = dados_inspecao.get("unidades") if isinstance(dados_inspecao, dict) else None
            unidades_iteracao = unidades if isinstance(unidades, list) else []

        if not unidades_iteracao:
            return JsonResponse(
                {"error": "Informe o chamado de garantia e as peças usadas na devolução."},
                status=400,
            )

        for unidade in unidades_iteracao:
            campos = unidade.get("campos") if isinstance(unidade, dict) else None
            campos = campos if isinstance(campos, dict) else {}

            if not str(campos.get("chamado_garantia") or "").strip():
                return JsonResponse(
                    {"error": "Informe o numero de chamado da garantia."},
                    status=400,
                )

            if not str(campos.get("devolucao_material") or "").strip():
                return JsonResponse(
                    {"error": "Selecione o material da devolução."},
                    status=400,
                )

            indices_pecas = set()
            for chave in campos:
                match = re.match(r"^devolucao_peca_(\d+)_(codigo|quantidade)$", chave)
                if match:
                    indices_pecas.add(match.group(1))

            if not indices_pecas:
                return JsonResponse(
                    {"error": "Adicione ao menos uma peça usada na devolução."},
                    status=400,
                )

            for indice in indices_pecas:
                codigo_peca = str(campos.get(f"devolucao_peca_{indice}_codigo") or "").strip()
                quantidade_peca = str(campos.get(f"devolucao_peca_{indice}_quantidade") or "").strip()
                try:
                    quantidade_valida = codigo_peca and float(quantidade_peca) > 0
                except ValueError:
                    quantidade_valida = False
                if not quantidade_valida:
                    return JsonResponse(
                        {"error": "Preencha a peça e a quantidade em todas as linhas de peças usadas."},
                        status=400,
                    )

    item = None
    if item_id:
        item = InspecaoRecebimentoItem.objects.filter(id=item_id).first()
        if item:
            sheet_hash = item.sheet_hash

    registro_existente = InspecaoRecebimento.objects.filter(sheet_hash=sheet_hash).first()
    if registro_existente and not registro_existente.excluido:
        return JsonResponse({"error": "Item ja inspecionado"}, status=409)

    inspetor_profile = Profile.objects.filter(user=request.user).first() if request.user.is_authenticated else None

    with transaction.atomic():
        if item and not item.inspecionado:
            item.inspecionado = True
            item.save(update_fields=["inspecionado"])

        if materiais_inspecao:
            for material_idx, material in enumerate(materiais_inspecao, start=1):
                if not isinstance(material, dict):
                    continue

                unidades = material.get("unidades")
                if not isinstance(unidades, list):
                    continue

                for unidade_idx, unidade in enumerate(unidades, start=1):
                    if not isinstance(unidade, dict):
                        continue

                    campo_imagem = str(unidade.get("imagem_campo") or "").strip()
                    imagem = request.FILES.get(campo_imagem) if campo_imagem else None
                    if imagem:
                        unidade["imagem"] = _salvar_imagem_inspecao_recebimento(
                            imagem,
                            sheet_hash,
                            material_idx,
                            unidade_idx,
                        )

                    campo_video = str(unidade.get("video_campo") or "").strip()
                    video = request.FILES.get(campo_video) if campo_video else None
                    if video:
                        unidade["video"] = _salvar_video_inspecao_recebimento(
                            video,
                            sheet_hash,
                            material_idx,
                            unidade_idx,
                        )

        inspection_fields = dict(
            inspetor=inspetor_profile,
            item=item,
            planilha_id=SHEET_ID,
            aba_nome=SHEET_TAB,
            linha_planilha=row_index if isinstance(row_index, int) else None,
            dados=row_data,
            dados_inspecao=dados_inspecao,
            resultado=resultado,
            observacao=observacao,
            excluido=False,
        )

        if registro_existente:
            for field, value in inspection_fields.items():
                setattr(registro_existente, field, value)
            registro_existente.save(update_fields=list(inspection_fields.keys()))
        else:
            InspecaoRecebimento.objects.create(sheet_hash=sheet_hash, **inspection_fields)

    return JsonResponse({"success": True}, status=200)


def excluir_recebimento_inspecao(request):
    if request.method != "POST":
        return JsonResponse({"error": "Método não permitido"}, status=405)
    if not _tem_acesso_edicao(request):
        return JsonResponse({"error": "Sem permissão"}, status=403)
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON inválido"}, status=400)

    registro_id = payload.get("id")
    if not registro_id:
        return JsonResponse({"error": "Campo 'id' obrigatório"}, status=400)

    registro = InspecaoRecebimento.objects.filter(id=registro_id).first()
    if not registro:
        return JsonResponse({"error": "Registro não encontrado"}, status=404)

    with transaction.atomic():
        registro.excluido = True
        registro.save(update_fields=["excluido"])

        if registro.item_id:
            ainda_ativo = InspecaoRecebimento.objects.filter(
                item_id=registro.item_id, excluido=False
            ).exists()
            if not ainda_ativo:
                InspecaoRecebimentoItem.objects.filter(id=registro.item_id).update(inspecionado=False)

    return JsonResponse({"success": True}, status=200)


TIPOS_ACESSO_EDICAO = {"supervisor", "admin", "pcp"}


def _tem_acesso_edicao(request):
    if not request.user.is_authenticated:
        return False
    profile = Profile.objects.filter(user=request.user).first()
    return profile is not None and profile.tipo_acesso in TIPOS_ACESSO_EDICAO


def editar_recebimento_inspecao(request):
    if request.method != "POST":
        return JsonResponse({"error": "Método não permitido"}, status=405)
    if not _tem_acesso_edicao(request):
        return JsonResponse({"error": "Sem permissão"}, status=403)
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON inválido"}, status=400)

    registro_id = payload.get("id")
    if not registro_id:
        return JsonResponse({"error": "Campo 'id' obrigatório"}, status=400)

    resultado = payload.get("resultado")
    if resultado not in {"conforme", "nao_conforme"}:
        return JsonResponse({"error": "Resultado inválido"}, status=400)

    observacao = (payload.get("observacao") or "").strip()
    dados_inspecao = payload.get("dados_inspecao")

    update_fields = {"resultado": resultado, "observacao": observacao}
    if dados_inspecao is not None:
        update_fields["dados_inspecao"] = dados_inspecao

    updated = InspecaoRecebimento.objects.filter(id=registro_id).update(**update_fields)
    if not updated:
        return JsonResponse({"error": "Registro não encontrado"}, status=404)

    return JsonResponse({"success": True}, status=200)


def desfazer_recebimento_inspecao(request):
    if request.method != "POST":
        return JsonResponse({"error": "Método não permitido"}, status=405)
    if not _tem_acesso_edicao(request):
        return JsonResponse({"error": "Sem permissão"}, status=403)
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON inválido"}, status=400)

    registro_id = payload.get("id")
    if not registro_id:
        return JsonResponse({"error": "Campo 'id' obrigatório"}, status=400)

    registro = (
        InspecaoRecebimento.objects.select_related("item")
        .filter(id=registro_id, excluido=False)
        .first()
    )
    if not registro:
        return JsonResponse({"error": "Registro não encontrado"}, status=404)

    data_referencia = None
    if isinstance(registro.dados, dict):
        data_referencia = _parse_br_date(registro.dados.get("Data"))

    item = registro.item
    if item is None and registro.sheet_hash:
        item = InspecaoRecebimentoItem.objects.filter(sheet_hash=registro.sheet_hash).first()
    if item is None and data_referencia is not None:
        item = _find_recebimento_item_by_business_key(registro.dados or {}, data_referencia)
    if item is None and data_referencia is not None:
        item = _find_recebimento_item_by_identity(registro.dados or {}, data_referencia)

    with transaction.atomic():
        if item is None:
            item = InspecaoRecebimentoItem.objects.create(
                planilha_id=registro.planilha_id,
                aba_nome=registro.aba_nome,
                linha_planilha=registro.linha_planilha,
                sheet_hash=registro.sheet_hash,
                dados=registro.dados or {},
                data_referencia=data_referencia or timezone.localdate(),
                status_h=True,
                inspecionado=False,
                excluido=False,
            )
        else:
            item.planilha_id = registro.planilha_id
            item.aba_nome = registro.aba_nome
            item.linha_planilha = registro.linha_planilha
            item.sheet_hash = registro.sheet_hash
            item.dados = registro.dados or {}
            if data_referencia is not None:
                item.data_referencia = data_referencia
            item.status_h = True
            item.inspecionado = False
            item.excluido = False
            item.save(
                update_fields=[
                    "planilha_id",
                    "aba_nome",
                    "linha_planilha",
                    "sheet_hash",
                    "dados",
                    "data_referencia",
                    "status_h",
                    "inspecionado",
                    "excluido",
                ]
            )

        registro.item = item
        registro.excluido = True
        registro.save(update_fields=["item", "excluido"])

    return JsonResponse({"success": True, "item_id": item.id}, status=200)


def excluir_recebimento_inspecao_lote(request):
    if request.method != "POST":
        return JsonResponse({"error": "Método não permitido"}, status=405)
    if not _tem_acesso_edicao(request):
        return JsonResponse({"error": "Sem permissão"}, status=403)
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON inválido"}, status=400)

    ids = payload.get("ids")
    if not ids or not isinstance(ids, list):
        return JsonResponse({"error": "Campo 'ids' deve ser uma lista"}, status=400)

    item_ids = list(
        InspecaoRecebimento.objects.filter(id__in=ids, item__isnull=False)
        .values_list("item_id", flat=True)
        .distinct()
    )

    with transaction.atomic():
        updated = InspecaoRecebimento.objects.filter(id__in=ids).update(excluido=True)

        for item_id in item_ids:
            ainda_ativo = InspecaoRecebimento.objects.filter(
                item_id=item_id, excluido=False
            ).exists()
            if not ainda_ativo:
                InspecaoRecebimentoItem.objects.filter(id=item_id).update(inspecionado=False)

    return JsonResponse({"success": True, "excluidos": updated}, status=200)


def excluir_recebimento_item(request):
    if request.method != "POST":
        return JsonResponse({"error": "Método não permitido"}, status=405)
    if not _tem_acesso_edicao(request):
        return JsonResponse({"error": "Sem permissão"}, status=403)
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON inválido"}, status=400)

    item_id = payload.get("id")
    if not item_id:
        return JsonResponse({"error": "Campo 'id' obrigatório"}, status=400)

    updated = InspecaoRecebimentoItem.objects.filter(id=item_id).update(excluido=True)
    if not updated:
        return JsonResponse({"error": "Item não encontrado"}, status=404)

    return JsonResponse({"success": True}, status=200)


def excluir_recebimento_item_lote(request):
    if request.method != "POST":
        return JsonResponse({"error": "Método não permitido"}, status=405)
    if not _tem_acesso_edicao(request):
        return JsonResponse({"error": "Sem permissão"}, status=403)
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON inválido"}, status=400)

    ids = payload.get("ids")
    if not ids or not isinstance(ids, list):
        return JsonResponse({"error": "Campo 'ids' deve ser uma lista"}, status=400)

    updated = InspecaoRecebimentoItem.objects.filter(id__in=ids).update(excluido=True)
    return JsonResponse({"success": True, "excluidos": updated}, status=200)


# ── Dashboard ────────────────────────────────────────────────────────────────

def dashboard_recebimento(request):
    return render(request, "dashboard/recebimento.html")


def _parse_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date() if value else None
    except ValueError:
        return None


def _filtrar_qs(qs, data_inicio, data_fim, tipo_data='inspecao'):
    if tipo_data == 'recebimento':
        if data_inicio:
            qs = qs.filter(item__data_referencia__gte=data_inicio)
        if data_fim:
            qs = qs.filter(item__data_referencia__lte=data_fim)
    else:
        if data_inicio:
            qs = qs.filter(data_inspecao__date__gte=data_inicio)
        if data_fim:
            qs = qs.filter(data_inspecao__date__lte=data_fim)
    return qs


def _classe_recebimento_devolucao_q(prefixo="dados"):
    return (
        Q(**{f"{prefixo}__Classe de Inspeção__istartswith": "devolu"})
        | Q(**{f"{prefixo}__Classe de inspeção__istartswith": "devolu"})
    )


def _build_date_filter(tipo_data, di, df, params):
    """Returns (join_sql, where_conditions) and appends date params to params list."""
    where = []
    if tipo_data == 'recebimento':
        join_sql = "JOIN inspecao_inspecaorecebimentoitem iri ON iri.id = ir.item_id"
        if di:
            where.append("iri.data_referencia >= %s")
            params.append(di)
        if df:
            where.append("iri.data_referencia <= %s")
            params.append(df)
    else:
        join_sql = ""
        if di:
            where.append("(ir.data_inspecao AT TIME ZONE 'America/Sao_Paulo')::date >= %s")
            params.append(di)
        if df:
            where.append("(ir.data_inspecao AT TIME ZONE 'America/Sao_Paulo')::date <= %s")
            params.append(df)
    return join_sql, where


def api_recebimento_resumo(request):
    if request.method != "GET":
        return JsonResponse({"error": "Método não permitido"}, status=405)

    di = _parse_date(request.GET.get("data_inicio"))
    df = _parse_date(request.GET.get("data_fim"))
    tipo_data = request.GET.get("tipo_data", "inspecao")

    qs = _filtrar_qs(InspecaoRecebimento.objects.filter(excluido=False), di, df, tipo_data)
    total      = qs.count()
    classe_devolucao = _classe_recebimento_devolucao_q()
    devolucoes = qs.filter(classe_devolucao).count()
    conforme   = qs.filter(resultado="conforme").count()
    nc         = qs.filter(resultado="nao_conforme").count()
    conforme_devolucoes = qs.filter(classe_devolucao, resultado="conforme").count()
    nc_devolucoes = qs.filter(classe_devolucao, resultado="nao_conforme").count()

    pendentes_qs = InspecaoRecebimentoItem.objects.filter(inspecionado=False, excluido=False)
    if di:
        pendentes_qs = pendentes_qs.filter(data_referencia__gte=di)
    if df:
        pendentes_qs = pendentes_qs.filter(data_referencia__lte=df)
    pendentes = pendentes_qs.count()
    pendentes_devolucoes = pendentes_qs.filter(_classe_recebimento_devolucao_q()).count()

    return JsonResponse({
        "total": total,
        "devolucoes": devolucoes,
        "conforme": conforme,
        "conforme_devolucoes": conforme_devolucoes,
        "nao_conforme": nc,
        "nao_conforme_devolucoes": nc_devolucoes,
        "pendentes": pendentes,
        "pendentes_devolucoes": pendentes_devolucoes,
        "taxa_conformidade":    round(conforme / total * 100, 1) if total else 0,
        "taxa_nao_conformidade": round(nc / total * 100, 1) if total else 0,
    })


def api_recebimento_analise_temporal(request):
    if request.method != "GET":
        return JsonResponse({"error": "Método não permitido"}, status=405)

    di = _parse_date(request.GET.get("data_inicio"))
    df = _parse_date(request.GET.get("data_fim"))
    tipo_data = request.GET.get("tipo_data", "inspecao")

    params = []
    join_sql, date_where = _build_date_filter(tipo_data, di, df, params)
    where = ["ir.excluido = FALSE"] + date_where

    if tipo_data == 'recebimento':
        date_trunc = "DATE_TRUNC('month', iri.data_referencia)"
    else:
        date_trunc = "DATE_TRUNC('month', ir.data_inspecao AT TIME ZONE 'America/Sao_Paulo')"

    sql = f"""
        SELECT
            TO_CHAR({date_trunc}, 'YYYY-MM')                                       AS mes,
            COUNT(*)                                                                AS total,
            COUNT(*) FILTER (
                WHERE ir.resultado = 'conforme'
                  AND NOT (COALESCE(ir.dados->>'Classe de Inspeção', ir.dados->>'Classe de inspeção', '') ILIKE 'devolu%%')
            )                                                                       AS conforme,
            COUNT(*) FILTER (
                WHERE ir.resultado = 'nao_conforme'
                  AND NOT (COALESCE(ir.dados->>'Classe de Inspeção', ir.dados->>'Classe de inspeção', '') ILIKE 'devolu%%')
            )                                                                       AS nao_conforme,
            COUNT(*) FILTER (
                WHERE COALESCE(ir.dados->>'Classe de Inspeção', ir.dados->>'Classe de inspeção', '') ILIKE 'devolu%%'
            )                                                                       AS devolucoes
        FROM inspecao_inspecaorecebimento ir
        {join_sql}
        WHERE {' AND '.join(where)}
        GROUP BY 1
        ORDER BY 1
    """
    with connection.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    return JsonResponse([
        {
            "mes": r[0],
            "total": r[1],
            "conforme": r[2],
            "nao_conforme": r[3],
            "devolucoes": r[4],
            "taxa_nc": round(r[3] / r[1] * 100, 1) if r[1] else 0,
        }
        for r in rows
    ], safe=False)


def api_recebimento_por_fornecedor(request):
    if request.method != "GET":
        return JsonResponse({"error": "Método não permitido"}, status=405)

    di = _parse_date(request.GET.get("data_inicio"))
    df = _parse_date(request.GET.get("data_fim"))
    tipo_data = request.GET.get("tipo_data", "inspecao")

    params = []
    join_sql, date_where = _build_date_filter(tipo_data, di, df, params)
    where = ["ir.excluido = FALSE"] + date_where

    sql = f"""
        SELECT
            COALESCE(NULLIF(TRIM(ir.dados->>'Fornecedor'), ''), '(Sem fornecedor)') AS fornecedor,
            COUNT(*)                                                    AS total,
            COUNT(*) FILTER (WHERE ir.resultado = 'conforme')          AS conforme,
            COUNT(*) FILTER (WHERE ir.resultado = 'nao_conforme')      AS nao_conforme
        FROM inspecao_inspecaorecebimento ir
        {join_sql}
        WHERE {' AND '.join(where)}
        GROUP BY 1
        ORDER BY nao_conforme DESC, total DESC
        LIMIT 15
    """
    with connection.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    return JsonResponse([
        {"fornecedor": r[0], "total": r[1], "conforme": r[2], "nao_conforme": r[3]}
        for r in rows
    ], safe=False)


def api_recebimento_por_classe(request):
    if request.method != "GET":
        return JsonResponse({"error": "Método não permitido"}, status=405)

    di = _parse_date(request.GET.get("data_inicio"))
    df = _parse_date(request.GET.get("data_fim"))
    tipo_data = request.GET.get("tipo_data", "inspecao")

    params = []
    join_sql, date_where = _build_date_filter(tipo_data, di, df, params)
    where = ["ir.excluido = FALSE"] + date_where

    sql = f"""
        SELECT
            COALESCE(NULLIF(ir.dados->>'Classe de Inspeção', ''), 'Não informado') AS classe,
            COUNT(*)                                                                AS total,
            COUNT(*) FILTER (WHERE ir.resultado = 'nao_conforme')                  AS nao_conforme
        FROM inspecao_inspecaorecebimento ir
        {join_sql}
        WHERE {' AND '.join(where)}
        GROUP BY 1
        ORDER BY total DESC
    """
    with connection.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    return JsonResponse([
        {"classe": r[0], "total": r[1], "nao_conforme": r[2]}
        for r in rows
    ], safe=False)


def api_recebimento_por_tipo_material(request):
    if request.method != "GET":
        return JsonResponse({"error": "Método não permitido"}, status=405)

    di = _parse_date(request.GET.get("data_inicio"))
    df = _parse_date(request.GET.get("data_fim"))
    tipo_data = request.GET.get("tipo_data", "inspecao")

    params = []
    join_sql, date_where = _build_date_filter(tipo_data, di, df, params)
    where = ["ir.excluido = FALSE"] + date_where

    sql = f"""
        SELECT
            COALESCE(NULLIF(ir.dados->>'Tipo de material', ''), 'Não informado') AS tipo,
            COUNT(*)                                                               AS total,
            COUNT(*) FILTER (WHERE ir.resultado = 'conforme')                     AS conforme,
            COUNT(*) FILTER (WHERE ir.resultado = 'nao_conforme')                 AS nao_conforme
        FROM inspecao_inspecaorecebimento ir
        {join_sql}
        WHERE {' AND '.join(where)}
        GROUP BY 1
        ORDER BY total DESC
    """
    with connection.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    return JsonResponse([
        {"tipo": r[0], "total": r[1], "conforme": r[2], "nao_conforme": r[3]}
        for r in rows
    ], safe=False)
