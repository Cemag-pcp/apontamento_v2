import pandas as pd
import os
import django
import logging

from django.utils.timezone import now
from django.db import transaction, IntegrityError

from apontamento_corte.utils import normalizar_tempo

# Configuração do Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "apontamento_v2.settings")  
django.setup()

from core.models import Ordem

# Configuração do logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]  # imprime no console
)

try:
    # Laser 1
    ordens_laser1 = Ordem.objects.filter(
        grupo_maquina='laser_1',
        tempo_estimado__contains='.'
    )

    logging.info(f"Encontradas {ordens_laser1.count()} ordens para corrigir em LASER 1")
    for ordem in ordens_laser1.iterator():
        tempo_estimado_corrigido = ordem.tempo_estimado.split('.')[0]
        ordem.tempo_estimado = tempo_estimado_corrigido
        ordem.save(update_fields=["tempo_estimado"])
        logging.debug(f"Ordem {ordem.id} corrigida para {tempo_estimado_corrigido}")

    # Laser 2
    ordens_laser2 = Ordem.objects.filter(
        grupo_maquina='laser_2',
        tempo_estimado__contains='s'
    )

    logging.info(f"Encontradas {ordens_laser2.count()} ordens para corrigir em LASER 2")
    for ordem in ordens_laser2.iterator():
        tempo_estimado_corrigido = normalizar_tempo(ordem.tempo_estimado)
        ordem.tempo_estimado = tempo_estimado_corrigido
        ordem.save(update_fields=["tempo_estimado"])
        logging.debug(f"Ordem {ordem.id} corrigida para {tempo_estimado_corrigido}")

    # Plasma
    ordens_plasma = Ordem.objects.filter(grupo_maquina='plasma')
    logging.info(f"Encontradas {ordens_plasma.count()} ordens para verificar em PLASMA")

    cont = 0
    for ordem in ordens_plasma.iterator():
        if len(str(ordem.tempo_estimado)) == 7:
            cont += 1
            tempo_estimado_corrigido = '0' + str(ordem.tempo_estimado)
            ordem.tempo_estimado = tempo_estimado_corrigido
            ordem.save(update_fields=["tempo_estimado"])
            logging.debug(f"Ordem {ordem.id} corrigida para {tempo_estimado_corrigido}")

    logging.info(f"Total de ordens corrigidas em PLASMA: {cont}")

except Exception as e:
    logging.error(f"Erro ao atualizar tempos estimados: {e}", exc_info=True)
