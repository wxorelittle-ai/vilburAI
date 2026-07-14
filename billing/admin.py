from django.contrib import admin

from .models import Platezh, LimitTracker


@admin.register(Platezh)
class PlatezhAdmin(admin.ModelAdmin):
    list_display = ('brigada', 'tarif', 'summa', 'status', 'demo_rezhim', 'data')
    list_filter = ('status', 'tarif', 'demo_rezhim')
    search_fields = ('brigada__nazvanie', 'yookassa_id')
    readonly_fields = ('data',)


@admin.register(LimitTracker)
class LimitTrackerAdmin(admin.ModelAdmin):
    list_display = ('brigada', 'god', 'mesyats', 'dokumenty_ispolzovano', 'raschety_ispolzovano', 'smety_ispolzovano')
    list_filter = ('god', 'mesyats')
    search_fields = ('brigada__nazvanie',)
