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

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)