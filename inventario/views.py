import json
import logging
import re
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET
from django.utils import timezone
from django.utils.timezone import localtime
from django.views.decorators.http import require_POST

from .importacao import ErroImportacao, ler_planilha_contagem
from .models import CadastroInventario, Inventario, ItemContagem

logger = logging.getLogger(__name__)

ROTA_INVENTARIO = 'inventario'

# Menu de dentro do inventário: aba -> (rótulo, ícone, template)
ABAS_INVENTARIO = {
    'geral': ('Visão geral', 'bi-house', 'inventario/abas/geral.html'),
    'cadastro': ('Cadastro', 'bi-person-lines-fill', 'inventario/abas/cadastro.html'),
    'contagem': ('Lista de contagem', 'bi-list-check', 'inventario/abas/contagem.html'),
}

TAMANHO_MAXIMO_PLANILHA = 10 * 1024 * 1024  # 10 MB


def tem_acesso_inventario(user):
    """Mesma regra do RotaAccessMiddleware: admin e PCP entram em tudo; os
    demais precisam da permissão "inventario". As APIs passam livres pelo
    middleware, então elas conferem aqui."""
    profile = getattr(user, 'profile', None)
    if profile is None:
        return user.is_superuser
    if (profile.tipo_acesso or '').lower() in {'admin', 'pcp'}:
        return True
    return profile.tem_acesso(ROTA_INVENTARIO)


def _texto(valor):
    """Tira espaços das pontas e espaços repetidos no meio."""
    return ' '.join(str(valor or '').split())


def _ler_json(request):
    try:
        return json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return None


def _serializar(inventario):
    return {
        'id': inventario.id,
        'nome': inventario.nome,
        'descricao': inventario.descricao,
        'status': inventario.status,
        'status_display': inventario.get_status_display(),
        'criado_por': inventario.criado_por.username if inventario.criado_por else '',
        'criado_em': localtime(inventario.criado_em).strftime('%d/%m/%Y %H:%M'),
    }


def _serializar_cadastro(cadastro):
    return {
        'id': cadastro.id,
        'setor': cadastro.setor,
        'celula': cadastro.celula,
        'responsavel': cadastro.responsavel,
        'pendente': cadastro.pendente,
        'criado_por': cadastro.criado_por.username if cadastro.criado_por else '',
        'criado_em': localtime(cadastro.criado_em).strftime('%d/%m/%Y %H:%M'),
    }


def _formatar_quantidade(valor):
    """Decimal('12.500') -> '12.5'; None -> None."""
    if valor is None:
        return None
    return f'{valor.normalize():f}'


def _serializar_item(item):
    return {
        'id': item.id,
        'setor': item.setor,
        'celula': item.celula,
        'codigo': item.codigo,
        'descricao': item.descricao,
        'quantidade': _formatar_quantidade(item.quantidade),
        # horário de Brasília (TIME_ZONE do projeto)
        'contado_em': localtime(item.contado_em).strftime('%d/%m/%Y %H:%M') if item.contado_em else '',
        'fora_da_lista': item.fora_da_lista,
        'observacao': item.observacao,
        'foto': item.foto.url if item.foto else '',
        'recontagem_habilitada': item.recontagem_habilitada,
        'recontagem': _formatar_quantidade(item.recontagem),
        'recontado_em': localtime(item.recontado_em).strftime('%d/%m/%Y %H:%M') if item.recontado_em else '',
    }


def _serializar_item_publico(item):
    """Para o link público: na recontagem a primeira contagem não aparece,
    para não influenciar quem está recontando."""
    dados = _serializar_item(item)
    if item.recontagem_habilitada:
        dados['quantidade'] = None
        dados['contado_em'] = ''
    return dados


def _link_contagem(request, inventario):
    return request.build_absolute_uri(
        reverse('inventario:contagem_publica', args=[inventario.token_contagem])
    )


def _percentual(contados, total):
    return round(contados * 100 / total) if total else 0


