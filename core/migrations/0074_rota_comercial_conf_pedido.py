from django.db import migrations, models


def criar_rota_comercial(apps, schema_editor):
    RotaAcesso = apps.get_model('core', 'RotaAcesso')
    RotaAcesso.objects.get_or_create(
        nome='comercial/conf-pedido',
        defaults={
            'descricao': 'Tela de conferência de pedido comercial',
            'tipo_rota': 'template',
            'app': 'comercial',
        },
    )


def remover_rota_comercial(apps, schema_editor):
    RotaAcesso = apps.get_model('core', 'RotaAcesso')
    RotaAcesso.objects.filter(nome='comercial/conf-pedido').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0073_rota_inspecao_dashboard_recebimento'),
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
                ],
                max_length=50,
            ),
        ),
        migrations.RunPython(criar_rota_comercial, remover_rota_comercial),
    ]
