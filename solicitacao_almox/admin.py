from django.contrib import admin

from .models import *
from core.admin import RestrictedAdmin

admin.site.register(SolicitacaoTransferencia)
admin.site.register(SolicitacaoCadastroItem)
admin.site.register(SolicitacaoRequisicao)
admin.site.register(SolicitacaoNovaMatricula)