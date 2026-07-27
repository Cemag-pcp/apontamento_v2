"""
Logica de negocio da expedicao, extraida das views pra ser compartilhada
entre a tela web (JsonResponse) e a API mobile (DRF Response) sem
duplicar codigo. Funcoes puras: recebem/devolvem tipos Python simples ou
instancias de model, nunca HttpRequest/JsonResponse.
"""
from datetime import timedelta
from collections import defaultdict
from zoneinfo import ZoneInfo

from django.db import transaction
from django.db.models import Sum, Exists, OuterRef, Count
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.timezone import localtime

from .models import (
    Carga, Pacote, ImagemPacote, PendenciasPacote, ItemPacote,
    FornecedorItemCarga, CarretaCarga,
)

# Tipos especiais de peças que exigem fornecedor informado antes de avançar da verificação
_TIPOS_ESPECIAIS = ['Pneu', 'Cilindro', 'Roda']


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


class FotoObrigatoriaError(Exception):
    """Levantada quando tenta confirmar um pacote em verificacao sem foto anexada."""
    pass


class PacoteValidationError(Exception):
    """Levantada quando os dados pra criar/atualizar um pacote sao invalidos."""
    pass


def listar_cargas_ativas():
    """Cargas ativas (planejamento/verificação) + despachadas recentes (últimos 30 dias)."""
    corte_despachado = timezone.now() - timedelta(days=30)
    cargas = list(
        Carga.objects
        .exclude(stage='despachado', data_criacao__lt=corte_despachado)
        .values('id', 'nome', 'carga', 'data_carga', 'cliente', 'obs_pacote', 'stage', 'data_criacao')
    )

    if not cargas:
        return []

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

    return cargas


def salvar_fornecedores_carga(carga, entries):
    """Salva/atualiza os fornecedores por codigo de peca especial de uma carga.

    entries: lista de dicts {tipo, codigo, fornecedor}.
    """
    with transaction.atomic():
        for entry in entries:
            tipo = (entry.get('tipo') or '').strip()
            codigo = (entry.get('codigo') or '').strip()
            fornecedor = (entry.get('fornecedor') or '').strip()
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
    return {'mensagem': 'Fornecedores salvos com sucesso!', 'fornecedores_pendentes': faltando}


def _carga_tem_carreta_bb(carretas):
    """Verifica se alguma carreta da carga tem o token 'BB' na descricao
    (ex: 'FT10500 SS T R15,5 BB M23') - regra que libera adicionar o item
    'Cardan' como item fora do planejado direto, sem precisar digitar.
    """
    for c in carretas:
        tokens = (c.get('carreta') or '').upper().split()
        if 'BB' in tokens:
            return True
    return False


def detalhar_pacotes_da_carga(carga):
    """Pacotes + itens de uma carga, junto com carretas e (se em verificação) fornecedores."""
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

    carretas = list(
        CarretaCarga.objects
        .filter(carga=carga)
        .values('id', 'carreta', 'quantidade', 'cor')
        .order_by('carreta', 'id')
    )

    # Códigos especiais e fornecedores (só relevante no estágio verificação)
    codigos_especiais = {}
    fornecedores = {}
    if carga.stage == 'verificacao':
        codigos_especiais = _detectar_codigos_especiais_da_carga(carga.id)
        salvos = FornecedorItemCarga.objects.filter(carga=carga)
        fornecedores = {f"{f.tipo}_{f.codigo}": f.fornecedor for f in salvos}

    return {
        'pacotes': dados,
        'status_carga': carga.stage,
        'cliente_carga': carga.cliente,
        'data_carga': carga.data_carga.strftime("%d/%m/%Y"),
        'carga': carga.carga,
        'carretas': carretas,
        'codigos_especiais': codigos_especiais,
        'fornecedores': fornecedores,
        'possui_carreta_bb': _carga_tem_carreta_bb(carretas),
    }


def salvar_foto_pacote(pacote, arquivo):
    """Anexa uma foto (UploadedFile) a um pacote e devolve o status atualizado da carga."""
    carga = pacote.carga
    id_carga = carga.id
    stage = carga.stage

    # Gera nome customizado (preserva extensão)
    extensao = (arquivo.name.rsplit('.', 1)[-1] if '.' in arquivo.name else 'jpg')
    nome_arquivo = f"pacote_{pacote.id}_{timezone.now().strftime('%Y%m%d%H%M%S')}.{extensao}"
    arquivo.name = nome_arquivo

    imagem = ImagemPacote.objects.create(
        pacote=pacote,
        arquivo=arquivo,
        stage=stage
    )

    # ---- Cálculos de status da carga (mesmo padrão de listar_cargas_ativas) ----
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

    return {
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
    }


def listar_fotos_pacote(pacote_id):
    imagens = ImagemPacote.objects.filter(pacote_id=pacote_id)
    return [{'id': img.id, 'url': img.arquivo.url, 'etapa': img.stage} for img in imagens]


