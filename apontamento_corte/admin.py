from django.contrib import admin
from .models import PecasOrdem, TransferenciaChapaCorte


@admin.register(PecasOrdem)
class PecasOrdemAdmin(admin.ModelAdmin):
    list_display = ('ordem', 'peca', 'qtd_planejada', 'qtd_boa', 'qtd_morta', 'data')
    search_fields = ('=ordem__ordem', 'ordem__ordem_duplicada', 'peca')
    list_filter = ('data',)


@admin.register(TransferenciaChapaCorte)
class TransferenciaChapaCorteAdmin(admin.ModelAdmin):
    list_display = ('ordem', 'codigo_chapa', 'peso_total', 'status', 'transferido_em', 'chave_transferencia')
    search_fields = ('=ordem__ordem', 'ordem__ordem_duplicada', 'codigo_chapa', 'chave_transferencia')
    list_filter = ('status', 'transferido_em', 'criado_em')
    readonly_fields = ('criado_em', 'atualizado_em')
