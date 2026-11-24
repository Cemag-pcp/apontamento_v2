"""Inspeção de Item de Garantia (Controle de Qualidade > Garantia).

Os itens vêm da planilha de cargas (RQ AV-002-000, aba "Importar Dados"):
linhas com a coluna "Carga" = GARANTIA, que são peças de reposição em
garantia a serem enviadas ao cliente. A planilha é lida todo dia de
madrugada (GitHub Actions, comando sincronizar_itens_garantia), pela tela no
máximo a cada 5 minutos, ou na hora pelo botão "Atualizar agora".

O inspetor registra cada inspeção (data, nº da garantia, o que foi
verificado, aprovado ou não, quem inspecionou, fotos). Reprovado volta para
reinspeção quantas vezes for preciso, até ser aprovado.
"""
import json
import logging
import os
import re
from datetime import datetime, timedelta

import gspread
import requests
from django.conf import settings
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import IntegerField, OuterRef, Q, Subquery, Value
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from core.models import Profile
from core.utils import get_google_credentials
from inspecao.models import (
    FotoInspecaoGarantia,
    InspecaoGarantia,
    ItemGarantia,
    SincronizacaoGarantia,
)

logger = logging.getLogger(__name__)

SHEET_ID = os.environ.get("GARANTIA_SHEET_ID", "1olnMhK7OI6W0eJ-dvsi3Lku5eCYqlpzTGJfh1Q7Pv9I")
SHEET_TAB = os.environ.get("GARANTIA_SHEET_TAB", "Importar Dados")
VALOR_CARGA = "GARANTIA"
ROTA = "inspecao/garantia"

INTERVALO_SYNC = 300  # segundos entre leituras automáticas da planilha
ACESSOS_DESFAZER = ("admin", "supervisor", "pcp")

# Ploomes: chamados de garantia ficam no "Funil de Chamados"; o campo
# "Peças" (texto longo) traz "CÓDIGO - DESCRIÇÃO - Qtd", e é por ele que
# sugerimos os chamados da peça do item.
PLOOMES_DEALS_URL = "https://api2.ploomes.com/Deals"
PLOOMES_FUNIL_CHAMADOS = int(os.environ.get("PLOOMES_FUNIL_CHAMADOS", "41117"))
PLOOMES_CAMPO_PECAS = "deal_BAAFDC7D-8467-4A14-AAE0-0C29B4FEFC2A"
PLOOMES_STATUS = {1: "Em aberto", 2: "Ganho", 3: "Perdido"}
PLOOMES_CAMPO_TIPO_CLIENTE = "contact_8FD23CD7-15E3-462E-97BA-462F8E09DDFE"  # no cadastro do cliente

