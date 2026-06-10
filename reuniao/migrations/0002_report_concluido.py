from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reuniao', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='report',
            name='concluido',
            field=models.BooleanField(default=False),
        ),
    ]
