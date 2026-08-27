from django.core.management.base import BaseCommand
from core.whatsapp import enviar_notificacao_qualidade


class Command(BaseCommand):
    help = "Envia uma mensagem de teste com o template 'notificacao_qualidade_1' para o numero informado."

    def add_arguments(self, parser):
        parser.add_argument(
            "telefone",
            help="Numero completo com DDI, sem '+' e sem espacos (ex: 5511999998888)",
        )
        parser.add_argument(
            "--mensagem",
            default="Faz *2* dias que não é registrado inspeção no setor de *Pintura*.",
        )

    def handle(self, *args, **options):
        message_id, erro = enviar_notificacao_qualidade(
            telefone=options["telefone"],
            mensagem=options["mensagem"],
        )

        if erro:
            self.stderr.write(self.style.ERROR(erro))
            return

        self.stdout.write(self.style.SUCCESS(f"Mensagem enviada. id={message_id}"))
