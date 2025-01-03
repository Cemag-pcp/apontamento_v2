from django.urls import path
from . import views
from .views import ProcessarArquivoView,SalvarArquivoView

app_name = 'apontamento_corte'

urlpatterns = [
    path('', views.planejamento, name='planejamento'),
    path('processar-arquivo/', ProcessarArquivoView.as_view(), name='processar_arquivo'),
    path('salvar-arquivo/', SalvarArquivoView.as_view(), name='salvar_arquivo'),

    path('api/ordens-criadas/', views.get_ordens_criadas, name='get_ordens_criadas'),
    path('api/ordens-criadas/<int:pk_ordem>/<str:name_maquina>/pecas/', views.get_pecas_ordem, name='get_pecas_ordem'),
    path('api/ordens/atualizar-status/', views.atualizar_status_ordem, name='atualizar_status_ordem'),
    path('api/ordens-iniciadas/', views.get_ordens_iniciadas, name='get_ordens_iniciadas'),
    path('api/ordens-interrompidas/', views.get_ordens_interrompidas, name='get_ordens_interrompidas'),

]