def excluir_foto_pacote(imagem):
    """Remove uma ImagemPacote (arquivo + registro)."""
    imagem.arquivo.delete(save=False)
    imagem.delete()


def excluir_carga_service(carga):
    """Remove o carregamento e todas as relacoes em cascata (carretas, pacotes, itens, imagens)."""
    carga.delete()


def atualizar_quantidade_item_service(item, nova_quantidade):
    """Atualiza a quantidade de um item dentro do pacote.

    Permitido apenas nos estagios planejamento e verificacao. Se aumentar,
    verifica saldo pendente disponivel; se diminuir, devolve a diferenca
    pra pendencia. Levanta PacoteValidationError pra qualquer violacao.
    """
    if nova_quantidade <= 0:
        raise PacoteValidationError('Quantidade deve ser maior que zero.')

    carga = item.pacote.carga
    if carga.stage not in ('planejamento', 'verificacao'):
        raise PacoteValidationError('Alteração permitida apenas em planejamento ou verificação.')

    pend = getattr(item, 'codigo', None)
    atual = int(item.quantidade or 0)
    delta = nova_quantidade - atual

    with transaction.atomic():
        if pend and delta > 0:
            disponivel = int(pend.qt_necessaria or 0)
            if disponivel <= 0:
                raise PacoteValidationError('Este item não possui saldo pendente para aumentar quantidade.')
            if disponivel < delta:
                raise PacoteValidationError(f'Quantidade indisponível. Restam {disponivel}.')
            pend.qt_necessaria = disponivel - delta
            pend.save(update_fields=['qt_necessaria'])
        elif pend and delta < 0:
            pend.qt_necessaria = int(pend.qt_necessaria or 0) + abs(delta)
            pend.save(update_fields=['qt_necessaria'])

        item.quantidade = nova_quantidade
        item.save(update_fields=['quantidade'])

    return {
        'mensagem': 'Quantidade atualizada com sucesso.',
        'item_id': item.id,
        'nova_quantidade': nova_quantidade,
        'pendente': int(pend.qt_necessaria or 0) if pend else None,
        'carga_id': carga.id,
        'stage': carga.stage,
    }


def excluir_item_pacote_service(item):
    """Remove um item do pacote e devolve a quantidade pra pendencia.

    Permitido apenas nos estagios planejamento ou verificacao.
    """
    carga = item.pacote.carga
    if carga.stage not in ('planejamento', 'verificacao'):
        raise PacoteValidationError('Exclusão permitida apenas em planejamento ou verificacao.')

    pend = item.codigo
    qtd_item = int(item.quantidade or 0)

    with transaction.atomic():
        if pend:
            pend.qt_necessaria = int(pend.qt_necessaria or 0) + qtd_item
            pend.save(update_fields=['qt_necessaria'])
        item.delete()

    return {
        'mensagem': 'Item removido do pacote.',
        'carga_id': carga.id,
        'stage': carga.stage,
        'pendente': int(pend.qt_necessaria or 0) if pend else 0,
    }


def mover_item_pacote(item, pacote_destino):
    """Move um item pra outro pacote (mesma carga, na pratica - quem chama garante)."""
    item.pacote = pacote_destino
    item.save(update_fields=['pacote'])
    return {'mensagem': 'Pacote alterado com sucesso.'}


def deletar_pacote_service(pacote):
    """Exclui o pacote e devolve as quantidades dos itens pras pendencias.

    Levanta PacoteValidationError se a carga ja estiver despachada - cada
    caller (view classica / DRF) formata a resposta de erro no seu idioma.
    """
    if pacote.carga.stage == 'despachado':
        raise PacoteValidationError('Não é permitido excluir pacotes despachados.')

    itens = list(ItemPacote.objects.filter(pacote=pacote).select_related('codigo'))

    with transaction.atomic():
        for item in itens:
            pend = item.codigo
            if pend:
                pend.qt_necessaria = (pend.qt_necessaria or 0) + (item.quantidade or 0)
                pend.save(update_fields=['qt_necessaria'])
        carga_id = pacote.carga_id
        stage = pacote.carga.stage
        pacote.delete()

    return {
        'mensagem': 'Pacote excluído com sucesso.',
        'carga_id': carga_id,
        'stage': stage,
    }


def duplicar_pacote_service(pacote):
    """Duplica um pacote reaproveitando os itens, respeitando o saldo pendente.

    O novo nome recebe sufixo incremental (.1, .2, ...). Levanta
    PacoteValidationError se nao houver itens validos pra duplicar.
    """
    itens_origem = list(ItemPacote.objects.filter(pacote=pacote).select_related('codigo'))
    if not itens_origem:
        raise PacoteValidationError('Pacote sem itens para duplicar.')

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
            raise PacoteValidationError('Sem itens válidos para duplicar neste pacote.')

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

    return {
        'mensagem': 'Pacote duplicado com sucesso.',
        'pacote_id': novo_pacote.id,
        'nome': novo_pacote.nome,
    }


