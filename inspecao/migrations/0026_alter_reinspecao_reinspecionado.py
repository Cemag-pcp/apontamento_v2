# Generated by Django 4.2.15 on 2025-03-29 14:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inspecao', '0025_alter_reinspecao_reinspecionado'),
    ]

    operations = [
        migrations.AlterField(
            model_name='reinspecao',
            name='reinspecionado',
            field=models.BooleanField(default=False),
        ),
    ]
