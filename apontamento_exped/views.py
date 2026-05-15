from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.views.decorators.http import require_http_methods
from django.db.models import Sum, Exists, OuterRef, Count, Q, Prefetch, F, Value
from django.db.models.functions import Coalesce, Replace, Trim, Upper
from django.utils.timezone import localtime

from cargas.utils import get_data_from_sheets,tratando_dados
from cargas.services import listar_itens_liberados_expedicao
from .models import Carga,ItemPacote,Pacote,VerificacaoPacote, CarretaCarga, ImagemPacote, PendenciasPacote, ItemPacote, FornecedorItemCarga
from .utils import chamar_impressora, buscar_conjuntos_carreta, limpar_cor, chamar_impressora_qrcode
from cadastro.models import CarretasExplodidas

import json
import boto3
import re
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo
from datetime import datetime

# === Helpers de normalização ===

SIGLA_POR_COR = {
    'amarelo': 'AV',
    'laranja': 'LC',
    'cinza': 'CO',
    'azul': 'AN',
    'verde': 'VJ',
    'preto': 'PR',
    'vermelho': 'VM',
    'cinza escuro': 'CE',
    # adicione outras se precisar...
}
SIGLAS_VALIDAS = {v.upper() for v in SIGLA_POR_COR.values()}

# === Helpers de normalização ===

_desc_prefix_re  = re.compile(r'^\s*[^-]+-\s*')   # remove "QUALQUER_COISA - " do início
_spaces_re       = re.compile(r'\s+')             # normaliza espaços

def strip_color_suffix(code: str) -> str:
    """
    Remove o sufixo de cor SOMENTE se for uma sigla conhecida (AV, LC, CO, ...).
    Ex.: 033594LC -> 033594 ; 032074 -> 032074 (inalterado)
    """
    if not code:
        return ''
    s = str(code).strip().upper()
    if len(s) >= 3:
        sufixo2 = s[-2:]
        if sufixo2 in SIGLAS_VALIDAS:
            return s[:-2]
    return s

def normalize_carreta_text(value: str) -> str:
    if not value:
        return ''
    s = strip_color_suffix(value)
    s = _spaces_re.sub(' ', s)
    return s.strip().upper()

def normalized_spaces_expr(field_name: str):
    expr = F(field_name)
    for _ in range(4):
        expr = Replace(expr, Value('  '), Value(' '))
    return Upper(Trim(expr))

def clean_description(desc: str) -> str:
    if not desc:
        return ''
    s = str(desc)
    s = _desc_prefix_re.sub('', s)    # tira "CÓDIGO - " do começo
    s = _spaces_re.sub(' ', s)        # colapsa espaços
    return s.strip()

def safe_int(v, default=0) -> int:
    if v is None:
        return default
    try:
        return int(str(v).strip().split('.')[0])
    except Exception:
        return default

def parse_total(v):
    if v is None:
        return 0
    s = str(v).strip()
    if not s:
        return 0
    # Remove separador de milhar e normaliza decimal pt-BR -> en-US
    s = s.replace('.', '').replace(',', '.')
    try:
        return int(Decimal(s))  # garante 1.000 -> 1000,  "2,0" -> 2
    except (InvalidOperation, ValueError):
        return 0

# Tipos especiais de peças que exigem fornecedor informado antes de avançar da verificação
_TIPOS_ESPECIAIS = ['Pneu', 'Cilindro', 'Roda']
_PROCESSOS_PENDENCIA_CARRETA = ['PINTAR', 'COMPONENTE EXTRA']

def _detectar_codigos_especiais_da_carga(carga_id):
    """
    Retorna dict {tipo: [{codigo, descricao}, ...]} com os códigos únicos
    de peças especiais presentes nos itens da carga.
    """
    itens = ItemPacote.objects.filter(
        pacote__carga_id=carga_id
    ).select_related('codigo')

    # tipo -> {codigo: descricao}
    codigos = {tipo: {} for tipo in _TIPOS_ESPECIAIS}
    for item in itens:
        cod_obj = getattr(item, 'codigo', None)
        codigo = (getattr(cod_obj, 'codigo', '') or item.codigo_informado or '').strip()
        descricao = (getattr(cod_obj, 'descricao', '') or item.descricao_informada or '').strip()
        texto = f"{codigo} {descricao}".upper()
        for tipo in _TIPOS_ESPECIAIS:
            if tipo.upper() in texto and codigo:
                codigos[tipo][codigo] = descricao

    return {
        tipo: [{'codigo': c, 'descricao': d} for c, d in cod_dict.items()]
        for tipo, cod_dict in codigos.items()
        if cod_dict
    }


def _buscar_componentes_por_carreta(lista_carretas):
    carretas_normalizadas = sorted({
        normalize_carreta_text(carreta)
        for carreta in (lista_carretas or [])
        if normalize_carreta_text(carreta)
    })

    if not carretas_normalizadas:
        return {}

    qs = (
        CarretasExplodidas.objects
        .annotate(
            carreta_normalizada=normalized_spaces_expr('carreta'),
        )
        .filter(
            carreta_normalizada__in=carretas_normalizadas,
            primeiro_processo__in=_PROCESSOS_PENDENCIA_CARRETA,
        )
        .order_by('carreta_normalizada', 'codigo_peca')
        .values('carreta', 'codigo_peca', 'descricao_peca', 'total_peca')
    )
    grupos_por_carreta = defaultdict(list)
    chaves_vistas = set()
    for row in qs:
        chave = (
            normalize_carreta_text(row.get('carreta') or ''),
            strip_color_suffix(row.get('codigo_peca') or ''),
        )
        if chave in chaves_vistas:
            continue
        chaves_vistas.add(chave)

        total_peca = parse_total(row.get('total_peca'))
        if total_peca <= 0:
            continue

        carreta_key = chave[0]
        if not carreta_key:
            continue

        grupos_por_carreta[carreta_key].append({
            'codigo_base': chave[1],
            'descricao_limpa': clean_description(row.get('descricao_peca') or ''),
            'total_por_carreta': total_peca,
        })

    return grupos_por_carreta


