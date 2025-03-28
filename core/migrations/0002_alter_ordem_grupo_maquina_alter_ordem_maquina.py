# Generated by Django 4.2.15 on 2024-12-23 19:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ordem',
            name='grupo_maquina',
            field=models.CharField(blank=True, choices=[('laser', 'Laser'), ('plasma', 'Plasma'), ('prensa', 'Prensa'), ('usinagem', 'Usinagem'), ('serra', 'Serra')], max_length=20, null=True),
        ),
        migrations.AlterField(
            model_name='ordem',
            name='maquina',
            field=models.CharField(blank=True, choices=[('laser_1', 'Laser 1'), ('laser_2', 'Laser 2 (JFY)'), ('plasma_1', 'Plasma 1'), ('plasma_2', 'Plasma 2'), ('prensa', 'Prensa'), ('furadeira', 'Furadeira'), ('centro_de_usinagem', 'Centro de usinagem'), ('serra_1', 'Serra 1'), ('serra_2', 'Serra 2')], max_length=20, null=True),
        ),
    ]
