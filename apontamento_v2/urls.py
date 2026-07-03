from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from core import views as core_views
from inspecao.views import corte as inspecao_corte
from inspecao.views import estamparia as inspecao_estamparia
from inspecao.views import recebimento as inspecao_recebimento
from inspecao.views import serra_usinagem as inspecao_serra_usinagem

urlpatterns = [
    path('', core_views.home, name='home'),
    path('api/docs/', core_views.api_docs, name='api_docs'),
    path('favicon.ico', RedirectView.as_view(url='', permanent=True)),

    path('core/', include('core.urls')),
    path('admin/', admin.site.urls),

    path('cadastro/', include('cadastro.urls')),

    path('almox/', include('core_almox.urls')),
    path('almox/', include('solicitacao_almox.urls')),
    
    path('serra/', include('apontamento_serra.urls')),
    path('usinagem/', include('apontamento_usinagem.urls')),
    path('corte/', include('apontamento_corte.urls')),
    path('prod-esp/', include('apontamento_prod_especiais.urls')),
    path('estamparia/', include('apontamento_estamparia.urls')),
    path('pintura/', include('apontamento_pintura.urls')),
    path('montagem/', include('apontamento_montagem.urls')),
    path('solda/', include('apontamento_solda.urls')),
    path('expedicao/', include('apontamento_exped.urls')),
    path(
        'controle-de-qualidade/estamparia/',
        inspecao_estamparia.inspecao_estamparia,
        name='controle_qualidade_estamparia',
    ),
    path(
        'controle-de-qualidade/serra-usinagem/',
        inspecao_serra_usinagem.inspecao_serra_usinagem,
        name='controle_qualidade_serra_usinagem',
    ),
    path(
        'controle-de-qualidade/corte/',
        inspecao_corte.inspecao_corte,
        name='controle_qualidade_corte',
    ),
    path(
        'controle-de-qualidade/recebimento/',
        inspecao_recebimento.inspecao_recebimento,
        name='controle_qualidade_recebimento',
    ),
    path('inspecao/', include('inspecao.urls')),
    path('cargas/', include('cargas.urls')),
    path('sucata/', include('sucata.urls')),
    path('compras/', include('compras.urls')),
    path('comercial/', include('comercial.urls')),
    path('reuniao/', include('reuniao.urls')),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
