# Generated by Django 4.2.15 on 2025-05-12 16:56

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('cadastro', '0028_pecas_processo_1'),
    ]

    operations = [
        migrations.AlterField(
            model_name='pecas',
            name='conjunto',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='peca_conjunto', to='cadastro.conjuntos'),
        ),
    ]
