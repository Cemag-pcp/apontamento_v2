# Generated by Django 5.0.6 on 2025-03-14 18:50

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cadastro', '0022_pecasestanqueidade'),
        ('inspecao', '0012_remove_inspecaoestanqueidade_codigo_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='inspecaoestanqueidade',
            name='peca',
            field=models.ForeignKey(blank=True, default='', null=True, on_delete=django.db.models.deletion.CASCADE, to='cadastro.pecasestanqueidade'),
        ),
    ]
