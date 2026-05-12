from django.db import migrations


def cadastrar(apps, schema_editor):
    RotaAcesso = apps.get_model("core", "RotaAcesso")
    RotaAcesso.objects.get_or_create(
        nome="pintura/historico",
        defaults={
            "descricao": "Histórico de Pintura",
            "tipo_rota": "template",
            "app": "pintura",
        },
    )


def remover(apps, schema_editor):
    RotaAcesso = apps.get_model("core", "RotaAcesso")
    RotaAcesso.objects.filter(nome="pintura/historico").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0071_alter_profile_tipo_acesso_alter_rotaacesso_app"),
    ]

    operations = [
        migrations.RunPython(cadastrar, remover),
    ]
