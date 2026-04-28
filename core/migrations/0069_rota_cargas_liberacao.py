from django.db import migrations


def cadastrar_rota_cargas_liberacao(apps, schema_editor):
    RotaAcesso = apps.get_model("core", "RotaAcesso")

    RotaAcesso.objects.get_or_create(
        nome="cargas/liberacao",
        defaults={
            "descricao": "Liberação de cargas",
            "tipo_rota": "template",
            "app": "cargas",
        },
    )


def remover_rota_cargas_liberacao(apps, schema_editor):
    RotaAcesso = apps.get_model("core", "RotaAcesso")
    Profile = apps.get_model("core", "Profile")

    try:
        rota = RotaAcesso.objects.get(nome="cargas/liberacao")
    except RotaAcesso.DoesNotExist:
        return

    for profile in Profile.objects.filter(permissoes=rota):
        profile.permissoes.remove(rota)

    if not Profile.objects.filter(permissoes=rota).exists():
        rota.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0068_rota_inspecao_recebimento"),
    ]

    operations = [
        migrations.RunPython(
            cadastrar_rota_cargas_liberacao,
            remover_rota_cargas_liberacao,
        ),
    ]
