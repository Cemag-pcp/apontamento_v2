from django.db import migrations, models


def criar_rota_reuniao(apps, schema_editor):
    RotaAcesso = apps.get_model('core', 'RotaAcesso')
    RotaAcesso.objects.get_or_create(
        nome='reuniao',
        defaults={
            'descricao': 'Reunião - Situação da Produção',
            'tipo_rota': 'template',
            'app': 'reuniao',
        },
    )


def remover_rota_reuniao(apps, schema_editor):
    RotaAcesso = apps.get_model('core', 'RotaAcesso')
    RotaAcesso.objects.filter(nome='reuniao').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0076_rota_cadastro_maquinas'),
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
                    ('reuniao', 'Reunião'),
                ],
                max_length=50,
            ),
        ),
        migrations.RunPython(criar_rota_reuniao, remover_rota_reuniao),
    ]
