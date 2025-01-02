# urls.py
from django.urls import path
from .views import atualizar_materia_prima, importar_peca#, importar_peca_processo_csv, importar_ordem

urlpatterns = [
    path('upload-peca-massa/', importar_peca, name='importar_peca'),
    # path('upload-peca-processo-massa/', importar_peca_processo_csv, name='importar_peca_processo_csv'),
    path('atualizar-mp-massa/', atualizar_materia_prima, name='atualizar_materia_prima'),
    # path('upload-ordem-massa/', importar_ordem, name='importar_ordem'),
    
]
