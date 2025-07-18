from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.db import transaction
from .models import Ordem, PecasOrdem, Pecas  # ajuste os imports se necessário

def criar_ordem_usinagem(data):
    with transaction.atomic():
        nova_ordem = Ordem.objects.create(
            obs=data.get('observacoes'),
            grupo_maquina='usinagem',
            data_programacao=data.get("dataProgramacao"),
            maquina=data.get("maquina") if data.get("maquina") else None
        )

        PecasOrdem.objects.create(
            qtd_planejada=data.get('qtdPlanejada'),
            ordem=nova_ordem,
            peca=get_object_or_404(Pecas, codigo=data.get('pecaSelect')),
        )

        if data.get("status_atual"):
            nova_ordem.status_atual = data.get("status_atual")
        
        nova_ordem.save()

    return nova_ordem  # ou outra estrutura se quiser retornar algo mais

def verificar_se_existe_ordem(peca):

    # Verifica se existe uma ordem no setor de usinagem com a mesma peça e status 'aguardando_prox_proc'
    pecas_ordem = PecasOrdem.objects.filter(
        peca=peca,  # Relaciona a PecasOrdem com a Peca
        ordem__grupo_maquina='usinagem',  # Verifica se a ordem está no setor de usinagem
        ordem__status_atual='agua_prox_proc'  # Status aguardando próxima etapa
    ).first()  # Retorna a primeira PecasOrdem que corresponder

    return pecas_ordem  # Retorna a ordem se encontrada ou None se não existir
