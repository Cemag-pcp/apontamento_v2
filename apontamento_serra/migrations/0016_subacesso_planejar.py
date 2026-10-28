from django.db import migrations

# Sub-acesso da tela /serra/ (padrao em core/permissoes.py: tipo_rota
# "acao", nome "<tela>#<acao>"). Vale para "Planejar" e "Importar Ordens".
TELA = 'serra'
PLANEJAR = 'serra#planejar'


def criar_subacesso(apps, schema_editor):
    RotaAcesso = apps.get_model('core', 'RotaAcesso')
    Profile = apps.get_model('core', 'Profile')

    planejar, criado = RotaAcesso.objects.get_or_create(
        nome=PLANEJAR,
        defaults={'descricao': 'Planejar ordem', 'tipo_rota': 'acao', 'app': 'serra'},
    )
    # Hoje todo mundo que entra na tela pode planejar: libera pra eles, pra
    # ninguem perder o acesso no deploy. Depois o admin tira de quem nao deve.
    if criado:
        for profile in Profile.objects.filter(permissoes__nome=TELA).distinct():
            profile.permissoes.add(planejar)


def remover_subacesso(apps, schema_editor):
    RotaAcesso = apps.get_model('core', 'RotaAcesso')
    RotaAcesso.objects.filter(nome=PLANEJAR).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('apontamento_serra', '0015_infoadicionaisserrausinagem_qtd_inspecionar'),
        ('core', '0082_rota_cadastro_tubos'),
    ]

    operations = [
        migrations.RunPython(criar_subacesso, remover_subacesso),
    ]
