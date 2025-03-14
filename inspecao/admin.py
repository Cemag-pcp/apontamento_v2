from django.contrib import admin
from .models import (
    Inspecao,
    DadosExecucaoInspecao,
    Reinspecao,
    CausasNaoConformidade,
    Causas,
    ArquivoCausa,
    InspecaoEstanqueidade,
    ReinspecaoEstanqueidade,
    DadosExecucaoInspecaoEstanqueidade,
    InfoAdicionaisExecTubosCilindros
)


class InspecaoAdmin(admin.ModelAdmin):
    list_display = (
        "data_inspecao",
        "pecas_ordem_pintura",
        "pecas_ordem_montagem",
        "pecas_ordem_estamparia",
    )
    list_display_links = ("data_inspecao",)


class DadosExecucaoInspecaoAdmin(admin.ModelAdmin):
    list_display = (
        "inspetor",
        "data_execucao",
        "num_execucao",
        "conformidade",
        "nao_conformidade",
        "observacao",
    )
    list_display_links = ("data_execucao",)


class ReinspecaoAdmin(admin.ModelAdmin):
    list_display = ("data_reinspecao", "reinspecionado")
    list_display_links = ("data_reinspecao",)


class InspecaoEstanqueidadeAdmin(admin.ModelAdmin):
    list_display = ("data_inspecao", "peca", "data_carga")
    list_display_links = ("peca",)

class ReinspecaoEstanqueidadeAdmin(admin.ModelAdmin):
    list_display = ("inspecao", "data_reinsp")
    list_display_links = ("inspecao",)

class DadosExecucaoInspecaoEstanqueidadeAdmin(admin.ModelAdmin):
    list_display = ("inspecao_estanqueidade", "inspetor", "num_execucao", "data_exec")
    list_display_links = ("inspecao_estanqueidade",)

class InfoAdicionaisExecTubosCilindrosAdmin(admin.ModelAdmin):
    list_display = ("dados_exec_inspecao", "nao_conformidade_retrabalho", "nao_conformidade_refugo", "qtd_inspecionada", "observacao", "ficha")
    list_display_links = ("dados_exec_inspecao",)


admin.site.register(Inspecao, InspecaoAdmin)
admin.site.register(DadosExecucaoInspecao, DadosExecucaoInspecaoAdmin)
admin.site.register(Reinspecao, ReinspecaoAdmin)
admin.site.register(ArquivoCausa)
admin.site.register(Causas)
admin.site.register(CausasNaoConformidade)

admin.site.register(InspecaoEstanqueidade, InspecaoEstanqueidadeAdmin)
admin.site.register(ReinspecaoEstanqueidade, ReinspecaoEstanqueidadeAdmin)
admin.site.register(DadosExecucaoInspecaoEstanqueidade, DadosExecucaoInspecaoEstanqueidadeAdmin)
admin.site.register(InfoAdicionaisExecTubosCilindros, InfoAdicionaisExecTubosCilindrosAdmin)