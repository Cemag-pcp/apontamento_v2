import csv
import os
from django.core.management.base import BaseCommand
from django.utils.timezone import localtime

from apontamento_pintura.models import CambaoPecas


class Command(BaseCommand):
    help = 'Exporta apontamentos de pintura para CSV'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            type=str,
            default='apontamento_pintura.csv',
            help='Caminho do arquivo CSV de saída',
        )
        parser.add_argument(
            '--data-inicio',
            type=str,
            default=None,
            help='Filtrar a partir desta data (formato: YYYY-MM-DD)',
        )
        parser.add_argument(
            '--data-fim',
            type=str,
            default=None,
            help='Filtrar até esta data (formato: YYYY-MM-DD)',
        )

    def handle(self, *args, **options):
        from datetime import datetime, date

        qs = CambaoPecas.objects.select_related(
            'cambao',
            'peca_ordem',
            'peca_ordem__ordem',
            'operador_inicio',
        ).order_by('data_pendura')

        data_inicio = options.get('data_inicio')
        data_fim = options.get('data_fim')

        if data_inicio:
            qs = qs.filter(data_pendura__date__gte=data_inicio)
        if data_fim:
            qs = qs.filter(data_pendura__date__lte=data_fim)

        output_path = options['output']

        cabecalho = [
            'ID Registro',
            'Número Ordem',
            'Peça',
            'Cambão',
            'Cor Cambão',
            'Tipo (PÓ/PU)',
            'Operador Início',
            'Data/Hora Pendura',
            'Data/Hora Fim',
            'Quantidade Pendurada',
            'Qtd Planejada (Ordem)',
            'Qtd Boa (Ordem)',
            'Qtd Morta (Ordem)',
            'Status Cambão Peça',
            'Status Ordem',
            'Data Carga',
            'Data Programação',
            'Cor Ordem',
        ]

        total = qs.count()
        self.stdout.write(f'Exportando {total} registros...')

        with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f, delimiter=';')
            writer.writerow(cabecalho)

            for cp in qs:
                peca_ordem = cp.peca_ordem
                ordem = peca_ordem.ordem if peca_ordem else None
                cambao = cp.cambao
                operador = cp.operador_inicio

                data_pendura = localtime(cp.data_pendura).strftime('%d/%m/%Y %H:%M:%S') if cp.data_pendura else ''
                data_fim_cp = localtime(cp.data_fim).strftime('%d/%m/%Y %H:%M:%S') if cp.data_fim else ''

                writer.writerow([
                    cp.id,
                    ordem.ordem if ordem else '',
                    peca_ordem.peca if peca_ordem else '',
                    cambao.nome if cambao else '',
                    cambao.cor if cambao else '',
                    cambao.tipo if cambao else '',
                    operador.nome if operador else '',
                    data_pendura,
                    data_fim_cp,
                    cp.quantidade_pendurada,
                    peca_ordem.qtd_planejada if peca_ordem else '',
                    peca_ordem.qtd_boa if peca_ordem else '',
                    peca_ordem.qtd_morta if peca_ordem else '',
                    cp.status,
                    ordem.status_atual if ordem else '',
                    ordem.data_carga.strftime('%d/%m/%Y') if ordem and ordem.data_carga else '',
                    ordem.data_programacao.strftime('%d/%m/%Y') if ordem and ordem.data_programacao else '',
                    ordem.cor if ordem else '',
                ])

        abs_path = os.path.abspath(output_path)
        self.stdout.write(self.style.SUCCESS(f'CSV exportado com sucesso: {abs_path}'))
        self.stdout.write(f'Total de registros: {total}')
