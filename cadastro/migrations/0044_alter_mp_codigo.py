from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cadastro', '0043_itensexplodidos'),
    ]

    operations = [
        migrations.AlterField(
            model_name='mp',
            name='codigo',
            field=models.CharField(max_length=100),
        ),
    ]
