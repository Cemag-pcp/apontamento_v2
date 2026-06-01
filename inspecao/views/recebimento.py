import hashlib
import json
import os
from datetime import datetime

import gspread
from django.core.files.storage import default_storage
from django.db import connection, transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.timezone import localtime

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

DEFAULT_CUT_OFF_DATE = "2026-05-01"
COLUNA_STATUS_IDX = 7  # Coluna H (0-based)
COLUNAS_EXIBIR = [0, 1, 2, 3, 4, 5, 6, 8, 9, 10]  # A,B,C,D,E,F,G,I,J,K


def _salvar_imagem_inspecao_recebimento(uploaded_file, sheet_hash, material_idx, unidade_idx):
    extensao = os.path.splitext(getattr(uploaded_file, "name", "") or "")[1].lower() or ".jpg"
    caminho = (
        f"inspecao_recebimento/{datetime.now().strftime('%Y/%m')}/"
        f"{sheet_hash}_m{material_idx}_u{unidade_idx}{extensao}"
    )
    caminho_salvo = default_storage.save(caminho, uploaded_file)

    try:
        url = default_storage.url(caminho_salvo)
    except Exception:
        url = ""

    return {
        "arquivo": caminho_salvo,
        "url": url,
        "nome": getattr(uploaded_file, "name", ""),
    }


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


def sincronizar_recebimento(request):
    if request.method != "POST":
        return JsonResponse({"error": "MÃ©todo não permitido"}, status=405)

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

    cutoff = _parse_br_date(DEFAULT_CUT_OFF_DATE)
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

    return JsonResponse({"novos": novos, "total": total}, status=200)


