from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.views.decorators.http import require_http_methods
from django.db.models import Sum, Exists, OuterRef, Count, Q
from django.db.models.functions import Coalesce
from django.utils.timezone import localtime

from cargas.utils import get_data_from_sheets,tratando_dados
from .models import Carga,ItemPacote,Pacote,VerificacaoPacote, CarretaCarga, ImagemPacote, PendenciasPacote, ItemPacote
from .utils import chamar_impressora, buscar_conjuntos_carreta, limpar_cor, chamar_impressora_qrcode
from cadastro.models import CarretasExplodidas

import json
import boto3
import re
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

# === Helpers de normalização ===

SIGLA_POR_COR = {
    'amarelo': 'AV',
    'laranja': 'LC',
    'cinza': 'CO',
    'azul': 'AN',
    'verde': 'VJ',
    'preto': 'PR',
    'vermelho': 'VM',
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
    
# =========== Template inicial ==========

def planejamento(request):

    return render(request, 'apontamento_exped/planejamento.html')

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

    base_carretas, base_carga = get_data_from_sheets()
    base_carretas, base_carga = tratando_dados(base_carretas, base_carga, data_carga)

    cargas = base_carga['Carga'].unique().tolist()

    return JsonResponse(cargas, safe=False)

def clientes(request):
    data_carga = request.GET.get('data_carga')
    carga = request.GET.get('carga')

    base_carretas, base_carga = get_data_from_sheets()
    base_carretas, base_carga = tratando_dados(
        base_carretas, base_carga, data_carga,cliente=None,carga=carga
    )
    
    clientes = base_carga['PED_PESSOA.CODIGO'].unique().tolist()

    return JsonResponse(clientes, safe=False)

def carretas(request):
    cliente = request.GET.get('cliente')
    data_carga = request.GET.get('data_carga')

    base_carretas, base_carga = get_data_from_sheets()
    base_carretas, base_carga = tratando_dados(base_carretas, base_carga, data_carga, cliente)

    # criar coluna de cor
    # procurar na coluna recurso as siglas
    # VM=VERMELHO,AN=AZUL,VJ=VERDE,LJ=LARANJA,AM=AMARELO,CO=CINZA

    base_carga['cor'] = base_carga['Recurso'].apply(cor_recurso)

    # Mostrar recurso e quantidade
    carretas = base_carga[['Recurso', 'Qtde', 'PED_NUMEROSERIE','cor']].to_dict(orient='records')
    
    return JsonResponse(carretas, safe=False)

@csrf_exempt
@transaction.atomic
def criar_caixa(request):
    if request.method != 'POST':
        return JsonResponse({'erro': 'Método não permitido'}, status=405)

    # --- Parse do JSON ---
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'erro': 'JSON inválido'}, status=400)

    data_carga     = data.get('data_carga')
    carga_nome     = data.get('carga_nome')
    cliente_codigo = data.get('cliente_codigo')
    observacoes    = data.get('observacoes')
    itens          = data.get('itens', [])

    if not itens:
        return JsonResponse({'erro': 'Nenhum item informado'}, status=400)

    # --- Cria Carga ---
    hora_atual = timezone.now().strftime("%H%M%S")
    carga = Carga.objects.create(
        nome=f"{carga_nome}_{cliente_codigo}_{str(data_carga).replace('-', '')}_{hora_atual}",
        carga=carga_nome,
        data_carga=data_carga,
        cliente=cliente_codigo,
        obs_pacote=observacoes
    )

    # --- Carretas limpas vindas dos itens (remove sufixo só se for sigla válida) ---
    lista_carretas = [strip_color_suffix(item.get('codigo_peca', '')).strip() for item in itens if item.get('codigo_peca')]

    if not lista_carretas:
        return JsonResponse({'erro': 'Nenhuma carreta válida nos itens'}, status=400)

    # --- Buscar componentes em CarretasExplodidas (apenas PINTAR) ---
    qs = (CarretasExplodidas.objects
        .filter(carreta__in=lista_carretas,
                primeiro_processo__in=['PINTAR', 'COMPONENTE EXTRA'])
        .values('carreta', 'codigo_peca', 'descricao_peca', 'total_peca'))
    
    # --- Preparar base agrupada por carreta, com tratamento de código/descrição ---
    grupos_por_carreta = defaultdict(list)
    for row in qs:
        codigo_peca       = row.get('codigo_peca') or ''
        descricao_peca    = row.get('descricao_peca') or ''
        total_peca      = parse_total(row.get('total_peca'))
        carreta_db_raw  = (row.get('carreta') or '')

        carreta_key = strip_color_suffix(carreta_db_raw).strip().upper()

        codigo_base       = strip_color_suffix(codigo_peca)
        descricao_limpa   = clean_description(descricao_peca)
        total_por_carreta = safe_int(total_peca, default=0)

        if carreta_key and total_peca > 0:
            grupos_por_carreta[carreta_key].append({
                'codigo_base': strip_color_suffix(codigo_peca),
                'descricao_limpa': clean_description(descricao_peca),
                'total_por_carreta': total_peca,
            })

    total_pendencias = 0
    created_carretas = 0

    # --- Criar CarretaCarga e Pendencias por item ---
    for item in itens:
        carreta_raw        = item.get('codigo_peca', '')
        quantidade_carreta = safe_int(item.get('quantidade'), default=0)
        cor                = item.get('cor')

        carreta_limpa = strip_color_suffix(carreta_raw).strip().upper()

        if not carreta_limpa or quantidade_carreta <= 0:
            continue

        carreta_carga_object = CarretaCarga.objects.create(
            carga=carga,
            carreta=carreta_limpa,
            quantidade=quantidade_carreta,
            cor=cor
        )
        created_carretas += 1

        componentes = grupos_por_carreta.get(carreta_limpa, [])
        if not componentes:
            continue

        pendencias_to_create = []
        for comp in componentes:
            total_por_carreta = comp['total_por_carreta']
            qt_necessaria     = quantidade_carreta * total_por_carreta
            if qt_necessaria <= 0:
                continue

            pendencias_to_create.append(PendenciasPacote(
                carreta_carga=carreta_carga_object,
                codigo=comp['codigo_base'],
                descricao=comp['descricao_limpa'],
                qt_necessaria=qt_necessaria
            ))

        if pendencias_to_create:
            PendenciasPacote.objects.bulk_create(pendencias_to_create)
            total_pendencias += len(pendencias_to_create)

    return JsonResponse({
        'mensagem': 'Caixa criada com sucesso!',
        'id': carga.id,
        'carretas_criadas': created_carretas,
        'pendencias_criadas': total_pendencias,
        'stage': 'verificacao',
        'cliente': cliente_codigo,
        'data_carga': data_carga,
        'carga': carga_nome,

    }, status=201)

