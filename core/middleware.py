from django.shortcuts import render, redirect
from django.urls import reverse
from django.core.cache import cache

from core.models import RotaAcesso

_ROTA_CACHE_KEY = 'rota_acesso_map'
_ROTA_CACHE_TTL = 300  # 5 minutos


def _get_rota(path):
    rota_map = cache.get(_ROTA_CACHE_KEY)
    if rota_map is None:
        rota_map = {r.nome: r for r in RotaAcesso.objects.all()}
        cache.set(_ROTA_CACHE_KEY, rota_map, _ROTA_CACHE_TTL)
    rota = rota_map.get(path)
    if rota is not None:
        return rota

    # Recarrega o cache quando uma rota foi criada recentemente e o mapa atual ficou defasado.
    rota_map = {r.nome: r for r in RotaAcesso.objects.all()}
    cache.set(_ROTA_CACHE_KEY, rota_map, _ROTA_CACHE_TTL)
    return rota_map.get(path)


class RotaAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        #  Se a URL contém "api/", libera automaticamente
        if "/api/" in request.path or request.path.startswith("api/"):
            return self.get_response(request)
        
        # Obtém o caminho da requisição, removendo "/" inicial e final
        path = request.path.strip("/")
        
        PUBLIC_PATHS = [
            "core/login",
            "almox/solicitar",
            "expedicao/relatorios/impressao",
        ]

        if path.startswith("cargas/acompanhamento/"):
            return self.get_response(request)

        if path in PUBLIC_PATHS:
            return self.get_response(request)
        
        # Se o usuário não estiver autenticado, redireciona para o login
        if request.user and not request.user.is_authenticated and path not in PUBLIC_PATHS:
            login_url = reverse('core:login')
            if path == "":
                return redirect(f"{login_url}")
            return redirect(f"{login_url}?next={request.path}")

        # Ignorar rotas administrativas
        EXCLUDED_PATHS = ['admin', 'login', 'logout', 'core', 'almox/solicitar']
        if any(path.startswith(excluded) for excluded in EXCLUDED_PATHS):
            return self.get_response(request)

        #  Se a URL contém "api/", libera automaticamente
        if "api/" in path or "media/" in path:
            return self.get_response(request)
        
        # Obtém o perfil do usuário
        profile = getattr(request.user, 'profile', None)

        # Se o usuário for do tipo "pcp", permite acesso irrestrito
        if profile and getattr(profile, "tipo_acesso", "").lower() == "admin":
            return self.get_response(request)
        elif profile and getattr(profile, "tipo_acesso", "").lower() == "pcp" and not 'almox' in path:
            return self.get_response(request)
        elif profile and getattr(profile, "tipo_acesso", "").lower() == "almoxarifado" and 'almox' in path:
            return self.get_response(request)

        # Busca a rota (cache em memória para reduzir queries ao banco)
        rota = _get_rota(path)

        # Se a rota **não existir no banco**, bloqueia o acesso
        if not rota:
            if path == "":
                return redirect("core:home")
            return render(request, 'home/erro-acesso.html', status=403)

        # Se a rota for do tipo API, sempre permite o acesso (apenas por segurança extra)
        # if rota.tipo_rota == 'api':
        #     return self.get_response(request)
        if not profile:
            return render(request, 'home/erro-acesso.html', status=403)

        # Verifica se o usuário tem permissão para acessar a rota
        if not profile.permissoes.filter(id=rota.id).exists():
            return render(request, 'home/erro-acesso.html', status=403)

        return self.get_response(request)
