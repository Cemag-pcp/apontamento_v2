from django.db import migrations, models


def migrar_tipo_para_lista(apps, schema_editor):
    EspessuraChapa = apps.get_model("cadastro", "EspessuraChapa")
    for chapa in EspessuraChapa.objects.exclude(tipo_chapa__isnull=True).exclude(tipo_chapa=""):
        chapa.tipos_chapa = [chapa.tipo_chapa]
        chapa.save(update_fields=["tipos_chapa"])


class Migration(migrations.Migration):

    dependencies = [
        ("cadastro", "0050_espessurachapa_largura_tipo_chapa"),
    ]

    operations = [
        migrations.AddField(
            model_name="espessurachapa",
            name="tipos_chapa",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.RunPython(migrar_tipo_para_lista, migrations.RunPython.noop),
    ]
