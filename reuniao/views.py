from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt
from django.utils.timezone import localtime
from django.db.models import Avg, Sum, FloatField, Value, F, ExpressionWrapper
from django.db.models.functions import Coalesce

from .models import Report
from core.models import Ordem, OrdemProcesso
from cadastro.models import Maquina
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


@login_required
def reuniao_home(request):
    return render(request, 'reuniao/reuniao.html')


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

    report = Report.objects.create(
        usuario=request.user,
        texto=texto,
        data=date.today(),
    )
    return JsonResponse({
        'id': report.id,
        'usuario': report.usuario.get_full_name() or report.usuario.username,
        'usuario_id': report.usuario.id,
        'texto': report.texto,
        'data': report.data.strftime('%d/%m/%Y'),
        'criado_em': localtime(report.criado_em).strftime('%d/%m/%Y %H:%M'),
    }, status=201)


@login_required
@require_GET
def listar_reports(request):
    data_str = request.GET.get('data')
    if data_str:
        try:
            data_filtro = datetime.strptime(data_str, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({'error': 'Formato de data inválido. Use YYYY-MM-DD'}, status=400)
    else:
        data_filtro = date.today()

    reports = Report.objects.filter(data=data_filtro).select_related('usuario')
    return JsonResponse([{
        'id': r.id,
        'usuario': r.usuario.get_full_name() or r.usuario.username,
        'usuario_id': r.usuario.id,
        'texto': r.texto,
        'data': r.data.strftime('%d/%m/%Y'),
        'criado_em': localtime(r.criado_em).strftime('%d/%m/%Y %H:%M'),
    } for r in reports], safe=False)


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
