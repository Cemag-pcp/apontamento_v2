import csv
from django.core.management.base import BaseCommand
from cadastro.models import DepositoDestino

class Command(BaseCommand):
    help = 'Importa itens de transferência do arquivo CSV'

    def handle(self, *args, **kwargs):
        with open('depositos.csv', 'r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                nome = row['deposito']

                item, created = DepositoDestino.objects.get_or_create(
                    nome=nome
                )

                if created:
                    self.stdout.write(self.style.SUCCESS(f'Item {nome} importado com sucesso.'))
                else:
                    self.stdout.write(self.style.WARNING(f'Item {nome} já existe no banco de dados.'))