def _progresso_contagem(inventario):
    """Contados x total da lista importada, por setor e por célula, para os
    gráficos da visão geral. Os lotes fora da lista entram só como contagem
    à parte por setor (não fazem parte do total)."""
    linhas = (
        inventario.itens_contagem.filter(fora_da_lista=False)
        .values('setor', 'celula')
        .annotate(total=Count('id'), contados=Count('quantidade'))
    )
    fora_por_setor = dict(
        inventario.itens_contagem.filter(fora_da_lista=True)
        .values('setor').annotate(n=Count('id')).values_list('setor', 'n')
    )

    setores = {}
    for linha in linhas:
        setor = setores.setdefault(linha['setor'], {
            'nome': linha['setor'], 'total': 0, 'contados': 0, 'celulas': [],
        })
        setor['total'] += linha['total']
        setor['contados'] += linha['contados']
        setor['celulas'].append({
            'nome': linha['celula'],
            'total': linha['total'],
            'contados': linha['contados'],
            'faltam': linha['total'] - linha['contados'],
            'pct': _percentual(linha['contados'], linha['total']),
        })

    lista = sorted(setores.values(), key=lambda s: s['nome'].lower())
    for setor in lista:
        setor['faltam'] = setor['total'] - setor['contados']
        setor['pct'] = _percentual(setor['contados'], setor['total'])
        setor['fora'] = fora_por_setor.get(setor['nome'], 0)
        # células mais atrasadas primeiro: é onde precisa de gente
        setor['celulas'].sort(key=lambda c: (c['pct'], c['nome'].lower()))

    total = sum(s['total'] for s in lista)
    contados = sum(s['contados'] for s in lista)
    return {
        'setores': lista,
        'total': total,
        'contados': contados,
        'faltam': total - contados,
        'pct': _percentual(contados, total),
        'fora': sum(fora_por_setor.values()),
        'celulas_completas': sum(1 for s in lista for c in s['celulas'] if c['total'] and c['faltam'] == 0),
        'celulas_total': sum(len(s['celulas']) for s in lista),
    }


def _qrcode_svg(texto):
    """QR code em SVG (inline na página, sem depender de CDN)."""
    import qrcode
    from qrcode.image.svg import SvgPathImage

    imagem = qrcode.make(texto, image_factory=SvgPathImage, box_size=10, border=2)
    svg = imagem.to_string(encoding='unicode')
    return re.sub(r'^<\?xml[^>]*\?>\s*', '', svg)


@login_required
def inventario_home(request):
    """Sem ?id: lista de inventários. Com ?id=<id>[&aba=<aba>]: dentro do
    inventário. Tudo numa rota só, porque o RotaAccessMiddleware compara o
    caminho exato com as rotas cadastradas (a query string não conta)."""
    id_inventario = request.GET.get('id')
    if not id_inventario:
        inventarios = Inventario.objects.select_related('criado_por')
        return render(request, 'inventario/inventarios.html', {'inventarios': inventarios})

    if not id_inventario.isdigit():
        return redirect('inventario:home')
    inventario = get_object_or_404(Inventario.objects.select_related('criado_por'), pk=id_inventario)

    aba = request.GET.get('aba', 'geral')
    if aba not in ABAS_INVENTARIO:
        aba = 'geral'

    contexto = {
        'inventario': inventario,
        'aba': aba,
        'abas': [(chave, rotulo, icone) for chave, (rotulo, icone, _) in ABAS_INVENTARIO.items()],
        'template_aba': ABAS_INVENTARIO[aba][2],
        'total_cadastros': inventario.cadastros.count(),
        'total_pendentes': inventario.cadastros.filter(responsavel='').count(),
        'total_itens': inventario.itens_contagem.filter(fora_da_lista=False).count(),
        'total_contados': inventario.itens_contagem.filter(fora_da_lista=False, quantidade__isnull=False).count(),
        'total_fora_da_lista': inventario.itens_contagem.filter(fora_da_lista=True).count(),
        'link_contagem': _link_contagem(request, inventario),
    }
    if aba == 'cadastro':
        contexto['cadastros'] = [
            _serializar_cadastro(c) for c in inventario.cadastros.select_related('criado_por')
        ]
    elif aba == 'contagem':
        contexto['itens'] = [_serializar_item(i) for i in inventario.itens_contagem.all()]
    elif aba == 'geral':
        contexto['qrcode_contagem'] = _qrcode_svg(contexto['link_contagem'])
        contexto['progresso'] = _progresso_contagem(inventario)
    return render(request, 'inventario/inventario_detalhe.html', contexto)


