from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inspecao', '0048_analisebanhoezinger_adicao_registrada'),
    ]

    operations = [
        migrations.AddField(
            model_name='inspecaorecebimento',
            name='excluido',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='inspecaorecebimentoitem',
            name='excluido',
            field=models.BooleanField(default=False),
        ),
    ]
