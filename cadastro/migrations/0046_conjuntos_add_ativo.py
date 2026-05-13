from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cadastro', '0045_pecas_add_ativo'),
    ]

    operations = [
        migrations.AddField(
            model_name='conjuntos',
            name='ativo',
            field=models.BooleanField(default=True),
        ),
    ]
