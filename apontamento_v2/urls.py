"""
URL configuration for apontamento_v2 project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('core/', include('core.urls')),
    path('admin/', admin.site.urls),

    path('cadastro/', include('cadastro.urls')),
    
    path('serra/', include('apontamento_serra.urls')),
    path('usinagem/', include('apontamento_usinagem.urls')),
    path('corte/', include('apontamento_corte.urls')),
    path('prod-esp/', include('apontamento_prod_especiais.urls')),
    path('estamparia/', include('apontamento_estamparia.urls')),
    path('pintura/', include('apontamento_pintura.urls')),
    path('montagem/', include('apontamento_montagem.urls')),
    path('inspecao/', include('inspecao.urls')),

]