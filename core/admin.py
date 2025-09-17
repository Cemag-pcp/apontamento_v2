from django.contrib import admin
from .models import MaquinaParada, Profile, Ordem, Versao, RotaAcesso, Notificacao


class ProfilePermissionMixin:
    """
    Mixin para restringir o acesso no Admin com base no 'tipo_acesso' do Profile.
    """

    def _get_profile(self, request):
        if not hasattr(request, "_cached_profile"):
            try:
                request._cached_profile = request.user.profile
            except Profile.DoesNotExist:
                request._cached_profile = None
        return request._cached_profile

    def _has_restricted_access(self, request):
        profile = self._get_profile(request)
        if not profile or profile.tipo_acesso.lower() == "almoxarifado":
            return False
        return True

    def has_module_permission(self, request):
        return self._has_restricted_access(request)

    def has_view_permission(self, request, obj=None):
        return self._has_restricted_access(request)

    def has_add_permission(self, request):
        return self._has_restricted_access(request)

    def has_change_permission(self, request, obj=None):
        return self._has_restricted_access(request)

    def has_delete_permission(self, request, obj=None):
        return self._has_restricted_access(request)


class RestrictedAdmin(ProfilePermissionMixin, admin.ModelAdmin):
    """
    Um ModelAdmin genérico que aplica as permissões do Mixin.
    Pode ser reutilizado para vários modelos.
    """

    pass


class OrdemAdmin(ProfilePermissionMixin, admin.ModelAdmin):
    list_display = ("ordem", "grupo_maquina")
    search_fields = ("ordem", "grupo_maquina")


class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'tipo_acesso')
    list_filter = ('tipo_acesso',)
    search_fields = ('user__username',)

    def has_module_permission(self, request):

        if request.user.is_superuser:
            return True
        
        try:
            profile = request.user.profile
            if profile.tipo_acesso.lower() != 'almoxarifado':
                return True
        except Profile.DoesNotExist:
            return False
        
        return False


admin.site.register(MaquinaParada, RestrictedAdmin)
admin.site.register(Versao, RestrictedAdmin)
admin.site.register(RotaAcesso, RestrictedAdmin)
admin.site.register(Notificacao, RestrictedAdmin)

admin.site.register(Ordem, OrdemAdmin)

admin.site.register(Profile, ProfileAdmin)
