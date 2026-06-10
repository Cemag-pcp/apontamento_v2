from django.shortcuts import get_object_or_404, render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt
from django.utils.timezone import localtime
from django.db.models import Avg, Sum, FloatField, Value, F, ExpressionWrapper
from django.db.models.functions import Coalesce

from .models import Report
from core.models import Ordem, OrdemProcesso
from cadastro.models import Maquina, Setor
from apontamento_montagem.models import PecasOrdem as POMontagem
from apontamento_solda.models import PecasOrdem as POSolda
from apontamento_pintura.models import PecasOrdem as POPintura
from apontamento_usinagem.models import PecasOrdem as POUsinagem
from apontamento_estamparia.models import PecasOrdem as POEstamparia
from apontamento_serra.models import PecasOrdem as POSerra
from apontamento_corte.models import PecasOrdem as POCorte

import json
from datetime import datetime, date


MAQUINAS_EXCLUIDAS = {
    'montagem': [
        'PLAT. TANQUE. CAÇAM. 2', 'QUALIDADE', 'FORJARIA',
        'ESTAMPARIA', 'Carpintaria', 'FEIXE DE MOLAS', 'ROÇADEIRA', 'SERRALHERIA',
    ],
    'solda': [
        'PLAT. TANQUE. CAÇAM. 2', 'QUALIDADE', 'FORJARIA',
        'ESTAMPARIA', 'Carpintaria', 'FEIXE DE MOLAS', 'SERRALHERIA',
    ],
    'pintura': [],
}

PO_MODELS = {
    'montagem': POMontagem,
    'solda': POSolda,
    'pintura': POPintura,
}


def pode_gerenciar_reports(user):
    profile = getattr(user, 'profile', None)
    tipo_acesso = getattr(profile, 'tipo_acesso', '').lower()
    return tipo_acesso in {'pcp', 'admin'}


def serializar_setor(setor):
    if setor is None:
        return None
    return {'id': setor.id, 'nome': setor.nome}


@login_required
def reuniao_home(request):
    pode_gerenciar = pode_gerenciar_reports(request.user)
    profile = getattr(request.user, 'profile', None)
    if pode_gerenciar:
        setores_usuario = list(Setor.objects.order_by('nome').values('id', 'nome'))
    elif profile is not None:
        setores_usuario = list(profile.setores.order_by('nome').values('id', 'nome'))
    else:
        setores_usuario = []

    return render(request, 'reuniao/reuniao.html', {
        'pode_concluir_reports': pode_gerenciar,
        'pode_excluir_reports': pode_gerenciar,
        'pode_reportar_qualquer_setor': pode_gerenciar,
        'setores_usuario': setores_usuario,
        'setores_filtro': Setor.objects.order_by('nome'),
    })


@login_required
@csrf_exempt
@require_POST
def criar_report(request):
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    texto = body.get('texto', '').strip()
    if not texto:
        return JsonResponse({'error': 'Texto é obrigatório'}, status=400)

    profile = getattr(request.user, 'profile', None)
    pode_reportar_qualquer_setor = pode_gerenciar_reports(request.user)
    setores_disponiveis = (
        Setor.objects.all()
        if pode_reportar_qualquer_setor
        else profile.setores.all() if profile is not None else Setor.objects.none()
    )
    setor_id = body.get('setor_id')
    setor = None

    if pode_reportar_qualquer_setor:
        if setor_id in (None, ''):
            return JsonResponse({'error': 'Selecione o setor do report.'}, status=400)
        try:
            setor = setores_disponiveis.get(pk=int(setor_id))
        except (TypeError, ValueError, Setor.DoesNotExist):
            return JsonResponse(
                {'error': 'O setor selecionado é inválido.'},
                status=400,
            )
    elif setores_disponiveis.exists():
        if setor_id in (None, ''):
            return JsonResponse({'error': 'Selecione o setor do report.'}, status=400)
        try:
            setor = setores_disponiveis.get(pk=int(setor_id))
        except (TypeError, ValueError, Setor.DoesNotExist):
            return JsonResponse(
                {'error': 'O setor selecionado não está vinculado ao usuário.'},
                status=400,
            )
    elif setor_id not in (None, ''):
        return JsonResponse(
            {'error': 'O usuário não possui setores vinculados.'},
            status=400,
        )

    report = Report.objects.create(
        usuario=request.user,
        texto=texto,
        data=date.today(),
        setor=setor,
    )
    return JsonResponse({
        'id': report.id,
        'usuario': report.usuario.get_full_name() or report.usuario.username,
        'usuario_id': report.usuario.id,
        'texto': report.texto,
        'data': report.data.strftime('%d/%m/%Y'),
        'criado_em': localtime(report.criado_em).strftime('%d/%m/%Y %H:%M'),
        'concluido': report.concluido,
        'setor': serializar_setor(report.setor),
    }, status=201)


