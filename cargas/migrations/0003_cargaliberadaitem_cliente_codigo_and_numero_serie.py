from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cargas", "0002_cargaliberadaitem_presente_no_carreta"),
    ]

    operations = [
        migrations.AddField(
            model_name="cargaliberadaitem",
            name="cliente_codigo",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="cargaliberadaitem",
            name="numero_serie",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
    ]
