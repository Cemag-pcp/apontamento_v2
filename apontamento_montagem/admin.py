from django.contrib import admin
from .models import ConjuntosInspecionados, PecasOrdem
from core.admin import RestrictedAdmin

admin.site.register(PecasOrdem, RestrictedAdmin)
admin.site.register(ConjuntosInspecionados, RestrictedAdmin)

# Register your models here.
