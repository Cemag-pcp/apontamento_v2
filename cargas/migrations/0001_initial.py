from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CargaLiberada",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("carga_uuid", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("data_carga", models.DateField()),
                ("carga_nome", models.CharField(max_length=100)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["-data_carga", "carga_nome"],
            },
        ),
        migrations.CreateModel(
            name="CargaLiberadaVersao",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("versao", models.PositiveIntegerField()),
                ("versao_uuid", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("data_inicio_pesquisa", models.DateField()),
                ("data_fim_pesquisa", models.DateField()),
                ("liberado_em", models.DateTimeField(auto_now_add=True)),
                ("payload_snapshot", models.JSONField(default=dict)),
                ("carga_liberada", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="versoes", to="cargas.cargaliberada")),
                ("liberado_por", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="cargas_liberadas_versoes", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["carga_liberada_id", "-versao"],
            },
        ),
        migrations.CreateModel(
            name="CargaLiberadaItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("codigo_recurso", models.CharField(max_length=255)),
                ("quantidade", models.FloatField()),
                ("carga_versao", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="itens", to="cargas.cargaliberadaversao")),
            ],
            options={
                "ordering": ["codigo_recurso"],
            },
        ),
        migrations.CreateModel(
            name="CargaLiberadaAlteracao",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tipo_alteracao", models.CharField(choices=[("item_adicionado", "Item adicionado"), ("item_removido", "Item removido"), ("quantidade_alterada", "Quantidade alterada"), ("liberacao_inicial", "Liberação inicial")], max_length=30)),
                ("codigo_recurso", models.CharField(blank=True, max_length=255)),
                ("quantidade_anterior", models.FloatField(blank=True, null=True)),
                ("quantidade_nova", models.FloatField(blank=True, null=True)),
                ("detalhes", models.JSONField(blank=True, default=dict)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("carga_liberada", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="alteracoes", to="cargas.cargaliberada")),
                ("versao_destino", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="alteracoes_destino", to="cargas.cargaliberadaversao")),
                ("versao_origem", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="alteracoes_origem", to="cargas.cargaliberadaversao")),
            ],
            options={
                "ordering": ["id"],
            },
        ),
        migrations.AddConstraint(
            model_name="cargaliberada",
            constraint=models.UniqueConstraint(fields=("data_carga", "carga_nome"), name="uq_carga_liberada_data_nome"),
        ),
        migrations.AddConstraint(
            model_name="cargaliberadaversao",
            constraint=models.UniqueConstraint(fields=("carga_liberada", "versao"), name="uq_carga_liberada_versao"),
        ),
    ]