def confirmar_pacote_service(pacote, observacao):
    """Confirma qualidade/expedição de um pacote conforme o stage atual da carga.

    Levanta FotoObrigatoriaError se o pacote estiver em verificacao sem
    nenhuma foto anexada - cada caller (view classica / DRF) decide como
    formatar essa resposta de erro.
    """
    stage = pacote.carga.stage

    if stage == 'verificacao':
        imagens = ImagemPacote.objects.filter(pacote=pacote, stage=stage)
        if not imagens.exists():
            raise FotoObrigatoriaError('É necessário anexar ao menos uma foto antes de confirmar o pacote.')

    if stage == 'apontamento':
        pacote.status_confirmacao_expedicao = 'ok'
        pacote.data_confirmacao_expedicao = timezone.now()
        pacote.obs_expedicao = observacao
    elif stage == 'verificacao':
        pacote.status_confirmacao_qualidade = 'ok'
        pacote.data_confirmacao_qualidade = timezone.now()
        pacote.obs_qualidade = observacao

    pacote.save()

    return {'mensagem': 'Pacote confirmado com sucesso!'}


def listar_pendencias_carga(carga_id):
    """Itens pendentes (qt_necessaria > 0) do carregamento informado (carga_id)."""
    qs = (
        PendenciasPacote.objects
        .filter(
            carreta_carga__carga_id=int(carga_id),
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

    return {
        "total_itens": len(itens),
        "itens": itens
    }


def criar_ou_atualizar_pacote(carga, nome_pacote=None, pacote_existente_id=None,
                               itens=None, itens_fora_planejado=None):
    """Cria um pacote novo (ou usa um existente) e anexa itens das pendencias
    e/ou itens fora do planejado (codigo/descricao livres).

    Levanta PacoteValidationError com a mensagem apropriada pra qualquer
    problema de validacao - cada caller (view classica / DRF) formata a
    resposta de erro no seu proprio idioma. Http404 (pacote existente
    inexistente) propaga normalmente, tratado pelo framework em ambos os
    casos.
    """
    itens = itens or []
    itens_fora_planejado = itens_fora_planejado or []

    if not nome_pacote and not pacote_existente_id:
        raise PacoteValidationError("nomePacote é obrigatório")

    with transaction.atomic():
        if pacote_existente_id:
            pacote = get_object_or_404(Pacote, id=pacote_existente_id, carga=carga)
        else:
            pacote = Pacote.objects.create(nome=nome_pacote, carga=carga)

        if itens:
            pend_ids = [int(i.get("pendencia_id", 0) or 0) for i in itens]
            if any(pid <= 0 for pid in pend_ids):
                raise PacoteValidationError("Cada item deve conter pendencia_id válido.")

            pendencias_qs = (
                PendenciasPacote.objects
                .select_for_update()
                .select_related("carreta_carga")
                .filter(id__in=pend_ids)
            )

            pend_por_id = {p.id: p for p in pendencias_qs}
            faltantes = [pid for pid in pend_ids if pid not in pend_por_id]
            if faltantes:
                raise PacoteValidationError(f"Pendência(s) inexistente(s): {faltantes}")

            for p in pend_por_id.values():
                if getattr(p.carreta_carga, "carga_id", None) != carga.id:
                    raise PacoteValidationError(f"A pendência {p.id} não pertence à carga #{carga.id}")

            itens_criados = []
            for item in itens:
                try:
                    qtd = int(item.get("quantidade", 0))
                except (TypeError, ValueError):
                    raise PacoteValidationError("Quantidade inválida.")
                if qtd <= 0:
                    raise PacoteValidationError("Quantidade deve ser maior que zero.")

                pend_id = int(item.get("pendencia_id"))
                pend = pend_por_id[pend_id]
                saldo_pendente = int(pend.qt_necessaria or 0)
                if saldo_pendente <= 0:
                    raise PacoteValidationError(
                        f"O item {pend.codigo} - {pend.descricao} não possui saldo pendente para empacotar."
                    )
                if qtd > saldo_pendente:
                    raise PacoteValidationError(
                        f"O item {pend.codigo} - {pend.descricao} "
                        f"ultrapassa a quantidade pendente (disp: {saldo_pendente}, req: {qtd})"
                    )

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
                    raise PacoteValidationError("Quantidade inválida para item fora do planejado.")

                if not codigo or not descricao:
                    raise PacoteValidationError("Código e descrição são obrigatórios para item fora do planejado.")
                if qtd <= 0:
                    raise PacoteValidationError("Quantidade deve ser maior que zero para item fora do planejado.")

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

    # ---- resumo apos a criacao (mesmo padrao de salvar_foto_pacote) ----
    id_carga = carga.id
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

    return {
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
    }
