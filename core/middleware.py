from django.shortcuts import render,redirect
from django.urls import reverse


from core.models import RotaAcesso

class RotaAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        #  Se a URL contém "api/", libera automaticamente
        if "/api/" in request.path or request.path.startswith("api/"):
            return self.get_response(request)
        
        # Obtém o caminho da requisição, removendo "/" inicial e final
        path = request.path.strip("/")
        
        login_url = reverse('core:login')

        # Se o usuário não estiver autenticado, redireciona para o login
        if not request.user.is_authenticated and path != login_url.strip("/"):
            print(login_url.strip("/"))
            if path == "":
                return redirect(f"{login_url}")
            return redirect(f"{login_url}?next={request.path}")

        # Ignorar rotas administrativas
        EXCLUDED_PATHS = ['admin', 'login', 'logout', 'core']
        if any(path.startswith(excluded) for excluded in EXCLUDED_PATHS):
            return self.get_response(request)

        #  Se a URL contém "api/", libera automaticamente
        if "api/" in path or "media/" in path:
            return self.get_response(request)
        
        # Obtém o perfil do usuário
        profile = getattr(request.user, 'profile', None)

        # Se o usuário for do tipo "pcp", permite acesso irrestrito
        if profile and getattr(profile, "tipo_acesso", "").lower() == "pcp":
            return self.get_response(request)

        # Busca a rota no banco de dados
        rota = RotaAcesso.objects.filter(nome=path).first()

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