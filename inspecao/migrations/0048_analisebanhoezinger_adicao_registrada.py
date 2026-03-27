from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0066_remove_consultasaldoinnovaro_core_consul_codigo_f3813a_idx_and_more"),
        ("inspecao", "0047_analisebanhoezinger_acumulados"),
    ]

    operations = [
        migrations.AddField(
            model_name="analisebanhoezinger",
            name="adicao_registrada_em",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="analisebanhoezinger",
            name="adicao_registrada_por",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="banhos_ezinger_com_adicao_registrada",
                to="core.profile",
            ),
        ),
    ]