@login_required
@require_POST
def criar_inventario(request):
    if not tem_acesso_inventario(request.user):
        return JsonResponse({'error': 'Sem permissão para criar inventário.'}, status=403)

    dados = _ler_json(request)
    if dados is None:
        return JsonResponse({'error': 'Dados inválidos.'}, status=400)

    nome = _texto(dados.get('nome'))
    descricao = str(dados.get('descricao') or '').strip()
    if not nome:
        return JsonResponse({'error': 'Informe o nome do inventário.'}, status=400)
    if len(nome) > 100:
        return JsonResponse({'error': 'O nome pode ter no máximo 100 caracteres.'}, status=400)
    if Inventario.objects.filter(nome__iexact=nome).exists():
        return JsonResponse({'error': f'Já existe um inventário chamado "{nome}".'}, status=400)

    inventario = Inventario.objects.create(nome=nome, descricao=descricao, criado_por=request.user)
    return JsonResponse({'inventario': _serializar(inventario)}, status=201)


@login_required
@require_POST
def criar_cadastro(request, inventario_id):
    if not tem_acesso_inventario(request.user):
        return JsonResponse({'error': 'Sem permissão para alterar o inventário.'}, status=403)
    inventario = get_object_or_404(Inventario, pk=inventario_id)

    dados = _ler_json(request)
    if dados is None:
        return JsonResponse({'error': 'Dados inválidos.'}, status=400)

    campos = {
        'setor': (_texto(dados.get('setor')), 'Setor', 100),
        'celula': (_texto(dados.get('celula')), 'Célula', 100),
        'responsavel': (_texto(dados.get('responsavel')), 'Responsável', 150),
    }
    for valor, rotulo, limite in campos.values():
        if not valor:
            return JsonResponse({'error': f'Informe o campo {rotulo}.'}, status=400)
        if len(valor) > limite:
            return JsonResponse({'error': f'{rotulo} pode ter no máximo {limite} caracteres.'}, status=400)

    setor, celula, responsavel = (campos[c][0] for c in ('setor', 'celula', 'responsavel'))
    mensagem_repetido = f'Já existe o cadastro {setor} / {celula} / {responsavel} neste inventário.'
    if inventario.cadastros.filter(
        setor__iexact=setor, celula__iexact=celula, responsavel__iexact=responsavel
    ).exists():
        return JsonResponse({'error': mensagem_repetido}, status=400)

    # Setor + célula pendente (veio da lista de contagem): preenche o
    # responsável nele em vez de criar outra linha.
    pendente = inventario.cadastros.filter(
        setor__iexact=setor, celula__iexact=celula, responsavel=''
    ).first()
    if pendente:
        pendente.responsavel = responsavel
        pendente.save(update_fields=['responsavel'])
        return JsonResponse({'cadastro': _serializar_cadastro(pendente), 'preencheu_pendente': True})

    try:
        # a constraint do banco segura dois cadastros iguais ao mesmo tempo
        with transaction.atomic():
            cadastro = CadastroInventario.objects.create(
                inventario=inventario,
                setor=setor,
                celula=celula,
                responsavel=responsavel,
                criado_por=request.user,
            )
    except IntegrityError:
        return JsonResponse({'error': mensagem_repetido}, status=400)

    return JsonResponse({'cadastro': _serializar_cadastro(cadastro)}, status=201)


