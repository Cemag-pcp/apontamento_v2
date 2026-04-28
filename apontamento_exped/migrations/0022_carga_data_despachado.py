from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("apontamento_exped", "0021_fornecedoritemcarga_delete_fornecedorescarga"),
    ]

    operations = [
        migrations.AddField(
            model_name="carga",
            name="data_despachado",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
