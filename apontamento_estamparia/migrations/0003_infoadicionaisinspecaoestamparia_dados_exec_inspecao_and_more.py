# Generated by Django 5.0.6 on 2025-02-27 19:43

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('apontamento_estamparia', '0002_infoadicionaisinspecaoestamparia_and_more'),
        ('cadastro', '0021_alter_conjuntos_codigo'),
        ('inspecao', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='infoadicionaisinspecaoestamparia',
            name='dados_exec_inspecao',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='inspecao.dadosexecucaoinspecao'),
        ),
        migrations.AddField(
            model_name='infoadicionaisinspecaoestamparia',
            name='operador',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='cadastro.operador'),
        ),
        migrations.AddField(
            model_name='medidasinspecaoestamparia',
            name='informacoes_adicionais_estamparia',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='apontamento_estamparia.infoadicionaisinspecaoestamparia'),
        ),
    ]
