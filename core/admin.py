from django.contrib import admin
from django import forms
from .models import MaquinaParada, Profile, Ordem, Versao, RotaAcesso

class OrdemAdmin(admin.ModelAdmin):
    list_display = ('ordem',)
    search_fields = ('ordem',)

# Registro do modelo MaquinaParada
admin.site.register(MaquinaParada)
admin.site.register(Ordem,OrdemAdmin)
admin.site.register(Versao)
admin.site.register(Profile)
admin.site.register(RotaAcesso)