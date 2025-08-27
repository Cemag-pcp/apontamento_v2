from django.urls import path
from . import views

app_name = 'expedicao'

urlpatterns = [
    
    #templates
    path('', views.planejamento, name='planejamento'),

    #apis
    path('api/clientes_disponiveis/', views.clientes, name='clientes'),
    path('api/carretas_disponiveis/', views.carretas, name='carretas'),

]
