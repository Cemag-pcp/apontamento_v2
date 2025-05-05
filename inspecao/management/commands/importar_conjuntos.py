# sua_app/management/commands/importar_conjuntos.py

import json
import os

from django.core.management.base import BaseCommand
from apontamento_montagem.models import ConjuntosInspecionados
from django.conf import settings

class Command(BaseCommand):
    help = 'Importa conjuntos inspecionados do arquivo conjuntos_inspecionados.json'

    def handle(self, *args, **options):
        # Caminho automático do JSON
        json_path = os.path.join(settings.BASE_DIR, 'conjuntos_inspecionados.json')

        try:
            with open(json_path, 'r', encoding='utf-8') as jsonfile:
                data = json.load(jsonfile)
                conjuntos = data.get('conjuntos_inspecionados', [])

                for item in conjuntos:
                    codigo = item.get('codigo')
                    descricao = item.get('descricao')

                    if codigo and descricao:
                        conjunto, created = ConjuntosInspecionados.objects.get_or_create(
                            codigo=codigo,
                            defaults={'descricao': descricao}
                        )
                        if created:
                            self.stdout.write(self.style.SUCCESS(f"Importado: {codigo} - {descricao}"))
                        else:
                            self.stdout.write(self.style.WARNING(f"Já existe: {codigo} - {descricao}"))
                    else:
                        self.stderr.write(self.style.ERROR(f"Item inválido no JSON: {item}"))

        except FileNotFoundError:
            self.stderr.write(self.style.ERROR(f"Arquivo não encontrado: {json_path}"))
        except json.JSONDecodeError:
            self.stderr.write(self.style.ERROR(f"Erro ao decodificar JSON em: {json_path}"))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Erro ao importar: {str(e)}"))
