from django.core.management.base import BaseCommand
from inspecao.models import Causas

class Command(BaseCommand):
    help = 'Importa causas padronizadas para os setores definidos'

    def handle(self, *args, **kwargs):
        causas_data = [
            ("Manchas", "pintura"),
            ("Casca de Laranja", "pintura"),
            ("Faltando Solda", "montagem"),
            ("Porosidade", "montagem"),
            ("Solda não conforme", "montagem"),
            ("Solda deslocada", "montagem"),
            ("Medida não conforme", "montagem"),
            ("Solda sem penetração", "montagem"),
            ("Medida não conforme", "montagem"),
            ("Solda sem penetração", "montagem"),
            ("Excesso de respingo", "montagem"),
            ("Excesso de rebarba", "montagem"),
            ("Excesso de solda", "montagem"),
            ("Mordedura", "montagem"),
            ("Erro de montagem", "montagem"),
            ("Ondulação no piso", "montagem"),
            ("Visual da solda", "montagem"),
            ("Vazamento", "montagem"),
            ("Amassado", "tubos cilindros"),
            ("Solda", "tubos cilindros"),
            ("Vazamento", "tubos cilindros"),
            ("Oxidação", "tubos cilindros"),
            ("Haste", "tubos cilindros"),
            ("Dimensional", "tubos cilindros"),
            ("Estanqueidade", "tubos cilindros"),
            ("Pressão", "tubos cilindros"),
            ("Virada irregular", "estamparia"),
            ("Oxidação", "estamparia"),
            ("Marcação", "estamparia"),
            ("Marcação rebarba", "estamparia"),
            ("Medida irregular", "estamparia"),
            ("Corte irregular", "estamparia"),
            ("Faltando Solda", "pintura"),
            ("Olho de Peixe", "pintura"),
            ("Arranhão", "pintura"),
            ("Escorrimento", "pintura"),
            ("Empoeiramento", "pintura"),
            ("Contato", "pintura"),
            ("Amassando", "pintura"),
            ("Camada Baixa", "pintura"),
            ("Corrosão", "pintura"),
            ("Marcação por Água", "pintura"),
            ("Marcação por Óleo", "pintura"),
            ("Tonalidade", "pintura"),
            ("Marca texto industrial", "pintura"),
            ("Respingo de Solda", "pintura"),
            ("Marcação de Peça", "pintura"),
            ("Falta de aderência", "pintura"),
            ("Decapante", "pintura"),
            ("Desplacamento", "pintura"),
            ("Água", "pintura"),
        ]

        for nome, setor in causas_data:
            causa, created = Causas.objects.get_or_create(nome=nome, setor=setor)
            if created:
                self.stdout.write(self.style.SUCCESS(f" Importado: {nome} ({setor})"))
            else:
                self.stdout.write(self.style.WARNING(f" Já existia: {nome} ({setor})"))

        self.stdout.write(self.style.SUCCESS(" Importação finalizada com sucesso!"))
