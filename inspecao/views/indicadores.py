from collections import OrderedDict
from datetime import datetime, timedelta

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from inspecao.models import DadosExecucaoInspecao, InspecaoRecebimento

DIAS_SEMANA = ['S', 'T', 'Q', 'Q', 'S', 'S', 'D']  # Segunda..Domingo, so a inicial


def indicadores_inspetores(request):
    return render(request, 'indicadores_inspetores.html')


def _quantidade_inspecoes(dia, campo_relacao):
    """
    Conta quantas inspecoes de `campo_relacao` (ex: 'pecas_ordem_montagem',
    'estanqueidade') tiveram ao menos uma execucao no dia. Deduplica por
    Inspecao (nao conta de novo se houve reexecucao no mesmo dia).
    """
    return (
        DadosExecucaoInspecao.objects
        .filter(**{f'inspecao__{campo_relacao}__isnull': False}, data_execucao__date=dia)
        .values_list('inspecao_id', flat=True)
        .distinct()
        .count()
    )


def _quantidade_recebimento(dia):
    return InspecaoRecebimento.objects.filter(
        data_inspecao__date=dia, excluido=False
    ).count()


@login_required
@require_GET
def api_indicadores_inspetores(request):
    data_inicio_str = request.GET.get('data_inicio')
    data_fim_str = request.GET.get('data_fim')

    try:
        data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
        data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return JsonResponse(
            {'error': 'Informe data_inicio e data_fim no formato YYYY-MM-DD.'}, status=400
        )

    if data_fim < data_inicio:
        return JsonResponse({'error': 'data_fim não pode ser antes de data_inicio.'}, status=400)

    semanas = OrderedDict()

    dia = data_inicio
    while dia <= data_fim:
        grupo_corte = (
            _quantidade_inspecoes(dia, 'pecas_ordem_estamparia')
            + _quantidade_inspecoes(dia, 'pecas_ordem_corte')
            + _quantidade_inspecoes(dia, 'pecas_ordem_serra')
            + _quantidade_inspecoes(dia, 'pecas_ordem_usinagem')
        )
        montagem_solda = (
            _quantidade_inspecoes(dia, 'pecas_ordem_montagem')
            + _quantidade_inspecoes(dia, 'estanqueidade')
        )
        pintura = _quantidade_inspecoes(dia, 'pecas_ordem_pintura')
        recebimento = _quantidade_recebimento(dia)

        # Agrupa por semana ISO (segunda a domingo) - cada semana tem sua
        # propria lista de dias e sua propria media, em vez de uma unica
        # media pro periodo inteiro.
        ano_iso, semana_iso, _ = dia.isocalendar()
        chave_semana = (ano_iso, semana_iso)

        if chave_semana not in semanas:
            inicio_semana = dia - timedelta(days=dia.weekday())
            fim_semana = inicio_semana + timedelta(days=6)
            semanas[chave_semana] = {
                'rotulo': f"Semana de {inicio_semana.strftime('%d/%m')} a {fim_semana.strftime('%d/%m')}",
                'linhas': [],
                'somas': {'grupo_corte': 0, 'montagem_solda': 0, 'pintura': 0, 'recebimento': 0},
            }

        semanas[chave_semana]['linhas'].append({
            'dia_semana': DIAS_SEMANA[dia.weekday()],
            'data': dia.strftime('%d/%m'),
            'grupo_corte': grupo_corte,
            'montagem_solda': montagem_solda,
            'pintura': pintura,
            'recebimento': recebimento,
        })

        somas_semana = semanas[chave_semana]['somas']
        somas_semana['grupo_corte'] += grupo_corte
        somas_semana['montagem_solda'] += montagem_solda
        somas_semana['pintura'] += pintura
        somas_semana['recebimento'] += recebimento

        dia += timedelta(days=1)

    resultado = []
    for dados_semana in semanas.values():
        total_dias_semana = len(dados_semana['linhas'])
        media = {
            chave: round(valor / total_dias_semana, 1) if total_dias_semana else 0
            for chave, valor in dados_semana['somas'].items()
        }
        resultado.append({
            'rotulo': dados_semana['rotulo'],
            'linhas': dados_semana['linhas'],
            'media': media,
        })

    return JsonResponse({'semanas': resultado})
