from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cargas", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="cargaliberadaitem",
            name="presente_no_carreta",
            field=models.CharField(blank=True, default="", max_length=5),
        ),
    ]
