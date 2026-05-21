from django.db import migrations


def criar_rota_compras(apps, schema_editor):
    RotaAcesso = apps.get_model('core', 'RotaAcesso')
    RotaAcesso.objects.get_or_create(
        nome='compras',
        defaults={
            'descricao': 'Tela de analise de compras',
            'tipo_rota': 'template',
            'app': 'compras',
        },
    )


def remover_rota_compras(apps, schema_editor):
    RotaAcesso = apps.get_model('core', 'RotaAcesso')
    RotaAcesso.objects.filter(nome='compras').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0074_rota_comercial_conf_pedido'),
    ]

    operations = [
        migrations.RunPython(criar_rota_compras, remover_rota_compras),
    ]
