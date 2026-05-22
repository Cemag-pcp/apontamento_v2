from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cargas", "0007_email_notificacao_carga"),
    ]

    operations = [
        migrations.AddField(
            model_name="cargaliberada",
            name="ativo",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="cargaliberada",
            name="inativada_em",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="cargaliberadaalteracao",
            name="tipo_alteracao",
            field=models.CharField(
                choices=[
                    ("item_adicionado", "Item adicionado"),
                    ("item_removido", "Item removido"),
                    ("quantidade_alterada", "Quantidade alterada"),
                    ("liberacao_inicial", "Liberação inicial"),
                    ("carga_inativada", "Carga inativada"),
                    ("carga_reativada", "Carga reativada"),
                ],
                max_length=30,
            ),
        ),
    ]
