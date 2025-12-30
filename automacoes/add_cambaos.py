import pandas as pd
import os
import django

from django.utils.timezone import now  # Para trabalhar com data e hora
from django.shortcuts import get_object_or_404  # Para buscar objetos no banco de dados
from django.db import connection
from django.db import transaction, models, IntegrityError

# Configurações do Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "apontamento_v2.settings")  
django.setup()

from apontamento_pintura.models import Cambao

registros = [
    (9, "Cinza", "livre", "PÓ", "Único 4"),
    (10, "Cinza", "livre", "PÓ", "Único 5"),
    (12, "Cinza", "livre", "PÓ", "Único 7"),
    (14, "Cinza", "livre", "PU", "6"),
    (15, "Cinza", "livre", "PU", "7"),
    (4, "Laranja", "livre", "PU", "4"),
    (7, "Cinza", "livre", "PÓ", "Único 2"),
    (11, "Cinza", "livre", "PÓ", "Único 6"),
    (1, "Cinza", "livre", "PU", "1"),
    (5, "Vermelho", "livre", "PÓ", "Único 1"),
    (2, "Cinza", "livre", "PU", "2"),
    (3, "Cinza", "livre", "PU", "3"),
    (16, "Vermelho", "em uso", "PU", "8"),
    (8, "Vermelho", "em uso", "PÓ", "Único 3"),
    (13, "Cinza", "livre", "PU", "5"),
]

for _, cor, status, tipo, nome in registros:
    try:
        Cambao.objects.update_or_create(
            tipo=tipo.strip(),
            nome=nome.strip(),
            defaults={
                "cor": cor.strip(),
                "status": status.strip()
            }
        )
    except IntegrityError as e:
        print(f"Erro com {nome}: {e}")
        continue
    