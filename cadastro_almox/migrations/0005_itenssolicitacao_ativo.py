from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cadastro_almox', '0004_funcionario_ativo'),
    ]

    operations = [
        migrations.AddField(
            model_name='itenssolicitacao',
            name='ativo',
            field=models.BooleanField(default=True),
        ),
    ]
