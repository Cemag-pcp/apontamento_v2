# Generated by Django 5.0.6 on 2025-04-17 11:51

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('apontamento_estamparia', '0009_remove_imagemnaoconformidade_nao_conformidade_and_more'),
        ('inspecao', '0027_alter_dadosexecucaoinspecao_data_execucao'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='infoadicionaisinspecaoestamparia',
            name='destino',
        ),
        migrations.CreateModel(
            name='DadosNaoConformidade',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('qt_nao_conformidade', models.IntegerField()),
                ('destino', models.CharField(choices=[('retrabalho', 'Retrabalho'), ('sucata', 'Sucata')], max_length=10)),
                ('causas', models.ManyToManyField(blank=True, related_name='causas_nao_conformidade_estamparia', to='inspecao.causas')),
                ('informacoes_adicionais_estamparia', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='apontamento_estamparia.infoadicionaisinspecaoestamparia')),
            ],
        ),
        migrations.CreateModel(
            name='ImagemNaoConformidade',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('imagem', models.ImageField(upload_to='nao_conformidade_estamparia/')),
                ('nao_conformidade', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='imagens', to='apontamento_estamparia.dadosnaoconformidade')),
            ],
        ),
    ]
