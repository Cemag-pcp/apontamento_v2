# Generated by Django 4.2.15 on 2025-01-24 16:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cadastro', '0016_motivoexclusao'),
    ]

    operations = [
        migrations.CreateModel(
            name='MotivoMaquinaParada',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=20, unique=True)),
                ('visivel', models.BooleanField(default=True)),
                ('setor', models.ManyToManyField(related_name='motivo_maq_parada_setor', to='cadastro.setor')),
            ],
        ),
    ]
