"""
Logica de negocio da expedicao, extraida das views pra ser compartilhada
entre a tela web (JsonResponse) e a API mobile (DRF Response) sem
duplicar codigo. Funcoes puras: recebem/devolvem tipos Python simples ou
instancias de model, nunca HttpRequest/JsonResponse.
"""
from datetime import timedelta
from collections import defaultdict, Counter
from zoneinfo import ZoneInfo

from django.db import transaction
from django.db.models import Sum, Exists, OuterRef, Count, Q
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.timezone import localtime

from .models import (
    Carga, Pacote, ImagemPacote, PendenciasPacote, ItemPacote,
    FornecedorItemCarga, CarretaCarga, BipagemPacote,
)
from .utils import codigo_barras_pacote, pacote_id_do_codigo_barras

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
    """Cargas ativas (planejamento/verificação/bipagem) + despachadas recentes (últimos 30 dias).

    Os 30 dias contam da data do despacho - contando da criação, uma carga
    criada há mais de 30 dias sumia na hora em que era despachada. Cargas
    antigas sem data_despachado continuam usando a data de criação.
    """
    corte_despachado = timezone.now() - timedelta(days=30)
    cargas = list(
        Carga.objects
        .exclude(
            Q(stage='despachado') & (
                Q(data_despachado__lt=corte_despachado) |
                Q(data_despachado__isnull=True, data_criacao__lt=corte_despachado)
            )
        )
        .values('id', 'nome', 'carga', 'data_carga', 'cliente', 'obs_pacote', 'stage', 'data_criacao', 'data_despachado')
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

    # 1 query: pacotes bipados no carregamento por carga
    bipados_map = {
        r['pacote__carga_id']: r['total']
        for r in BipagemPacote.objects
            .filter(pacote__carga_id__in=carga_ids)
            .values('pacote__carga_id')
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
        carga['total_pacotes'] = total_pac
        carga['total_bipados'] = bipados_map.get(cid, 0)

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
        .annotate(
            tem_foto=Exists(ImagemPacote.objects.filter(pacote=OuterRef('pk'))),
            bipado=Exists(BipagemPacote.objects.filter(pacote=OuterRef('pk'))),
        )
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
            'bipado': bool(getattr(pacote, 'bipado', False)),
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
    if pacote.carga.stage in ('bipagem', 'despachado'):
        raise PacoteValidationError('Não é permitido excluir pacotes em bipagem ou despachados.')

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
    if pacote.carga.stage in ('bipagem', 'despachado'):
        raise PacoteValidationError('Não é permitido duplicar pacotes em cargas em bipagem ou despachadas.')

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


_PROXIMO_STAGE = {'planejamento': 'verificacao', 'verificacao': 'bipagem', 'bipagem': 'despachado'}


def verificar_avanco_stage(carga):
    """Diz se a carga pode ir pra próxima etapa e, se não, o que está faltando.

    Mesmas regras do botão "Avançar" da tela web (kanbans.js):
    - planejamento -> verificacao: sempre liberado (itens sem pacote só avisam)
    - verificacao -> bipagem: todos os pacotes com foto de verificação,
      nenhum item pendente e fornecedores de peças especiais informados
    - bipagem -> despachado: todos os pacotes bipados no carregamento
      (acontece sozinho ao bipar o último pacote)
    - despachado: última etapa
    """
    proximo = _PROXIMO_STAGE.get(carga.stage)
    bloqueios = []
    avisos = []

    total_pendente = int(
        PendenciasPacote.objects
        .filter(carreta_carga__carga_id=carga.id, qt_necessaria__gt=0)
        .aggregate(total=Coalesce(Sum('qt_necessaria'), 0))['total'] or 0
    )

    if carga.stage == 'planejamento' and total_pendente > 0:
        avisos.append(f'{total_pendente} item(ns) ainda sem pacote.')

    if carga.stage == 'verificacao':
        pacotes = Pacote.objects.filter(carga=carga)
        if not pacotes.exists():
            bloqueios.append('A carga não tem pacotes.')
        sem_foto = list(
            pacotes
            .exclude(pacote_imagem__stage='verificacao')
            .order_by('nome')
            .values_list('nome', flat=True)
        )
        if sem_foto:
            bloqueios.append(f'{len(sem_foto)} pacote(s) sem foto: {", ".join(sem_foto)}.')
        if total_pendente > 0:
            bloqueios.append(f'{total_pendente} item(ns) ainda sem pacote.')

        codigos_especiais = _detectar_codigos_especiais_da_carga(carga.id)
        if codigos_especiais:
            salvos = {(f.tipo, f.codigo): f.fornecedor for f in FornecedorItemCarga.objects.filter(carga=carga)}
            faltando = [
                f"{tipo} ({item['codigo']})"
                for tipo, itens in codigos_especiais.items()
                for item in itens
                if not salvos.get((tipo, item['codigo']), '').strip()
            ]
            if faltando:
                bloqueios.append(f'Informe o fornecedor de {", ".join(faltando)}.')

    if carga.stage == 'bipagem':
        total_pacotes = Pacote.objects.filter(carga=carga).count()
        total_bipados = BipagemPacote.objects.filter(pacote__carga=carga).count()
        if total_pacotes == 0:
            bloqueios.append('A carga não tem pacotes.')
        elif total_bipados < total_pacotes:
            bloqueios.append(f'Faltam {total_pacotes - total_bipados} pacote(s) para bipar ({total_bipados}/{total_pacotes}).')

    return {
        'stage_atual': carga.stage,
        'proximo_stage': proximo,
        'pode_avancar': proximo is not None and not bloqueios,
        'bloqueios': bloqueios,
        'avisos': avisos,
    }


def avancar_stage_service(carga):
    """Leva a carga pra próxima etapa. Levanta PacoteValidationError se
    alguma regra de verificar_avanco_stage bloquear."""
    requisitos = verificar_avanco_stage(carga)
    if requisitos['proximo_stage'] is None:
        raise PacoteValidationError('Estágio atual inválido para avanço automático.')
    if requisitos['bloqueios']:
        raise PacoteValidationError(' '.join(requisitos['bloqueios']))

    stage_antigo = carga.stage
    carga.stage = requisitos['proximo_stage']
    if carga.stage == 'despachado':
        carga.data_despachado = timezone.now()
    carga.save()

    return {
        'mensagem': 'Estágio alterado com sucesso!',
        'stage_antigo': stage_antigo,
        'novo_stage': carga.stage,
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


def status_bipagem_carga(carga):
    """Pacotes da carga com o código de barras de cada um e se já foi bipado.

    O app baixa essa lista ao abrir a tela de carregamento e valida as
    leituras localmente (resposta instantânea e funciona sem conexão).
    """
    pacotes = (
        Pacote.objects
        .filter(carga=carga)
        .select_related('bipagem__bipado_por__user')
        .annotate(total_itens=Count('itens'))
        .order_by('nome', 'id')
    )

    dados = []
    for pacote in pacotes:
        bipagem = getattr(pacote, 'bipagem', None)
        bipado_por = None
        if bipagem and bipagem.bipado_por:
            user = bipagem.bipado_por.user
            bipado_por = user.get_full_name() or user.username
        dados.append({
            'id': pacote.id,
            'nome': pacote.nome,
            'codigo_barras': codigo_barras_pacote(pacote.id),
            'total_itens': pacote.total_itens,
            'bipado': bipagem is not None,
            'data_bipagem': (
                localtime(bipagem.data_bipagem, ZoneInfo('America/Fortaleza')).strftime('%d/%m/%Y %H:%M')
                if bipagem else None
            ),
            'bipado_por': bipado_por,
        })

    total_bipados = sum(1 for p in dados if p['bipado'])
    return {
        'carga_id': carga.id,
        'stage': carga.stage,
        'total_pacotes': len(dados),
        'total_bipados': total_bipados,
        'completo': len(dados) > 0 and total_bipados == len(dados),
        'pacotes': dados,
    }


# A bipagem acontece no carregamento do caminhão, etapa própria entre a
# verificação e o despacho. Com 100% bipado a carga vai sozinha pra despachado.
STAGE_BIPAGEM = 'bipagem'
_MSG_FORA_DA_ETAPA = 'A bipagem só é liberada quando a carga está na etapa Bipagem.'


def bipar_pacote_service(carga, codigo, profile=None, data_bipagem=None):
    """Registra a leitura de uma etiqueta no carregamento da carga.

    Não levanta exceção pra leitura inválida: devolve um 'resultado' que o
    app usa pra dar o retorno ao operador (ok / duplicado / outra_carga /
    nao_encontrado / codigo_invalido / fora_da_etapa).
    """
    pacote_id = pacote_id_do_codigo_barras(codigo)
    if pacote_id is None:
        return {'resultado': 'codigo_invalido', 'mensagem': f'Código "{codigo}" não é de um pacote.'}

    if carga.stage != STAGE_BIPAGEM:
        return {'resultado': 'fora_da_etapa', 'mensagem': _MSG_FORA_DA_ETAPA, 'stage': carga.stage}

    pacote = Pacote.objects.select_related('carga').filter(id=pacote_id).first()
    if not pacote:
        return {'resultado': 'nao_encontrado', 'mensagem': 'Pacote não encontrado (pode ter sido excluído).'}

    if pacote.carga_id != carga.id:
        return {
            'resultado': 'outra_carga',
            'mensagem': f'Pacote {pacote.nome} é da carga {pacote.carga.nome} ({pacote.carga.cliente}).',
            'pacote_id': pacote.id,
        }

    bipagem, criado = BipagemPacote.objects.get_or_create(
        pacote=pacote,
        defaults={'bipado_por': profile, 'data_bipagem': data_bipagem or timezone.now()},
    )

    total_pacotes = Pacote.objects.filter(carga=carga).count()
    total_bipados = BipagemPacote.objects.filter(pacote__carga=carga).count()
    completo = total_pacotes > 0 and total_bipados == total_pacotes

    if completo:
        # update condicional: com dois aparelhos bipando os últimos pacotes
        # ao mesmo tempo, só um faz a transição
        Carga.objects.filter(id=carga.id, stage=STAGE_BIPAGEM).update(
            stage='despachado', data_despachado=timezone.now(),
        )
        carga.refresh_from_db(fields=['stage', 'data_despachado'])

    return {
        'resultado': 'ok' if criado else 'duplicado',
        'mensagem': f'Pacote {pacote.nome} ' + ('bipado.' if criado else 'já tinha sido bipado.'),
        'pacote_id': pacote.id,
        'total_pacotes': total_pacotes,
        'total_bipados': total_bipados,
        'completo': completo,
        'stage': carga.stage,
    }


def desfazer_bipagem_service(carga, pacote_id):
    """Remove a bipagem de um pacote da carga (leitura feita por engano)."""
    if carga.stage != STAGE_BIPAGEM:
        raise PacoteValidationError(_MSG_FORA_DA_ETAPA)
    BipagemPacote.objects.filter(pacote_id=pacote_id, pacote__carga=carga).delete()
    return status_bipagem_carga(carga)


def sugerir_pacote_service(carga, cobertura_minima=0.75):
    """Sugere um pacote a partir das pendencias disponiveis na carga.

    A sugestao parte sempre do que esta disponivel (nunca inventa item);
    o historico de pacotes de OUTRAS cargas com a mesma carreta e usado so
    pra confirmar que aquele agrupamento de pendencias e um padrao real
    (cobertura minima de itens do padrao historico presentes na pendencia
    atual). Entre os padroes confirmados, escolhe o de maior cobertura
    (desempate por numero de ocorrencias historicas e depois por
    quantidade de itens cobertos).

    Retorna None se nao houver pendencia ou nenhum padrao confirmado.
    """
    pendencias = list(
        PendenciasPacote.objects
        .filter(carreta_carga__carga_id=carga.id, qt_necessaria__gt=0)
        .select_related('carreta_carga')
    )
    if not pendencias:
        return None

    pendencias_por_carreta = defaultdict(list)
    for p in pendencias:
        pendencias_por_carreta[p.carreta_carga.carreta].append(p)

    melhor_score = None
    melhor_sugestao = None

    for carreta_codigo, pends in pendencias_por_carreta.items():
        # Se o mesmo codigo aparecer em mais de uma pendencia da carreta
        # (ex: duas carretas iguais na mesma carga), usa a de maior saldo.
        pendentes_map = {}
        for p in pends:
            atual = pendentes_map.get(p.codigo)
            if atual is None or (p.qt_necessaria or 0) > (atual.qt_necessaria or 0):
                pendentes_map[p.codigo] = p
        codigos_pendentes = set(pendentes_map.keys())
        if not codigos_pendentes:
            continue

        pacotes_historicos_ids = (
            Pacote.objects
            .filter(carga__carretas__carreta=carreta_codigo)
            .exclude(carga_id=carga.id)
            .values_list('id', flat=True)
            .distinct()
        )

        itens_historicos = (
            ItemPacote.objects
            .filter(pacote_id__in=pacotes_historicos_ids, codigo__isnull=False)
            .values('pacote_id', 'codigo__codigo', 'quantidade')
        )

        itens_por_pacote_historico = defaultdict(list)
        for row in itens_historicos:
            itens_por_pacote_historico[row['pacote_id']].append(
                (row['codigo__codigo'], row['quantidade'])
            )

        # Conta quantas vezes cada combinacao de codigos (fingerprint) se
        # repete entre os pacotes historicos dessa carreta.
        freq_fingerprint = Counter()
        exemplo_qtd_por_fingerprint = {}
        for lst in itens_por_pacote_historico.values():
            fp = frozenset(codigo for codigo, _ in lst)
            if not fp:
                continue
            freq_fingerprint[fp] += 1
            exemplo_qtd_por_fingerprint.setdefault(fp, dict(lst))

        for fp, ocorrencias in freq_fingerprint.items():
            intersecao = fp & codigos_pendentes
            if not intersecao:
                continue
            cobertura = len(intersecao) / len(fp)
            if cobertura < cobertura_minima:
                continue

            score = (round(cobertura, 4), ocorrencias, len(intersecao))
            if melhor_score is not None and score <= melhor_score:
                continue

            qtds_hist = exemplo_qtd_por_fingerprint[fp]
            itens_sugeridos = []
            for codigo in sorted(intersecao):
                pend = pendentes_map[codigo]
                qtd_sugerida = min(int(qtds_hist.get(codigo) or 1), int(pend.qt_necessaria or 0))
                if qtd_sugerida <= 0:
                    continue
                itens_sugeridos.append({
                    'pendencia_id': pend.id,
                    'codigo': pend.codigo,
                    'descricao': pend.descricao,
                    'quantidade': qtd_sugerida,
                })

            if not itens_sugeridos:
                continue

            melhor_score = score
            melhor_sugestao = {
                'carreta': carreta_codigo,
                'cobertura_percentual': round(cobertura * 100, 1),
                'ocorrencias_historicas': ocorrencias,
                'itens': itens_sugeridos,
            }

    return melhor_sugestao


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

    if carga.stage in ('bipagem', 'despachado'):
        raise PacoteValidationError("Não é permitido criar pacotes em cargas em bipagem ou despachadas.")

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
