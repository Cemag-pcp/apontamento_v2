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
from .services import (
    _TIPOS_ESPECIAIS, _detectar_codigos_especiais_da_carga,
    FotoObrigatoriaError, PacoteValidationError, listar_cargas_ativas,
    detalhar_pacotes_da_carga, salvar_foto_pacote, listar_fotos_pacote,
    confirmar_pacote_service, listar_pendencias_carga, criar_ou_atualizar_pacote,
    excluir_foto_pacote, deletar_pacote_service, duplicar_pacote_service,
)
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
# (_TIPOS_ESPECIAIS e _detectar_codigos_especiais_da_carga agora vivem em services.py,
# compartilhados com a API mobile - importados no topo deste arquivo)
_PROCESSOS_PENDENCIA_CARRETA = ['PINTAR', 'COMPONENTE EXTRA']


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
    from datetime import timedelta
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

    # Pré-validação dos itens antes de abrir a transação
    itens_validos = []
    for item in itens:
        carreta_raw        = item.get('codigo_peca', '')
        quantidade_carreta = safe_int(item.get('quantidade'), default=0)
        cor                = item.get('cor')
        carreta_limpa = normalize_carreta_text(carreta_raw)
        if carreta_limpa and quantidade_carreta > 0:
            itens_validos.append({'carreta': carreta_limpa, 'quantidade': quantidade_carreta, 'cor': cor})

    if not itens_validos:
        return JsonResponse({'erro': 'Nenhuma carreta valida nos itens'}, status=400)

    with transaction.atomic():
        # Idempotência: impede criação duplicada em cliques acidentais (janela de 10 s)
        recente = Carga.objects.filter(
            carga=carga_nome,
            data_carga=data_carga,
            cliente=cliente_nome,
            data_criacao__gte=timezone.now() - timedelta(seconds=10),
        ).first()
        if recente:
            return JsonResponse({
                'mensagem': 'Caixa criada com sucesso!',
                'id': recente.id,
                'carretas_criadas': recente.carretas.count(),
                'pendencias_criadas': 0,
                'stage': recente.stage,
                'cliente': recente.cliente,
                'data_carga': str(recente.data_carga),
                'carga': recente.carga,
                'carretas_sem_componentes': [],
            }, status=201)

        hora_atual = timezone.now().strftime("%H%M%S")
        carga = Carga.objects.create(
            nome=f"{carga_nome}_{cliente_nome}_{str(data_carga).replace('-', '')}_{hora_atual}",
            carga=carga_nome,
            data_carga=data_carga,
            cliente=cliente_nome,
            obs_pacote=observacoes
        )

        carretas_carga_criadas = []
        for item in itens_validos:
            carreta_carga_object = CarretaCarga.objects.create(
                carga=carga,
                carreta=item['carreta'],
                quantidade=item['quantidade'],
                cor=item['cor'],
            )
            carretas_carga_criadas.append(carreta_carga_object)

        resultado_pendencias = _criar_pendencias_para_carretas_carga(carretas_carga_criadas)

    return JsonResponse({
        'mensagem': 'Caixa criada com sucesso!',
        'id': carga.id,
        'carretas_criadas': len(carretas_carga_criadas),
        'pendencias_criadas': resultado_pendencias['pendencias_criadas'],
        'stage': 'verificacao',
        'cliente': cliente_nome,
        'data_carga': data_carga,
        'carga': carga_nome,
        'carretas_sem_componentes': resultado_pendencias['carretas_sem_componentes'],

    }, status=201)

def buscar_cargas(request):
    return JsonResponse(listar_cargas_ativas(), safe=False)

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
    try:
        resultado = deletar_pacote_service(pacote)
    except PacoteValidationError as exc:
        return JsonResponse({'erro': str(exc)}, status=400)

    return JsonResponse(resultado, status=200)

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
    try:
        resultado = duplicar_pacote_service(pacote)
    except PacoteValidationError as exc:
        return JsonResponse({'erro': str(exc)}, status=400)

    return JsonResponse(resultado, status=201)


@csrf_exempt
@require_http_methods(["POST"])
def guardar_pacotes(request):
    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"erro": "JSON inválido"}, status=400)

    id_carga = data.get("idCargaPacote")
    if not id_carga:
        return JsonResponse({"erro": "idCargaPacote é obrigatório"}, status=400)

    carga = get_object_or_404(Carga, id=id_carga)

    try:
        resultado = criar_ou_atualizar_pacote(
            carga,
            nome_pacote=data.get("nomePacote"),
            pacote_existente_id=data.get("pacoteExistenteId"),
            itens=data.get("itens", []),
            itens_fora_planejado=data.get("itensForaPlanejado", []),
        )
    except PacoteValidationError as exc:
        return JsonResponse({"erro": str(exc)}, status=400)

    return JsonResponse(resultado, status=201)

def buscar_pacotes_carga(request, id):
    carga = get_object_or_404(Carga, id=id)
    return JsonResponse(detalhar_pacotes_da_carga(carga))

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

    try:
        resultado = confirmar_pacote_service(pacote, obs)
    except FotoObrigatoriaError as exc:
        return JsonResponse({'erro': str(exc)}, status=400)

    return JsonResponse(resultado, status=200)

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
    resultado = salvar_foto_pacote(pacote_object, foto)

    return JsonResponse(resultado, status=201)

def buscar_fotos(request, pacote_id):
    if request.method == 'GET':
        return JsonResponse({'fotos': listar_fotos_pacote(pacote_id)})
    return JsonResponse({'erro': 'Método não permitido'}, status=405)


@require_http_methods(["DELETE"])
def excluir_foto(request, foto_id):
    imagem = get_object_or_404(ImagemPacote, id=foto_id)
    excluir_foto_pacote(imagem)
    return JsonResponse({'mensagem': 'Foto excluída com sucesso.'})

@require_http_methods(["DELETE"])
def excluir_pendencia(request, pendencia_id):
    pendencia = get_object_or_404(PendenciasPacote, id=pendencia_id)

    ItemPacote.objects.filter(codigo=pendencia).delete()

    pendencia.delete()
    return JsonResponse({'mensagem': 'Pendência removida com sucesso.'})

@require_http_methods(["GET"])
def mostrar_pendencias(request, carregamento_id):
    """
    Lista as pendências (qt_necessaria > 0) do carregamento informado (carga_id).
    Retorna JSON com os itens.
    """
    return JsonResponse(listar_pendencias_carga(carregamento_id))

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

