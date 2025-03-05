from django.http import HttpResponseForbidden
from django.shortcuts import render

class SetorAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Ignorar caminhos específicos
        EXCLUDED_PATHS = ['/pintura','/montagem','/cargas','/cadastro', '/core', '/admin', '/login', '/logout']  # Adicione outros caminhos que deseja ignorar

        # Ignora a verificação para as URLs configuradas em EXCLUDED_PATHS
        if any(request.path.startswith(path) for path in EXCLUDED_PATHS):
            return self.get_response(request)

        # Verifica se o usuário está autenticado e possui perfil
        if request.user.is_authenticated and hasattr(request.user, 'profile'):
            # Verifica o setor solicitado na URL
            setor_solicitado = request.path.split('/')[1]  # Exemplo: /serra/ -> 'serra'
            if setor_solicitado not in request.user.profile.setores_permitidos:
                return render(request, 'home/erro-acesso.html', status=403)  # Renderiza a página de erro

        return self.get_response(request)
