from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("apontamento_estamparia", "0014_infoadicionaisinspecaoestamparia_inspecao_finalizada"),
    ]

    operations = [
        migrations.AddField(
            model_name="infoadicionaisinspecaoestamparia",
            name="qtd_mortas_inicio_operacao",
            field=models.IntegerField(default=0),
        ),
    ]