def _criar_pendencias_para_carretas_carga(carretas_carga, somente_sem_pendencias=False):
    carretas_carga = list(carretas_carga or [])
    if not carretas_carga:
        return {
            'carretas_processadas': 0,
            'pendencias_criadas': 0,
            'carretas_sem_componentes': [],
            'carretas_sem_pendencias': [],
        }

    if somente_sem_pendencias:
        ids = [carreta.id for carreta in carretas_carga]
        ids_com_pendencia = set(
            PendenciasPacote.objects
            .filter(carreta_carga_id__in=ids)
            .values_list('carreta_carga_id', flat=True)
            .distinct()
        )
        carretas_sem_pendencias = [c for c in carretas_carga if c.id not in ids_com_pendencia]
    else:
        carretas_sem_pendencias = carretas_carga

    grupos_por_carreta = _buscar_componentes_por_carreta([c.carreta for c in carretas_sem_pendencias])

    total_pendencias = 0
    carretas_sem_componentes = []

    for carreta_carga in carretas_sem_pendencias:
        carreta_limpa = normalize_carreta_text(carreta_carga.carreta)
        quantidade_carreta = safe_int(carreta_carga.quantidade, default=0)

        if not carreta_limpa or quantidade_carreta <= 0:
            continue

        componentes = grupos_por_carreta.get(carreta_limpa, [])
        if not componentes:
            carretas_sem_componentes.append(carreta_limpa)
            continue

        pendencias_to_create = []
        for comp in componentes:
            qt_necessaria = quantidade_carreta * comp['total_por_carreta']
            if qt_necessaria <= 0:
                continue

            pendencias_to_create.append(PendenciasPacote(
                carreta_carga=carreta_carga,
                codigo=comp['codigo_base'],
                descricao=comp['descricao_limpa'],
                qt_necessaria=qt_necessaria,
            ))

        if pendencias_to_create:
            PendenciasPacote.objects.bulk_create(pendencias_to_create)
            total_pendencias += len(pendencias_to_create)

    return {
        'carretas_processadas': len(carretas_sem_pendencias),
        'pendencias_criadas': total_pendencias,
        'carretas_sem_componentes': sorted(set(carretas_sem_componentes)),
        'carretas_sem_pendencias': sorted({
            normalize_carreta_text(c.carreta)
            for c in carretas_sem_pendencias
            if normalize_carreta_text(c.carreta)
        }),
    }


# =========== Template inicial ==========

def planejamento(request):

    return render(request, 'apontamento_exped/planejamento.html')

def relatorios(request):
    data_str = (request.GET.get('data') or '').strip()
    return render(request, 'apontamento_exped/relatorios.html', {'data_str': data_str})




def relatorios_clientes_api(request):
    data_str = (request.GET.get('data') or '').strip()
    if not data_str:
        return JsonResponse({'error': 'Data n?o informada.'}, status=400)
    try:
        data_consulta = datetime.strptime(data_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'error': 'Data invalida. Use o formato AAAA-MM-DD.'}, status=400)

    clientes = (
        Carga.objects
        .filter(data_carga=data_consulta)
        .values_list('cliente', flat=True)
        .distinct()
        .order_by('cliente')
    )
    return JsonResponse({'clientes': list(clientes)})

def relatorios_impressao(request):
    data_str = (request.GET.get('data') or '').strip()
    cliente = (request.GET.get('cliente') or '').strip()
    data_consulta = None
    erro = None
    carretas_cliente = []

    if data_str:
        try:
            data_consulta = datetime.strptime(data_str, '%Y-%m-%d').date()
        except ValueError:
            erro = 'Data inválida. Use o formato AAAA-MM-DD.'

    cargas = []
    if data_consulta:
        pacotes_qs = (
            Pacote.objects
            .prefetch_related(
                Prefetch(
                    'itens',
                    queryset=ItemPacote.objects.select_related('codigo')
                ),
                Prefetch(
                    'pacote_imagem',
                    queryset=ImagemPacote.objects.all()
                )
            )
            .order_by('nome', 'id')
        )

        cargas_qs = Carga.objects.filter(data_carga=data_consulta)
        cargas = cargas_qs
        if cliente:
            cargas = cargas.filter(cliente=cliente)

        cargas = (
            cargas
            .prefetch_related(
                Prefetch('pacotes', queryset=pacotes_qs),
                Prefetch('fornecedores_itens', queryset=FornecedorItemCarga.objects.all())
            )
            .order_by('cliente', 'carga', 'id')
        )

        if cliente:
            carretas_agrupadas = (
                CarretaCarga.objects
                .filter(carga__data_carga=data_consulta, carga__cliente=cliente)
                .values('carreta')
                .annotate(quantidade=Coalesce(Sum('quantidade'), 0))
                .order_by('carreta')
            )

            carretas_cliente = [
                {'codigo': item['carreta'], 'quantidade': item['quantidade']}
                for item in carretas_agrupadas
            ]

    # fornecedores_map: {carga_id: {codigo: fornecedor}}
    fornecedores_map = {}
    if data_consulta:
        for carga_obj in cargas:
            fdict = {}
            for f in carga_obj.fornecedores_itens.all():
                fdict[f.codigo] = f.fornecedor
            fornecedores_map[carga_obj.id] = fdict

            # Facilita o uso no template de impressão: cada item já sai com o
            # fornecedor resolvido pelo código da peça.
            for pacote in carga_obj.pacotes.all():
                for item in pacote.itens.all():
                    codigo_item = (
                        (getattr(getattr(item, 'codigo', None), 'codigo', None))
                        or item.codigo_informado
                        or ''
                    ).strip()
                    item.fornecedor_relatorio = fdict.get(codigo_item, '')

    context = {
        'data_str': data_str,
        'data_consulta': data_consulta,
        'erro': erro,
        'carretas_cliente': carretas_cliente,
        'cargas': cargas,
        'report_ready': bool(data_str),
        'cliente': cliente,
        'fornecedores_map': fornecedores_map,
    }
    return render(request, 'apontamento_exped/relatorios_impressao.html', context)

# =========== utils ==============

def cor_recurso(recurso):
    if 'VM' in recurso:
        return 'vermelho'
    elif 'AN' in recurso:
        return 'azul'
    elif 'VJ' in recurso:
        return 'verde'
    elif 'LJ' in recurso:
        return 'laranja'
    elif 'AV' in recurso:
        return 'amarelo'
    elif 'CO' in recurso:
        return 'cinza'
    else:
        return 'laranja'

# ============ apis ===============

