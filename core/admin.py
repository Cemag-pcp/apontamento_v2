from django.contrib import admin
from django import forms
from .models import MaquinaParada, Profile, Ordem, Versao

# Registro do modelo MaquinaParada
admin.site.register(MaquinaParada)
admin.site.register(Ordem)
admin.site.register(Versao)

# Formulário personalizado para Profile
class ProfileAdminForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['user', 'tipo_acesso', 'setores_permitidos']
        widgets = {
            'setores_permitidos': forms.CheckboxSelectMultiple(choices=Profile.SETOR_CHOICES),
        }

# Registro do modelo Profile com o formulário personalizado
@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    form = ProfileAdminForm  # Associa o formulário personalizado
    list_display = ('user', 'tipo_acesso', 'get_setores_permitidos')  # Campos exibidos na listagem do admin

    def get_setores_permitidos(self, obj):
        return ", ".join(obj.setores_permitidos) if obj.setores_permitidos else "Nenhum"
    get_setores_permitidos.short_description = 'Setores Permitidos'
