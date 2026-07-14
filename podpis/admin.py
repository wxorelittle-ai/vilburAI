from django.contrib import admin

from .models import PodpisZakazchika


@admin.register(PodpisZakazchika)
class PodpisZakazchikaAdmin(admin.ModelAdmin):
    list_display = ('dokument', 'status', 'telefon', 'ip_adres', 'data_podpisi')
    list_filter = ('status',)
    search_fields = ('dokument__nomer', 'telefon', 'doc_hash')
    readonly_fields = ('token', 'kod_sms_hash', 'doc_hash', 'ip_adres', 'data_sozdaniya', 'data_podpisi')
