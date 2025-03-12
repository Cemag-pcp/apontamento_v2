from django.contrib import admin
from .models import Inspecao, DadosExecucaoInspecao, Reinspecao, CausasNaoConformidade, Causas, ArquivoCausa

class InspecaoAdmin(admin.ModelAdmin):
    list_display = ("data_inspecao", "pecas_ordem_pintura", "pecas_ordem_montagem", "pecas_ordem_estamparia")
    list_display_links = ("data_inspecao",)

class DadosExecucaoInspecaoAdmin(admin.ModelAdmin):
    list_display = ("inspetor", "data_execucao", "num_execucao", "conformidade", "nao_conformidade", "observacao")
    list_display_links = ("data_execucao",)

class ReinspecaoAdmin(admin.ModelAdmin):
    list_display = ("data_reinspecao", "reinspecionado")
    list_display_links = ("data_reinspecao",)

admin.site.register(Inspecao, InspecaoAdmin)
admin.site.register(DadosExecucaoInspecao, DadosExecucaoInspecaoAdmin)
admin.site.register(Reinspecao, ReinspecaoAdmin)
admin.site.register(ArquivoCausa)
admin.site.register(Causas)
admin.site.register(CausasNaoConformidade)