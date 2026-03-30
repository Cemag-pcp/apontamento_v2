from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("cadastro_almox", "0002_regraslaalmox"),
        ("solicitacao_almox", "0002_solicitacaorequisicao_chave_innovaro_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="solicitacaorequisicao",
            name="status",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="requisicoes_status",
                to="cadastro_almox.regraslaalmox",
            ),
        ),
        migrations.AddField(
            model_name="solicitacaotransferencia",
            name="status",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="transferencias_status",
                to="cadastro_almox.regraslaalmox",
            ),
        ),
    ]
