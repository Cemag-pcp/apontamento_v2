from django.db import migrations

# Sub-acessos da tela /estamparia/ (padrao em core/permissoes.py: tipo_rota
# "acao", nome "<tela>#<acao>").
TELA = 'estamparia'
PLANEJAR = 'estamparia#planejar'
RETIRAR_ANTIGO = 'estamparia/painel-prioridades/retirar'
RETIRAR = 'estamparia#retirar-prioridade'


def criar_subacessos(apps, schema_editor):
    RotaAcesso = apps.get_model('core', 'RotaAcesso')
    Profile = apps.get_model('core', 'Profile')

    # "Retirar da prioridade" (0019) passa para o padrao de sub-acesso;
    # mantem o id, entao quem ja tinha a permissao continua com ela
    RotaAcesso.objects.filter(nome=RETIRAR_ANTIGO).update(nome=RETIRAR, tipo_rota='acao')

    planejar, criado = RotaAcesso.objects.get_or_create(
        nome=PLANEJAR,
        defaults={'descricao': 'Planejar ordem', 'tipo_rota': 'acao', 'app': 'estamparia'},
    )
    # Hoje todo mundo que entra na tela pode planejar: libera pra eles, pra
    # ninguem perder o acesso no deploy. Depois o admin tira de quem nao deve.
    if criado:
        for profile in Profile.objects.filter(permissoes__nome=TELA).distinct():
            profile.permissoes.add(planejar)


def remover_subacessos(apps, schema_editor):
    RotaAcesso = apps.get_model('core', 'RotaAcesso')
    RotaAcesso.objects.filter(nome=PLANEJAR).delete()
    RotaAcesso.objects.filter(nome=RETIRAR).update(nome=RETIRAR_ANTIGO, tipo_rota='api')


class Migration(migrations.Migration):

    dependencies = [
        ('apontamento_estamparia', '0020_rascunho_inspecao_estamparia'),
        ('core', '0082_rota_cadastro_tubos'),
    ]

    operations = [
        migrations.RunPython(criar_subacessos, remover_subacessos),
    ]
