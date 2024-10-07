from django.contrib import admin

from apontamento.models import Planejamento, Apontamento, PlanejamentoPeca, OrdemPadrao

admin.site.register(Planejamento)
admin.site.register(Apontamento)
admin.site.register(PlanejamentoPeca)
admin.site.register(OrdemPadrao)
