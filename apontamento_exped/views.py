from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.views.decorators.http import require_http_methods
from django.db.models import Sum, Exists, OuterRef, Q
from django.db.models.functions import Coalesce

from cargas.utils import get_data_from_sheets,tratando_dados
from .models import Carga,ItemPacote,Pacote,VerificacaoPacote, CarretaCarga, ImagemPacote, PendenciasPacote, ItemPacote
from .utils import chamar_impressora, buscar_conjuntos_carreta, limpar_cor

import json
import boto3

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

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'erro': 'JSON inválido'}, status=400)

    data_carga      = data.get('data_carga')
    carga_nome      = data.get('carga_nome')
    cliente_codigo  = data.get('cliente_codigo')
    observacoes     = data.get('observacoes')
    itens           = data.get('itens', [])

    if not itens:
        return JsonResponse({'erro': 'Nenhum item informado'}, status=400)

    hora_atual = timezone.now().strftime("%H%M%S")

    # Cria Carga
    carga = Carga.objects.create(
        nome=f"{carga_nome}_{cliente_codigo}_{str(data_carga).replace('-', '')}_{hora_atual}",
        carga=carga_nome,
        data_carga=data_carga,
        cliente=cliente_codigo,
        obs_pacote=observacoes
    )

    # Lista de carretas limpas vindas dos itens
    lista_carretas = [limpar_cor(item.get('codigo_peca', '')) for item in itens]

    # Busca base de conjuntos para essas carretas e prepara DF
    base_conjuntos = buscar_conjuntos_carreta(lista_carretas)

    # Indexa por carreta para acesso rápido
    grupos_por_carreta = {k: g for k, g in base_conjuntos.groupby('CARRETA')}

    total_pendencias = 0
    created_carretas = 0

    # Loop para salvar CarretaCarga e Pendencias
    for item in itens:
        carreta_limpa = limpar_cor(item.get('codigo_peca', ''))
        quantidade_carreta = int(item.get('quantidade') or 0)
        cor = item.get('cor')

        # Cria a CarretaCarga
        carreta_carga_object = CarretaCarga.objects.create(
            carga=carga,
            carreta=carreta_limpa,
            quantidade=quantidade_carreta,
            cor=cor
        )
        created_carretas += 1

        df_comp = grupos_por_carreta.get(carreta_limpa)
        if df_comp is None or df_comp.empty:
            # Sem componentes mapeados para essa carreta
            continue

        pendencias = []
        for _, row in df_comp.iterrows():
            total_por_carreta = int(row['TOTAL'])
            if total_por_carreta <= 0 or quantidade_carreta <= 0:
                continue

            qt_necessaria = quantidade_carreta * total_por_carreta
            pendencias.append(PendenciasPacote(
                carreta_carga=carreta_carga_object,
                codigo=row['CODIGO_BASE'],
                descricao=row['DESCRICAO_LIMPA'],
                qt_necessaria=qt_necessaria
            ))

        if pendencias:
            PendenciasPacote.objects.bulk_create(pendencias)
            total_pendencias += len(pendencias)

    return JsonResponse({
        'mensagem': 'Caixa criada com sucesso!',
        'carga_id': carga.id,
        'carretas_criadas': created_carretas,
        'pendencias_criadas': total_pendencias,
    }, status=201)

def buscar_cargas(request):

    cargas = Carga.objects.all().values('id', 'nome', 'carga', 'data_carga', 'cliente', 'obs_pacote', 'stage', 'data_criacao')

    # verifica se todos os pacotes dessa carga contém foto
    for carga in cargas:
        pacotes = Pacote.objects.filter(carga_id=carga['id'])
        total_pacotes = pacotes.count()
        pacotes_com_foto_verificacao = ImagemPacote.objects.filter(pacote__in=pacotes, stage='verificacao').values('pacote').distinct().count()
        pacotes_com_foto_despachado = ImagemPacote.objects.filter(pacote__in=pacotes, stage='despachado').values('pacote').distinct().count()
        
        carga['todos_pacotes_tem_foto_verificacao'] = (total_pacotes > 0 and total_pacotes == pacotes_com_foto_verificacao)
        carga['todos_pacotes_tem_foto_despachado'] = (total_pacotes > 0 and total_pacotes == pacotes_com_foto_despachado)
        

    print(list(cargas))

    return JsonResponse(list(cargas), safe=False)