@login_required
@require_POST
def definir_responsavel(request, cadastro_id):
    """Define (ou troca) o responsável de um setor + célula, usado
    principalmente para resolver os pendentes da importação."""
    if not tem_acesso_inventario(request.user):
        return JsonResponse({'error': 'Sem permissão para alterar o inventário.'}, status=403)
    cadastro = get_object_or_404(CadastroInventario, pk=cadastro_id)

    dados = _ler_json(request)
    if dados is None:
        return JsonResponse({'error': 'Dados inválidos.'}, status=400)
    responsavel = _texto(dados.get('responsavel'))
    if not responsavel:
        return JsonResponse({'error': 'Informe o responsável.'}, status=400)
    if len(responsavel) > 150:
        return JsonResponse({'error': 'Responsável pode ter no máximo 150 caracteres.'}, status=400)

    mensagem_repetido = (
        f'Já existe o cadastro {cadastro.setor} / {cadastro.celula} / {responsavel} neste inventário.'
    )
    if CadastroInventario.objects.filter(
        inventario_id=cadastro.inventario_id,
        setor__iexact=cadastro.setor,
        celula__iexact=cadastro.celula,
        responsavel__iexact=responsavel,
    ).exclude(pk=cadastro.pk).exists():
        return JsonResponse({'error': mensagem_repetido}, status=400)

    cadastro.responsavel = responsavel
    try:
        with transaction.atomic():
            cadastro.save(update_fields=['responsavel'])
    except IntegrityError:
        return JsonResponse({'error': mensagem_repetido}, status=400)
    return JsonResponse({'cadastro': _serializar_cadastro(cadastro)})


@login_required
@require_POST
def excluir_cadastro(request, cadastro_id):
    if not tem_acesso_inventario(request.user):
        return JsonResponse({'error': 'Sem permissão para alterar o inventário.'}, status=403)
    cadastro = get_object_or_404(CadastroInventario, pk=cadastro_id)
    cadastro.delete()
    return JsonResponse({'ok': True})


@login_required
@require_POST
def importar_contagem(request, inventario_id):
    """Recebe a planilha Setor | Célula | Código | Descrição.

    - Itens novos são criados; os que já existem (mesmo setor + célula +
      código) têm a descrição atualizada. Nada é apagado, para não perder o
      que já foi lançado.
    - Cada setor + célula que ainda não tem cadastro vira um cadastro
      pendente (sem responsável).
    - Se a planilha tiver qualquer erro, nada é importado."""
    if not tem_acesso_inventario(request.user):
        return JsonResponse({'error': 'Sem permissão para alterar o inventário.'}, status=403)
    inventario = get_object_or_404(Inventario, pk=inventario_id)

    arquivo = request.FILES.get('arquivo')
    if not arquivo:
        return JsonResponse({'error': 'Selecione a planilha.'}, status=400)
    if arquivo.size > TAMANHO_MAXIMO_PLANILHA:
        return JsonResponse({'error': 'A planilha pode ter no máximo 10 MB.'}, status=400)

    try:
        linhas = ler_planilha_contagem(arquivo)
    except ErroImportacao as erro:
        return JsonResponse({'error': erro.mensagem, 'detalhes': erro.detalhes}, status=400)

    # Mesma grafia do que já existe no inventário: se o cadastro tem
    # "Montagem", uma linha com "MONTAGEM" entra como "Montagem".
    grafia = {}
    for setor, celula in list(inventario.cadastros.values_list('setor', 'celula')) + list(
        inventario.itens_contagem.filter(fora_da_lista=False).values_list('setor', 'celula')
    ):
        grafia.setdefault(('s', setor.lower()), setor)
        grafia.setdefault(('c', setor.lower(), celula.lower()), celula)

    for linha in linhas:
        linha['setor'] = grafia.setdefault(('s', linha['setor'].lower()), linha['setor'])
        linha['celula'] = grafia.setdefault(
            ('c', linha['setor'].lower(), linha['celula'].lower()), linha['celula']
        )

    with transaction.atomic():
        # os lançados "fora da lista" ficam de fora: são lotes avulsos
        existentes = {
            (i.setor.lower(), i.celula.lower(), i.codigo.lower()): i
            for i in inventario.itens_contagem.filter(fora_da_lista=False).select_for_update()
        }
        novos, alterados = [], []
        agora = timezone.now()  # bulk_update não preenche o auto_now
        for linha in linhas:
            chave = (linha['setor'].lower(), linha['celula'].lower(), linha['codigo'].lower())
            item = existentes.get(chave)
            if item is None:
                novos.append(ItemContagem(inventario=inventario, importado_por=request.user, **linha))
            elif item.descricao != linha['descricao']:
                item.descricao = linha['descricao']
                item.atualizado_em = agora
                alterados.append(item)
        ItemContagem.objects.bulk_create(novos, batch_size=1000)
        ItemContagem.objects.bulk_update(alterados, ['descricao', 'atualizado_em'], batch_size=1000)

        com_cadastro = {
            (s.lower(), c.lower()) for s, c in inventario.cadastros.values_list('setor', 'celula')
        }
        pendentes = []
        for linha in linhas:
            chave = (linha['setor'].lower(), linha['celula'].lower())
            if chave not in com_cadastro:
                com_cadastro.add(chave)
                pendentes.append(CadastroInventario(
                    inventario=inventario,
                    setor=linha['setor'],
                    celula=linha['celula'],
                    responsavel='',
                    criado_por=request.user,
                ))
        CadastroInventario.objects.bulk_create(pendentes)

    return JsonResponse({
        'linhas': len(linhas),
        'criados': len(novos),
        'atualizados': len(alterados),
        'sem_alteracao': len(linhas) - len(novos) - len(alterados),
        'celulas_pendentes': len(pendentes),
        'itens': [_serializar_item(i) for i in inventario.itens_contagem.all()],
    })


