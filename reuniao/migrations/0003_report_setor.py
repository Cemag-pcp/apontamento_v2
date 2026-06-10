import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cadastro', '0047_maquina_add_ativo'),
        ('reuniao', '0002_report_concluido'),
    ]

    operations = [
        migrations.AddField(
            model_name='report',
            name='setor',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='reports_reuniao',
                to='cadastro.setor',
            ),
        ),
    ]
