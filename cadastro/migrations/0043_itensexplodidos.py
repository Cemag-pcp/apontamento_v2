from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cadastro", "0042_carretasexplodidas_peso"),
    ]

    operations = [
        migrations.CreateModel(
            name="ItensExplodidos",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("produto", models.CharField(max_length=255, unique=True)),
            ],
        ),
    ]
