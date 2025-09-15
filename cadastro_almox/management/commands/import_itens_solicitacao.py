import csv
from django.core.management.base import BaseCommand
from cadastro.models import ItensSolicitacao, ClasseRequisicao

class Command(BaseCommand):
    help = 'Importa itens do arquivo CSV'

    def handle(self, *args, **kwargs):
        with open('itens_solicitacao.csv', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                # Extrai as classes de requisição
                classes = row['Classe Requisição'].split(',')
                # Cria ou obtém as instâncias de ClasseRequisicao
                classe_requisicoes = []
                for class_nome in classes:
                    class_nome = class_nome.strip()
                    classe_requisao, created = ClasseRequisicao.objects.get_or_create(nome=class_nome)
                    classe_requisicoes.append(classe_requisao)

                # Verifica se o item já existe
                item_exists = ItensSolicitacao.objects.filter(codigo=row['Código']).exists()
                if item_exists:
                    self.stdout.write(self.style.WARNING(f'Item com código {row["Código"]} já cadastrado. Pulando...'))
                    continue  # Pula para o próximo item
                
                print(f"Importando: Código: {row['Código']}, Nome: {row['Descrição']}, Unidade: {row['Unid. Medida']}, Classes: {classes}")
                # Cria o item de solicitação
                item = ItensSolicitacao(
                    codigo=row['Código'],
                    nome=row['Descrição'],
                    unidade=row['Unid. Medida'],
                )
                item.save()  # Salva o item
                # Adiciona as classes de requisição ao ManyToManyField
                item.classe_requisicao.set(classe_requisicoes)

        self.stdout.write(self.style.SUCCESS('Importação concluída com sucesso!'))
