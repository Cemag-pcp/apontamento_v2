import unicodedata

from django.db import migrations

# Falhas do checklist de montagem em 3 grupos (inspecao/views/montagem.py,
# GRUPOS_CHECKLIST_MONTAGEM). Cada uma usa a causa já cadastrada com nome
# equivalente (sem diferenciar maiúsculas, acento e plural); se ela estiver
# excluída, volta a ficar ativa. Só cria quando não existe nenhuma.
FALHAS = [
    "Folgas", "Desalinhamentos", "Falta de peças",
    "Falta de fusão", "Trincas", "Porosidade", "Mordedura", "Perfuração",
    "Respingo de solda", "Falta de solda", "Sobreposição", "Cratera aberta",
]


def _normalizar(nome):
    texto = unicodedata.normalize("NFKD", str(nome or "")).encode("ascii", "ignore").decode()
    palavras = texto.casefold().split()
    return " ".join(p[:-1] if len(p) > 3 and p.endswith("s") else p for p in palavras)


def preparar_causas(apps, schema_editor):
    Causas = apps.get_model("inspecao", "Causas")
    existentes = list(Causas.objects.filter(setor="montagem").order_by("excluida", "id"))
    for falha in FALHAS:
        chave = _normalizar(falha)
        # prefere a ativa; entre iguais, a mais antiga (order_by acima)
        causa = next((c for c in existentes if _normalizar(c.nome) == chave), None)
        if causa is None:
            existentes.append(Causas.objects.create(setor="montagem", nome=falha))
        elif causa.excluida:
            causa.excluida = False
            causa.save(update_fields=["excluida"])


class Migration(migrations.Migration):

    dependencies = [
        ('inspecao', '0059_causa_cor_errada_pintura'),
    ]

    operations = [
        migrations.RunPython(preparar_causas, migrations.RunPython.noop),
    ]
