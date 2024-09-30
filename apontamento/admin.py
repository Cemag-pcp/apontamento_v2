from django.contrib import admin

from apontamento.models import Planejamento, Apontamento, PlanejamentoPeca

admin.site.register(Planejamento)
admin.site.register(Apontamento)
admin.site.register(PlanejamentoPeca)
