from decimal import Decimal

from django.db import migrations, models


def preencher_acumulados(apps, schema_editor):
    AnaliseBanhoEzinger = apps.get_model("inspecao", "AnaliseBanhoEzinger")

    for registro in AnaliseBanhoEzinger.objects.all().iterator():
        registro.desengraxante_acumulado = (
            (registro.desengraxante_amostra_1 or Decimal("0.00"))
            + (registro.desengraxante_amostra_2 or Decimal("0.00"))
            + (registro.desengraxante_amostra_3 or Decimal("0.00"))
        )
        registro.fosfatizante_acumulado = (
            (registro.fosfatizante_amostra_1 or Decimal("0.00"))
            + (registro.fosfatizante_amostra_2 or Decimal("0.00"))
            + (registro.fosfatizante_amostra_3 or Decimal("0.00"))
        )
        registro.save(
            update_fields=[
                "desengraxante_acumulado",
                "fosfatizante_acumulado",
            ]
        )


class Migration(migrations.Migration):
    dependencies = [
        ("inspecao", "0046_analisebanhoezinger_observacao"),
    ]

    operations = [
        migrations.AddField(
            model_name="analisebanhoezinger",
            name="desengraxante_acumulado",
            field=models.DecimalField(
                decimal_places=2, default=Decimal("0.00"), max_digits=8
            ),
        ),
        migrations.AddField(
            model_name="analisebanhoezinger",
            name="fosfatizante_acumulado",
            field=models.DecimalField(
                decimal_places=2, default=Decimal("0.00"), max_digits=8
            ),
        ),
        migrations.RunPython(
            preencher_acumulados,
            migrations.RunPython.noop,
        ),
    ]
