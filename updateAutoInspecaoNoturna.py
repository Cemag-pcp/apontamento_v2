import os
import django
import logging
from django.db import transaction
from django.contrib.sessions.models import Session
from django.utils import timezone

# Configuração do Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "apontamento_v2.settings")
django.setup()

from inspecao.models import Inspecao, DadosExecucaoInspecao
from apontamento_estamparia.models import InfoAdicionaisInspecaoEstamparia
from core.models import Profile
from datetime import timedelta
from django.utils.timezone import localtime


# Configuração do logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("update_auto_inspecao_noturna.log"),
        logging.StreamHandler()
    ]
)

def atualizar_auto_inspecao_noturna():
    try:
        logging.info("Iniciando atualização das inspeções noturnas...")
        dados_execucao_inspecoes = InfoAdicionaisInspecaoEstamparia.objects.filter(autoinspecao_noturna=True)
        total = dados_execucao_inspecoes.count()
        logging.info(f"Total de inspeções encontradas: {total}")

        inspetorNoturno = Profile.objects.filter(user__username='autoInspecaoNoturna', user__pk=34).first()
        #id base de teste = 13
        #id base produção = 34
        if not inspetorNoturno:
            logging.error("Inspetor noturno não encontrado!")
            return

        logging.info(f"Inspetor noturno: {inspetorNoturno}")

        atualizados = 0
        with transaction.atomic():
            for dados in dados_execucao_inspecoes:
                original_inspetor = dados.dados_exec_inspecao.inspetor
                original_data = dados.dados_exec_inspecao.data_execucao

                # Atualiza inspetor
                dados.dados_exec_inspecao.inspetor = inspetorNoturno

                original_data = localtime(original_data)
                # Atualiza data_execucao para (data_execucao - 1 dia) às 20:00
                data_execucao_atualizada = (original_data - timedelta(days=1)).replace(hour=20, minute=0, second=0, microsecond=0)
                
                dados.dados_exec_inspecao.data_execucao = data_execucao_atualizada

                dados.dados_exec_inspecao.save()
                atualizados += 1

                logging.info(
                    f"Inspeção ID {dados.dados_exec_inspecao.pk}: "
                    f"Inspetor de '{original_inspetor}' para '{inspetorNoturno}', "
                    f"Data de '{original_data}' para '{data_execucao_atualizada}'"
                )

        logging.info(f"Atualização concluída. Total de inspeções atualizadas: {atualizados}")

    except Exception as e:
        logging.exception("Erro ao atualizar inspeções:")

if __name__ == "__main__":
    atualizar_auto_inspecao_noturna()
