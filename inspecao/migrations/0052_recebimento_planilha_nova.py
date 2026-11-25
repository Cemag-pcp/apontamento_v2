from django.db import migrations

# A planilha do recebimento mudou (copia da anterior, mesmas linhas). Os itens
# e inspecoes ja sincronizados guardam o id da planilha: sem trocar, a busca
# por chave de negocio (que filtra pela planilha atual) nao os acharia mais e
# duplicaria itens quando uma linha fosse editada.
ANTIGA = '1mLuw4jM5WpD0pgxXREio15Ju8MZZ7QMJHb3vapz94Ac'
NOVA = '1K5MkyAIYmNq3jpSS_GXd5VlqERaBnPW0h8fzxDE-vys'


def trocar(de, para):
    def _run(apps, schema_editor):
        for modelo in ('InspecaoRecebimentoItem', 'InspecaoRecebimento'):
            apps.get_model('inspecao', modelo).objects.filter(planilha_id=de).update(planilha_id=para)
    return _run


class Migration(migrations.Migration):

    dependencies = [
        ('inspecao', '0051_dadosexecucaoinspecaoestanqueidade_operador'),
    ]

    operations = [
        migrations.RunPython(trocar(ANTIGA, NOVA), trocar(NOVA, ANTIGA)),
    ]
