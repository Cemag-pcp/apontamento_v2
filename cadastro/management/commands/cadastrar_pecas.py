from django.core.management.base import BaseCommand
from django.db.utils import IntegrityError

from cadastro.models import Pecas

import csv

class Command(BaseCommand):
    # """
    # Forma de rodar:
    # python manage.py cadastrar_pecas C:\Users\pcp2\sistema_apontamento_2\pecas_new.csv

    # Modelo em csv:
    # codigo,descricao,materia_prima
    # """

    help = 'Cadastra peças em massa a partir de um arquivo CSV'

    def add_arguments(self, parser):
        # Argumento para o caminho do arquivo CSV
        parser.add_argument('csv_filepath', type=str, help='Caminho do arquivo CSV contendo os dados das peças.')

    def handle(self, *args, **kwargs):
        # Obtém o caminho do arquivo CSV do argumento
        csv_filepath = kwargs['csv_filepath']

        # Lê o arquivo CSV
        with open(csv_filepath, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)

            # Itera sobre as linhas do CSV e cadastra as peças
            for row in reader:
                codigo = row['codigo']
                descricao = row['descricao']
                materia_prima = row['materia_prima']

                try:
                    # Cria a peça, e verifica duplicidade no código
                    peca, created = Pecas.objects.get_or_create(
                        codigo=codigo,
                        defaults={
                            'descricao': descricao,
                            'materia_prima': materia_prima,
                        }
                    )
                    if created:
                        self.stdout.write(self.style.SUCCESS(f'Peça cadastrada: {codigo} - {descricao}'))
                    else:
                        self.stdout.write(self.style.WARNING(f'Peça já existente: {codigo} - {descricao}'))

                except IntegrityError:
                    self.stdout.write(self.style.ERROR(f'Erro ao cadastrar a peça: {codigo} - {descricao}'))
