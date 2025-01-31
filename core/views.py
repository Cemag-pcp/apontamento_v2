from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.views import LoginView
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login

from .models import Ordem
from cadastro.models import MotivoExclusao

import json
import time

@login_required  # Garante que apenas usuários autenticados possam acessar a view
def excluir_ordem(request):
    # Verifica se o usuário tem o tipo de acesso "pcp"
    if not hasattr(request.user, 'profile') or request.user.profile.tipo_acesso != 'pcp':
        return JsonResponse({'error': 'Acesso negado: você não tem permissão para excluir ordens.'}, status=403)

    if request.method == 'POST':
        try:
            # Decodifica o corpo da requisição
            data = json.loads(request.body)
            print(data)
            ordem_id = data['ordem_id']
            motivo = data['motivo']
            setor = data['setor']

            # Busca o motivo de exclusão
            motivo_exclusao = get_object_or_404(MotivoExclusao, pk=int(motivo))

            # Busca a ordem
            ordem = get_object_or_404(Ordem, ordem=ordem_id, grupo_maquina=setor)

            # Verifica o status atual da ordem antes de permitir a exclusão
            if ordem.status_atual in ['aguardando_iniciar', 'finalizada']:
                ordem.excluida = True
                ordem.motivo_exclusao = motivo_exclusao
                ordem.save()
                return JsonResponse({'success': 'Ordem excluída com sucesso.'}, status=201)
            else:
                return JsonResponse({'error': 'Finalize a ordem para excluí-la.'}, status=400)

        except Exception as e:
            print(f"Erro ao excluir ordem: {str(e)}")
            return JsonResponse({'error': 'Erro interno no servidor.'}, status=500)

    return JsonResponse({'error': 'Método não permitido.'}, status=405)

class CustomLoginView(LoginView):
    template_name = 'login/login.html'

    def form_valid(self, form):
        start_time = time.time()

        user = authenticate(
            self.request,
            username=form.cleaned_data["username"],
            password=form.cleaned_data["password"]
        )
        if user:
            login(self.request, user)

        end_time = time.time()
        print(f"Tempo de login: {end_time - start_time:.2f} segundos")  # Log de tempo de login

        return super().form_valid(form)

def home(request):
    return render(request, 'home/home.html')  