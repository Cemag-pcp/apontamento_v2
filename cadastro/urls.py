# urls.py
from django.urls import path
from .views import crud

app_name = 'cadastro'

urlpatterns = [
    path('crud/', crud, name='crud')
]
