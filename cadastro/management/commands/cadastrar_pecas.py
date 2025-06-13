import csv
import re
from django.core.management.base import BaseCommand
from cadastro.models import Maquina, Pecas, Setor
from django.core.management.base import BaseCommand, CommandError

class Command(BaseCommand):
    help = 'Atualiza o campo processo_1 de Peças a partir de um CSV, mas somente para peças no setor=1.'

    def add_arguments(self, parser):
        parser.add_argument('csv_path', type=str, help='Caminho para o arquivo CSV (com colunas "peça" e "processo_1")')

    def handle(self, *args, **options):
        path = options['csv_path']
        try:
            with open(path, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    codigo = row['peça'].strip()
                    proc1_id = row['processo_1'].strip()

                    # 1) Verifica se a máquina existe
                    try:
                        maquina = Maquina.objects.get(pk=proc1_id)
                    except Maquina.DoesNotExist:
                        self.stdout.write(self.style.WARNING(
                            f'Máquina id={proc1_id} não encontrada — pulando peça {codigo}'
                        ))
                        continue

                    # 2) Filtra Peca com esse código e que tenha setor=1
                    qs = Pecas.objects.filter(codigo=codigo)

                    if not qs.exists():
                        self.stdout.write(self.style.WARNING(
                            f'Peca "{codigo}" não encontrada no banco — nada a fazer'
                        ))
                        continue

                    for peca in qs:
                        # Se a peça não tem o setor 1, adiciona o setor 1
                        if not peca.setor.filter(id=1).exists():
                            setor1 = Setor.objects.get(id=1)
                            peca.setor.add(setor1)  # Adiciona o setor 1 à peça
                            self.stdout.write(self.style.SUCCESS(
                                f'Adicionado setor 1 à peça "{codigo}"'
                            ))

                        # 3) Atualiza campo processo_1 da peça
                        peca.processo_1 = maquina
                        peca.save()
                        self.stdout.write(self.style.SUCCESS(
                            f'Atualizado processo_1={proc1_id} para a peça "{codigo}"'
                        ))

        except FileNotFoundError:
            raise CommandError(f'Arquivo não encontrado: {path}')
        except Exception as e:
            raise CommandError(f'Erro ao processar CSV: {e}')
