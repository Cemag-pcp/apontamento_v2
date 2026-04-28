from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cargas", "0004_cargaliberadaitem_cliente"),
    ]

    operations = [
        migrations.AddField(
            model_name="cargaliberada",
            name="data_sugerida_planejamento",
            field=models.DateField(blank=True, null=True),
        ),
    ]
