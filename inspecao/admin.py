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
    InfoAdicionaisExecTubosCilindros,
    DetalhesPressaoTanque,
)
from core.admin import ProfilePermissionMixin, RestrictedAdmin


class InspecaoAdmin(ProfilePermissionMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "data_inspecao",
        "pecas_ordem_pintura",
        "pecas_ordem_montagem",
        "pecas_ordem_estamparia",
        "pecas_ordem_serra",
        "pecas_ordem_usinagem",
        "estanqueidade",
    )
    list_display_links = ("data_inspecao",)


class DadosExecucaoInspecaoAdmin(ProfilePermissionMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "inspetor",
        "data_execucao",
        "num_execucao",
        "conformidade",
        "nao_conformidade",
        "observacao",
    )
    list_display_links = ("data_execucao",)


class ReinspecaoAdmin(ProfilePermissionMixin, admin.ModelAdmin):
    list_display = ("id","data_reinspecao", "reinspecionado")
    list_display_links = ("data_reinspecao",)


class InspecaoEstanqueidadeAdmin(ProfilePermissionMixin, admin.ModelAdmin):
    list_display = ("id","data_inspecao", "peca", "data_carga")
    list_display_links = ("peca",)

class ReinspecaoEstanqueidadeAdmin(ProfilePermissionMixin, admin.ModelAdmin):
    list_display = ("id","inspecao", "data_reinsp")
    list_display_links = ("inspecao",)

class DadosExecucaoInspecaoEstanqueidadeAdmin(ProfilePermissionMixin, admin.ModelAdmin):
    list_display = ("id","inspecao_estanqueidade", "inspetor", "num_execucao", "data_exec")
    list_display_links = ("inspecao_estanqueidade",)

class DetalhesPressaoTanqueAdmin(ProfilePermissionMixin, admin.ModelAdmin):
    list_display = ("id","dados_exec_inspecao", "pressao_inicial", "pressao_final", "nao_conformidade", "tipo_teste", "tempo_execucao")
    list_display_links = ("id",)

class InfoAdicionaisExecTubosCilindrosAdmin(ProfilePermissionMixin, admin.ModelAdmin):
    list_display = ("id","dados_exec_inspecao", "nao_conformidade", "nao_conformidade_refugo", "qtd_inspecionada", "observacao", "ficha")
    list_display_links = ("dados_exec_inspecao",)


admin.site.register(Inspecao, InspecaoAdmin)
admin.site.register(DadosExecucaoInspecao, DadosExecucaoInspecaoAdmin)
admin.site.register(Reinspecao, ReinspecaoAdmin)
admin.site.register(ArquivoCausa, RestrictedAdmin)
admin.site.register(Causas, RestrictedAdmin)
admin.site.register(CausasNaoConformidade, RestrictedAdmin)

admin.site.register(InspecaoEstanqueidade, InspecaoEstanqueidadeAdmin)
admin.site.register(ReinspecaoEstanqueidade, ReinspecaoEstanqueidadeAdmin)
admin.site.register(DadosExecucaoInspecaoEstanqueidade, DadosExecucaoInspecaoEstanqueidadeAdmin)
admin.site.register(InfoAdicionaisExecTubosCilindros, InfoAdicionaisExecTubosCilindrosAdmin)
admin.site.register(DetalhesPressaoTanque, DetalhesPressaoTanqueAdmin)