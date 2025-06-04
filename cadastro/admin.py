from django.contrib import admin

from .models import *

class PecasEstanqueidadeAdmim(admin.ModelAdmin):
    list_display = ("codigo", "descricao", "tipo")
    list_display_links = ("codigo",)

class PecasAdmin(admin.ModelAdmin):
    search_fields = ['codigo', 'descricao', 'materia_prima', 'apelido']

    fieldsets = (
        ('Informações Principais', {
            'fields': ('codigo', 'descricao', 'materia_prima', 'apelido', 'comprimento')
        }),
        ('Relacionamentos', {
            'fields': ('setor', 'conjunto', 'processo_1')
        }),
    )

class MpAdmin(admin.ModelAdmin):
    search_fields = ['codigo', 'descricao', 'setor__nome']

admin.site.register(Maquina)
admin.site.register(MotivoInterrupcao)
admin.site.register(Operador)
admin.site.register(Pecas, PecasAdmin)
admin.site.register(Setor)
admin.site.register(Mp, MpAdmin)
admin.site.register(Espessura)
admin.site.register(Conjuntos)
admin.site.register(MotivoMaquinaParada)
admin.site.register(MotivoExclusao)
admin.site.register(Carretas)
admin.site.register(PecasEstanqueidade, PecasEstanqueidadeAdmim)