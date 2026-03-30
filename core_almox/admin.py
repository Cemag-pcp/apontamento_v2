from django.contrib import admin

from .models import RegistroAcaoSolicitacaoAlmox


@admin.register(RegistroAcaoSolicitacaoAlmox)
class RegistroAcaoSolicitacaoAlmoxAdmin(admin.ModelAdmin):
    list_display = ("data_criacao", "tipo_solicitacao", "acao", "solicitacao_id_original", "usuario")
    list_filter = ("tipo_solicitacao", "acao", "data_criacao")
    search_fields = ("motivo", "solicitacao_id_original", "usuario__username")
