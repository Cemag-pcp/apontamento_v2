import logging
import time

from django.shortcuts import render, redirect
from django.urls import reverse
from django.core.cache import cache
from django.db import OperationalError

from core.models import RotaAcesso

logger = logging.getLogger(__name__)

try:
    from sqlalchemy.exc import TimeoutError as _SQLAlchemyPoolTimeoutError
    _DB_TRANSIENT_ERRORS = (OperationalError, _SQLAlchemyPoolTimeoutError)
except ImportError:
    _DB_TRANSIENT_ERRORS = (OperationalError,)


class DBConnectionRetryMiddleware:
    """
    O banco (RDS, us-east-1) fica em regiao diferente do app (Render,
    oregon): instabilidades transitorias de rede entre as regioes derrubam
    varias conexoes ao mesmo tempo (OperationalError) ou esgotam o pool de
    conexoes (sqlalchemy.exc.TimeoutError). Tenta a requisicao de novo uma
    vez apos uma pausa curta antes de devolver erro ao usuario.
    """

    MAX_TENTATIVAS = 2
    PAUSA_SEGUNDOS = 0.5

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        for tentativa in range(1, self.MAX_TENTATIVAS + 1):
            try:
                return self.get_response(request)
            except _DB_TRANSIENT_ERRORS as exc:
                if tentativa >= self.MAX_TENTATIVAS:
                    raise
                logger.warning(
                    "Erro transitorio de conexao com o banco (tentativa %s/%s) em %s: %s",
                    tentativa, self.MAX_TENTATIVAS, request.path, exc,
                )
                # Descarta a sessao parcialmente carregada para que a
                # proxima tentativa recarregue do zero (evita o
                # AttributeError de SessionStore sem _session_cache).
                request.__dict__.pop("session", None)
                time.sleep(self.PAUSA_SEGUNDOS)
        return self.get_response(request)

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
        try:
            is_authenticated = request.user and request.user.is_authenticated
        except OperationalError:
            login_url = reverse('core:login')
            return redirect(f"{login_url}?next={request.path}" if path else login_url)

        if not is_authenticated and path not in PUBLIC_PATHS:
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
