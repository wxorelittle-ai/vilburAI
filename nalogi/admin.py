from django.contrib import admin

from .models import ChekFNS, NalogOtchet


@admin.register(ChekFNS)
class ChekFNSAdmin(admin.ModelAdmin):
    list_display = ('data', 'brigada', 'summa', 'naznachenie', 'status', 'demo_rezhim')
    list_filter = ('status', 'demo_rezhim')
    search_fields = ('brigada__nazvanie', 'naznachenie', 'fns_id')


@admin.register(NalogOtchet)
class NalogOtchetAdmin(admin.ModelAdmin):
    list_display = ('brigada', 'god', 'mesyats', 'dohod', 'nalog_4', 'nalog_6', 'status')
    list_filter = ('status', 'god')
