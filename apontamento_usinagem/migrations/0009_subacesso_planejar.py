from django.db import migrations

# Sub-acesso da tela /usinagem/ (padrao em core/permissoes.py: tipo_rota
# "acao", nome "<tela>#<acao>").
TELAS = ['usinagem', 'usinagem/processos']  # as duas paginas tem o botao Planejar
PLANEJAR = 'usinagem#planejar'


def criar_subacesso(apps, schema_editor):
    RotaAcesso = apps.get_model('core', 'RotaAcesso')
    Profile = apps.get_model('core', 'Profile')

    planejar, criado = RotaAcesso.objects.get_or_create(
        nome=PLANEJAR,
        defaults={'descricao': 'Planejar ordem', 'tipo_rota': 'acao', 'app': 'usinagem'},
    )
    # Hoje todo mundo que entra na tela pode planejar: libera pra eles, pra
    # ninguem perder o acesso no deploy. Depois o admin tira de quem nao deve.
    if criado:
        for profile in Profile.objects.filter(permissoes__nome__in=TELAS).distinct():
            profile.permissoes.add(planejar)


def remover_subacesso(apps, schema_editor):
    RotaAcesso = apps.get_model('core', 'RotaAcesso')
    RotaAcesso.objects.filter(nome=PLANEJAR).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('apontamento_usinagem', '0008_pecasordem_apontado_pecasordem_chave_apontamento_and_more'),
        ('core', '0082_rota_cadastro_tubos'),
    ]

    operations = [
        migrations.RunPython(criar_subacesso, remover_subacesso),
    ]
