from django.contrib import admin

from .models import GolosovayaKomanda


@admin.register(GolosovayaKomanda)
class GolosovayaKomandaAdmin(admin.ModelAdmin):
    list_display = ('tekst_raspoznanny', 'brigada', 'pozicii_najdeno', 'status', 'data')
    list_filter = ('status',)
    search_fields = ('tekst_raspoznanny', 'brigada__nazvanie')
