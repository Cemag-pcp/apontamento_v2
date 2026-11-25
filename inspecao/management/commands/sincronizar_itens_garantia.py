from django.core.management.base import BaseCommand, CommandError

from inspecao.views.garantia import sincronizar_itens_garantia


class Command(BaseCommand):
    help = (
        "Sincroniza os itens de garantia (planilha de cargas, aba \"Importar Dados\", "
        "Carga = GARANTIA) com a tela de Inspeção de Item de Garantia. "
        "Roda todo dia de madrugada pelo GitHub Actions."
    )

    # Mesmo motivo do verificar_qualidade_inspecao: os checks padrão importam o
    # urls.py do projeto inteiro (módulos com efeito colateral no import) e
    # exigem credenciais que este comando não usa.
    requires_system_checks = []

    def handle(self, *args, **options):
        resumo, erro = sincronizar_itens_garantia(forcar=True, origem="agendamento")
        if erro:
            raise CommandError(erro)
        self.stdout.write(self.style.SUCCESS(
            f"Garantia sincronizada: {resumo['na_planilha']} item(ns) na planilha, "
            f"{resumo['novos']} novo(s), {resumo['atualizados']} atualizado(s)."
        ))