def buscar_cargas(request):

    cargas = Carga.objects.all().values('id', 'nome', 'carga', 'data_carga', 'cliente', 'obs_pacote', 'stage', 'data_criacao')

    # verifica se todos os pacotes dessa carga contém foto
    for carga in cargas:
        pacotes = Pacote.objects.filter(carga_id=carga['id'])
        total_pacotes = pacotes.count()
        pacotes_com_foto_verificacao = ImagemPacote.objects.filter(pacote__in=pacotes, stage='verificacao').values('pacote').distinct().count()
        pacotes_com_foto_despachado = ImagemPacote.objects.filter(pacote__in=pacotes, stage='despachado').values('pacote').distinct().count()
        
        # VERIFICA SE TODOS PACOTES FORAM CRIADOS
        total = (
            PendenciasPacote.objects
            .filter(carreta_carga__carga_id=carga['id'], qt_necessaria__gt=0)
            .aggregate(total=Coalesce(Sum('qt_necessaria'), 0))
            ['total']
        )

        carga['todos_pacotes_tem_foto_verificacao'] = (total_pacotes > 0 and total_pacotes == pacotes_com_foto_verificacao and total == 0)
        carga['todos_pacotes_tem_foto_despachado'] = (total_pacotes > 0 and total_pacotes == pacotes_com_foto_despachado)

    return JsonResponse(list(cargas), safe=False)

