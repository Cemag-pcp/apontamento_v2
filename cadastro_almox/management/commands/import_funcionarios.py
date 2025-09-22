import csv
from django.core.management.base import BaseCommand
from cadastro.models import Funcionario, Cc

class Command(BaseCommand):
    help = 'Importa dados de funcionários e centros de custo a partir de um arquivo CSV'

    def handle(self, *args, **kwargs):
        with open('funcionarios.csv', 'r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                matricula = row['MATRICULA']
                nome_funcionario = row['COLABORADOR']
                cc_codes = row['cc'].split('-')

                # Obtém ou cria os objetos de Cc
                cc_objects = []
                for code in cc_codes:
                    cc_obj, created = Cc.objects.get_or_create(
                        codigo=code,
                        defaults={'nome': f'CC {code}'}
                    )
                    cc_objects.append(cc_obj)

                # Obtém ou cria o Funcionario
                funcionario, created = Funcionario.objects.get_or_create(
                    matricula=matricula,
                    defaults={'nome': nome_funcionario}
                )

                # Atualiza os centros de custo associados ao funcionário
                funcionario.cc.set(cc_objects)

                # Salva as mudanças
                funcionario.save()

                self.stdout.write(self.style.SUCCESS(f'Funcionário {nome_funcionario} atualizado com sucesso.'))
