# Generated manually to store Corte sheet transfer audit data.

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0078_profile_setores'),
        ('apontamento_corte', '0006_alter_pecasordem_unique_together'),
    ]

    operations = [
        migrations.CreateModel(
            name='TransferenciaChapaCorte',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('descricao_chapa', models.CharField(blank=True, max_length=255, null=True)),
                ('espessura_planilha', models.CharField(blank=True, max_length=80, null=True)),
                ('espessura_mm', models.CharField(blank=True, max_length=20, null=True)),
                ('codigo_chapa', models.CharField(blank=True, max_length=20, null=True)),
                ('quantidade_chapas', models.FloatField(default=0)),
                ('peso_total', models.FloatField(default=0)),
                ('deposito_origem', models.CharField(max_length=100)),
                ('deposito_destino', models.CharField(max_length=100)),
                ('pessoa', models.CharField(max_length=100)),
                ('payload', models.JSONField(blank=True, null=True)),
                ('resposta_api', models.JSONField(blank=True, null=True)),
                ('chave_transferencia', models.CharField(blank=True, max_length=255, null=True)),
                ('status', models.CharField(choices=[('pendente', 'Pendente'), ('sucesso', 'Sucesso'), ('erro', 'Erro'), ('ignorada', 'Ignorada')], default='pendente', max_length=20)),
                ('erro', models.TextField(blank=True, null=True)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
                ('transferido_em', models.DateTimeField(blank=True, null=True)),
                ('ordem', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='transferencias_chapa_corte', to='core.ordem')),
            ],
            options={
                'ordering': ['-criado_em'],
            },
        ),
        migrations.AddConstraint(
            model_name='transferenciachapacorte',
            constraint=models.UniqueConstraint(fields=('ordem',), name='unique_transferencia_chapa_corte_ordem'),
        ),
    ]
