from django.contrib import admin

from .models import PecasOrdem, CambaoPecas, Retrabalho, Cambao

admin.site.register(PecasOrdem)
admin.site.register(CambaoPecas)
admin.site.register(Retrabalho)
admin.site.register(Cambao)
