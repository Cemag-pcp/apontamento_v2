from django.core.management.base import BaseCommand
from django.db.models import Max
from django.utils.timezone import now

from inspecao.models import DadosExecucaoInspecao
from core.whatsapp import enviar_notificacao_qualidade, destinatarios_notificacao_qualidade

LIMITE_DIAS = 2

# Cada setor e identificado pelo filtro que localiza suas execucoes dentro de
# DadosExecucaoInspecao (tabela compartilhada por todos os setores, via as FKs
# opcionais em Inspecao). Estanqueidade nao tem FK direta de tipo em Inspecao/
# InspecaoEstanqueidade - o tipo (tanque/tubo/cilindro) vem de
# InspecaoEstanqueidade.peca.tipo (cadastro.PecasEstanqueidade).
SETORES = [
    ('Pintura', {'inspecao__pecas_ordem_pintura__isnull': False}),
    ('Montagem', {'inspecao__pecas_ordem_montagem__isnull': False}),
    ('Estamparia', {'inspecao__pecas_ordem_estamparia__isnull': False}),
    ('Corte', {'inspecao__pecas_ordem_corte__isnull': False}),
    ('Serra', {'inspecao__pecas_ordem_serra__isnull': False}),
    ('Usinagem', {'inspecao__pecas_ordem_usinagem__isnull': False}),
    ('Tanque', {'inspecao__estanqueidade__peca__tipo': 'tanque'}),
    ('Tubo', {'inspecao__estanqueidade__peca__tipo': 'tubo'}),
    ('Cilindro', {'inspecao__estanqueidade__peca__tipo': 'cilindro'}),
]


class Command(BaseCommand):
    help = (
        f"Verifica setores sem nenhuma inspecao executada ha {LIMITE_DIAS}+ dias "
        "e notifica os destinatarios de qualidade via WhatsApp."
    )

    def handle(self, *args, **options):
        destinatarios = destinatarios_notificacao_qualidade()
        if not destinatarios:
            self.stdout.write(self.style.WARNING(
                "Nenhum destinatario cadastrado (tipo_notificacao=notificacao_qualidade). Abortando."
            ))
            return

        agora = now()

        for nome_setor, filtro in SETORES:
            ultima_execucao = (
                DadosExecucaoInspecao.objects
                .filter(**filtro)
                .aggregate(ultima=Max('data_execucao'))
                .get('ultima')
            )

            if ultima_execucao is None:
                # Nunca teve inspecao executada nesse setor - fora do escopo
                # deste alerta (ausencia total é um problema diferente de
                # "parou de inspecionar").
                continue

            dias_sem_inspecao = (agora - ultima_execucao).days
            if dias_sem_inspecao < LIMITE_DIAS:
                continue

            mensagem = (
                f"Faz *{dias_sem_inspecao}* dias que não é registrado "
                f"inspeção no setor de *{nome_setor}*."
            )

            for telefone in destinatarios:
                _, erro = enviar_notificacao_qualidade(telefone=telefone, mensagem=mensagem)
                if erro:
                    self.stderr.write(self.style.ERROR(f"[{nome_setor}] {telefone}: {erro}"))
                else:
                    self.stdout.write(self.style.SUCCESS(
                        f"[{nome_setor}] notificado {telefone} ({dias_sem_inspecao} dias sem inspecao)"
                    ))
