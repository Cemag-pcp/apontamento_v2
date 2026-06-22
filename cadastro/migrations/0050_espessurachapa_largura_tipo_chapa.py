from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cadastro", "0049_atualiza_espessuras_chapas"),
    ]

    operations = [
        migrations.AddField(
            model_name="espessurachapa",
            name="largura",
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name="espessurachapa",
            name="tipo_chapa",
            field=models.CharField(
                blank=True,
                choices=[
                    ("aco_carbono", "Aço carbono"),
                    ("alta_resistencia", "Alta resistência"),
                    ("anti_derrapante", "Anti derrapante"),
                    ("aco_inox", "Aço inox"),
                ],
                max_length=30,
                null=True,
            ),
        ),
    ]
