# Generated manually to add configurable sheet thickness aliases.

from decimal import Decimal

from django.db import migrations, models


ESPESSURAS_CHAPAS = [
    ("14", "2", "120134"),
    ("13", "2.25", "120136"),
    ("12", "2.65", "120549"),
    ("11", "3.175", "120545"),
    ("5/32", "3.75", "120278"),
    ("3/16", "4.75", "120305"),
    ("3/8", "9.525", "120157"),
    ("1/2", "12.7", "120352"),
    ("5/8", "16", "120054"),
    ("3/4", "19.05", "120509"),
    ("1/4", "6.35", "120203"),
    ("12,7 mm", "12.7", "120352"),
    ("18", "1.21", ""),
    ("MS 6,00 mm", "6.35", "120203"),
    ("3,35", "3", "120545"),
    ("1", "25.4", "120376"),
    ("20", "0.91", ""),
    ("MS 3,50 mm", "3", "120545"),
    ("5 mm", "4.75", "120305"),
    ("6 mm", "6.35", "120203"),
    ("10 mm", "10", "120157"),
    ("6,35 mm", "6.35", "120203"),
    ("2,7 mm", "2.65", "120549"),
    ("4,75", "4.75", "120305"),
    ("8 mm", "8", "120650"),
    ("5/16", "8", "120650"),
    ("3/16 A.D", "4.75", "120305"),
    ("MS 3,04 mm A.R", "3.04", ""),
    ("MS 3,04 mm A.D", "3.04", "120110"),
    ("19 mm", "19.04", "120509"),
    ("16 mm", "15.87", "120054"),
    ("3,04 mm Inox", "3.04", "120870"),
    ("26 mm", "25.4", "120376"),
    ("1,5 mm Inox", "1.5", ""),
    ("0,91 mm Inox", "0.91", ""),
    ("4,75 mm Inox", "4.75", ""),
    ("8 mm Inox", "8", ""),
    ("2 mm Inox", "2", ""),
]


def carregar_espessuras_chapas(apps, schema_editor):
    EspessuraChapa = apps.get_model("cadastro", "EspessuraChapa")

    for como_aparece, espessura, codigo in ESPESSURAS_CHAPAS:
        EspessuraChapa.objects.update_or_create(
            como_aparece_planilha=como_aparece,
            defaults={
                "espessura": Decimal(espessura),
                "codigo": codigo or None,
                "ativo": True,
            },
        )


def remover_espessuras_chapas(apps, schema_editor):
    EspessuraChapa = apps.get_model("cadastro", "EspessuraChapa")
    EspessuraChapa.objects.filter(
        como_aparece_planilha__in=[item[0] for item in ESPESSURAS_CHAPAS]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("cadastro", "0047_maquina_add_ativo"),
    ]

    operations = [
        migrations.AddField(
            model_name="espessura",
            name="codigo",
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
        migrations.AddField(
            model_name="espessura",
            name="como_aparece_planilha",
            field=models.CharField(blank=True, max_length=80, null=True),
        ),
        migrations.CreateModel(
            name="EspessuraChapa",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "como_aparece_planilha",
                    models.CharField(max_length=80, unique=True),
                ),
                ("espessura", models.DecimalField(decimal_places=3, max_digits=7)),
                ("codigo", models.CharField(blank=True, max_length=20, null=True)),
                ("ativo", models.BooleanField(default=True)),
            ],
            options={
                "verbose_name": "Espessura de chapa",
                "verbose_name_plural": "Espessuras de chapas",
                "ordering": ["espessura", "como_aparece_planilha"],
            },
        ),
        migrations.RunPython(
            carregar_espessuras_chapas,
            remover_espessuras_chapas,
        ),
    ]
