from django.contrib import admin

from .models import Dokument, DokumentPozicia


class PoziciaInline(admin.TabularInline):
    model = DokumentPozicia
    extra = 0


@admin.register(Dokument)
class DokumentAdmin(admin.ModelAdmin):
    list_display = ('nomer', 'tip', 'brigada', 'zakazchik', 'summa', 'data_sozdaniya')
    list_filter = ('tip', 'data_sozdaniya')
    search_fields = ('nomer', 'zakazchik', 'brigada__nazvanie', 'adres_obekta')
    readonly_fields = ('nomer', 'data_sozdaniya')
    inlines = [PoziciaInline]
