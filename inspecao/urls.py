from django.urls import path
from . import views

app_name = "inspecao"

urlpatterns = [
    path('montagem/', views.inspecao_montagem, name='inspecao-montagem'),
    
    path('estamparia/', views.inspecao_estamparia, name='inspecao-estamparia'),

    path('pintura/', views.inspecao_pintura, name='inspecao-pintura'),
    path('api/itens-inspecao-pintura/', views.get_itens_inspecao_pintura, name='itens-inspecao-pintura'),
    path('api/itens-inspecionados-pintura/', views.get_itens_inspecionados_pintura, name='itens-inspecionados-pintura'),
    path('api/itens-reinspecao-pintura/', views.get_itens_reinspecao_pintura, name='itens-reinspecao-pintura'),

    path('tanque/', views.inspecao_tanque, name='inspecao-tanque'),
    path('tubos-cilindros/', views.inspecao_tubos_cilindros, name='inspecao-tubos-cilindros'),
]