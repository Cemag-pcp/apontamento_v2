from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('apontamento_serra', '0014_remove_imagemnaoconformidade_nao_conformidade_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='infoadicionaisserrausinagem',
            name='qtd_inspecionar',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
