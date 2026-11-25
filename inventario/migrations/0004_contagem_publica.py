import uuid

from django.db import migrations, models


def gerar_tokens(apps, schema_editor):
    Inventario = apps.get_model('inventario', 'Inventario')
    for inventario in Inventario.objects.all():
        inventario.token_contagem = uuid.uuid4()
        inventario.save(update_fields=['token_contagem'])


class Migration(migrations.Migration):

    dependencies = [
        ('inventario', '0003_lista_contagem'),
    ]

    operations = [
        # campo único com valor gerado: cria sem unique, gera um token por
        # inventário e só depois torna único
        migrations.AddField(
            model_name='inventario',
            name='token_contagem',
            field=models.UUIDField(null=True, editable=False),
        ),
        migrations.RunPython(gerar_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='inventario',
            name='token_contagem',
            field=models.UUIDField(default=uuid.uuid4, unique=True, editable=False),
        ),
        migrations.AddField(
            model_name='itemcontagem',
            name='quantidade',
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=14, null=True),
        ),
        migrations.AddField(
            model_name='itemcontagem',
            name='contado_em',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
