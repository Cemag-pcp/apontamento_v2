from django.contrib import admin
from .models import Inspecao

class InspecaoAdmin(admin.ModelAdmin):
    list_display = ("data_inspecao", "pecas_ordem_pintura", "pecas_ordem_montagem", "pecas_ordem_estamparia")
    list_display_links = ("data_inspecao",)

admin.site.register(Inspecao, InspecaoAdmin)