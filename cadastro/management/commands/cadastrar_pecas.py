import csv
import re
from django.core.management.base import BaseCommand
from cadastro.models import Conjuntos, Carretas, ConjuntoCarreta  # Ajuste para seu app

class Command(BaseCommand):
    help = 'Importa conjuntos e amarra às carretas'

    def handle(self, *args, **kwargs):
        csv_file_path = r'C:\Users\pcp2\apontamento_usinagem\conj_carreta.csv'  # Substitua pelo caminho real

        conjuntos_list = []  # Lista para inserção em massa
        relacoes_list = []  # Lista para vincular Conjuntos às Carretas

        with open(csv_file_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile, delimiter=',')  # Ajuste o delimitador se necessário
            
            for row in reader:
                codigo_descricao = row['codigo'].strip()
                quantidade = int(row['quantidade'])
                nome_carreta = row['carreta'].strip()

                # Separando código e descrição, independente se for numérico ou não
                partes = codigo_descricao.split(" - ", 1)  # Divide pelo primeiro " - "
                codigo = partes[0].strip()  # Sempre pega a primeira parte como código
                descricao = partes[1].strip() if len(partes) > 1 else ""  # Se houver uma descrição, pega a segunda parte

                # Verificar se a carreta já existe
                try:
                    carreta = Carretas.objects.get(codigo=nome_carreta)
                except Carretas.DoesNotExist:
                    self.stdout.write(self.style.ERROR(f"Carreta '{nome_carreta}' não encontrada!"))
                    continue  # Pula esse registro

                # Criar conjunto se não existir
                conjunto, created = Conjuntos.objects.get_or_create(
                    codigo=codigo,
                    defaults={'descricao': descricao, 'quantidade': quantidade}
                )

                # Criar relação ManyToMany via tabela intermediária
                relacoes_list.append(ConjuntoCarreta(conjunto=conjunto, carreta=carreta))

        # Inserir em massa
        ConjuntoCarreta.objects.bulk_create(relacoes_list, ignore_conflicts=True)

        self.stdout.write(self.style.SUCCESS(f"Importação concluída! {len(relacoes_list)} registros adicionados."))
