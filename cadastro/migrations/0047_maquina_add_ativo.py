from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cadastro', '0046_conjuntos_add_ativo'),
    ]

    operations = [
        migrations.AddField(
            model_name='maquina',
            name='ativo',
            field=models.BooleanField(default=True),
        ),
    ]
