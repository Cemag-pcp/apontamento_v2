from django.contrib import admin

from .models import *

admin.site.register(SolicitacaoTransferencia)
admin.site.register(SolicitacaoCadastroItem)
admin.site.register(SolicitacaoRequisicao)
admin.site.register(SolicitacaoNovaMatricula)