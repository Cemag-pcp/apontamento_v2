from django.db import migrations, models


def copiar_largura_para_maxima(apps, schema_editor):
    EspessuraChapa = apps.get_model("cadastro", "EspessuraChapa")
    for chapa in EspessuraChapa.objects.exclude(largura__isnull=True):
        chapa.largura_maxima = chapa.largura
        chapa.save(update_fields=["largura_maxima"])


def limpar_largura_maxima(apps, schema_editor):
    EspessuraChapa = apps.get_model("cadastro", "EspessuraChapa")
    EspessuraChapa.objects.update(largura_maxima=None)


class Migration(migrations.Migration):

    dependencies = [
        ("cadastro", "0052_alter_espessurachapa_como_aparece_planilha"),
    ]

    operations = [
        migrations.AddField(
            model_name="espessurachapa",
            name="largura_maxima",
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=10, null=True),
        ),
        migrations.RunPython(copiar_largura_para_maxima, limpar_largura_maxima),
    ]
