from django.urls import path

from . import views

app_name = 'montagem'

urlpatterns = [
    path('api/criar-ordem/', views.criar_ordem, name='criar_ordem'),
    path('api/ordens/atualizar-status/', views.atualizar_status_ordem, name='atualizar_status_ordem'),

]
