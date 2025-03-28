# Generated by Django 4.2.15 on 2025-02-27 12:01

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('cadastro', '0022_remove_pecas_unique_codigo_pecas_conjunto_and_more'),
        ('core', '0036_remove_ordem_tipo'),
    ]

    operations = [
        migrations.CreateModel(
            name='SolicitacaoPeca',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('qtd_solicitada', models.FloatField(default=1)),
                ('mais_informacoes', models.TextField(blank=True, null=True)),
                ('data_solicitacao', models.DateField(auto_now_add=True)),
                ('data_carga', models.DateField(blank=True, null=True)),
                ('peca', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='peca_solicitacao_peca', to='cadastro.pecas')),
                ('setor_solicitante', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='setor_solicitacao_peca', to='cadastro.setor')),
            ],
        ),
    ]