def cargas(request):
    data_carga = request.GET.get('data_carga')
    if not data_carga:
        return JsonResponse([], safe=False)

    try:
        data_carga_obj = datetime.strptime(data_carga, "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({'erro': 'Data invalida. Use AAAA-MM-DD.'}, status=400)

    itens = listar_itens_liberados_expedicao(data_carga_obj)
    cargas = sorted({item['carga'] for item in itens if item.get('carga')})

    return JsonResponse(cargas, safe=False)

def clientes(request):
    data_carga = request.GET.get('data_carga')
    carga = request.GET.get('carga')
    if not data_carga or not carga:
        return JsonResponse([], safe=False)

    try:
        data_carga_obj = datetime.strptime(data_carga, "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({'erro': 'Data invalida. Use AAAA-MM-DD.'}, status=400)

    itens = listar_itens_liberados_expedicao(data_carga_obj, carga_nome=carga)
    clientes = sorted(
        {
            (item.get('cliente') or item.get('cliente_codigo') or '').strip()
            for item in itens
            if (item.get('cliente') or item.get('cliente_codigo'))
        }
    )

    return JsonResponse(clientes, safe=False)

def carretas(request):
    cliente = request.GET.get('cliente')
    data_carga = request.GET.get('data_carga')
    carga = request.GET.get('carga')

    if not data_carga or not cliente or not carga:
        return JsonResponse([], safe=False)

    try:
        data_carga_obj = datetime.strptime(data_carga, "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({'erro': 'Data invalida. Use AAAA-MM-DD.'}, status=400)

    itens = listar_itens_liberados_expedicao(
        data_carga_obj,
        carga_nome=carga,
        cliente_codigo=cliente,
    )

    carretas = [
        {
            'Recurso': item['codigo_recurso'],
            'Qtde': item['quantidade'],
            'PED_NUMEROSERIE': item['numero_serie'],
            'cor': cor_recurso(item['codigo_recurso']),
        }
        for item in itens
    ]

    return JsonResponse(carretas, safe=False)

@csrf_exempt
@transaction.atomic
def criar_caixa(request):
    if request.method != 'POST':
        return JsonResponse({'erro': 'Metodo nao permitido'}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'erro': 'JSON invalido'}, status=400)

    data_carga  = data.get('data_carga')
    carga_nome  = data.get('carga_nome')
    cliente_nome = (data.get('cliente_codigo') or data.get('cliente') or '').strip()
    observacoes = data.get('observacoes')
    itens       = data.get('itens', [])

    if not itens:
        return JsonResponse({'erro': 'Nenhum item informado'}, status=400)

    if not cliente_nome:
        return JsonResponse({'erro': 'Cliente não informado'}, status=400)

    hora_atual = timezone.now().strftime("%H%M%S")
    carga = Carga.objects.create(
        nome=f"{carga_nome}_{cliente_nome}_{str(data_carga).replace('-', '')}_{hora_atual}",
        carga=carga_nome,
        data_carga=data_carga,
        cliente=cliente_nome,
        obs_pacote=observacoes
    )

    created_carretas = 0
    carretas_carga_criadas = []

    for item in itens:
        carreta_raw        = item.get('codigo_peca', '')
        quantidade_carreta = safe_int(item.get('quantidade'), default=0)
        cor                = item.get('cor')

        carreta_limpa = normalize_carreta_text(carreta_raw)

        if not carreta_limpa or quantidade_carreta <= 0:
            continue

        carreta_carga_object = CarretaCarga.objects.create(
            carga=carga,
            carreta=carreta_limpa,
            quantidade=quantidade_carreta,
            cor=cor
        )
        created_carretas += 1
        carretas_carga_criadas.append(carreta_carga_object)

    if not carretas_carga_criadas:
        return JsonResponse({'erro': 'Nenhuma carreta valida nos itens'}, status=400)

    resultado_pendencias = _criar_pendencias_para_carretas_carga(carretas_carga_criadas)

    return JsonResponse({
        'mensagem': 'Caixa criada com sucesso!',
        'id': carga.id,
        'carretas_criadas': created_carretas,
        'pendencias_criadas': resultado_pendencias['pendencias_criadas'],
        'stage': 'verificacao',
        'cliente': cliente_nome,
        'data_carga': data_carga,
        'carga': carga_nome,
        'carretas_sem_componentes': resultado_pendencias['carretas_sem_componentes'],

    }, status=201)

def buscar_cargas(request):
    from django.utils import timezone
    from datetime import timedelta

    # Cargas ativas (planejamento/verificação) + despachadas recentes (últimos 30 dias)
    # O kanban já limita despachadas a 5 no frontend, mas sem filtro aqui todas são processadas
    corte_despachado = timezone.now() - timedelta(days=30)
    cargas = list(
        Carga.objects
        .exclude(stage='despachado', data_criacao__lt=corte_despachado)
        .values('id', 'nome', 'carga', 'data_carga', 'cliente', 'obs_pacote', 'stage', 'data_criacao')
    )

    if not cargas:
        return JsonResponse([], safe=False)

    carga_ids = [c['id'] for c in cargas]

    # 1 query: total de pacotes por carga
    total_pacotes_map = {
        r['carga_id']: r['total']
        for r in Pacote.objects
            .filter(carga_id__in=carga_ids)
            .values('carga_id')
            .annotate(total=Count('id'))
    }

    # 1 query: pacotes com foto de verificação por carga
    foto_verif_map = {
        r['carga_id']: r['total']
        for r in Pacote.objects
            .filter(carga_id__in=carga_ids, pacote_imagem__stage='verificacao')
            .values('carga_id')
            .annotate(total=Count('id', distinct=True))
    }

    # 1 query: pacotes com foto de despachado por carga
    foto_desp_map = {
        r['carga_id']: r['total']
        for r in Pacote.objects
            .filter(carga_id__in=carga_ids, pacote_imagem__stage='despachado')
            .values('carga_id')
            .annotate(total=Count('id', distinct=True))
    }

    # 1 query: total de itens pendentes por carga
    pendente_map = {
        r['carreta_carga__carga_id']: r['total']
        for r in PendenciasPacote.objects
            .filter(carreta_carga__carga_id__in=carga_ids, qt_necessaria__gt=0)
            .values('carreta_carga__carga_id')
            .annotate(total=Sum('qt_necessaria'))
    }

    # Detectar fornecedores pendentes (apenas cargas em verificação)
    verificacao_ids = [c['id'] for c in cargas if c['stage'] == 'verificacao']

    # codigos_por_carga: carga_id -> {tipo -> set of codigos}
    codigos_por_carga = defaultdict(lambda: defaultdict(set))
    if verificacao_ids:
        items_verif = ItemPacote.objects.filter(
            pacote__carga_id__in=verificacao_ids
        ).values('pacote__carga_id', 'codigo__codigo', 'codigo__descricao',
                 'codigo_informado', 'descricao_informada')

        for row in items_verif:
            codigo = (row['codigo__codigo'] or row['codigo_informado'] or '').strip()
            descricao = (row['codigo__descricao'] or row['descricao_informada'] or '').strip()
            texto = f"{codigo} {descricao}".upper()
            cid_row = row['pacote__carga_id']
            for tipo in _TIPOS_ESPECIAIS:
                if tipo.upper() in texto and codigo:
                    codigos_por_carga[cid_row][tipo].add(codigo)

        # fornecedores já salvos para essas cargas: carga_id -> {(tipo, codigo) -> fornecedor}
        forn_map = defaultdict(dict)
        for f in FornecedorItemCarga.objects.filter(carga_id__in=verificacao_ids):
            forn_map[f.carga_id][(f.tipo, f.codigo)] = f.fornecedor
    else:
        forn_map = {}

    for carga in cargas:
        cid = carga['id']
        total_pac = total_pacotes_map.get(cid, 0)
        foto_verif = foto_verif_map.get(cid, 0)
        foto_desp = foto_desp_map.get(cid, 0)
        pendente = pendente_map.get(cid, 0)

        carga['todos_pacotes_tem_foto_verificacao'] = (
            total_pac > 0 and total_pac == foto_verif and pendente == 0
        )
        carga['todos_pacotes_tem_foto_despachado'] = (
            total_pac > 0 and total_pac == foto_desp
        )
        carga['total_pendente'] = pendente

        # Badge de fornecedores pendentes
        if carga['stage'] == 'verificacao':
            codigos = codigos_por_carga.get(cid, {})
            faltando = any(
                not forn_map.get(cid, {}).get((tipo, cod), '').strip()
                for tipo, cods in codigos.items()
                for cod in cods
            )
            carga['fornecedores_pendentes'] = faltando
        else:
            carga['fornecedores_pendentes'] = False

    return JsonResponse(cargas, safe=False)

@csrf_exempt
@require_http_methods(["DELETE", "POST"])
def excluir_carga(request, id):
    """
    Remove o carregamento e todas as relaÇõÇœes em cascata (carretas, pacotes, itens, imagens).
    Aceita DELETE ou POST para compatibilidade com clientes que não enviam DELETE.
    """

    # Permite apenas usuario PCP ou ADMIN
    if not request.user.is_authenticated or not hasattr(request.user, 'profile') or request.user.profile.tipo_acesso != 'pcp' or request.user.profile.tipo_acesso == 'admin':
        return JsonResponse({'erro': 'Acesso negado: apenas PCP pode excluir carregamentos.'}, status=403)

    carga = get_object_or_404(Carga, id=id)
    carga.delete()
    return JsonResponse({'mensagem': 'Carregamento excluÍdo com sucesso.'}, status=200)

@csrf_exempt
@require_http_methods(["DELETE", "POST"])
def deletar_pacote(request, id):
    """
    Deleta o pacote e devolve as quantidades dos itens para as pendências.
    Permitido apenas se a carga não estiver despachada.
    """
    pacote = get_object_or_404(Pacote.objects.select_related('carga'), id=id)
    if pacote.carga.stage == 'despachado':
        return JsonResponse({'erro': 'Não é permitido excluir pacotes despachados.'}, status=400)

    itens = list(ItemPacote.objects.filter(pacote=pacote).select_related('codigo'))

    with transaction.atomic():
        for item in itens:
            pend = item.codigo
            if pend:
                pend.qt_necessaria = (pend.qt_necessaria or 0) + (item.quantidade or 0)
                pend.save(update_fields=['qt_necessaria'])
        pacote.delete()

    return JsonResponse({
        'mensagem': 'Pacote excluído com sucesso.',
        'carga_id': pacote.carga_id,
        'stage': pacote.carga.stage,
    }, status=200)

@csrf_exempt
@require_http_methods(["POST"])
def atualizar_quantidade_item(request, item_id):
    """
    Atualiza a quantidade de um item dentro do pacote.
    - Somente permitido nos estÃ¡gios planejamento e verificacao.
    - Se aumentar, verifica se hÃ¡ saldo pendente disponível.
    - Se diminuir, devolve a diferenÃ§a para a pendÃªncia.
    """
    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({'erro': 'JSON invÃ¡lido'}, status=400)

    nova_qt = data.get('quantidade')
    try:
        nova_qt = int(nova_qt)
    except (TypeError, ValueError):
        return JsonResponse({'erro': 'Quantidade invÃ¡lida.'}, status=400)

    if nova_qt <= 0:
        return JsonResponse({'erro': 'Quantidade deve ser maior que zero.'}, status=400)

    item = get_object_or_404(
        ItemPacote.objects.select_related('codigo', 'pacote__carga'),
        id=item_id
    )
    carga = item.pacote.carga
    if carga.stage not in ('planejamento', 'verificacao'):
        return JsonResponse({'erro': 'AlteraÃ§Ã£o permitida apenas em planejamento ou verificaÃ§Ã£o.'}, status=400)

    pend = getattr(item, 'codigo', None)
    atual = int(item.quantidade or 0)
    delta = nova_qt - atual

    with transaction.atomic():
        if pend and delta > 0:
            disponivel = int(pend.qt_necessaria or 0)
            if disponivel <= 0:
                return JsonResponse({'erro': 'Este item não possui saldo pendente para aumentar quantidade.'}, status=400)
            if disponivel < delta:
                return JsonResponse({'erro': f'Quantidade indisponível. Restam {disponivel}.'}, status=400)
            pend.qt_necessaria = disponivel - delta
            pend.save(update_fields=['qt_necessaria'])
        elif pend and delta < 0:
            pend.qt_necessaria = int(pend.qt_necessaria or 0) + abs(delta)
            pend.save(update_fields=['qt_necessaria'])

        item.quantidade = nova_qt
        item.save(update_fields=['quantidade'])

    return JsonResponse({
        'mensagem': 'Quantidade atualizada com sucesso.',
        'item_id': item.id,
        'nova_quantidade': nova_qt,
        'pendente': int(pend.qt_necessaria or 0) if pend else None,
        'carga_id': carga.id,
        'stage': carga.stage,
    }, status=200)

@csrf_exempt
@require_http_methods(["DELETE", "POST"])
def deletar_item_pacote(request, item_id):
    """
    Remove um item do pacote e devolve a quantidade para a pendência.
    Permitido apenas nos estágios planejamento ou verificacao.
    """
    item = get_object_or_404(
        ItemPacote.objects.select_related('codigo', 'pacote__carga'),
        id=item_id
    )
    carga = item.pacote.carga
    if carga.stage not in ('planejamento', 'verificacao'):
        return JsonResponse({'erro': 'Exclusão permitida apenas em planejamento ou verificacao.'}, status=400)

    pend = item.codigo
    qtd_item = int(item.quantidade or 0)

    with transaction.atomic():
        if pend:
            pend.qt_necessaria = int(pend.qt_necessaria or 0) + qtd_item
            pend.save(update_fields=['qt_necessaria'])
        item.delete()

    return JsonResponse({
        'mensagem': 'Item removido do pacote.',
        'carga_id': carga.id,
        'stage': carga.stage,
        'pendente': int(pend.qt_necessaria or 0) if pend else 0,
    }, status=200)

@csrf_exempt
@require_http_methods(["POST"])
def duplicar_pacote(request, id):
    """
    Duplica um pacote reaproveitando os itens, respeitando a quantidade restante pendente.
    O novo nome recebe sufixo incremental (.1, .2, ...).
    """
    pacote = get_object_or_404(Pacote.objects.select_related('carga'), id=id)
    itens_origem = list(ItemPacote.objects.filter(pacote=pacote).select_related('codigo'))

    if not itens_origem:
        return JsonResponse({'erro': 'Pacote sem itens para duplicar.'}, status=400)

    with transaction.atomic():
        base_nome = pacote.nome
        partes = base_nome.rsplit('.', 1)
        if len(partes) == 2 and partes[1].isdigit():
            base_nome = partes[0]

        sufixos = []
        for nome in Pacote.objects.filter(carga=pacote.carga, nome__startswith=base_nome).values_list('nome', flat=True):
            resto = nome[len(base_nome):]
            if resto.startswith('.') and resto[1:].isdigit():
                try:
                    sufixos.append(int(resto[1:]))
                except ValueError:
                    continue
        proximo_sufixo = (max(sufixos) if sufixos else 0) + 1
        novo_nome = f"{base_nome}.{proximo_sufixo}"

        itens_para_criar_planejados = []
        itens_para_criar_avulsos = []
        for item in itens_origem:
            original = int(item.quantidade or 0)
            if original <= 0:
                continue

            pend = getattr(item, 'codigo', None)
            if pend:
                disponivel = int(pend.qt_necessaria or 0)
                if disponivel <= 0:
                    continue
                usar = min(disponivel, original)
                if usar > 0:
                    itens_para_criar_planejados.append((pend, usar))
            else:
                itens_para_criar_avulsos.append(item)

        if not itens_para_criar_planejados and not itens_para_criar_avulsos:
            return JsonResponse({'erro': 'Sem itens válidos para duplicar neste pacote.'}, status=400)

        novo_pacote = Pacote.objects.create(
            nome=novo_nome,
            carga=pacote.carga,
            criado_por=pacote.criado_por,
        )

        for pend, qtd in itens_para_criar_planejados:
            ItemPacote.objects.create(
                pacote=novo_pacote,
                codigo=pend,
                quantidade=qtd
            )
            pend.qt_necessaria = max(pend.qt_necessaria - qtd, 0)
            pend.save(update_fields=['qt_necessaria'])

        for item in itens_para_criar_avulsos:
            ItemPacote.objects.create(
                pacote=novo_pacote,
                codigo=None,
                codigo_informado=item.codigo_informado,
                descricao_informada=item.descricao_informada,
                fora_planejado=True,
                quantidade=item.quantidade
            )

    return JsonResponse({
        'mensagem': 'Pacote duplicado com sucesso.',
        'pacote_id': novo_pacote.id,
        'nome': novo_pacote.nome,
    }, status=201)


@csrf_exempt
@require_http_methods(["POST"])
def guardar_pacotes(request):
    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"erro": "JSON inválido"}, status=400)

    id_carga = data.get("idCargaPacote")
    nome_pacote = data.get("nomePacote")
    pacote_existente = data.get("pacoteExistenteId")  # pode vir null/None
    itens = data.get("itens", [])
    itens_fora_planejado = data.get("itensForaPlanejado", [])

    if not id_carga:
        return JsonResponse({"erro": "idCargaPacote é obrigatório"}, status=400)
    if not nome_pacote and not pacote_existente:
        return JsonResponse({"erro": "nomePacote é obrigatório"}, status=400)

    carga = get_object_or_404(Carga, id=id_carga)

    with transaction.atomic():
        if pacote_existente:
            pacote = get_object_or_404(Pacote, id=pacote_existente, carga=carga)
        else:
            pacote = Pacote.objects.create(nome=nome_pacote, carga=carga)

        if itens:
            pend_ids = [int(i.get("pendencia_id", 0) or 0) for i in itens]
            if any(pid <= 0 for pid in pend_ids):
                return JsonResponse({"erro": "Cada item deve conter pendencia_id válido."}, status=400)

            pendencias_qs = (
                PendenciasPacote.objects
                .select_for_update()
                .select_related("carreta_carga")
                .filter(id__in=pend_ids)
            )

            pend_por_id = {p.id: p for p in pendencias_qs}
            faltantes = [pid for pid in pend_ids if pid not in pend_por_id]
            if faltantes:
                return JsonResponse({"erro": f"Pendência(s) inexistente(s): {faltantes}"}, status=400)

            for p in pend_por_id.values():
                if getattr(p.carreta_carga, "carga_id", None) != carga.id:
                    return JsonResponse({
                        "erro": f"A pendência {p.id} não pertence à carga #{carga.id}"
                    }, status=400)

            itens_criados = []
            for item in itens:
                try:
                    qtd = int(item.get("quantidade", 0))
                except (TypeError, ValueError):
                    return JsonResponse({"erro": "Quantidade inválida."}, status=400)
                if qtd <= 0:
                    return JsonResponse({"erro": "Quantidade deve ser maior que zero."}, status=400)

                pend_id = int(item.get("pendencia_id"))
                pend = pend_por_id[pend_id]
                saldo_pendente = int(pend.qt_necessaria or 0)
                if saldo_pendente <= 0:
                    return JsonResponse({
                        "erro": f"O item {pend.codigo} - {pend.descricao} não possui saldo pendente para empacotar."
                    }, status=400)
                if qtd > saldo_pendente:
                    return JsonResponse({
                        "erro": (
                            f"O item {pend.codigo} - {pend.descricao} "
                            f"ultrapassa a quantidade pendente (disp: {saldo_pendente}, req: {qtd})"
                        )
                    }, status=400)

                itens_criados.append(ItemPacote(
                    pacote=pacote,
                    codigo_id=pend_id,
                    quantidade=qtd
                ))

                pend.qt_necessaria = pend.qt_necessaria - qtd
                pend.save(update_fields=["qt_necessaria"])

            if itens_criados:
                ItemPacote.objects.bulk_create(itens_criados)

        if itens_fora_planejado:
            itens_avulsos = []
            for item in itens_fora_planejado:
                codigo = str(item.get("codigo", "")).strip()
                descricao = str(item.get("descricao", "")).strip()
                try:
                    qtd = int(item.get("quantidade", 0))
                except (TypeError, ValueError):
                    return JsonResponse({"erro": "Quantidade inválida para item fora do planejado."}, status=400)

                if not codigo or not descricao:
                    return JsonResponse({"erro": "Código e descrição são obrigatórios para item fora do planejado."}, status=400)
                if qtd <= 0:
                    return JsonResponse({"erro": "Quantidade deve ser maior que zero para item fora do planejado."}, status=400)

                itens_avulsos.append(ItemPacote(
                    pacote=pacote,
                    codigo=None,
                    codigo_informado=codigo,
                    descricao_informada=descricao,
                    fora_planejado=True,
                    quantidade=qtd
                ))

            if itens_avulsos:
                ItemPacote.objects.bulk_create(itens_avulsos)

    # ---- resumo após a criação (inalterado) ----
    pacotes = Pacote.objects.filter(carga_id=id_carga)
    total_pacotes = pacotes.count()
    pacotes_com_foto_verificacao = (
        ImagemPacote.objects
        .filter(pacote__in=pacotes, stage='verificacao')
        .values('pacote').distinct().count()
    )
    pacotes_com_foto_despachado = (
        ImagemPacote.objects
        .filter(pacote__in=pacotes, stage='despachado')
        .values('pacote').distinct().count()
    )

    total_pendente = (
        PendenciasPacote.objects
        .filter(carreta_carga__carga_id=id_carga, qt_necessaria__gt=0)
        .aggregate(total=Coalesce(Sum('qt_necessaria'), 0))
        ['total']
    )

    todos_verificacao_ok = (
        total_pacotes > 0 and
        total_pacotes == pacotes_com_foto_verificacao and
        total_pendente == 0
    )
    todos_despachado_ok = (
        total_pacotes > 0 and
        total_pacotes == pacotes_com_foto_despachado
    )

    return JsonResponse({
        "mensagem": "Pacote criado com sucesso!",
        "pacote_id": pacote.id,
        "etapa": carga.stage,
        "info_add": {
            "id": carga.id,
            "nome": carga.nome,
            "carga": carga.carga,
            "data_carga": carga.data_carga.isoformat() if carga.data_carga else None,
            "cliente": carga.cliente,
            "obs_pacote": carga.obs_pacote,
            "stage": carga.stage,
            "todos_pacotes_tem_foto_verificacao": todos_verificacao_ok,
            "todos_pacotes_tem_foto_despachado": todos_despachado_ok,
            "total_pendente": int(total_pendente or 0),
        }
    }, status=201)

