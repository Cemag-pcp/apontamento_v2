from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cadastro', '0047_maquina_add_ativo'),
        ('core', '0077_rota_reuniao'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='setores',
            field=models.ManyToManyField(
                blank=True,
                related_name='perfis',
                to='cadastro.setor',
            ),
        ),
    ]
