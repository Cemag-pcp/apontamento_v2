from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("cargas", "0002_cargaliberadaitem_presente_no_carreta"),
        ("core", "0069_rota_cargas_liberacao"),
    ]

    operations = [
        migrations.AddField(
            model_name="ordem",
            name="carga_liberada",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="ordens_sequenciadas",
                to="cargas.cargaliberada",
            ),
        ),
        migrations.AddField(
            model_name="ordem",
            name="carga_liberada_versao",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="ordens_sequenciadas",
                to="cargas.cargaliberadaversao",
            ),
        ),
    ]
