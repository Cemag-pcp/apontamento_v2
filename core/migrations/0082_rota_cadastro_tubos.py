from django.db import migrations


def criar_rota_cadastro_tubos(apps, schema_editor):
    RotaAcesso = apps.get_model('core', 'RotaAcesso')
    RotaAcesso.objects.get_or_create(
        nome='cadastro/cadastro-tubos',
        defaults={'descricao': 'Cadastro de tubos', 'tipo_rota': 'template', 'app': 'cadastro'},
    )


def remover_rota_cadastro_tubos(apps, schema_editor):
    RotaAcesso = apps.get_model('core', 'RotaAcesso')
    RotaAcesso.objects.filter(nome='cadastro/cadastro-tubos').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0081_rota_indicadores_inspetores'),
    ]

    operations = [
        migrations.RunPython(criar_rota_cadastro_tubos, remover_rota_cadastro_tubos),
    ]