@csrf_exempt
@require_http_methods(["POST"])
def guardar_pacotes(request):
    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"erro": "JSON inválido"}, status=400)

    id_carga     = data.get("idCargaPacote")
    nome_pacote  = data.get("nomePacote")
    itens        = data.get("itens", [])

    # validações básicas
    if not id_carga:
        return JsonResponse({"erro": "idCargaPacote é obrigatório"}, status=400)
    if not nome_pacote:
        return JsonResponse({"erro": "nomePacote é obrigatório"}, status=400)
    if not itens:
        return JsonResponse({"erro": "O campo de itens precisa ser preenchido."}, status=400)

    # carrega a carga
    carga = get_object_or_404(Carga, id=id_carga)

    # tudo-ou-nada
    with transaction.atomic():
        # bloqueia as pendências que serão usadas para evitar corrida
        # mapeia por id para validar/atualizar
        pend_ids = [int(i.get("pendencia_id", 0) or 0) for i in itens]
        if any(pid <= 0 for pid in pend_ids):
            return JsonResponse({"erro": "Cada item deve conter pendencia_id válido."}, status=400)

        pendencias_qs = (PendenciasPacote.objects
                         .select_for_update()
                         .select_related("carreta_carga")
                         .filter(id__in=pend_ids))

        # índice rápido por id
        pend_por_id = {p.id: p for p in pendencias_qs}

        # valida existência de todas as pendências
        faltantes = [pid for pid in pend_ids if pid not in pend_por_id]
        if faltantes:
            return JsonResponse({"erro": f"Pendência(s) inexistente(s): {faltantes}"}, status=400)

        # valida que todas pertencem à mesma carga
        for p in pend_por_id.values():
            if getattr(p.carreta_carga, "carga_id", None) != carga.id:
                return JsonResponse({
                    "erro": f"A pendência {p.id} não pertence à carga #{carga.id}"
                }, status=400)

        # valida quantidades
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

        # se passou nas validações, cria o pacote
        pacote = Pacote.objects.create(
            nome=nome_pacote,
            carga=carga,
        )

        # cria itens + atualiza pendências
        itens_criados = []
        for item in itens:
            pend_id = int(item["pendencia_id"])
            qtd     = int(item["quantidade"])
            pend    = pend_por_id[pend_id]

            itens_criados.append(ItemPacote(
                pacote=pacote,
                codigo_id=pend_id,          # confirme se este campo é FK certa
                quantidade=qtd
            ))

            # debita pendência
            pend.qt_necessaria = pend.qt_necessaria - qtd
            pend.save(update_fields=["qt_necessaria"])

        # bulk_create para eficiência
        ItemPacote.objects.bulk_create(itens_criados)

    return JsonResponse({
        "mensagem": "Pacote criado com sucesso!",
        "pacote_id": pacote.id
    }, status=201)

