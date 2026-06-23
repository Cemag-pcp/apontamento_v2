# Generated manually to add ERP pointing controls for montagem.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('apontamento_montagem', '0005_takt_celula_excluida'),
    ]

    operations = [
        migrations.AddField(
            model_name='pecasordem',
            name='data_apontamento',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='pecasordem',
            name='resp_apontamento',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='apontamentos_montagem_responsavel',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='pecasordem',
            name='chave_apontamento',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='pecasordem',
            name='apontado',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='pecasordem',
            name='tipo_apontamento',
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
        migrations.AddField(
            model_name='pecasordem',
            name='erro_apontamento',
            field=models.TextField(blank=True, null=True),
        ),
    ]