@csrf_exempt
@require_http_methods(["POST"])
def guardar_pacotes(request):
    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"erro": "JSON inválido"}, status=400)

    id_carga         = data.get("idCargaPacote")
    nome_pacote      = data.get("nomePacote")
    pacote_existente = data.get("pacoteExistenteId")  # pode vir null/None
    itens            = data.get("itens", [])

    if not id_carga:
        return JsonResponse({"erro": "idCargaPacote é obrigatório"}, status=400)
    if not nome_pacote and not pacote_existente:
        return JsonResponse({"erro": "nomePacote é obrigatório"}, status=400)

    carga = get_object_or_404(Carga, id=id_carga)

    with transaction.atomic():
        # === NOVO: permitir pacote sem itens ===
        if not itens:
            if pacote_existente:
                # >>> usar pacote já existente (e validar a carga)
                pacote = get_object_or_404(Pacote, id=pacote_existente, carga=carga)
            else:
                pacote = Pacote.objects.create(nome=nome_pacote, carga=carga)

        else:
            # ------- Fluxo original (com itens) -------
            pend_ids = [int(i.get("pendencia_id", 0) or 0) for i in itens]
            if any(pid <= 0 for pid in pend_ids):
                return JsonResponse({"erro": "Cada item deve conter pendencia_id válido."}, status=400)

            pendencias_qs = (PendenciasPacote.objects
                             .select_for_update()
                             .select_related("carreta_carga")
                             .filter(id__in=pend_ids))

            pend_por_id = {p.id: p for p in pendencias_qs}
            faltantes = [pid for pid in pend_ids if pid not in pend_por_id]
            if faltantes:
                return JsonResponse({"erro": f"Pendência(s) inexistente(s): {faltantes}"}, status=400)

            for p in pend_por_id.values():
                if getattr(p.carreta_carga, "carga_id", None) != carga.id:
                    return JsonResponse({
                        "erro": f"A pendência {p.id} não pertence à carga #{carga.id}"
                    }, status=400)

            for item in itens:
                try:
                    qtd = int(item.get("quantidade", 0))
                except (TypeError, ValueError):
                    return JsonResponse({"erro": "Quantidade inválida."}, status=400)
                if qtd <= 0:
                    return JsonResponse({"erro": "Quantidade deve ser maior que zero."}, status=400)

                pend_id = int(item.get("pendencia_id"))
                pend    = pend_por_id[pend_id]
                if (pend.qt_necessaria - qtd) < 0:
                    return JsonResponse({
                        "erro": (
                            f"O item {pend.codigo} - {pend.descricao} "
                            f"ultrapassa a quantidade pendente (disp: {pend.qt_necessaria}, req: {qtd})"
                        )
                    }, status=400)

            # >>> AQUI: escolher o pacote (existente OU novo)
            if pacote_existente:
                pacote = get_object_or_404(Pacote, id=pacote_existente, carga=carga)
            else:
                pacote = Pacote.objects.create(nome=nome_pacote, carga=carga)

            itens_criados = []
            for item in itens:
                pend_id = int(item["pendencia_id"])
                qtd     = int(item["quantidade"])
                pend    = pend_por_id[pend_id]

                itens_criados.append(ItemPacote(
                    pacote=pacote,
                    codigo_id=pend_id,   # mantém sua lógica atual
                    quantidade=qtd
                ))

                pend.qt_necessaria = pend.qt_necessaria - qtd
                pend.save(update_fields=["qt_necessaria"])

            ItemPacote.objects.bulk_create(itens_criados)

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
            itens_list.append({
                'id': item.id,
                'codigo_peca': getattr(cod_obj, 'codigo', None),
                'descricao': getattr(cod_obj, 'descricao', None),
                'quantidade': item.quantidade,
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

    return JsonResponse({
        'pacotes': dados,
        'status_carga': carga.stage,
        'cliente_carga': carga.cliente,
        'data_carga': carga.data_carga.strftime("%d/%m/%Y"),
        'carga': carga.carga,
        'carretas': carretas,
    })

def listar_pacotes_criados(request, id):
    # garante que a carga existe (opcional)
    print(id)
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
        carga.stage = 'despachado'
    else:
        return JsonResponse({'erro': 'Estágio atual inválido para avanço automático.'}, status=400)

    carga.save()

    return JsonResponse({
        'mensagem': 'Estágio alterado com sucesso!',
        'stage_antigo': stage_atual,
        'novo_stage': carga.stage,
    }, status=200)

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

    # data = json.loads(request.body)

    # id_pacote = data.get('pacote_id')
    # cliente = data.get('cliente')
    # data_carga = data.get('data_carga')
    # nome_pacote = data.get('nome_pacote')

    # # buscar observações do pacote
    # pacote = get_object_or_404(Pacote, id=id_pacote)
    # obs_qualidade = pacote.obs_qualidade
    # obs_expedicao = pacote.obs_expedicao


    # # juntar observações
    # if obs_qualidade and obs_expedicao:
    #     obs_completa = f"Expedição: {obs_expedicao} | Qualidade: {obs_qualidade}"
    # elif obs_qualidade:
    #     obs_completa = f"Qualidade: {obs_qualidade}"
    # elif obs_expedicao:
    #     obs_completa = f"Expedição: {obs_expedicao}"
    # else:
    #     obs_completa = "Sem observações"

    # chamar_impressora(cliente, data_carga, nome_pacote, obs_completa)
    chamar_impressora_qrcode()

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
        fotos = [{'url': img.arquivo.url, 'etapa': img.stage} for img in imagens]
        return JsonResponse({'fotos': fotos})
    return JsonResponse({'erro': 'Método não permitido'}, status=405)

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

    print(itens)

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
    esperadas = { (c or '').strip().upper() for c in esperadas_qs if c }

    # 2) Conjunto de carretas que "têm pendência" (aparecem em PendenciasPacote)
    com_pendencia_qs = (PendenciasPacote.objects
                        .filter(carreta_carga__carga_id=carga_id)
                        .values_list('carreta_carga__carreta', flat=True)
                        .distinct())
    com_pendencia = { (c or '').strip().upper() for c in com_pendencia_qs if c }

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

