from django.contrib import admin

from .models import (
    PecasOrdem,
    InfoAdicionaisInspecaoEstamparia,
    MedidasInspecaoEstamparia,
    DadosNaoConformidade,
    ImagemNaoConformidade,
)

admin.site.register(PecasOrdem)
admin.site.register(InfoAdicionaisInspecaoEstamparia)
admin.site.register(MedidasInspecaoEstamparia)
admin.site.register(DadosNaoConformidade)
admin.site.register(ImagemNaoConformidade)
