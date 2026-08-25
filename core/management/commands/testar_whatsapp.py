from django.core.management.base import BaseCommand
from core.whatsapp import enviar_falta_de_peca


class Command(BaseCommand):
    help = "Envia uma mensagem de teste com o template 'falta_de_peca_2' para o numero informado."

    def add_arguments(self, parser):
        parser.add_argument(
            "telefone",
            help="Numero completo com DDI, sem '+' e sem espacos (ex: 5511999998888)",
        )
        parser.add_argument("--celula", default="Celula 12")
        parser.add_argument("--conjunto", default="OP-123456")
        parser.add_argument(
            "--peca",
            action="append",
            dest="pecas",
            default=None,
            help="Pode ser passado varias vezes, uma por peca em falta",
        )

    def handle(self, *args, **options):
        pecas = options["pecas"] or [
            "256019 - PARAF FRANC 1/2 X 2",
            "120870 - CHAPA 1/8 (3.15) INOX-304",
        ]

        message_id, erro = enviar_falta_de_peca(
            telefone=options["telefone"],
            celula=options["celula"],
            conjunto=options["conjunto"],
            pecas_faltantes=pecas,
        )

        if erro:
            self.stderr.write(self.style.ERROR(erro))
            return

        self.stdout.write(self.style.SUCCESS(f"Mensagem enviada. id={message_id}"))
