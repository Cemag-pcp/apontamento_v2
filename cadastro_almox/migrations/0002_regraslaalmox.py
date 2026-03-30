from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cadastro_almox', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='RegraSlaAlmox',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('prioridade', models.CharField(max_length=50, unique=True)),
                ('minutos_limite', models.PositiveIntegerField()),
                ('ativo', models.BooleanField(default=True)),
                ('data_criacao', models.DateTimeField(auto_now_add=True)),
                ('data_atualizacao', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Regra de SLA',
                'verbose_name_plural': 'Regras de SLA',
                'ordering': ['minutos_limite', 'prioridade'],
            },
        ),
    ]
