from django.contrib import admin

from .models import Brigada


@admin.register(Brigada)
class BrigadaAdmin(admin.ModelAdmin):
    list_display = ('nazvanie', 'telefon', 'region', 'tarif', 'data_okonchaniya_tarifa', 'data_registracii')
    list_filter = ('tarif', 'region')
    search_fields = ('nazvanie', 'telefon', 'user__username', 'user__email')
    readonly_fields = ('data_registracii',)
