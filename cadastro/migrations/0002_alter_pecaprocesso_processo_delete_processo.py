# Generated by Django 4.2.15 on 2024-10-02 08:13

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('cadastro', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='pecaprocesso',
            name='processo',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='cadastro.setor'),
        ),
        migrations.DeleteModel(
            name='Processo',
        ),
    ]
