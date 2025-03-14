# Generated by Django 4.2.15 on 2025-02-27 12:01

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('cadastro', '0021_alter_conjuntos_codigo'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='pecas',
            name='unique_codigo',
        ),
        migrations.AddField(
            model_name='pecas',
            name='conjunto',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, related_name='peca_conjunto', to='cadastro.conjuntos'),
            preserve_default=False,
        ),
        migrations.AddConstraint(
            model_name='pecas',
            constraint=models.UniqueConstraint(fields=('codigo', 'conjunto'), name='unique_codigo_conjunto'),
        ),
    ]
