from django.db import migrations


def cadastrar(apps, schema_editor):
    RotaAcesso = apps.get_model("core", "RotaAcesso")
    RotaAcesso.objects.get_or_create(
        nome="inspecao/dashboard/recebimento",
        defaults={
            "descricao": "Dashboard Inspeção Recebimento",
            "tipo_rota": "template",
            "app": "inspecao",
        },
    )


def remover(apps, schema_editor):
    RotaAcesso = apps.get_model("core", "RotaAcesso")
    RotaAcesso.objects.filter(nome="inspecao/dashboard/recebimento").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0072_rota_pintura_historico"),
    ]

    operations = [
        migrations.RunPython(cadastrar, remover),
    ]
