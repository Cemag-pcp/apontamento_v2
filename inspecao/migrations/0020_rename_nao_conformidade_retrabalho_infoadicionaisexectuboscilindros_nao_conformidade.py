# Generated by Django 5.0.6 on 2025-03-17 12:59

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('inspecao', '0019_alter_inspecaoestanqueidade_peca'),
    ]

    operations = [
        migrations.RenameField(
            model_name='infoadicionaisexectuboscilindros',
            old_name='nao_conformidade_retrabalho',
            new_name='nao_conformidade',
        ),
    ]
