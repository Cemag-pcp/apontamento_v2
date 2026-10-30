from django.db import migrations

# Causas principais do checklist de pintura: cria as que faltarem no cadastro
NOVAS_CAUSAS = [
    "Brilho",
    "Camada Baixa",
    "Olho de Peixe",
    "Contaminação",
    "Casca de Laranja",
    "Escorrimento",
    "Marcação por Óleo ou Água",
]


def criar_causas(apps, schema_editor):
    Causas = apps.get_model("inspecao", "Causas")
    for nome in NOVAS_CAUSAS:
        if not Causas.objects.filter(setor="pintura", nome__iexact=nome).exists():
            Causas.objects.create(setor="pintura", nome=nome)


class Migration(migrations.Migration):

    dependencies = [
        ('inspecao', '0056_rascunho_inspecao'),
    ]

    operations = [
        migrations.RunPython(criar_causas, migrations.RunPython.noop),
    ]
