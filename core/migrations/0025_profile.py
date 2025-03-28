# Generated by Django 4.2.15 on 2025-01-28 12:00

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0024_alter_maquinaparada_motivo'),
    ]

    operations = [
        migrations.CreateModel(
            name='Profile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo_acesso', models.CharField(choices=[('operador', 'Operador'), ('supervisor', 'Supervisor'), ('pcp', 'PCP')], max_length=20)),
                ('setores_permitidos', models.JSONField(default=list)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='profile', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
