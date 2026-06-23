from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cadastro_almox', '0005_itenssolicitacao_ativo'),
    ]

    operations = [
        migrations.AddField(
            model_name='itenstransferencia',
            name='ativo',
            field=models.BooleanField(default=True),
        ),
    ]
