# Generated by Django 4.2.15 on 2025-02-21 16:25

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0035_remove_ordem_setor_conjunto'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='ordem',
            name='tipo',
        ),
    ]
