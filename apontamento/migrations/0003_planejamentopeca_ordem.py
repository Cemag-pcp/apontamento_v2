# Generated by Django 4.2.15 on 2024-10-02 08:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('apontamento', '0002_planejamento_setor'),
    ]

    operations = [
        migrations.AddField(
            model_name='planejamentopeca',
            name='ordem',
            field=models.IntegerField(default=1),
        ),
    ]
