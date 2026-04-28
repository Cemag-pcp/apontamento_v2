from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cargas", "0003_cargaliberadaitem_cliente_codigo_and_numero_serie"),
    ]

    operations = [
        migrations.AddField(
            model_name="cargaliberadaitem",
            name="cliente",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
    ]
