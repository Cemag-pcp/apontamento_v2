import csv
from django.core.management.base import BaseCommand
from cadastro.models import ItensTransferencia

class Command(BaseCommand):
    help = 'Importa itens de transferência do arquivo CSV'

    def handle(self, *args, **kwargs):
        with open('itens transferencia - Página1.csv', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)

            for row in reader:
                codigo = row['Código']
                nome = row['Descrição']

                item, created = ItensTransferencia.objects.get_or_create(
                    codigo=codigo,
                    defaults={'nome': nome}
                )

                if created:
                    self.stdout.write(self.style.SUCCESS(f'Item {codigo} - {nome} importado com sucesso.'))
                else:
                    self.stdout.write(self.style.WARNING(f'Item {codigo} já existe no banco de dados.'))
