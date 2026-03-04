from django.contrib import admin

from .models import *
from core.admin import RestrictedAdmin, ProfilePermissionMixin

class PecasEstanqueidadeAdmim(ProfilePermissionMixin, admin.ModelAdmin):
    list_display = ("codigo", "descricao", "tipo")
    list_display_links = ("codigo",)

class PecasAdmin(ProfilePermissionMixin, admin.ModelAdmin):
    search_fields = ['codigo', 'descricao', 'materia_prima', 'apelido']

    fieldsets = (
        ('Informações Principais', {
            'fields': ('codigo', 'descricao', 'materia_prima', 'apelido', 'comprimento')
        }),
        ('Relacionamentos', {
            'fields': ('setor', 'conjunto', 'processo_1')
        }),
    )

class MpAdmin(ProfilePermissionMixin, admin.ModelAdmin):
    search_fields = ['codigo', 'descricao', 'setor__nome']

class OperadorAdmin(ProfilePermissionMixin, admin.ModelAdmin):
    list_display = ('matricula', 'nome', 'setor')
    search_fields = ('matricula', 'nome', 'setor__nome')


class ItensExplodidosAdmin(ProfilePermissionMixin, admin.ModelAdmin):
    list_display = ('produto',)
    search_fields = ('produto',)
  

admin.site.register(Maquina, RestrictedAdmin)
admin.site.register(MotivoInterrupcao, RestrictedAdmin)
admin.site.register(Operador, OperadorAdmin)
admin.site.register(Pecas, PecasAdmin)
admin.site.register(Setor, RestrictedAdmin)
admin.site.register(Mp, MpAdmin)
admin.site.register(Espessura, RestrictedAdmin)
admin.site.register(Conjuntos, RestrictedAdmin)
admin.site.register(MotivoMaquinaParada, RestrictedAdmin)
admin.site.register(MotivoExclusao, RestrictedAdmin)
admin.site.register(Carretas, RestrictedAdmin)
admin.site.register(PecasEstanqueidade, PecasEstanqueidadeAdmim)
admin.site.register(ItensExplodidos, ItensExplodidosAdmin)
