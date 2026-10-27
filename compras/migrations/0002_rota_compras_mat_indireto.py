from django.db import migrations


def criar_rota_mat_indireto(apps, schema_editor):
    RotaAcesso = apps.get_model('core', 'RotaAcesso')
    RotaAcesso.objects.get_or_create(
        nome='compras/mat_indireto',
        defaults={
            'descricao': 'Tela de materiais indiretos (compras)',
            'tipo_rota': 'template',
            'app': 'compras',
        },
    )


def remover_rota_mat_indireto(apps, schema_editor):
    RotaAcesso = apps.get_model('core', 'RotaAcesso')
    RotaAcesso.objects.filter(nome='compras/mat_indireto').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('compras', '0001_initial'),
        ('core', '0082_rota_cadastro_tubos'),
    ]

    operations = [
        migrations.RunPython(criar_rota_mat_indireto, remover_rota_mat_indireto),
    ]
