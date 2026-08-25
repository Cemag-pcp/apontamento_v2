from django.db import migrations


def criar_rota_cadastro_configuracoes(apps, schema_editor):
    RotaAcesso = apps.get_model('core', 'RotaAcesso')
    RotaAcesso.objects.get_or_create(
        nome='cadastro/configuracoes',
        defaults={
            'descricao': 'Configurações - Destinatários de notificação',
            'tipo_rota': 'template',
            'app': 'cadastro',
        },
    )


def remover_rota_cadastro_configuracoes(apps, schema_editor):
    RotaAcesso = apps.get_model('core', 'RotaAcesso')
    RotaAcesso.objects.filter(nome='cadastro/configuracoes').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0078_profile_setores'),
    ]

    operations = [
        migrations.RunPython(criar_rota_cadastro_configuracoes, remover_rota_cadastro_configuracoes),
    ]
