from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="RegistroAcaoSolicitacaoAlmox",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tipo_solicitacao", models.CharField(choices=[("requisicao", "Requisicao"), ("transferencia", "Transferencia")], max_length=20)),
                ("acao", models.CharField(choices=[("edicao", "Edicao"), ("exclusao", "Exclusao")], max_length=20)),
                ("solicitacao_id_original", models.PositiveIntegerField()),
                ("motivo", models.TextField()),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("data_criacao", models.DateTimeField(auto_now_add=True)),
                ("usuario", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="registros_acao_almox", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Registro de acao do almoxarifado",
                "verbose_name_plural": "Registros de acoes do almoxarifado",
                "ordering": ["-data_criacao"],
            },
        ),
    ]
