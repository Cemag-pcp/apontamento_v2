from django.db import migrations


# Permissao de acao (nao e uma URL de pagina): marcada na tela de acessos,
# libera o botao "Retirar da prioridade" do painel de prioridades da
# estamparia para usuarios que nao sao PCP.
NOME_ROTA = 'estamparia/painel-prioridades/retirar'


def criar_rota_retirar_prioridade(apps, schema_editor):
    RotaAcesso = apps.get_model('core', 'RotaAcesso')
    RotaAcesso.objects.get_or_create(
        nome=NOME_ROTA,
        defaults={
            'descricao': 'Retirar ordem do painel de prioridades',
            'tipo_rota': 'api',
            'app': 'estamparia',
        },
    )


def remover_rota_retirar_prioridade(apps, schema_editor):
    RotaAcesso = apps.get_model('core', 'RotaAcesso')
    RotaAcesso.objects.filter(nome=NOME_ROTA).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('apontamento_estamparia', '0018_pecasordem_erro_apontamento'),
        ('core', '0082_rota_cadastro_tubos'),
    ]

    operations = [
        migrations.RunPython(criar_rota_retirar_prioridade, remover_rota_retirar_prioridade),
    ]