@login_required
@require_GET
def listar_reports(request):
    reports = Report.objects.filter(data=date.today())
    setor_filtro = request.GET.get('setor', '').strip()

    if setor_filtro == 'sem-setor':
        reports = reports.filter(setor__isnull=True)
    elif setor_filtro:
        try:
            setor_id = int(setor_filtro)
        except ValueError:
            return JsonResponse({'error': 'Filtro de setor inválido.'}, status=400)
        if not Setor.objects.filter(pk=setor_id).exists():
            return JsonResponse({'error': 'Setor não encontrado.'}, status=400)
        reports = reports.filter(setor_id=setor_id)

    reports = reports.select_related('usuario', 'setor')
    return JsonResponse([{
        'id': r.id,
        'usuario': r.usuario.get_full_name() or r.usuario.username,
        'usuario_id': r.usuario.id,
        'texto': r.texto,
        'data': r.data.strftime('%d/%m/%Y'),
        'criado_em': localtime(r.criado_em).strftime('%d/%m/%Y %H:%M'),
        'concluido': r.concluido,
        'setor': serializar_setor(r.setor),
    } for r in reports], safe=False)


@login_required
@require_POST
def atualizar_conclusao_report(request, report_id):
    if not pode_gerenciar_reports(request.user):
        return JsonResponse(
            {'error': 'Apenas usuários PCP ou administradores podem alterar a conclusão dos reports.'},
            status=403,
        )

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    concluido = body.get('concluido')
    if not isinstance(concluido, bool):
        return JsonResponse(
            {'error': 'O campo concluido deve ser verdadeiro ou falso.'},
            status=400,
        )

    report = get_object_or_404(Report, pk=report_id)
    report.concluido = concluido
    report.save(update_fields=['concluido'])

    return JsonResponse({
        'id': report.id,
        'concluido': report.concluido,
    })


@login_required
@require_POST
def excluir_report(request, report_id):
    if not pode_gerenciar_reports(request.user):
        return JsonResponse(
            {'error': 'Apenas usuários PCP ou administradores podem excluir reports.'},
            status=403,
        )

    report = get_object_or_404(Report, pk=report_id)
    report.delete()

    return JsonResponse({
        'id': report_id,
        'excluido': True,
    })


@login_required
@require_GET
def tabela_producao(request):
    setor = request.GET.get('setor', '').lower().strip()
    datas_str = request.GET.getlist('datas[]') or request.GET.getlist('datas')

    if setor not in ('solda', 'montagem', 'pintura'):
        return JsonResponse({'error': 'Setor inválido. Use: solda, montagem ou pintura'}, status=400)

    datas = []
    for d in datas_str:
        try:
            datas.append(datetime.strptime(d, '%Y-%m-%d').date())
        except ValueError:
            pass

    if not datas:
        return JsonResponse({'error': 'Nenhuma data válida fornecida'}, status=400)

    maquinas_excluidas = MAQUINAS_EXCLUIDAS.get(setor, [])
    maquinas_excluidas_ids = list(
        Maquina.objects.filter(nome__in=maquinas_excluidas).values_list('id', flat=True)
    )

    POModel = PO_MODELS[setor]

    ordens_base = Ordem.objects.filter(
        grupo_maquina=setor,
        data_carga__in=datas,
    ).exclude(maquina_id__in=maquinas_excluidas_ids)

    # Pintura agrupa por cor; demais setores agrupam por máquina
    is_pintura = setor == 'pintura'
    group_field = 'cor' if is_pintura else 'maquina__nome'

    linhas = list(
        ordens_base
        .values_list(group_field, flat=True)
        .distinct()
        .order_by(group_field)
    )
    # Remove valores nulos/vazios que possam existir no campo cor
    linhas = [l for l in linhas if l]

    dados = {}
    for linha in linhas:
        dados[linha] = {}
        for data in datas:
            data_key = data.strftime('%Y-%m-%d')
            filtro = {'data_carga': data}
            filtro[group_field] = linha
            ordens_grupo = ordens_base.filter(**filtro)

            if not ordens_grupo.exists():
                dados[linha][data_key] = None
                continue

            ordem_ids = list(ordens_grupo.values_list('id', flat=True))
            pecas_qs = POModel.objects.filter(ordem_id__in=ordem_ids)

            # qtd_planejada repete para cada execução da mesma (ordem, peca).
            # Agrupa por (ordem_id, peca): Avg do planejado (valor fixo que se repete)
            # e Sum do executado (acumula a cada apontamento).
            per_item = list(
                pecas_qs.values('ordem_id', 'peca').annotate(
                    qtd_plan=Coalesce(Avg('qtd_planejada', output_field=FloatField()), Value(0.0)),
                    qtd_boa_sum=Coalesce(Sum('qtd_boa', output_field=FloatField()), Value(0.0)),
                )
            )

            total_planejado = sum(i['qtd_plan'] for i in per_item)
            total_finalizado = sum(i['qtd_boa_sum'] for i in per_item)
            percentual = round((total_finalizado / total_planejado * 100), 2) if total_planejado > 0 else 0.0

            itens_por_peca = {}
            for i in per_item:
                p = i['peca']
                if p not in itens_por_peca:
                    itens_por_peca[p] = {'plan': 0.0, 'boa': 0.0}
                itens_por_peca[p]['plan'] += i['qtd_plan']
                itens_por_peca[p]['boa'] += i['qtd_boa_sum']

            itens = sorted(
                [
                    {'peca': p, 'qtd_restante': int(v['plan'] - v['boa'])}
                    for p, v in itens_por_peca.items()
                    if v['plan'] - v['boa'] > 0
                ],
                key=lambda x: x['peca'],
            )

            dados[linha][data_key] = {
                'percentual': percentual,
                'total_planejado': total_planejado,
                'total_finalizado': total_finalizado,
                'finalizada': percentual >= 100,
                'itens_restantes': [
                    {'peca': i['peca'], 'qtd_restante': int(i['qtd_restante'])}
                    for i in itens
                ],
            }

    return JsonResponse({
        'setor': setor,
        'agrupamento': 'cor' if is_pintura else 'maquina',
        'datas': [d.strftime('%Y-%m-%d') for d in datas],
        'linhas': linhas,
        'dados': dados,
    })


