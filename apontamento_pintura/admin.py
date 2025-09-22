from django.contrib import admin

from .models import PecasOrdem, CambaoPecas, Retrabalho, Cambao
from core.admin import RestrictedAdmin

admin.site.register(PecasOrdem, RestrictedAdmin)
admin.site.register(CambaoPecas, RestrictedAdmin)
admin.site.register(Retrabalho, RestrictedAdmin)
admin.site.register(Cambao, RestrictedAdmin)
