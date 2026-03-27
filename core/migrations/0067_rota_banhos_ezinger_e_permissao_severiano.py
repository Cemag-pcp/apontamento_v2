from django.conf import settings
from django.db import migrations


def cadastrar_rota_e_permissao(apps, schema_editor):
    RotaAcesso = apps.get_model("core", "RotaAcesso")
    Profile = apps.get_model("core", "Profile")
    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))

    rota, _ = RotaAcesso.objects.get_or_create(
        nome="inspecao/banhos-ezinger",
        defaults={
            "descricao": "Banhos EZINGER",
            "tipo_rota": "template",
            "app": "inspecao",
        },
    )

    try:
        usuario = User.objects.get(username="severiano")
        profile = Profile.objects.get(user=usuario)
    except (User.DoesNotExist, Profile.DoesNotExist):
        return

    profile.permissoes.add(rota)


def remover_permissao_severiano(apps, schema_editor):
    RotaAcesso = apps.get_model("core", "RotaAcesso")
    Profile = apps.get_model("core", "Profile")
    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))

    try:
        rota = RotaAcesso.objects.get(nome="inspecao/banhos-ezinger")
    except RotaAcesso.DoesNotExist:
        return

    try:
        usuario = User.objects.get(username="severiano")
        profile = Profile.objects.get(user=usuario)
    except (User.DoesNotExist, Profile.DoesNotExist):
        profile = None

    if profile:
        profile.permissoes.remove(rota)

    if not Profile.objects.filter(permissoes=rota).exists():
        rota.delete()


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("core", "0066_remove_consultasaldoinnovaro_core_consul_codigo_f3813a_idx_and_more"),
    ]

    operations = [
        migrations.RunPython(
            cadastrar_rota_e_permissao,
            remover_permissao_severiano,
        ),
    ]
