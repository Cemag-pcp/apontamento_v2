from django.core.management.base import BaseCommand
from cadastro.models import ItensSolicitacao, ClasseRequisicao

class Command(BaseCommand):
    help = "Atualiza todos os itens com código iniciando em 7 para ter apenas 'Req p Consumo'"

    def handle(self, *args, **options):
        # Obtém ou cria a classe 'Req p Consumo'
        classe_consumo = ClasseRequisicao.objects.get(
            nome="Req p Consumo"
        )
        
        # Filtra itens onde o código (sem espaços) começa com 7
        itens = ItensSolicitacao.objects.filter(
            codigo__iregex=r'^\s*7'  # regex para códigos que começam com 7 (ignorando espaços)
        )
        
        # Atualiza cada item para ter apenas a classe 'Req p Consumo'
        for item in itens:
            item.classe_requisicao.clear()  # Remove todas as classes existentes
            item.classe_requisicao.add(classe_consumo)  # Adiciona apenas 'Req p Consumo'
            self.stdout.write(
                self.style.SUCCESS(f'Atualizado: {item.codigo} - {item.nome}')
            )
        
        self.stdout.write(
            self.style.SUCCESS(f'Concluído! {itens.count()} itens atualizados.')
        )