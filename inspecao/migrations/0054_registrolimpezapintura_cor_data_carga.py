from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inspecao', '0053_registro_limpeza_pintura'),
    ]

    operations = [
        migrations.AddField(
            model_name='registrolimpezapintura',
            name='cor',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='registrolimpezapintura',
            name='data_carga',
            field=models.DateField(blank=True, null=True),
        ),
    ]
