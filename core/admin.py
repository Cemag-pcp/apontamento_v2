from django.contrib import admin
from .models import MaquinaParada, Profile, Ordem, Versao, RotaAcesso

# Registro do modelo MaquinaParada
admin.site.register(MaquinaParada)
admin.site.register(Versao)
admin.site.register(RotaAcesso)
admin.site.register(Profile)

class OrdemAdmin(admin.ModelAdmin):
    search_fields = ['ordem']

admin.site.register(Ordem, OrdemAdmin)