# Seções do chamado mostradas ao escolher a garantia (mesma ordem do Ploomes).
# (rótulo, chave do campo no chamado | atributo especial, formato)
PLOOMES_SECOES = [
    ("Pedido", [
        ("Valor das peças", "deal_852659FB-96A9-4361-A429-9DBE05B5E024", "moeda"),
        ("Valor do reembolso", "deal_4393F0E7-13E2-4BF0-B7F6-EEE85FA198B3", "moeda"),
        ("Status peças", "deal_DAB68EB5-4EAF-4643-AB4F-D827D487117D", None),
        ("Previsão de envio", "deal_5A9DFB60-53C1-439E-9A91-D8F124F6EF27", "data"),
    ]),
    ("Análise", [
        ("Tipo de garantia", "deal_79FAF32E-9ABD-4072-B9E0-28F8AF65EEB9", None),
        ("Motivo do chamado", "deal_59A5385D-C967-4BC6-A14A-670C700E0D8E", None),
        ("Departamento do chamado", "deal_F48A727D-8829-4643-98E5-7A46D34D050B", None),
        ("Conjunto", "deal_9B977313-ABB1-45B2-B17F-8034CC7C4D55", None),
        ("Conclusão da análise", "deal_A943980E-0CEC-4B43-8D59-8A99EAAA7DEC", None),
        ("Observações da análise", "deal_638EB051-9E51-46A6-92D8-2CBACB5E266A", None),
    ]),
    ("Análise - Peças", [
        ("Peças", PLOOMES_CAMPO_PECAS, None),
    ]),
    ("Abertura", [
        ("Data de início", "@inicio", "data"),
        ("Tipo de cliente", "@tipo_cliente", None),
        ("Descrição do problema", "deal_40C58B1F-181F-4D37-A90A-05870B3076F3", None),
        ("Número de série", "deal_C15CFF90-33AE-411F-924B-E6F5AAA0B10F", None),
        ("Modelo da carreta (produto)", "deal_A75214B5-297E-4C3A-870B-AD10BEA67135", None),
        ("Quantidade de carretas", "deal_B36E25A2-6EBE-4F21-BE8A-BAF401C699C7", None),
        ("NF da venda", "deal_77EE3AB1-319E-4662-9CD1-4F672381766C", None),
        ("Data de emissão da NF", "deal_8600D458-6632-4BAD-888A-724163554FE9", "data"),
        ("Observações da abertura", "deal_89315559-A573-423F-85A5-F514A0448F73", None),
        ("RNC", "deal_EFDC7DDF-60D8-4ECF-B0E2-A1C10ED09538", None),
    ]),
    ("Dados básicos", [
        ("Valor", "@valor", "moeda"),
        ("Cliente", "@cliente", None),
        ("Cidade", "@cidade", None),
        ("Contato", "@contato", None),
        ("Responsável", "@responsavel", None),
        ("Link do Drive", "deal_38F3B538-F8E2-4B79-A2DE-AEC0F8ED0382", "link"),
    ]),
]

# situação do item pela última inspeção
PENDENTE, REINSPECAO, APROVADO = "pendente", "reinspecao", "aprovado"

# --------------------------------------------------------------------------
# Planilha
# --------------------------------------------------------------------------

def _data_br(valor):
    texto = str(valor or "").strip()
    for formato in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    return None


def _numero_br(valor):
    """'1', '2,5', 'R$ 1.265,49' -> float (0 se não der)."""
    texto = re.sub(r"[^\d,.\-]", "", str(valor or ""))
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return 0.0


def _ler_planilha():
    credenciais = get_google_credentials()
    if credenciais is None:
        raise RuntimeError("Credenciais do Google Sheets não encontradas.")
    gc = gspread.service_account_from_dict(credenciais)
    # bem abaixo do timeout do worker: uma resposta lenta do Google não pode derrubar a tela
    gc.set_timeout((5, 25))
    return gc.open_by_key(SHEET_ID).worksheet(SHEET_TAB).get_all_values()


def ultima_sincronizacao():
    return SincronizacaoGarantia.objects.order_by("-data").first()


