from django.db import migrations


NOVAS_CAUSAS_MONTAGEM = [
    "Folgas",
    "Desalinhamentos",
    "Falta de solda",
    "Mordedura",
    "Porosidade",
    "Respingo de Solda",
    "Perfuração",
    "Falta de peças",
    "Aspecto visual da solda",
]

# Causas que ja existiam com esse nome exato e devem ser reaproveitadas
# (mantidas ativas) em vez de duplicadas.
CAUSAS_REAPROVEITADAS = {"Mordedura", "Porosidade"}


def ajustar_causas(apps, schema_editor):
    Causas = apps.get_model("inspecao", "Causas")

    # Desativa todas as causas de montagem que nao fazem parte da lista nova,
    # sem excluir - registros historicos que ja usam essas causas continuam
    # com a referencia intacta, so paramos de oferece-las no checklist.
    Causas.objects.filter(setor="montagem").exclude(
        nome__in=NOVAS_CAUSAS_MONTAGEM
    ).update(excluida=True)

    for nome in NOVAS_CAUSAS_MONTAGEM:
        causa, criada = Causas.objects.get_or_create(
            setor="montagem", nome=nome, defaults={"excluida": False}
        )
        if not criada and causa.excluida:
            causa.excluida = False
            causa.save(update_fields=["excluida"])


def reverter_causas(apps, schema_editor):
    Causas = apps.get_model("inspecao", "Causas")

    # Reativa tudo que foi desativado por essa migracao
    Causas.objects.filter(setor="montagem").update(excluida=False)

    # Remove as causas novas que essa migracao criou e que nunca foram
    # usadas em nenhum registro (as reaproveitadas - Mordedura/Porosidade -
    # ja existiam antes e nao devem ser removidas).
    Causas.objects.filter(
        setor="montagem",
        nome__in=set(NOVAS_CAUSAS_MONTAGEM) - CAUSAS_REAPROVEITADAS,
        causas_nao_conformidade__isnull=True,
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("inspecao", "0049_recebimento_excluido"),
    ]

    operations = [
        migrations.RunPython(ajustar_causas, reverter_causas),
    ]
