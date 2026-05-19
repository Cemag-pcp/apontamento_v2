from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cadastro_almox', '0003_regraslaalmox_cor'),
    ]

    operations = [
        migrations.AddField(
            model_name='funcionario',
            name='ativo',
            field=models.BooleanField(default=True),
        ),
    ]