def buscar_pacotes_carga(request, id):
    carga = get_object_or_404(Carga, id=id)

    pacotes_qs = (
        Pacote.objects
        .filter(carga=carga)
        .annotate(tem_foto=Exists(ImagemPacote.objects.filter(pacote=OuterRef('pk'))))
        .order_by('id')
        .prefetch_related('itens')
    )

    dados = []
    for pacote in pacotes_qs:
        itens = pacote.itens.all().select_related('codigo')
        itens_list = []
        for item in itens:
            cod_obj = getattr(item, 'codigo', None)
            codigo_peca = getattr(cod_obj, 'codigo', None) or item.codigo_informado
            descricao = getattr(cod_obj, 'descricao', None) or item.descricao_informada
            itens_list.append({
                'id': item.id,
                'codigo_peca': codigo_peca,
                'descricao': descricao,
                'quantidade': item.quantidade,
                'fora_planejado': bool(getattr(item, 'fora_planejado', False)),
            })

        dados.append({
            'id': pacote.id,
            'nome': pacote.nome,
            'status_expedicao': pacote.status_confirmacao_expedicao,
            'status_qualidade': pacote.status_confirmacao_qualidade,
            'data_criacao': (
                localtime(pacote.data_criacao, ZoneInfo('America/Fortaleza')).strftime('%d/%m/%Y %H:%M')
                if getattr(pacote, 'data_criacao', None) else None
            ),            
            'itens': itens_list,
            'cliente': carga.cliente,
            'data_carga': carga.data_carga.strftime("%d/%m/%Y"),
            'tem_foto': bool(getattr(pacote, 'tem_foto', False)),
        })

    # << NOVO >> — lista de carretas da carga
    carretas = list(
        CarretaCarga.objects
        .filter(carga=carga)
        .values('id', 'carreta', 'quantidade', 'cor')   # ajuste campos se precisar
        .order_by('carreta', 'id')
    )

    # Códigos especiais e fornecedores (só relevante no estágio verificação)
    codigos_especiais = {}
    fornecedores = {}
    if carga.stage == 'verificacao':
        codigos_especiais = _detectar_codigos_especiais_da_carga(carga.id)
        salvos = FornecedorItemCarga.objects.filter(carga=carga)
        fornecedores = {f"{f.tipo}_{f.codigo}": f.fornecedor for f in salvos}

    return JsonResponse({
        'pacotes': dados,
        'status_carga': carga.stage,
        'cliente_carga': carga.cliente,
        'data_carga': carga.data_carga.strftime("%d/%m/%Y"),
        'carga': carga.carga,
        'carretas': carretas,
        'codigos_especiais': codigos_especiais,
        'fornecedores': fornecedores,
    })

