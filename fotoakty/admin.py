from django.contrib import admin

from .models import FotoAkt


@admin.register(FotoAkt)
class FotoAktAdmin(admin.ModelAdmin):
    list_display = ('dokument', 'podpis_snizu', 'geo_lat', 'geo_lon', 'data_zagruzki')
    search_fields = ('dokument__nomer',)