@login_required
@require_POST
def limpar_contagem(request, inventario_id):
    """Apaga a lista de contagem do inventário (os cadastros ficam)."""
    if not tem_acesso_inventario(request.user):
        return JsonResponse({'error': 'Sem permissão para alterar o inventário.'}, status=403)
    inventario = get_object_or_404(Inventario, pk=inventario_id)
    for item in inventario.itens_contagem.exclude(foto='').exclude(foto__isnull=True):
        _apagar_foto(item)
    apagados, _ = inventario.itens_contagem.all().delete()
    return JsonResponse({'apagados': apagados})


@login_required
@require_POST
def alterar_recontagem(request, inventario_id):
    """Habilita ou cancela a recontagem dos itens escolhidos no painel.

    - habilitar: só itens já contados. Começa uma recontagem nova (apaga a
      recontagem anterior, se houver); a primeira contagem fica.
    - cancelar: tira o item da recontagem e apaga o que foi recontado."""
    if not tem_acesso_inventario(request.user):
        return JsonResponse({'error': 'Sem permissão para alterar o inventário.'}, status=403)
    inventario = get_object_or_404(Inventario, pk=inventario_id)

    dados = _ler_json(request)
    if dados is None:
        return JsonResponse({'error': 'Dados inválidos.'}, status=400)
    ids = dados.get('ids')
    if not isinstance(ids, list) or not ids or not all(isinstance(i, int) for i in ids):
        return JsonResponse({'error': 'Selecione ao menos um item.'}, status=400)
    habilitar = bool(dados.get('habilitar'))

    itens = inventario.itens_contagem.filter(pk__in=ids)
    if habilitar:
        alterados = itens.filter(quantidade__isnull=False).update(
            recontagem_habilitada=True, recontagem=None, recontado_em=None, atualizado_em=timezone.now()
        )
    else:
        alterados = itens.filter(recontagem_habilitada=True).update(
            recontagem_habilitada=False, recontagem=None, recontado_em=None, atualizado_em=timezone.now()
        )
    ignorados = len(set(ids)) - alterados
    atualizados = [_serializar_item(i) for i in inventario.itens_contagem.filter(pk__in=ids)]
    return JsonResponse({'alterados': alterados, 'ignorados': ignorados, 'itens': atualizados})


@login_required
@require_POST
def alterar_status(request, inventario_id):
    """Abre ou finaliza o inventário. Finalizado, o link de contagem para de
    aceitar lançamentos."""
    if not tem_acesso_inventario(request.user):
        return JsonResponse({'error': 'Sem permissão para alterar o inventário.'}, status=403)
    inventario = get_object_or_404(Inventario, pk=inventario_id)
    dados = _ler_json(request)
    status = (dados or {}).get('status')
    if status not in dict(Inventario.STATUS_CHOICES):
        return JsonResponse({'error': 'Status inválido.'}, status=400)
    inventario.status = status
    inventario.save(update_fields=['status'])
    return JsonResponse({'inventario': _serializar(inventario)})


