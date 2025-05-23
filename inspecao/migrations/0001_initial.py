# Generated by Django 5.0.6 on 2025-02-27 19:43

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('apontamento_estamparia', '0002_infoadicionaisinspecaoestamparia_and_more'),
        ('apontamento_montagem', '0003_pecasordem_processo_ordem'),
        ('apontamento_pintura', '0009_retrabalho'),
        ('core', '0036_remove_ordem_tipo'),
    ]

    operations = [
        migrations.CreateModel(
            name='Causas',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=40)),
                ('setor', models.CharField(max_length=40)),
            ],
        ),
        migrations.CreateModel(
            name='InspecaoEstanqueidade',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('data_inspecao', models.DateTimeField()),
                ('codigo', models.CharField(max_length=50)),
                ('descricao', models.CharField(max_length=50)),
                ('tipo_inspecao', models.CharField(choices=[('tanque', 'Tanque'), ('tubo', 'Tubo'), ('cilindro', 'Cilindro')], max_length=10)),
                ('data_carga', models.DateField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='DadosExecucaoInspecao',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('data_execucao', models.DateTimeField(auto_now_add=True)),
                ('num_execucao', models.IntegerField()),
                ('conformidade', models.IntegerField()),
                ('nao_conformidade', models.IntegerField()),
                ('observacao', models.CharField(blank=True, max_length=150, null=True)),
                ('inspetor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='core.profile')),
            ],
        ),
        migrations.CreateModel(
            name='CausasNaoConformidade',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('foto', models.CharField(max_length=255)),
                ('quantidade', models.IntegerField()),
                ('causa', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='inspecao.causas')),
                ('dados_execucao', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='inspecao.dadosexecucaoinspecao')),
            ],
        ),
        migrations.CreateModel(
            name='DadosExecucaoInspecaoEstanqueidade',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('num_execucao', models.IntegerField()),
                ('data_exec', models.DateTimeField(auto_now_add=True)),
                ('inspetor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='core.profile')),
                ('inspecao_estanqueidade', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='inspecao.inspecaoestanqueidade')),
            ],
        ),
        migrations.CreateModel(
            name='DetalhesPressaoTanque',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('pressao_inicial', models.FloatField()),
                ('pressao_final', models.FloatField()),
                ('nao_conformidade', models.BooleanField(default=False)),
                ('tipo_teste', models.CharField(choices=[('CTPI', 'Corpo do tanque parte inferior'), ('CTL', 'Corpo do tanque + longarinas'), ('CT', 'Corpo do tanque'), ('CTC', 'Corpo do tanque + chassi')], max_length=5)),
                ('tempo_execucao', models.TimeField()),
                ('dados_exec_inspecao', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='inspecao.dadosexecucaoinspecaoestanqueidade')),
            ],
        ),
        migrations.CreateModel(
            name='InfoAdicionaisExecTubosCilindros',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nao_conformidade', models.IntegerField()),
                ('nao_conformidade_refugo', models.IntegerField()),
                ('qtd_inspecionada', models.IntegerField()),
                ('observacao', models.CharField(blank=True, max_length=100, null=True)),
                ('foto_ficha', models.CharField(max_length=150)),
                ('dados_exec_inspecao', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='inspecao.dadosexecucaoinspecaoestanqueidade')),
            ],
        ),
        migrations.CreateModel(
            name='CausasEstanqueidadeTubosCilindros',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('foto', models.CharField(max_length=255)),
                ('quantidade', models.IntegerField()),
                ('causa', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='inspecao.causas')),
                ('info_tubos_cilindros', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='inspecao.infoadicionaisexectuboscilindros')),
            ],
        ),
        migrations.CreateModel(
            name='Inspecao',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('data_inspecao', models.DateTimeField(auto_now_add=True)),
                ('pecas_ordem_estamparia', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='apontamento_estamparia.pecasordem')),
                ('pecas_ordem_montagem', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='apontamento_montagem.pecasordem')),
                ('pecas_ordem_pintura', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='apontamento_pintura.pecasordem')),
            ],
        ),
        migrations.AddField(
            model_name='dadosexecucaoinspecao',
            name='inspecao',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='inspecao.inspecao'),
        ),
        migrations.CreateModel(
            name='Reinspecao',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('data_reinspecao', models.DateTimeField(auto_now_add=True)),
                ('dados_execucao', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='inspecao.dadosexecucaoinspecao')),
            ],
        ),
        migrations.CreateModel(
            name='ReinspecaoEstanqueidade',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('data_reinsp', models.DateTimeField(auto_now_add=True)),
                ('dados_exec_inspecao', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='inspecao.dadosexecucaoinspecaoestanqueidade')),
            ],
        ),
    ]
