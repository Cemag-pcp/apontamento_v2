from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cadastro", "0051_espessurachapa_tipos_chapa"),
    ]

    operations = [
        migrations.AlterField(
            model_name="espessurachapa",
            name="como_aparece_planilha",
            field=models.CharField(max_length=80),
        ),
    ]