def listar_pacotes_criados(request, id):
    # garante que a carga existe (opcional)
    carga = get_object_or_404(Carga, id=id)

    pacotes = list(
        Pacote.objects
        .filter(carga=carga)
        .values('id', 'nome')
        .order_by('nome', 'id')
    )
    # normaliza a chave pro frontend
    pacotes = [{'id_pacote': p['id'], 'nome_pacote': p['nome']} for p in pacotes]

    return JsonResponse({"pacotes": pacotes}, status=200)

@csrf_exempt
def alterar_stage(request, id):
    if request.method != 'POST':
        return JsonResponse({'erro': 'Método não permitido'}, status=405)

    # novo_stage = data.get('stage', None)
    carga = get_object_or_404(Carga, id=id)
    stage_atual = carga.stage

    # Regras de avanço de estágio
    # if stage_atual == 'planejamento':
    
    #     # VERIFICA SE TODOS PACOTES FORAM CRIADOS
    #     total = (
    #         PendenciasPacote.objects
    #         .filter(carreta_carga__carga_id=id, qt_necessaria__gt=0)
    #         .aggregate(total=Coalesce(Sum('qt_necessaria'), 0))
    #         ['total']
    #     )
        
    #     if total > 0:
    #         return JsonResponse({'erro': 'Forme todos os pacotes antes de passar para próximo estágio.'}, status=400)

    # Atualização do estágio
    if stage_atual == 'planejamento':
        carga.stage = 'verificacao'
    elif stage_atual == 'verificacao':
        # Verificar fornecedores obrigatórios para cada código especial presente
        codigos_especiais = _detectar_codigos_especiais_da_carga(id)
        if codigos_especiais:
            salvos = {(f.tipo, f.codigo): f.fornecedor
                      for f in FornecedorItemCarga.objects.filter(carga=carga)}
            faltando = [
                f"{tipo} ({item['codigo']})"
                for tipo, itens in codigos_especiais.items()
                for item in itens
                if not salvos.get((tipo, item['codigo']), '').strip()
            ]
            if faltando:
                return JsonResponse({
                    'erro': f'Informe o fornecedor de {", ".join(faltando)} antes de avançar.'
                }, status=400)

        carga.stage = 'despachado'
        carga.data_despachado = timezone.now()
    else:
        return JsonResponse({'erro': 'Estágio atual inválido para avanço automático.'}, status=400)

    carga.save()

    return JsonResponse({
        'mensagem': 'Estágio alterado com sucesso!',
        'stage_antigo': stage_atual,
        'novo_stage': carga.stage,
    }, status=200)