# ---------------------------------------------------------------------------
# Link público da contagem (sem login). O RotaAccessMiddleware libera
# "inventario/contagem/"; quem acessa é identificado só pelo token do link.
# ---------------------------------------------------------------------------

MENSAGEM_FINALIZADO = 'Este inventário foi finalizado. A contagem está encerrada.'
TAMANHO_MAXIMO_FOTO = 10 * 1024 * 1024  # 10 MB (o celular já reduz antes de enviar)


def _apagar_foto(item):
    """Tira o arquivo do storage; falha no storage não impede apagar o item."""
    if not item.foto:
        return
    try:
        item.foto.delete(save=False)
    except Exception:
        logger.warning('Não foi possível apagar a foto %s do item %s', item.foto.name, item.pk, exc_info=True)


def _validar_foto(arquivo):
    """Devolve a mensagem de erro, ou None se for uma imagem válida."""
    if arquivo.size > TAMANHO_MAXIMO_FOTO:
        return 'A foto pode ter no máximo 10 MB.'
    try:
        from PIL import Image

        with Image.open(arquivo) as imagem:
            imagem.verify()
    except Exception:
        return 'O arquivo enviado não é uma imagem válida.'
    finally:
        arquivo.seek(0)
    return None


def _inventario_por_token(token):
    return get_object_or_404(Inventario, token_contagem=token)


def _ler_quantidade(valor):
    """Aceita "12", "12,5" ou "12.5" (sem separador de milhar, que deixaria
    "1.234" ambíguo). Devolve (Decimal ou None, erro)."""
    texto = str(valor if valor is not None else '').strip().replace(' ', '')
    if not texto:
        return None, None
    texto = texto.replace(',', '.')
    if not re.fullmatch(r'-?\d+(\.\d+)?', texto):
        return None, 'Quantidade inválida. Use só números, ex.: 12 ou 12,5.'
    try:
        quantidade = Decimal(texto)
    except InvalidOperation:
        return None, 'Quantidade inválida.'
    if not quantidade.is_finite() or quantidade < 0:
        return None, 'A quantidade não pode ser negativa.'
    if quantidade.as_tuple().exponent < -3:
        return None, 'Use no máximo 3 casas decimais.'
    if quantidade >= Decimal('100000000000'):
        return None, 'Quantidade grande demais.'
    return quantidade, None


@ensure_csrf_cookie
def contagem_publica(request, token):
    inventario = _inventario_por_token(token)
    setores = list(
        inventario.itens_contagem.values('setor')
        # progresso só da lista importada; os lotes fora da lista são extras
        .annotate(
            total=Count('id', filter=Q(fora_da_lista=False)),
            contados=Count('quantidade', filter=Q(fora_da_lista=False)),
            recontar=Count('id', filter=Q(recontagem_habilitada=True, recontagem__isnull=True)),
        )
        .order_by('setor')
    )
    return render(request, 'inventario/contagem_publica.html', {
        'inventario': inventario,
        'setores': setores,
    })


@require_GET
def contagem_publica_itens(request, token):
    inventario = _inventario_por_token(token)
    if not inventario.aberto:
        return JsonResponse({'error': MENSAGEM_FINALIZADO}, status=403)
    setor = request.GET.get('setor', '')
    itens = inventario.itens_contagem.filter(setor=setor)
    return JsonResponse({'itens': [_serializar_item_publico(i) for i in itens]})


