from django.contrib import admin

from .models import *

class PecasEstanqueidadeAdmim(admin.ModelAdmin):
    list_display = ("codigo", "descricao", "tipo")
    list_display_links = ("codigo",)

admin.site.register(Maquina)
admin.site.register(MotivoInterrupcao)
admin.site.register(Operador)
admin.site.register(Pecas)
admin.site.register(Setor)
admin.site.register(Mp)
admin.site.register(Espessura)
admin.site.register(Conjuntos)
admin.site.register(MotivoMaquinaParada)
admin.site.register(MotivoExclusao)
admin.site.register(Carretas)
admin.site.register(PecasEstanqueidade, PecasEstanqueidadeAdmim)