# Setores "ao vivo": sem datas, mostram ordens em andamento agora
_LIVE_GRUPO_MAQUINA = {
    'estamparia': ['estamparia'],
    'usinagem':   ['usinagem'],
    'serra':      ['serra'],
    'corte':      ['laser_1', 'laser_2', 'laser_3', 'plasma'],
}

# PecasOrdem de cada setor live e se peca é FK (True) ou CharField (False)
_LIVE_PO_MODEL = {
    'estamparia': (POEstamparia, True),
    'usinagem':   (POUsinagem,   True),
    'serra':      (POSerra,      True),
    'corte':      (POCorte,      False),
}

STATUS_LABELS = {
    'aguardando_iniciar': 'Aguardando',
    'iniciada':           'Em andamento',
    'interrompida':       'Interrompida',
    'finalizada':         'Finalizada',
    'agua_prox_proc':     'Ag. próx. processo',
}


@login_required
@require_GET
def andamento_live(request):
    setor = request.GET.get('setor', '').lower().strip()

    if setor not in _LIVE_GRUPO_MAQUINA:
        return JsonResponse({'error': 'Setor inválido para andamento live'}, status=400)

    grupos = _LIVE_GRUPO_MAQUINA[setor]
    POModel, peca_is_fk = _LIVE_PO_MODEL[setor]

    ordens = (
        Ordem.objects
        .filter(grupo_maquina__in=grupos, status_atual='iniciada', excluida=False)
        .select_related('maquina', 'operador_final')
        .order_by('maquina__nome', 'ultima_atualizacao')
    )

    resultado = []
    for ordem in ordens:
        pecas_qs = POModel.objects.filter(ordem=ordem)

        if peca_is_fk:
            pecas_raw = list(
                pecas_qs.values(
                    'peca__codigo', 'peca__descricao', 'qtd_planejada', 'qtd_boa'
                )
            )
            pecas = [
                {
                    'codigo': p['peca__codigo'] or '',
                    'descricao': p['peca__descricao'] or '',
                    'qtd_planejada': p['qtd_planejada'],
                    'qtd_boa': p['qtd_boa'],
                }
                for p in pecas_raw
            ]
        else:
            pecas_raw = list(pecas_qs.values('peca', 'qtd_planejada', 'qtd_boa'))
            pecas = [
                {
                    'codigo': p['peca'],
                    'descricao': '',
                    'qtd_planejada': p['qtd_planejada'],
                    'qtd_boa': p['qtd_boa'],
                }
                for p in pecas_raw
            ]

        processo_inicio = (
            OrdemProcesso.objects
            .filter(ordem=ordem, status='iniciada')
            .order_by('-data_inicio')
            .first()
        )
        iniciado_em = (
            localtime(processo_inicio.data_inicio).strftime('%d/%m/%Y %H:%M')
            if processo_inicio else '—'
        )

        numero_ordem = ordem.ordem or ordem.ordem_duplicada or '—'

        resultado.append({
            'maquina': ordem.maquina.nome if ordem.maquina else '—',
            'ordem': numero_ordem,
            'operador': ordem.operador_final.nome if ordem.operador_final else '—',
            'status': STATUS_LABELS.get(ordem.status_atual, ordem.status_atual),
            'data_programacao': ordem.data_programacao.strftime('%d/%m/%Y') if ordem.data_programacao else '—',
            'iniciado_em': iniciado_em,
            'pecas': pecas,
        })

    return JsonResponse({'setor': setor, 'ordens': resultado})