@csrf_exempt
@require_http_methods(["POST"])
def salvar_fornecedores(request, carga_id):
    """Salva/atualiza os fornecedores por código de peça especial para uma carga."""
    carga = get_object_or_404(Carga, id=carga_id)
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'erro': 'JSON inválido.'}, status=400)

    # data é uma lista de {tipo, codigo, fornecedor}
    if not isinstance(data, list):
        return JsonResponse({'erro': 'Formato inválido. Esperado lista de {tipo, codigo, fornecedor}.'}, status=400)

    with transaction.atomic():
        for entry in data:
            tipo = entry.get('tipo', '').strip()
            codigo = entry.get('codigo', '').strip()
            fornecedor = entry.get('fornecedor', '').strip()
            if tipo and codigo:
                obj, _ = FornecedorItemCarga.objects.get_or_create(carga=carga, tipo=tipo, codigo=codigo)
                obj.fornecedor = fornecedor
                obj.save()

    codigos_especiais = _detectar_codigos_especiais_da_carga(carga.id)
    salvos = {(f.tipo, f.codigo): f.fornecedor for f in FornecedorItemCarga.objects.filter(carga=carga)}
    faltando = any(
        not salvos.get((tipo, item['codigo']), '').strip()
        for tipo, itens in codigos_especiais.items()
        for item in itens
    )
    return JsonResponse({'mensagem': 'Fornecedores salvos com sucesso!', 'fornecedores_pendentes': faltando})

@csrf_exempt
def confirmar_pacote(request, id):
    
    data = json.loads(request.body)

    obs = data.get('observacao')

    pacote = get_object_or_404(Pacote, id=id)

    # identificar em qual estage está esse pacote
    stage = pacote.carga.stage

    # verifica se o pacote ja tem imagem
    # if stage == 'apontamento':
    #     imagens = ImagemPacote.objects.filter(pacote=pacote, stage=stage)
    if stage == 'verificacao':
        imagens = ImagemPacote.objects.filter(pacote=pacote, stage=stage)

        if not imagens.exists():
            return JsonResponse({'erro': 'É necessário anexar ao menos uma foto antes de confirmar o pacote.'}, status=400)

    if stage == 'apontamento':
        pacote.status_confirmacao_expedicao = 'ok'
        pacote.data_confirmacao_expedicao = timezone.now()
        pacote.obs_expedicao = obs
    elif stage == 'verificacao':
        pacote.status_confirmacao_qualidade = 'ok'
        pacote.data_confirmacao_qualidade = timezone.now()
        pacote.obs_qualidade = obs
    
    pacote.save()    

    return JsonResponse({
        'mensagem': 'Pacote confirmado com sucesso!',
    }, status=200)

