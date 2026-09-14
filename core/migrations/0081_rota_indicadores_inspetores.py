from django.db import migrations


def criar_rota_indicadores_inspetores(apps, schema_editor):
    RotaAcesso = apps.get_model('core', 'RotaAcesso')
    RotaAcesso.objects.get_or_create(
        nome='controle-de-qualidade/indicadores-inspetores',
        defaults={
            'descricao': 'Controle de Qualidade - Indicadores de inspetores',
            'tipo_rota': 'template',
            'app': 'inspecao',
        },
    )


def remover_rota_indicadores_inspetores(apps, schema_editor):
    RotaAcesso = apps.get_model('core', 'RotaAcesso')
    RotaAcesso.objects.filter(nome='controle-de-qualidade/indicadores-inspetores').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0080_rota_corte_nao_conforme'),
    ]

    operations = [
        migrations.RunPython(criar_rota_indicadores_inspetores, remover_rota_indicadores_inspetores),
    ]
