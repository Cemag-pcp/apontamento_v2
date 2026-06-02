from django.db import migrations, models


def criar_rota_cadastro_maquinas(apps, schema_editor):
    RotaAcesso = apps.get_model('core', 'RotaAcesso')
    RotaAcesso.objects.get_or_create(
        nome='cadastro/maquinas',
        defaults={
            'descricao': 'Cadastro de Máquinas',
            'tipo_rota': 'template',
            'app': 'cadastro',
        },
    )


def remover_rota_cadastro_maquinas(apps, schema_editor):
    RotaAcesso = apps.get_model('core', 'RotaAcesso')
    RotaAcesso.objects.filter(nome='cadastro/maquinas').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0075_rota_compras_analise'),
    ]

    operations = [
        migrations.AlterField(
            model_name='rotaacesso',
            name='app',
            field=models.CharField(
                choices=[
                    ('core', 'Core'),
                    ('users', 'Users'),
                    ('sucata', 'Sucata'),
                    ('serra', 'Serra'),
                    ('estamparia', 'Estamparia'),
                    ('montagem', 'Montagem'),
                    ('pintura', 'Pintura'),
                    ('prod_especiais', 'Prod Especiais'),
                    ('corte', 'Corte'),
                    ('solda', 'Solda'),
                    ('expedicao', 'Expedição'),
                    ('usinagem', 'Usinagem'),
                    ('cargas', 'Cargas'),
                    ('inspecao', 'Inspeção'),
                    ('almoxarifado', 'Almoxarifado'),
                    ('compras', 'Compras'),
                    ('comercial', 'Comercial'),
                    ('cadastro', 'Cadastro'),
                ],
                max_length=50,
            ),
        ),
        migrations.RunPython(criar_rota_cadastro_maquinas, remover_rota_cadastro_maquinas),
    ]
