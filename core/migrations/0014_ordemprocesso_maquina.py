# Generated by Django 4.2.15 on 2025-01-09 12:26

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0013_alter_ordem_grupo_maquina_alter_ordem_maquina'),
    ]

    operations = [
        migrations.AddField(
            model_name='ordemprocesso',
            name='maquina',
            field=models.CharField(blank=True, max_length=30, null=True),
        ),
    ]
