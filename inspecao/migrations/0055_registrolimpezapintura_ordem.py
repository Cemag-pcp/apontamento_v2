from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0082_rota_cadastro_tubos'),
        ('inspecao', '0054_registrolimpezapintura_cor_data_carga'),
    ]

    operations = [
        migrations.AddField(
            model_name='registrolimpezapintura',
            name='ordem',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='registros_limpeza_pintura', to='core.ordem'),
        ),
    ]
