from django.db import migrations

ROTA = "inspecao/garantia"


def criar(apps, schema_editor):
    RotaAcesso = apps.get_model("core", "RotaAcesso")
    Profile = apps.get_model("core", "Profile")

    rota, _ = RotaAcesso.objects.get_or_create(
        nome=ROTA,
        defaults={
            "descricao": "Inspeção de Item de Garantia",
            "tipo_rota": "template",
            "app": "inspecao",
        },
    )

    # quem já inspeciona a montagem também acessa a garantia
    rota_montagem = RotaAcesso.objects.filter(nome="inspecao/montagem").first()
    if rota_montagem:
        for profile in Profile.objects.filter(permissoes=rota_montagem):
            profile.permissoes.add(rota)


def remover(apps, schema_editor):
    RotaAcesso = apps.get_model("core", "RotaAcesso")
    RotaAcesso.objects.filter(nome=ROTA).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("inspecao", "0063_item_garantia"),
        ("core", "0082_rota_cadastro_tubos"),
    ]

    operations = [
        migrations.RunPython(criar, remover),
    ]
