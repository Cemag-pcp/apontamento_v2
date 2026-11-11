import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


# Rota de acesso da tela (RotaAccessMiddleware). Fica nesta migração, e não
# numa do core, para não disputar numeração com as migrações do core em
# andamento em outra branch.
def criar_rota(apps, schema_editor):
    RotaAcesso = apps.get_model('core', 'RotaAcesso')
    RotaAcesso.objects.get_or_create(
        nome='inventario',
        defaults={
            'descricao': 'Tela de inventários',
            'tipo_rota': 'template',
            'app': 'inventario',
        },
    )


def remover_rota(apps, schema_editor):
    RotaAcesso = apps.get_model('core', 'RotaAcesso')
    RotaAcesso.objects.filter(nome='inventario').delete()


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0082_rota_cadastro_tubos'),
    ]

    operations = [
        migrations.CreateModel(
            name='Inventario',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=100, unique=True)),
                ('descricao', models.TextField(blank=True, default='')),
                ('status', models.CharField(choices=[('aberto', 'Aberto'), ('finalizado', 'Finalizado')], default='aberto', max_length=20)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('criado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='inventarios_criados', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Inventário',
                'verbose_name_plural': 'Inventários',
                'ordering': ['-criado_em'],
            },
        ),
        migrations.RunPython(criar_rota, remover_rota),
    ]