COLUNAS_PENDENCIAS = [
    "Data",
    "CNPJ",
    "Fornecedor",
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


def recebimento_inspecionados(request):
    if request.method != "GET":
        return JsonResponse({"error": "Método não permitido"}, status=405)

    registros = (
        InspecaoRecebimento.objects.select_related("inspetor__user")
        .filter(excluido=False)
        .order_by("-data_inspecao")
    )

    COLUNAS_OCULTAS = {"Situação do frete"}

    headers = []
    linhas = []

    for registro in registros:
        data = registro.dados or {}
        for key in data.keys():
            if key not in headers and key not in COLUNAS_OCULTAS:
                headers.append(key)

        linhas.append(
            {
                "data": data,
                "meta": {
                    "id": registro.id,
                    "data_inspecao": localtime(registro.data_inspecao).strftime("%d/%m/%Y %H:%M"),
                    "inspetor": (
                        registro.inspetor.user.username
                        if registro.inspetor and registro.inspetor.user
                        else ""
                    ),
                    "resultado": registro.get_resultado_display(),
                    "observacao": registro.observacao or "",
                },
                "dados_inspecao": registro.dados_inspecao or {},
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
        rows.append(
            {
                "data": display,
                "meta": linha["meta"],
                "dados_inspecao": linha["dados_inspecao"],
            }
        )

    return JsonResponse(
        {
            "columns": columns,
            "rows": rows,
            "total": len(rows),
            "pode_editar": _tem_acesso_edicao(request),
        },
        status=200,
    )


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

    item = None
    if item_id:
        item = InspecaoRecebimentoItem.objects.filter(id=item_id).first()
        if item:
            sheet_hash = item.sheet_hash

    if InspecaoRecebimento.objects.filter(sheet_hash=sheet_hash, excluido=False).exists():
        return JsonResponse({"error": "Item ja inspecionado"}, status=409)

    inspetor_profile = Profile.objects.filter(user=request.user).first()

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
                    if not campo_imagem:
                        continue

                    imagem = request.FILES.get(campo_imagem)
                    if not imagem:
                        continue

                    unidade["imagem"] = _salvar_imagem_inspecao_recebimento(
                        imagem,
                        sheet_hash,
                        material_idx,
                        unidade_idx,
                    )

        InspecaoRecebimento.objects.create(
            inspetor=inspetor_profile,
            item=item,
            planilha_id=SHEET_ID,
            aba_nome=SHEET_TAB,
            linha_planilha=row_index if isinstance(row_index, int) else None,
            sheet_hash=sheet_hash,
            dados=row_data,
            dados_inspecao=dados_inspecao,
            resultado=resultado,
            observacao=observacao,
        )

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


def _filtrar_qs(qs, data_inicio, data_fim):
    if data_inicio:
        qs = qs.filter(data_inspecao__date__gte=data_inicio)
    if data_fim:
        qs = qs.filter(data_inspecao__date__lte=data_fim)
    return qs


def api_recebimento_resumo(request):
    if request.method != "GET":
        return JsonResponse({"error": "Método não permitido"}, status=405)

    di = _parse_date(request.GET.get("data_inicio"))
    df = _parse_date(request.GET.get("data_fim"))

    qs = _filtrar_qs(InspecaoRecebimento.objects.filter(excluido=False), di, df)
    total      = qs.count()
    conforme   = qs.filter(resultado="conforme").count()
    nc         = qs.filter(resultado="nao_conforme").count()
    pendentes  = InspecaoRecebimentoItem.objects.filter(inspecionado=False, excluido=False).count()

    return JsonResponse({
        "total": total,
        "conforme": conforme,
        "nao_conforme": nc,
        "pendentes": pendentes,
        "taxa_conformidade":    round(conforme / total * 100, 1) if total else 0,
        "taxa_nao_conformidade": round(nc / total * 100, 1) if total else 0,
    })


def api_recebimento_analise_temporal(request):
    if request.method != "GET":
        return JsonResponse({"error": "Método não permitido"}, status=405)

    di = _parse_date(request.GET.get("data_inicio"))
    df = _parse_date(request.GET.get("data_fim"))

    params = []
    where  = ["excluido = FALSE"]
    if di:
        where.append("(data_inspecao AT TIME ZONE 'America/Sao_Paulo')::date >= %s")
        params.append(di)
    if df:
        where.append("(data_inspecao AT TIME ZONE 'America/Sao_Paulo')::date <= %s")
        params.append(df)

    sql = f"""
        SELECT
            TO_CHAR(DATE_TRUNC('month', data_inspecao AT TIME ZONE 'America/Sao_Paulo'), 'YYYY-MM') AS mes,
            COUNT(*)                                                                AS total,
            COUNT(*) FILTER (WHERE resultado = 'conforme')                         AS conforme,
            COUNT(*) FILTER (WHERE resultado = 'nao_conforme')                     AS nao_conforme
        FROM inspecao_inspecaorecebimento
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
            "taxa_nc": round(r[3] / r[1] * 100, 1) if r[1] else 0,
        }
        for r in rows
    ], safe=False)


def api_recebimento_por_fornecedor(request):
    if request.method != "GET":
        return JsonResponse({"error": "Método não permitido"}, status=405)

    di = _parse_date(request.GET.get("data_inicio"))
    df = _parse_date(request.GET.get("data_fim"))

    params = []
    where  = ["excluido = FALSE", "dados->>'Fornecedor' IS NOT NULL", "dados->>'Fornecedor' <> ''"]
    if di:
        where.append("(data_inspecao AT TIME ZONE 'America/Sao_Paulo')::date >= %s")
        params.append(di)
    if df:
        where.append("(data_inspecao AT TIME ZONE 'America/Sao_Paulo')::date <= %s")
        params.append(df)

    sql = f"""
        SELECT
            dados->>'Fornecedor'                                       AS fornecedor,
            COUNT(*)                                                    AS total,
            COUNT(*) FILTER (WHERE resultado = 'conforme')              AS conforme,
            COUNT(*) FILTER (WHERE resultado = 'nao_conforme')          AS nao_conforme
        FROM inspecao_inspecaorecebimento
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

    params = []
    where  = ["excluido = FALSE"]
    if di:
        where.append("(data_inspecao AT TIME ZONE 'America/Sao_Paulo')::date >= %s")
        params.append(di)
    if df:
        where.append("(data_inspecao AT TIME ZONE 'America/Sao_Paulo')::date <= %s")
        params.append(df)

    sql = f"""
        SELECT
            COALESCE(NULLIF(dados->>'Classe de Inspeção', ''), 'Não informado') AS classe,
            COUNT(*)                                                              AS total,
            COUNT(*) FILTER (WHERE resultado = 'nao_conforme')                   AS nao_conforme
        FROM inspecao_inspecaorecebimento
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

    params = []
    where  = ["excluido = FALSE"]
    if di:
        where.append("(data_inspecao AT TIME ZONE 'America/Sao_Paulo')::date >= %s")
        params.append(di)
    if df:
        where.append("(data_inspecao AT TIME ZONE 'America/Sao_Paulo')::date <= %s")
        params.append(df)

    sql = f"""
        SELECT
            COALESCE(NULLIF(dados->>'Tipo de material', ''), 'Não informado') AS tipo,
            COUNT(*)                                                            AS total,
            COUNT(*) FILTER (WHERE resultado = 'conforme')                     AS conforme,
            COUNT(*) FILTER (WHERE resultado = 'nao_conforme')                 AS nao_conforme
        FROM inspecao_inspecaorecebimento
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