def sincronizar_itens_garantia(forcar=False, origem="tela"):
    """Traz para o banco as linhas de GARANTIA da planilha de cargas.

    Retorna (resumo, erro). Sem `forcar`, só lê a planilha se a última
    leitura (gravada no banco, vale para todos os processos) tiver mais de
    INTERVALO_SYNC segundos."""
    if not forcar:
        ultima = ultima_sincronizacao()
        if ultima and timezone.now() - ultima.data < timedelta(seconds=INTERVALO_SYNC):
            return None, None

    try:
        linhas = _ler_planilha()
    except Exception as exc:  # planilha fora do ar não pode derrubar a tela
        logger.warning("Falha ao ler a planilha de garantia: %s", exc)
        return None, f"Não foi possível ler a planilha de cargas: {exc}"

    if not linhas:
        return None, "A planilha de cargas veio vazia."

    cabecalho = [str(h).strip() for h in linhas[0]]
    indice = {nome: i for i, nome in enumerate(cabecalho) if nome}

    def campo(linha, nome):
        i = indice.get(nome)
        return str(linha[i]).strip() if i is not None and i < len(linha) else ""

    if "Carga" not in indice:
        return None, 'A coluna "Carga" não foi encontrada na planilha.'

    encontrados = {}
    for numero_linha, linha in enumerate(linhas[1:], start=2):
        if campo(linha, "Carga").upper() != VALOR_CARGA:
            continue
        pedido = campo(linha, "PED_CHCRIACAO")
        codigo = campo(linha, "PED_RECURSO.CODIGO")
        cod_unico = campo(linha, "COD_UNICO") or f"{pedido}{codigo}"
        if not cod_unico:
            continue
        encontrados[cod_unico] = {
            "pedido": pedido[:30],
            "cliente": campo(linha, "PED_PESSOA.CODIGO")[:120],
            "cidade": campo(linha, "Cidade")[:120],
            "uf": campo(linha, "UF")[:5],
            "codigo": codigo[:60],
            "descricao": campo(linha, "PED_RECURSO.DESCRICAOGENERICA"),
            "classe": campo(linha, "PED_RECURSO.CLASSE.NOME")[:120],
            "quantidade": _numero_br(campo(linha, "PED_QUANTIDADE")),
            "numero_serie": campo(linha, "PED_NUMEROSERIE")[:120],
            "data_emissao": _data_br(campo(linha, "PED_EMISSAO")),
            "data_programacao": _data_br(campo(linha, "PED_PROGRAMACA")),
            "dados": {nome: (linha[i] if i < len(linha) else "") for nome, i in indice.items()},
            "linha_planilha": numero_linha,
            "na_planilha": True,
        }

    novos = atualizados = 0
    with transaction.atomic():
        existentes = {i.cod_unico: i for i in ItemGarantia.objects.filter(cod_unico__in=encontrados)}
        for cod_unico, valores in encontrados.items():
            item = existentes.get(cod_unico)
            if item is None:
                ItemGarantia.objects.create(cod_unico=cod_unico, **valores)
                novos += 1
                continue
            mudou = [k for k, v in valores.items() if getattr(item, k) != v]
            if mudou:
                for k in mudou:
                    setattr(item, k, valores[k])
                item.save(update_fields=mudou + ["atualizado_em"])
                atualizados += 1
        # saiu da planilha (faturado/removido): o item fica, só deixa de constar nela
        ItemGarantia.objects.filter(na_planilha=True).exclude(cod_unico__in=encontrados).update(na_planilha=False)

        SincronizacaoGarantia.objects.create(
            origem=origem, itens_na_planilha=len(encontrados), novos=novos, atualizados=atualizados,
        )

    return {"novos": novos, "atualizados": atualizados, "na_planilha": len(encontrados)}, None



# --------------------------------------------------------------------------
# Ploomes (só leitura: vincula o chamado de garantia à inspeção)
# --------------------------------------------------------------------------

class PloomesIndisponivel(Exception):
    pass


def _texto_odata(texto):
    return str(texto).replace("'", "''")


def buscar_chamados_ploomes(filtro_extra, top=20):
    """Chamados do Funil de Chamados que atendem ao filtro OData, mais
    recentes primeiro. Levanta PloomesIndisponivel em falha de rede/API."""
    chave = getattr(settings, "PLOOMES_USER_KEY", "")
    if not chave:
        raise PloomesIndisponivel("A chave do Ploomes (PLOOMES_USER_KEY) não está configurada.")
    filtro = f"PipelineId eq {PLOOMES_FUNIL_CHAMADOS}"
    if filtro_extra:
        filtro += f" and ({filtro_extra})"
    try:
        resposta = requests.get(
            PLOOMES_DEALS_URL,
            headers={"User-Key": chave},
            params={
                "$filter": filtro,
                "$select": "Id,Title,StatusId,CreateDate",
                "$expand": (
                    "Stage($select=Name),"
                    f"OtherProperties($filter=FieldKey eq '{PLOOMES_CAMPO_PECAS}';$select=FieldKey,BigStringValue)"
                ),
                "$orderby": "CreateDate desc",
                "$top": str(top),
            },
            timeout=(5, 20),
        )
    except requests.RequestException as exc:
        raise PloomesIndisponivel(f"Não foi possível consultar o Ploomes: {exc}") from exc
    if resposta.status_code != 200:
        raise PloomesIndisponivel(f"O Ploomes respondeu {resposta.status_code}: {resposta.text[:200]}")

    chamados = []
    for deal in resposta.json().get("value") or []:
        pecas = next((p.get("BigStringValue") or "" for p in deal.get("OtherProperties") or []), "")
        chamados.append({
            "id": deal["Id"],
            "titulo": deal.get("Title") or f"Chamado {deal['Id']}",
            "etapa": (deal.get("Stage") or {}).get("Name") or "",
            "status": PLOOMES_STATUS.get(deal.get("StatusId"), ""),
            "pecas": pecas,
            "data": (deal.get("CreateDate") or "")[:10],
            "link": f"https://app10.ploomes.com/deal/{deal['Id']}",
        })
    return chamados


