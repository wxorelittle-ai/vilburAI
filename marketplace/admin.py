from django.contrib import admin

from .models import Otzyv, IzlishekMateriala, Tender, TenderOtklik


@admin.register(Otzyv)
class OtzyvAdmin(admin.ModelAdmin):
    list_display = ('brigada', 'ocenka', 'avtor_imya', 'podtverzhden', 'opublikovan', 'data')
    list_filter = ('ocenka', 'podtverzhden', 'opublikovan')
    search_fields = ('brigada__nazvanie', 'avtor_imya')


@admin.register(IzlishekMateriala)
class IzlishekAdmin(admin.ModelAdmin):
    list_display = ('nazvanie', 'brigada', 'kolvo', 'edinica', 'cena', 'region', 'status')
    list_filter = ('status',)
    search_fields = ('nazvanie', 'region')


class OtklikInline(admin.TabularInline):
    model = TenderOtklik
    extra = 0


@admin.register(Tender)
class TenderAdmin(admin.ModelAdmin):
    list_display = ('nazvanie', 'brigada', 'region', 'byudzhet', 'status', 'data')
    list_filter = ('status',)
    inlines = [OtklikInline]
