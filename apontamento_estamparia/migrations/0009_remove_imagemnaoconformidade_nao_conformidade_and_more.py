# Generated by Django 5.0.6 on 2025-04-17 11:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('apontamento_estamparia', '0008_dadosnaoconformidade_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='imagemnaoconformidade',
            name='nao_conformidade',
        ),
        migrations.AddField(
            model_name='infoadicionaisinspecaoestamparia',
            name='destino',
            field=models.CharField(choices=[('retrabalho', 'Retrabalho'), ('sucata', 'Sucata')], default='retrabalho', max_length=10),
        ),
        migrations.DeleteModel(
            name='DadosNaoConformidade',
        ),
        migrations.DeleteModel(
            name='ImagemNaoConformidade',
        ),
    ]
