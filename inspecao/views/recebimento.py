import hashlib
import json
import os
from datetime import datetime

import gspread
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render

from core.models import Profile
from core.utils import get_google_credentials
from ..models import InspecaoRecebimento, InspecaoRecebimentoItem

SHEET_ID = os.environ.get(
    "RECEBIMENTO_SHEET_ID",
    "1mLuw4jM5WpD0pgxXREio15Ju8MZZ7QMJHb3vapz94Ac",
)
SHEET_TAB = os.environ.get(
    "RECEBIMENTO_SHEET_TAB",
    "Base controle de entrada",
)

DEFAULT_CUT_OFF_DATE = "01/02/2026"
COLUNA_STATUS_IDX = 7  # Coluna H (0-based)
COLUNAS_EXIBIR = [0, 1, 2, 3, 4, 5, 6, 8, 9, 10]  # A,B,C,D,E,F,G,I,J,K


def inspecao_recebimento(request):
    user_profile = Profile.objects.filter(user=request.user).first()
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
        return None, "Credenciais do Google Sheets nÃ£o encontradas."

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


def _row_hash_from_list(row_values):
    payload = json.dumps(row_values, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def sincronizar_recebimento(request):
    if request.method != "POST":
        return JsonResponse({"error": "MÃ©todo nÃ£o permitido"}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        payload = {}

    cutoff_input = (payload.get("cutoff_date") or "").strip() if isinstance(payload, dict) else ""
    if not cutoff_input:
        cutoff_input = DEFAULT_CUT_OFF_DATE

    values, error = _load_recebimento_sheet()
    if error:
        return JsonResponse({"error": error}, status=500)

    if not values or len(values) < 2:
        return JsonResponse({"novos": 0, "total": 0}, status=200)

    header_row_index = 5
    header_row = values[header_row_index - 1] if len(values) >= header_row_index else []
    selected_headers = _make_unique_headers(
        [header_row[i] if i < len(header_row) else "" for i in COLUNAS_EXIBIR]
    )
    data_rows = values[header_row_index:]

    cutoff = _parse_br_date(cutoff_input)
    if cutoff is None:
        return JsonResponse({"error": "Data de corte invÃ¡lida"}, status=500)

    novos = 0
    total = 0

    for row_index, row in enumerate(data_rows, start=header_row_index + 1):
        row_values = list(row)
        if not row_values:
            continue
        if len(row_values) <= COLUNA_STATUS_IDX:
            continue

        data_coluna_a = _parse_br_date(row_values[0])
        if data_coluna_a is None or data_coluna_a <= cutoff:
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

        existing_item = InspecaoRecebimentoItem.objects.filter(sheet_hash=sheet_hash).first()
        if existing_item:
            existing_item.dados = dados
            existing_item.data_referencia = data_coluna_a
            existing_item.status_h = True
            existing_item.save(update_fields=["dados", "data_referencia", "status_h"])
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

    return JsonResponse({"novos": novos, "total": total}, status=200)


def recebimento_pendencias(request):
    if request.method != "GET":
        return JsonResponse({"error": "MÃ©todo nÃ£o permitido"}, status=405)

    itens = InspecaoRecebimentoItem.objects.filter(inspecionado=False).order_by("-id")
    rows = []
    headers = []

    for item in itens:
        data = item.dados or {}
        for key in data.keys():
            if key not in headers:
                headers.append(key)
        rows.append(
            {
                "row_index": item.linha_planilha,
                "hash": item.sheet_hash,
                "data": data,
                "item_id": item.id,
            }
        )

    return JsonResponse(
        {
            "columns": headers,
            "rows": rows,
            "total": len(rows),
        },
        status=200,
    )


def recebimento_inspecionados(request):
    if request.method != "GET":
        return JsonResponse({"error": "Método não permitido"}, status=405)

    registros = (
        InspecaoRecebimento.objects.select_related("inspetor__user")
        .order_by("-data_inspecao")
    )

    headers = []
    linhas = []

    for registro in registros:
        data = registro.dados or {}
        for key in data.keys():
            if key not in headers:
                headers.append(key)

        linhas.append(
            {
                "data": data,
                "meta": {
                    "data_inspecao": registro.data_inspecao.strftime("%d/%m/%Y %H:%M"),
                    "inspetor": (
                        registro.inspetor.user.username
                        if registro.inspetor and registro.inspetor.user
                        else ""
                    ),
                    "resultado": registro.get_resultado_display(),
                    "observacao": registro.observacao or "",
                },
            }
        )

    columns = ["Data inspeção", "Inspetor", "Resultado", "Observação"] + headers

    rows = []
    for linha in linhas:
        display = {
            "Data inspeção": linha["meta"]["data_inspecao"],
            "Inspetor": linha["meta"]["inspetor"],
            "Resultado": linha["meta"]["resultado"],
            "Observação": linha["meta"]["observacao"],
        }
        for header in headers:
            display[header] = linha["data"].get(header, "")
        rows.append({"data": display})

    return JsonResponse(
        {
            "columns": columns,
            "rows": rows,
            "total": len(rows),
        },
        status=200,
    )


def inspecionar_recebimento(request):
    if request.method != "POST":
        return JsonResponse({"error": "MÃ©todo nÃ£o permitido"}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON invÃ¡lido"}, status=400)

    row_data = payload.get("data")
    if not isinstance(row_data, dict) or not row_data:
        return JsonResponse({"error": "Dados da linha nÃ£o informados"}, status=400)

    resultado = payload.get("resultado")
    if resultado not in {"conforme", "nao_conforme"}:
        return JsonResponse({"error": "Resultado invÃ¡lido"}, status=400)

    observacao = (payload.get("observacao") or "").strip()
    row_index = payload.get("row_index")
    item_id = payload.get("item_id")
    sheet_hash = _row_hash(row_data)

    item = None
    if item_id:
        item = InspecaoRecebimentoItem.objects.filter(id=item_id).first()
        if item:
            sheet_hash = item.sheet_hash

    if InspecaoRecebimento.objects.filter(sheet_hash=sheet_hash).exists():
        return JsonResponse({"error": "Item jÃ¡ inspecionado"}, status=409)

    inspetor_profile = Profile.objects.filter(user=request.user).first()

    with transaction.atomic():
        if item and not item.inspecionado:
            item.inspecionado = True
            item.save(update_fields=["inspecionado"])

        InspecaoRecebimento.objects.create(
            inspetor=inspetor_profile,
            item=item,
            planilha_id=SHEET_ID,
            aba_nome=SHEET_TAB,
            linha_planilha=row_index if isinstance(row_index, int) else None,
            sheet_hash=sheet_hash,
            dados=row_data,
            resultado=resultado,
            observacao=observacao,
        )

    return JsonResponse({"success": True}, status=200)
