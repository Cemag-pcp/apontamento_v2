from django.contrib import admin
from core.admin import RestrictedAdmin

from .models import (
    PecasOrdem,
    InfoAdicionaisInspecaoEstamparia,
    MedidasInspecaoEstamparia,
    DadosNaoConformidade,
    ImagemNaoConformidade,
)

admin.site.register(PecasOrdem, RestrictedAdmin)
admin.site.register(InfoAdicionaisInspecaoEstamparia, RestrictedAdmin)
admin.site.register(MedidasInspecaoEstamparia, RestrictedAdmin)
admin.site.register(DadosNaoConformidade, RestrictedAdmin)
admin.site.register(ImagemNaoConformidade, RestrictedAdmin)
