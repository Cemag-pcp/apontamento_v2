from django.urls import path
from django.contrib.auth import views as auth_views

from . import views
from .views import CustomLoginView

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),

    path('api/excluir-ordem/', views.excluir_ordem, name='excluir_ordem'),
    
    # path('login/', auth_views.LoginView.as_view(template_name='login/login.html'), name='login'),
    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),  # Para logout, se necessário

]