"""Sub-acessos: ações dentro de uma tela (ex.: planejar ordem na estamparia)
liberadas por usuário na tela de acessos.

Cada sub-acesso é uma RotaAcesso com tipo_rota="acao" e nome "<tela>#<acao>"
(ex.: "estamparia#planejar"), onde <tela> é o nome da RotaAcesso da página.
O "#" nunca aparece numa URL, então o RotaAccessMiddleware nunca confunde um
sub-acesso com uma página. Na tela de acessos ele aparece dentro da tela pai.
"""

from core.models import Profile

TIPO_SUBACESSO = "acao"

# PCP e admin podem tudo dentro das telas, como no RotaAccessMiddleware
TIPOS_LIBERADOS = ("pcp", "admin")


def tem_subacesso(user, nome):
    """True se o usuário pode executar a ação `nome` ("<tela>#<acao>")."""
    if not getattr(user, "is_authenticated", False):
        return False
    profile = Profile.objects.filter(user=user).first()
    if profile is None:
        return False
    return profile.tipo_acesso in TIPOS_LIBERADOS or profile.tem_acesso(nome)