def buscar_pacotes_carga(request, id):
    carga = get_object_or_404(Carga, id=id)

    # Anota se tem foto com subquery (evita N chamadas .exists())
    pacotes_qs = (
        Pacote.objects
        .filter(carga=carga)
        .annotate(
            tem_foto=Exists(
                ImagemPacote.objects.filter(pacote=OuterRef('pk'))
            )
        )
        .order_by('id')
        .prefetch_related(
            # prefetch dos itens; dentro dele, carregamos a FK 'codigo' via select_related
            # se seu related_name for diferente de 'itens', ajuste aqui
            # em alguns casos vale usar Prefetch para customizar:
            # Prefetch('itens', queryset=ItemPacote.objects.select_related('codigo'))
            'itens'
        )
    )

    # Para garantir que acessar item.codigo não gere N+1:
    # carregamos select_related na hora de iterar os itens
    dados = []
    for pacote in pacotes_qs:
        itens_list = []
        # se quiser eliminar N+1 aqui, pode fazer:
        itens = pacote.itens.all().select_related('codigo')

        for item in itens:
            # item.codigo deve ser o objeto relacionado (FK)
            cod_obj = getattr(item, 'codigo', None)
            codigo_peca = getattr(cod_obj, 'codigo', None)
            descricao   = getattr(cod_obj, 'descricao', None)

            itens_list.append({
                'id': item.id,
                'codigo_peca': codigo_peca,
                'descricao': descricao,
                # 'cor': item.cor,  # se existir
                'quantidade': item.quantidade,
            })

        # datas em ISO 8601 (ou padronize como preferir)
        data_criacao_iso = pacote.data_criacao.isoformat() if getattr(pacote, 'data_criacao', None) else None
        data_carga_iso   = carga.data_carga.isoformat() if getattr(carga, 'data_carga', None) else None

        dados.append({
            'id': pacote.id,
            'nome': pacote.nome,
            'status_expedicao': pacote.status_confirmacao_expedicao,
            'status_qualidade': pacote.status_confirmacao_qualidade,
            'data_criacao': data_criacao_iso,
            'itens': itens_list,
            'cliente': carga.cliente,
            'data_carga': data_carga_iso,
            'tem_foto': bool(getattr(pacote, 'tem_foto', False)),
        })

    return JsonResponse({
        'pacotes': dados,
        'status_carga': carga.stage,
        'cliente_carga': carga.cliente,
        'data_carga': carga.data_carga.isoformat() if getattr(carga, 'data_carga', None) else None,
        'carga': carga.carga,
    })

@csrf_exempt
def alterar_stage(request, id):
    if request.method != 'POST':
        return JsonResponse({'erro': 'Método não permitido'}, status=405)

    # novo_stage = data.get('stage', None)
    carga = get_object_or_404(Carga, id=id)
    stage_atual = carga.stage

    print(stage_atual)

    # Regras de avanço de estágio
    if stage_atual == 'planejamento':
    
        # VERIFICA SE TODOS PACOTES FORAM CRIADOS
        total = (
            PendenciasPacote.objects
            .filter(carreta_carga__carga_id=id, qt_necessaria__gt=0)
            .aggregate(total=Coalesce(Sum('qt_necessaria'), 0))
            ['total']
        )
        
        if total > 0:
            return JsonResponse({'erro': 'Forme todos os pacotes antes de passar para próximo estágio.'}, status=400)

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
        'novo_stage': carga.stage
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

    return JsonResponse({'status': 'ok'})

@csrf_exempt
def salvar_foto(request):
    if request.method == 'POST' and request.FILES.get('foto'):

        foto = request.FILES['foto']
        pacote_id = request.POST.get('pacote')

        pacote_object = get_object_or_404(Pacote, id=pacote_id)

        # stage atual do pacote
        stage = pacote_object.carga.stage

        # Gera nome customizado
        extensao = foto.name.split('.')[-1]  # preserva extensão original
        nome_arquivo = f"pacote_{pacote_id}_{timezone.now().strftime('%Y%m%d%H%M%S')}.{extensao}"

        # Sobrescreve o nome do arquivo
        foto.name = nome_arquivo

        imagem = ImagemPacote.objects.create(
            pacote=pacote_object,
            arquivo=foto,
            stage=stage
        )

        return JsonResponse({'status': 'ok', 'url': imagem.arquivo.url})

    return JsonResponse({'erro': 'Foto não recebida'}, status=400)

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