@require_POST
def contagem_publica_registrar(request, token, item_id):
    """Grava a quantidade contada (e o horário). Quantidade vazia apaga a
    contagem do item. Recontar substitui o valor anterior."""
    inventario = _inventario_por_token(token)
    if not inventario.aberto:
        return JsonResponse({'error': MENSAGEM_FINALIZADO}, status=403)
    item = get_object_or_404(ItemContagem, pk=item_id, inventario=inventario)

    dados = _ler_json(request)
    if dados is None:
        return JsonResponse({'error': 'Dados inválidos.'}, status=400)
    quantidade, erro = _ler_quantidade(dados.get('quantidade'))
    if erro:
        return JsonResponse({'error': erro}, status=400)

    agora = timezone.now() if quantidade is not None else None
    if item.recontagem_habilitada:
        # recontagem: a primeira contagem fica intacta
        item.recontagem = quantidade
        item.recontado_em = agora
        item.save(update_fields=['recontagem', 'recontado_em', 'atualizado_em'])
        return JsonResponse({'item': _serializar_item_publico(item)})

    if quantidade is None and item.fora_da_lista:
        # lote fora da lista sem contagem não tem razão de existir
        _apagar_foto(item)
        item.delete()
        return JsonResponse({'removido': True, 'id': item_id})

    item.quantidade = quantidade
    item.contado_em = agora
    item.save(update_fields=['quantidade', 'contado_em', 'atualizado_em'])
    return JsonResponse({'item': _serializar_item_publico(item)})


@require_POST
def contagem_publica_fora_da_lista(request, token):
    """Peça achada que não está na lista (ex.: lote no pátio). O operador
    informa só o código, onde achou (observação) e a quantidade; a descrição
    vem de outra linha do inventário com o mesmo código, quando houver. Cada
    lançamento é um lote próprio, mesmo que o código se repita."""
    inventario = _inventario_por_token(token)
    if not inventario.aberto:
        return JsonResponse({'error': MENSAGEM_FINALIZADO}, status=403)

    # com foto vem como formulário (multipart); sem foto pode vir JSON
    if request.content_type.startswith('multipart/'):
        dados = request.POST
    else:
        dados = _ler_json(request)
    if dados is None:
        return JsonResponse({'error': 'Dados inválidos.'}, status=400)
    foto = request.FILES.get('foto')
    if foto:
        erro_foto = _validar_foto(foto)
        if erro_foto:
            return JsonResponse({'error': erro_foto}, status=400)

    setor = (
        inventario.itens_contagem.filter(setor__iexact=_texto(dados.get('setor')))
        .values_list('setor', flat=True).first()
    )
    if not setor:
        return JsonResponse({'error': 'Setor não encontrado neste inventário.'}, status=400)

    codigo = _texto(dados.get('codigo'))
    observacao = _texto(dados.get('observacao'))
    if not codigo:
        return JsonResponse({'error': 'Informe o código da peça.'}, status=400)
    if len(codigo) > 60:
        return JsonResponse({'error': 'O código pode ter no máximo 60 caracteres.'}, status=400)
    if not observacao:
        return JsonResponse({'error': 'Informe onde a peça está.'}, status=400)
    if len(observacao) > 255:
        return JsonResponse({'error': 'A observação pode ter no máximo 255 caracteres.'}, status=400)

    quantidade, erro = _ler_quantidade(dados.get('quantidade'))
    if erro:
        return JsonResponse({'error': erro}, status=400)
    if quantidade is None:
        return JsonResponse({'error': 'Informe a quantidade encontrada.'}, status=400)

    conhecida = (
        inventario.itens_contagem.filter(codigo__iexact=codigo).exclude(descricao='')
        .order_by('fora_da_lista').first()
    )
    try:
        # a foto sobe para o storage (S3) no save; se falhar, nada é gravado
        with transaction.atomic():
            item = ItemContagem.objects.create(
                inventario=inventario,
                setor=setor,
                celula='',
                codigo=conhecida.codigo if conhecida else codigo,
                descricao=conhecida.descricao if conhecida else '',
                observacao=observacao,
                quantidade=quantidade,
                contado_em=timezone.now(),
                fora_da_lista=True,
                foto=foto or None,
            )
    except Exception:
        if not foto:
            raise
        logger.exception('Falha ao enviar a foto do lote fora da lista')
        return JsonResponse(
            {'error': 'Não foi possível enviar a foto. Tente de novo ou registre sem foto.'}, status=502
        )
    return JsonResponse({'item': _serializar_item_publico(item)}, status=201)
