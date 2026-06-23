from django.contrib import admin

from .models import *
from core.admin import RestrictedAdmin, ProfilePermissionMixin

class FuncionarioAdmin(admin.ModelAdmin):
    search_fields = ['nome', 'matricula', 'cc__nome']

class ItensSolicitacaoAdmin(admin.ModelAdmin):
    search_fields = ['codigo', 'nome', 'classe_requisicao__nome']
    list_display = ['codigo', 'nome', 'unidade', 'ativo']
    list_filter = ['ativo', 'classe_requisicao']

class ItensTransferenciaAdmin(admin.ModelAdmin):
    search_fields = ['codigo', 'nome']
    list_display = ['codigo', 'nome', 'unidade', 'ativo']
    list_filter = ['ativo']

class DepositoDestinoAdmin(admin.ModelAdmin):
    search_fields = ['nome']

admin.site.register(Cc)
admin.site.register(DepositoDestino,DepositoDestinoAdmin)
admin.site.register(Funcionario,FuncionarioAdmin)
admin.site.register(ItensSolicitacao,ItensSolicitacaoAdmin)
admin.site.register(ItensTransferencia,ItensTransferenciaAdmin)
admin.site.register(OperadorAlmox)
admin.site.register(ClasseRequisicao)
admin.site.register(RegraSlaAlmox)
