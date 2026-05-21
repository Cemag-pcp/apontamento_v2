from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ConferenciaPedido',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('chave_pedido', models.CharField(max_length=100)),
                ('deal_id', models.CharField(max_length=100)),
                ('quote_id', models.CharField(max_length=100)),
                ('data_criacao', models.CharField(blank=True, max_length=100)),
                ('contato', models.CharField(blank=True, max_length=255)),
                ('observacao', models.TextField(blank=True)),
                ('itens', models.JSONField(default=list)),
                ('conferido_em', models.DateTimeField(auto_now_add=True)),
                ('conferido_por', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='conferencias_pedido', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-conferido_em'],
            },
        ),
        migrations.AddConstraint(
            model_name='conferenciapedido',
            constraint=models.UniqueConstraint(fields=('chave_pedido', 'deal_id', 'quote_id'), name='unique_conferencia_pedido'),
        ),
    ]
