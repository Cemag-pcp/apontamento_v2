from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('comercial', '0002_pendenciaimportacaoplanilha'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='conferenciapedido',
            index=models.Index(
                fields=['chave_pedido', 'deal_id'],
                name='conf_pedido_chave_deal_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='pendenciaimportacaoplanilha',
            index=models.Index(
                fields=['ped_emissao'],
                name='pend_import_emissao_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='pendenciaimportacaoplanilha',
            index=models.Index(
                fields=['ped_chcriacao', 'ped_idnegociacao'],
                name='pend_import_chave_neg_idx',
            ),
        ),
    ]