def mover_item(request):
    
    data = json.loads(request.body)

    item_id = data.get('item_id')
    pacote_destino_id = data.get('pacote_destino_id')

    item_pacote_atual = get_object_or_404(ItemPacote, id=item_id)
    item_pacote_atual.pacote_id = pacote_destino_id
    item_pacote_atual.save()

    return JsonResponse({
        'mensagem': 'Pacote alterado com sucesso.',
    }, status=200)

def impressao_pacote(request):

    data = json.loads(request.body)

    id_pacote = data.get('pacote_id')
    cliente = data.get('cliente')
    data_carga = data.get('data_carga')
    nome_pacote = data.get('nome_pacote')

    # buscar observações do pacote
    pacote = get_object_or_404(Pacote, id=id_pacote)
    obs_qualidade = pacote.obs_qualidade
    obs_expedicao = pacote.obs_expedicao

    # juntar observações
    if obs_qualidade and obs_expedicao:
        obs_completa = f"Expedição: {obs_expedicao} | Qualidade: {obs_qualidade}"
    elif obs_qualidade:
        obs_completa = f"Qualidade: {obs_qualidade}"
    elif obs_expedicao:
        obs_completa = f"Expedição: {obs_expedicao}"
    else:
        obs_completa = "Sem observações"

    chamar_impressora(cliente, data_carga, nome_pacote, obs_completa)
    # chamar_impressora_qrcode()

    return JsonResponse({'status': 'ok'})

@csrf_exempt
def salvar_foto(request):
    if request.method != 'POST':
        return JsonResponse({'erro': 'Método não permitido'}, status=405)

    if 'foto' not in request.FILES:
        return JsonResponse({'erro': 'Foto não recebida'}, status=400)

    foto = request.FILES['foto']
    pacote_id = request.POST.get('pacote')
    if not pacote_id:
        return JsonResponse({'erro': 'pacote não informado'}, status=400)

    pacote_object = get_object_or_404(Pacote, id=pacote_id)
    carga = pacote_object.carga
    id_carga = carga.id

    # stage atual do pacote (da carga)
    stage = carga.stage

    # Gera nome customizado (preserva extensão)
    extensao = (foto.name.rsplit('.', 1)[-1] if '.' in foto.name else 'jpg')
    nome_arquivo = f"pacote_{pacote_id}_{timezone.now().strftime('%Y%m%d%H%M%S')}.{extensao}"
    foto.name = nome_arquivo

    imagem = ImagemPacote.objects.create(
        pacote=pacote_object,
        arquivo=foto,
        stage=stage
    )

    # ---- Cálculos de status da carga (mesmo padrão da outra view) ----
    pacotes = Pacote.objects.filter(carga_id=id_carga)
    total_pacotes = pacotes.count()

    pacotes_com_foto_verificacao = (
        ImagemPacote.objects
        .filter(pacote__in=pacotes, stage='verificacao')
        .values('pacote').distinct().count()
    )
    pacotes_com_foto_despachado = (
        ImagemPacote.objects
        .filter(pacote__in=pacotes, stage='despachado')
        .values('pacote').distinct().count()
    )

    total_pendente = (
        PendenciasPacote.objects
        .filter(carreta_carga__carga_id=id_carga, qt_necessaria__gt=0)
        .aggregate(total=Coalesce(Sum('qt_necessaria'), 0))
        ['total']
    ) or 0

    todos_verificacao_ok = (
        total_pacotes > 0 and
        total_pacotes == pacotes_com_foto_verificacao and
        total_pendente == 0
    )
    todos_despachado_ok = (
        total_pacotes > 0 and
        total_pacotes == pacotes_com_foto_despachado
    )

    return JsonResponse({
        'status': 'ok',
        'url': imagem.arquivo.url,
        'info_add': {
            'carga_id': id_carga,
            'etapa': carga.stage,
            'total_pacotes': total_pacotes,
            'pacotes_com_foto_verificacao': pacotes_com_foto_verificacao,
            'pacotes_com_foto_despachado': pacotes_com_foto_despachado,
            'total_pendente': int(total_pendente),
            'todos_pacotes_tem_foto_verificacao': todos_verificacao_ok,
            'todos_pacotes_tem_foto_despachado': todos_despachado_ok,
        }
    }, status=201)

def buscar_fotos(request, pacote_id):
    if request.method == 'GET':
        imagens = ImagemPacote.objects.filter(pacote_id=pacote_id)
        fotos = [{'id': img.id, 'url': img.arquivo.url, 'etapa': img.stage} for img in imagens]
        return JsonResponse({'fotos': fotos})
    return JsonResponse({'erro': 'Método não permitido'}, status=405)


@require_http_methods(["DELETE"])
def excluir_foto(request, foto_id):
    imagem = get_object_or_404(ImagemPacote, id=foto_id)
    imagem.arquivo.delete(save=False)
    imagem.delete()
    return JsonResponse({'mensagem': 'Foto excluída com sucesso.'})

@require_http_methods(["DELETE"])
def excluir_pendencia(request, pendencia_id):
    pendencia = get_object_or_404(PendenciasPacote, id=pendencia_id)

    itens_vinculados = ItemPacote.objects.filter(codigo=pendencia).select_related('pacote')
    if itens_vinculados.exists():
        nomes = ', '.join(
            i.pacote.nome for i in itens_vinculados[:5]
        )
        return JsonResponse({
            'erro': (
                f'Esta pendência está vinculada a itens nos pacotes: {nomes}. '
                'Remova os itens dos pacotes antes de excluir a pendência.'
            )
        }, status=400)

    pendencia.delete()
    return JsonResponse({'mensagem': 'Pendência removida com sucesso.'})

@require_http_methods(["GET"])
def mostrar_pendencias(request, carregamento_id):
    """
    Lista as pendências (qt_necessaria > 0) do carregamento informado (carga_id).
    Retorna JSON com os itens.
    """

    qs = (
        PendenciasPacote.objects
        .filter(
            carreta_carga__carga_id=int(carregamento_id),
            qt_necessaria__gt=0
        )
        .select_related('carreta_carga')
        .order_by('carreta_carga__carreta', 'codigo')
    )

    itens = [
        {
            "id": p.id,
            "carreta_carga_id": p.carreta_carga_id,
            "carreta": getattr(p.carreta_carga, "carreta", None),
            "codigo": p.codigo,
            "descricao": p.descricao,
            "qt_necessaria": p.qt_necessaria,
            "data_criacao": p.data_criacao.isoformat(),
        }
        for p in qs
    ]

    return JsonResponse({
        "total_itens": len(itens),
        "itens": itens
    })

@require_http_methods(["GET"])
def verificar_pendencias(request, carregamento_id):
    total = (
        PendenciasPacote.objects
        .filter(carreta_carga__carga_id=int(carregamento_id), qt_necessaria__gt=0)
        .aggregate(total=Sum('qt_necessaria'))
        .get('total') or 0
    )

    return JsonResponse({"total_itens_pendente": int(total)})


