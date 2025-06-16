from django.urls import path
from . import views

app_name = 'sucata'

urlpatterns = [
    path('', views.sucata, name='sucata'),
    path('api/corte', views.filtrar_sucata, name='filtrar-sucata')
]