def _valor_ploomes(prop):
    if not prop:
        return None
    if prop.get("ObjectValueName"):
        return prop["ObjectValueName"]
    for chave in ("BigStringValue", "StringValue", "DecimalValue", "IntegerValue", "DateTimeValue"):
        if prop.get(chave) not in (None, ""):
            return prop[chave]
    if prop.get("BoolValue") is not None:
        return "Sim" if prop["BoolValue"] else "Não"
    return None


def _formatar_ploomes(valor, formato):
    if valor in (None, ""):
        return ""
    if formato == "moeda":
        try:
            return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except (TypeError, ValueError):
            return str(valor)
    if formato == "data":
        texto = str(valor)[:10]
        try:
            return datetime.strptime(texto, "%Y-%m-%d").strftime("%d/%m/%Y")
        except ValueError:
            return texto
    return str(valor).strip()


def detalhes_chamado_ploomes(deal_id):
    """Chamado do Funil de Chamados com as seções exibidas na inspeção
    (Pedido, Análise, Peças, Abertura, Dados básicos). None se não existir.
    Levanta PloomesIndisponivel em falha de rede/API."""
    chave = getattr(settings, "PLOOMES_USER_KEY", "")
    if not chave:
        raise PloomesIndisponivel("A chave do Ploomes (PLOOMES_USER_KEY) não está configurada.")
    try:
        resposta = requests.get(
            PLOOMES_DEALS_URL,
            headers={"User-Key": chave},
            params={
                "$filter": f"Id eq {int(deal_id)} and PipelineId eq {PLOOMES_FUNIL_CHAMADOS}",
                "$select": "Id,Title,Amount,StartDate,StatusId",
                "$expand": (
                    "OtherProperties,Stage($select=Name),Person($select=Name),Owner($select=Name),"
                    "Contact($select=Name;$expand=City($select=Name;$expand=State($select=Short)),"
                    f"OtherProperties($filter=FieldKey eq '{PLOOMES_CAMPO_TIPO_CLIENTE}'))"
                ),
            },
            timeout=(5, 20),
        )
    except requests.RequestException as exc:
        raise PloomesIndisponivel(f"Não foi possível consultar o Ploomes: {exc}") from exc
    if resposta.status_code != 200:
        raise PloomesIndisponivel(f"O Ploomes respondeu {resposta.status_code}: {resposta.text[:200]}")

    encontrados = resposta.json().get("value") or []
    if not encontrados:
        return None
    deal = encontrados[0]
    props = {p["FieldKey"]: p for p in deal.get("OtherProperties") or []}
    contato = deal.get("Contact") or {}
    cidade = contato.get("City") or {}
    especiais = {
        "@inicio": deal.get("StartDate"),
        "@valor": deal.get("Amount"),
        "@cliente": contato.get("Name"),
        "@cidade": " - ".join(p for p in (cidade.get("Name"), (cidade.get("State") or {}).get("Short")) if p),
        "@contato": (deal.get("Person") or {}).get("Name"),
        "@responsavel": (deal.get("Owner") or {}).get("Name"),
        "@tipo_cliente": next((_valor_ploomes(p) for p in contato.get("OtherProperties") or []), None),
    }

    secoes = []
    for titulo, campos in PLOOMES_SECOES:
        itens = []
        for rotulo, chave_campo, formato in campos:
            bruto = especiais.get(chave_campo) if chave_campo.startswith("@") else _valor_ploomes(props.get(chave_campo))
            valor = _formatar_ploomes(bruto, formato)
            if valor:
                itens.append({"rotulo": rotulo, "valor": valor, "link": formato == "link"})
        if itens:
            secoes.append({"titulo": titulo, "campos": itens})

    return {
        "id": deal["Id"],
        "titulo": deal.get("Title") or f"Chamado {deal['Id']}",
        "etapa": (deal.get("Stage") or {}).get("Name") or "",
        "status": PLOOMES_STATUS.get(deal.get("StatusId"), ""),
        "link": f"https://app10.ploomes.com/deal/{deal['Id']}",
        "secoes": secoes,
    }


