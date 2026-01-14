from django.contrib import admin

from .models import PecasOrdem, CambaoPecas, Retrabalho, Cambao, CambaoInterrupcao
from core.admin import RestrictedAdmin

@admin.register(CambaoInterrupcao)
class CambaoInterrupcaoAdmin(RestrictedAdmin):
    list_display = ('cambao', 'motivo_resumido', 'data_inicio', 'data_fim', 'duracao')
    list_filter = ('cambao', 'data_inicio', 'data_fim')
    search_fields = ('cambao__nome', 'motivo')
    readonly_fields = ('data_inicio',)
    
    def motivo_resumido(self, obj):
        return obj.motivo[:50] + '...' if len(obj.motivo) > 50 else obj.motivo
    motivo_resumido.short_description = 'Motivo'
    
    def duracao(self, obj):
        if obj.data_fim:
            delta = obj.data_fim - obj.data_inicio
            horas = delta.total_seconds() / 3600
            return f"{horas:.2f}h"
        return "Em andamento"
    duracao.short_description = 'Duração'

admin.site.register(PecasOrdem, RestrictedAdmin)
admin.site.register(CambaoPecas, RestrictedAdmin)
admin.site.register(Retrabalho, RestrictedAdmin)
admin.site.register(Cambao, RestrictedAdmin)
