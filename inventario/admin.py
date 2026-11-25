from django.contrib import admin

from .models import CadastroInventario, Inventario, ItemContagem


@admin.register(Inventario)
class InventarioAdmin(admin.ModelAdmin):
    list_display = ('nome', 'status', 'criado_por', 'criado_em')
    list_filter = ('status',)
    search_fields = ('nome',)


@admin.register(CadastroInventario)
class CadastroInventarioAdmin(admin.ModelAdmin):
    list_display = ('inventario', 'setor', 'celula', 'responsavel', 'criado_por', 'criado_em')
    list_filter = ('inventario',)
    search_fields = ('setor', 'celula', 'responsavel')


@admin.register(ItemContagem)
class ItemContagemAdmin(admin.ModelAdmin):
    list_display = ('inventario', 'setor', 'celula', 'codigo', 'descricao', 'importado_em')
    list_filter = ('inventario',)
    search_fields = ('setor', 'celula', 'codigo', 'descricao')