@require_GET
def api_detalhes_chamado_ploomes(request, deal_id):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Usuário não autenticado"}, status=401)
    try:
        chamado = detalhes_chamado_ploomes(deal_id)
    except PloomesIndisponivel as exc:
        return JsonResponse({"error": str(exc)}, status=502)
    if not chamado:
        return JsonResponse({"error": "Chamado não encontrado no Funil de Chamados do Ploomes."}, status=404)
    return JsonResponse(chamado)


@require_GET
def api_chamados_ploomes(request):
    """Opções do select "Chamado de garantia": sem texto, os chamados que
    citam a peça do item; com texto, busca por nº do chamado, cliente
    (título) ou peça."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Usuário não autenticado"}, status=401)

    termo = (request.GET.get("q") or "").strip()
    item = ItemGarantia.objects.filter(pk=request.GET.get("item_id")).first() if str(request.GET.get("item_id") or "").isdigit() else None

    pecas = f"OtherProperties/any(p: p/FieldKey eq '{PLOOMES_CAMPO_PECAS}' and contains(p/BigStringValue,'{{}}'))"
    if termo:
        t = _texto_odata(termo)
        partes = [f"contains(Title,'{t}')", pecas.format(t)]
        if termo.isdigit():
            partes.insert(0, f"Id eq {int(termo)}")
        filtro = " or ".join(partes)
    elif item and item.codigo:
        filtro = pecas.format(_texto_odata(item.codigo))
    else:
        filtro = ""

    try:
        chamados = buscar_chamados_ploomes(filtro)
    except PloomesIndisponivel as exc:
        logger.warning("Busca de chamados no Ploomes falhou: %s", exc)
        return JsonResponse({"error": str(exc)}, status=502)

    return JsonResponse({"chamados": chamados, "sugestao_por_peca": bool(not termo and item and item.codigo)})


# --------------------------------------------------------------------------
# Telas / API
# --------------------------------------------------------------------------

def _tipo_acesso(request):
    profile = getattr(request.user, "profile", None) if request.user.is_authenticated else None
    return getattr(profile, "tipo_acesso", None)


def _nome(profile):
    if not profile:
        return ""
    return profile.user.get_full_name() or profile.user.username


def _perfil_logado(request):
    if not request.user.is_authenticated:
        return None
    return Profile.objects.filter(user=request.user).select_related("user").first()


def inspecao_garantia(request):
    tipo_acesso = _tipo_acesso(request)
    return render(request, "inspecao_garantia.html", {
        "tipo_acesso": tipo_acesso,
        "pode_desfazer": tipo_acesso in ACESSOS_DESFAZER,
        # quem inspeciona é sempre quem está logado (não dá para trocar)
        "inspetor_nome": _nome(_perfil_logado(request)) or request.user.get_username(),
        "hoje": timezone.localdate().isoformat(),
    })


def _qtd_inteira(item):
    return max(int(round(item.quantidade or 0)), 1)


def _com_situacao(queryset):
    """Anota o nº e o resultado da última inspeção de cada item."""
    ultima = InspecaoGarantia.objects.filter(item=OuterRef("pk")).order_by("-numero")
    return queryset.annotate(
        total_inspecoes=Coalesce(Subquery(ultima.values("numero")[:1]), Value(0), output_field=IntegerField()),
        ultimo_aprovado=Subquery(ultima.values("aprovado")[:1]),
        ultima_data=Subquery(ultima.values("data_inspecao")[:1]),
    )


def _situacao(item):
    if not item.total_inspecoes:
        return PENDENTE
    return APROVADO if item.ultimo_aprovado else REINSPECAO


def _inspecao_json(inspecao):
    return {
        "id": inspecao.id,
        "numero": inspecao.numero,
        "data_inspecao": inspecao.data_inspecao.strftime("%d/%m/%Y"),
        "numero_garantia": inspecao.numero_garantia,
        "garantia_titulo": inspecao.garantia_titulo,
        "garantia_etapa": inspecao.garantia_etapa,
        "garantia_dados": inspecao.garantia_dados or {},
        "link_ploomes": inspecao.link_ploomes,
        "verificado": inspecao.verificado,
        "aprovado": inspecao.aprovado,
        "inspetor": _nome(inspecao.inspetor),
        "registrado_por": _nome(inspecao.registrado_por),
        "registrado_em": timezone.localtime(inspecao.registrado_em).strftime("%d/%m/%Y %H:%M"),
        "fotos": [f.arquivo.url for f in inspecao.fotos.all() if f.arquivo],
    }


def _item_json(item):
    return {
        "id": item.id,
        "pedido": item.pedido,
        "cliente": item.cliente,
        "cidade_uf": " - ".join(p for p in (item.cidade, item.uf) if p),
        "codigo": item.codigo,
        "descricao": item.descricao,
        "classe": item.classe,
        "quantidade": _qtd_inteira(item),
        "numero_serie": item.numero_serie,
        "data_emissao": item.data_emissao.strftime("%d/%m/%Y") if item.data_emissao else "",
        "data_programacao": item.data_programacao.strftime("%d/%m/%Y") if item.data_programacao else "",
        "na_planilha": item.na_planilha,
    }


@require_GET
def api_itens_garantia(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Usuário não autenticado"}, status=401)

    resumo, erro_sync = sincronizar_itens_garantia(forcar=request.GET.get("atualizar") == "1")

    aba = request.GET.get("aba", PENDENTE)
    if aba not in (PENDENTE, REINSPECAO, APROVADO):
        aba = PENDENTE
    pesquisa = request.GET.get("pesquisar", "").strip()
    try:
        pagina = int(request.GET.get("pagina", 1))
    except ValueError:
        pagina = 1

    base = _com_situacao(ItemGarantia.objects.all())
    filtros_aba = {
        PENDENTE: Q(total_inspecoes=0),
        REINSPECAO: Q(total_inspecoes__gt=0, ultimo_aprovado=False),
        APROVADO: Q(total_inspecoes__gt=0, ultimo_aprovado=True),
    }
    contadores = {nome: base.filter(filtro).count() for nome, filtro in filtros_aba.items()}
    queryset = base.filter(filtros_aba[aba])

    if pesquisa:
        filtro = (
            Q(pedido__icontains=pesquisa) | Q(codigo__icontains=pesquisa)
            | Q(descricao__icontains=pesquisa) | Q(cliente__icontains=pesquisa)
            | Q(cidade__icontains=pesquisa) | Q(inspecoes__numero_garantia__icontains=pesquisa)
            | Q(inspecoes__garantia_titulo__icontains=pesquisa)
        )
        queryset = queryset.filter(pk__in=ItemGarantia.objects.filter(filtro).values("pk"))

    data_inicio = request.GET.get("data_inicio")
    data_fim = request.GET.get("data_fim")
    campo_data = "data_programacao" if aba == PENDENTE else "ultima_data"
    try:
        if data_inicio:
            queryset = queryset.filter(**{f"{campo_data}__gte": datetime.strptime(data_inicio, "%Y-%m-%d").date()})
        if data_fim:
            queryset = queryset.filter(**{f"{campo_data}__lte": datetime.strptime(data_fim, "%Y-%m-%d").date()})
    except ValueError:
        pass

    if aba == PENDENTE:
        queryset = queryset.order_by("-na_planilha", "data_programacao", "id")
    elif aba == REINSPECAO:
        queryset = queryset.order_by("ultima_data", "id")  # reprovado há mais tempo primeiro
    else:
        queryset = queryset.order_by("-ultima_data", "-id")

    paginador = Paginator(queryset, 12)
    pagina_obj = paginador.get_page(pagina)

    ultimas = {}
    ids = [item.id for item in pagina_obj]
    if aba != PENDENTE and ids:
        for inspecao in (
            InspecaoGarantia.objects.filter(item_id__in=ids).select_related("inspetor__user")
            .order_by("item_id", "-numero").distinct("item_id")
        ):
            ultimas[inspecao.item_id] = inspecao

    dados = []
    for item in pagina_obj:
        registro = _item_json(item)
        registro["situacao"] = _situacao(item)
        registro["total_inspecoes"] = item.total_inspecoes
        ultima = ultimas.get(item.id)
        if ultima:
            registro["ultima_inspecao"] = {
                "numero": ultima.numero,
                "data_inspecao": ultima.data_inspecao.strftime("%d/%m/%Y"),
                "numero_garantia": ultima.numero_garantia,
                "garantia_titulo": ultima.garantia_titulo,
                "link_ploomes": ultima.link_ploomes,
                "inspetor": _nome(ultima.inspetor),
                "aprovado": ultima.aprovado,
            }
        dados.append(registro)

    ultima_sync = ultima_sincronizacao()
    return JsonResponse({
        "dados": dados,
        "contadores": contadores,
        "total_filtrado": paginador.count,
        "pagina_atual": pagina_obj.number,
        "total_paginas": paginador.num_pages,
        "sincronizacao": resumo,
        "erro_sincronizacao": erro_sync,
        "ultima_sincronizacao": {
            "data": timezone.localtime(ultima_sync.data).strftime("%d/%m/%Y às %H:%M"),
            "origem": ultima_sync.get_origem_display(),
            "itens_na_planilha": ultima_sync.itens_na_planilha,
        } if ultima_sync else None,
    })


@require_GET
def api_detalhes_garantia(request, item_id):
    """Item + histórico de todas as inspeções (da mais recente para a primeira)."""
    item = get_object_or_404(_com_situacao(ItemGarantia.objects.all()), pk=item_id)
    inspecoes = (
        InspecaoGarantia.objects.filter(item=item)
        .select_related("inspetor__user", "registrado_por__user")
        .prefetch_related("fotos").order_by("-numero")
    )
    return JsonResponse({
        "item": {**_item_json(item), "situacao": _situacao(item), "total_inspecoes": item.total_inspecoes},
        "inspecoes": [_inspecao_json(i) for i in inspecoes],
    })


@require_POST
def api_inspecionar_garantia(request):
    """Registra uma inspeção (multipart): item_id, data_inspecao (AAAA-MM-DD),
    numero_garantia (Id do chamado no Ploomes), garantia_titulo, verificado,
    aprovado ('sim' | 'nao') e fotos. O inspetor é sempre o usuário logado.
    Item aprovado não recebe nova inspeção; reprovado recebe a próxima
    (2ª, 3ª, ...)."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Usuário não autenticado"}, status=401)

    inspetor = _perfil_logado(request)
    if not inspetor:
        return JsonResponse({"error": "Seu usuário não tem perfil cadastrado para registrar inspeções."}, status=403)

    numero_garantia = (request.POST.get("numero_garantia") or "").strip()
    verificado = (request.POST.get("verificado") or "").strip()
    aprovado = request.POST.get("aprovado")

    if not numero_garantia.isdigit():
        return JsonResponse({"error": "Escolha o chamado de garantia do Ploomes."}, status=400)
    try:
        data_inspecao = datetime.strptime(request.POST.get("data_inspecao") or "", "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({"error": "Informe a data da inspeção."}, status=400)
    if data_inspecao > timezone.localdate():
        return JsonResponse({"error": "A data da inspeção não pode ser no futuro."}, status=400)
    if not verificado:
        return JsonResponse({"error": "Descreva o que foi verificado na inspeção."}, status=400)
    if aprovado not in ("sim", "nao"):
        return JsonResponse({"error": "Informe se o item está aprovado ou não."}, status=400)

    # confere o chamado no Ploomes e guarda título/etapa de lá; se o Ploomes
    # estiver fora do ar, não trava a inspeção: fica o título que a tela mandou
    garantia_titulo = (request.POST.get("garantia_titulo") or "").strip()[:255]
    garantia_etapa = (request.POST.get("garantia_etapa") or "").strip()[:120]
    garantia_dados = {}
    try:
        chamado = detalhes_chamado_ploomes(int(numero_garantia))
    except PloomesIndisponivel as exc:
        logger.warning("Chamado %s não conferido no Ploomes: %s", numero_garantia, exc)
    else:
        if not chamado:
            return JsonResponse({"error": "Chamado não encontrado no Funil de Chamados do Ploomes."}, status=400)
        garantia_titulo = chamado["titulo"][:255]
        garantia_etapa = chamado["etapa"][:120]
        garantia_dados = {"status": chamado["status"], "secoes": chamado["secoes"]}

    with transaction.atomic():
        # trava o item: duas inspeções salvas ao mesmo tempo não pegam o mesmo número
        item = get_object_or_404(ItemGarantia.objects.select_for_update(), pk=request.POST.get("item_id"))
        ultima = InspecaoGarantia.objects.filter(item=item).order_by("-numero").first()
        if ultima and ultima.aprovado:
            return JsonResponse({"error": "Este item já está aprovado. Atualize a página."}, status=409)

        inspecao = InspecaoGarantia.objects.create(
            item=item,
            numero=(ultima.numero + 1) if ultima else 1,
            data_inspecao=data_inspecao,
            numero_garantia=numero_garantia,
            garantia_titulo=garantia_titulo,
            garantia_etapa=garantia_etapa,
            garantia_dados=garantia_dados,
            verificado=verificado,
            aprovado=(aprovado == "sim"),
            inspetor=inspetor,
            registrado_por=inspetor,
        )
        for arquivo in request.FILES.getlist("fotos"):
            FotoInspecaoGarantia.objects.create(inspecao=inspecao, arquivo=arquivo)

    return JsonResponse({"success": True, "numero": inspecao.numero, "aprovado": inspecao.aprovado})


@require_POST
def api_desfazer_garantia(request):
    """Apaga a última inspeção do item (a anterior volta a valer).
    Só admin, supervisor ou PCP."""
    if _tipo_acesso(request) not in ACESSOS_DESFAZER:
        return JsonResponse({"error": "Apenas administradores, supervisores e PCP podem desfazer inspeções."}, status=403)

    try:
        corpo = json.loads(request.body or "{}")
    except ValueError:
        corpo = {}

    with transaction.atomic():
        item = get_object_or_404(ItemGarantia.objects.select_for_update(), pk=corpo.get("item_id"))
        ultima = InspecaoGarantia.objects.filter(item=item).order_by("-numero").first()
        if not ultima:
            return JsonResponse({"error": "Nenhuma inspeção encontrada para este item."}, status=404)
        numero = ultima.numero
        ultima.delete()  # fotos saem em cascata
    return JsonResponse({"success": True, "numero": numero})