@csrf_exempt
@transaction.atomic
@require_http_methods(["POST"])
def reatualizar_carretas_faltantes(request, carga_id):
    carga = get_object_or_404(Carga, id=carga_id)
    if carga.stage == 'despachado':
        return JsonResponse({'erro': 'Nao e permitido reprocessar carretas em cargas despachadas.'}, status=400)

    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'erro': 'JSON invalido.'}, status=400)

    carreta_alvo = normalize_carreta_text(payload.get('carreta') or '')
    if not carreta_alvo:
        return JsonResponse({'erro': 'Informe a carreta pendente para reprocessar.'}, status=400)

    carretas_qs = list(
        CarretaCarga.objects
        .select_for_update()
        .annotate(carreta_normalizada=normalized_spaces_expr('carreta'))
        .filter(carga_id=carga_id, carreta_normalizada=carreta_alvo)
        .order_by('id')
    )

    if not carretas_qs:
        return JsonResponse({'erro': f'Carreta {carreta_alvo} nao encontrada nesta carga.'}, status=404)

    possui_pendencias = PendenciasPacote.objects.filter(
        carreta_carga_id__in=[c.id for c in carretas_qs]
    ).exists()
    if possui_pendencias:
        return JsonResponse({'erro': f'A carreta {carreta_alvo} ja possui pendencias geradas.'}, status=400)

    resultado = _criar_pendencias_para_carretas_carga(carretas_qs, somente_sem_pendencias=False)

    faltando_qs = (
        CarretaCarga.objects
        .filter(carga_id=carga_id)
        .exclude(id__in=PendenciasPacote.objects.filter(
            carreta_carga__carga_id=carga_id
        ).values('carreta_carga_id'))
        .values_list('carreta', flat=True)
        .distinct()
    )
    faltando = sorted({
        normalize_carreta_text(carreta)
        for carreta in faltando_qs
        if normalize_carreta_text(carreta)
    })

    total_pendente = (
        PendenciasPacote.objects
        .filter(carreta_carga__carga_id=carga_id, qt_necessaria__gt=0)
        .aggregate(total=Coalesce(Sum('qt_necessaria'), 0))
        ['total']
    ) or 0

    if carreta_alvo in faltando:
        if carreta_alvo in (resultado.get('carretas_sem_componentes') or []):
            return JsonResponse({
                'erro': (
                    f'Nao foi possivel gerar pendencias para a carreta {carreta_alvo}. '
                    'Ela nao possui componentes elegiveis na base explodida.'
                ),
                'carga_id': carga_id,
                'carreta': carreta_alvo,
                'faltando_gerar': faltando,
                'carretas_sem_componentes': resultado.get('carretas_sem_componentes') or [],
                'total_pendente': int(total_pendente),
            }, status=400)

        return JsonResponse({
            'erro': f'Nao foi possivel gerar pendencias para a carreta {carreta_alvo}.',
            'carga_id': carga_id,
            'carreta': carreta_alvo,
            'faltando_gerar': faltando,
            'carretas_sem_componentes': resultado.get('carretas_sem_componentes') or [],
            'total_pendente': int(total_pendente),
        }, status=400)

    return JsonResponse({
        'mensagem': 'Carreta reprocessada com sucesso.',
        'carga_id': carga_id,
        'carreta_reprocessada': carreta_alvo,
        'carretas_reprocessadas': resultado['carretas_sem_pendencias'],
        'pendencias_criadas': resultado['pendencias_criadas'],
        'carretas_sem_componentes': resultado['carretas_sem_componentes'],
        'faltando_gerar': faltando,
        'ok': len(faltando) == 0,
        'total_pendente': int(total_pendente),
    }, status=200)

@require_http_methods(['GET'])
def comparar_carretas_geradas(request, carga_id):
    """
    Verifica se todas as carretas criadas em CarretaCarga para a carga_id
    possuem ao menos uma PendenciasPacote gerada.
    Retorna a lista de carretas faltantes (sem pendência) e um resumo.
    """

    # 1) Conjunto de carretas "esperadas" (foram criadas em CarretaCarga)
    esperadas_qs = (CarretaCarga.objects
                    .filter(carga_id=carga_id)
                    .values_list('carreta', flat=True)
                    .distinct())
    esperadas = {normalize_carreta_text(c) for c in esperadas_qs if normalize_carreta_text(c)}

    # 2) Conjunto de carretas que "têm pendência" (aparecem em PendenciasPacote)
    com_pendencia_qs = (PendenciasPacote.objects
                        .filter(carreta_carga__carga_id=carga_id)
                        .values_list('carreta_carga__carreta', flat=True)
                        .distinct())
    com_pendencia = {normalize_carreta_text(c) for c in com_pendencia_qs if normalize_carreta_text(c)}

    # 3) Diferenças
    faltando = sorted(esperadas - com_pendencia)   # carretas criadas mas sem nenhuma pendência

    # 4) Resumo por carreta (qtd de itens e soma das quantidades necessárias)
    resumo_qs = (PendenciasPacote.objects
                 .filter(carreta_carga__carga_id=carga_id)
                 .values('carreta_carga__carreta')
                 .annotate(
                     total_itens=Count('id'),
                     total_qt=Coalesce(Sum('qt_necessaria'), 0),
                 )
                 .order_by('carreta_carga__carreta'))

    return JsonResponse({
        'carga_id': carga_id,
        'carretas_esperadas': sorted(esperadas),
        'carretas_com_pendencias': sorted(com_pendencia),
        'faltando_gerar': faltando,
        'resumo_pendencias_por_carreta': list(resumo_qs),
        'ok': len(faltando) == 0,
    }, status=200)

@require_http_methods(['GET'])
def quantidade_pendente_carretas(request, carga_id):
    """
    Retorna, por carreta da carga_id, quantos 'conjuntos' faltam ser empacotados.
    - Soma qt_necessaria (por padrão considera apenas > 0).
    - Também retorna a contagem de itens (linhas) pendentes por carreta.
    Querystring:
      - include_zero=1  -> inclui itens com qt_necessaria <= 0 no somatório/contagem
    """
    include_zero = request.GET.get('include_zero') in ('1', 'true', 'True')

    base_filter = Q(carreta_carga__carga_id=carga_id)
    if not include_zero:
        base_filter &= Q(qt_necessaria__gt=0)

    pend_qs = (PendenciasPacote.objects
               .filter(base_filter)
               .values('carreta_carga__carreta')
               .annotate(
                   total_conjuntos=Coalesce(Sum('qt_necessaria'), 0),
                   itens_pendentes=Count('id'),
               )
               .order_by('carreta_carga__carreta'))

    # lista por carreta
    por_carreta = [
        {
            'carreta': (row['carreta_carga__carreta'] or '').strip(),
            'total_conjuntos': int(row['total_conjuntos'] or 0),
            'itens_pendentes': int(row['itens_pendentes'] or 0),
        }
        for row in pend_qs
    ]

    # totais gerais
    total_conjuntos_geral = sum(x['total_conjuntos'] for x in por_carreta)
    total_itens_geral = sum(x['itens_pendentes'] for x in por_carreta)

    return JsonResponse({
        'carga_id': carga_id,
        'include_zero': include_zero,
        'por_carreta': por_carreta,
        'totais': {
            'total_conjuntos': total_conjuntos_geral,
            'total_itens': total_itens_geral,
            'qtd_carretas': len(por_carreta),
        }
    }, status=200)

