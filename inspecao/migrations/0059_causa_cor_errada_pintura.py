from django.db import migrations

# Falha "Cor errada" do grupo "Brilho e Tonalidade" do checklist de pintura:
# única que ainda não existia no cadastro de causas
NOVAS_CAUSAS = ["Cor errada"]


def criar_causas(apps, schema_editor):
    Causas = apps.get_model("inspecao", "Causas")
    for nome in NOVAS_CAUSAS:
        if not Causas.objects.filter(setor="pintura", nome__iexact=nome).exists():
            Causas.objects.create(setor="pintura", nome=nome)


class Migration(migrations.Migration):

    dependencies = [
        ('inspecao', '0058_registro_limpeza_etapas'),
    ]

    operations = [
        migrations.RunPython(criar_causas, migrations.RunPython.noop),
    ]
