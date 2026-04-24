from django.db import migrations


def cadastrar_rota_inspecao_recebimento(apps, schema_editor):
    RotaAcesso = apps.get_model("core", "RotaAcesso")

    RotaAcesso.objects.get_or_create(
        nome="inspecao/recebimento",
        defaults={
            "descricao": "Inspeção de Recebimento",
            "tipo_rota": "template",
            "app": "inspecao",
        },
    )


def remover_rota_inspecao_recebimento(apps, schema_editor):
    RotaAcesso = apps.get_model("core", "RotaAcesso")
    Profile = apps.get_model("core", "Profile")

    try:
        rota = RotaAcesso.objects.get(nome="inspecao/recebimento")
    except RotaAcesso.DoesNotExist:
        return

    for profile in Profile.objects.filter(permissoes=rota):
        profile.permissoes.remove(rota)

    if not Profile.objects.filter(permissoes=rota).exists():
        rota.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0067_rota_banhos_ezinger_e_permissao_severiano"),
    ]

    operations = [
        migrations.RunPython(
            cadastrar_rota_inspecao_recebimento,
            remover_rota_inspecao_recebimento,
        ),
    ]

