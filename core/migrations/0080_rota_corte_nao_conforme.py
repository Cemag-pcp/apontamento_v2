from django.db import migrations


def criar_rota_corte_nao_conforme(apps, schema_editor):
    RotaAcesso = apps.get_model('core', 'RotaAcesso')
    RotaAcesso.objects.get_or_create(
        nome='corte/nao-conforme',
        defaults={
            'descricao': 'Corte - Peças não conforme',
            'tipo_rota': 'template',
            'app': 'corte',
        },
    )


def remover_rota_corte_nao_conforme(apps, schema_editor):
    RotaAcesso = apps.get_model('core', 'RotaAcesso')
    RotaAcesso.objects.filter(nome='corte/nao-conforme').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0079_rota_cadastro_configuracoes'),
    ]

    operations = [
        migrations.RunPython(criar_rota_corte_nao_conforme, remover_rota_corte_nao_conforme),
    ]
