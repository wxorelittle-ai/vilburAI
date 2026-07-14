from django.contrib import admin

from .models import Raschet


@admin.register(Raschet)
class RaschetAdmin(admin.ModelAdmin):
    list_display = ('brigada', 'ploshad', 'tip_remonta', 'sebestoimost_m2', 'cena_30_m2', 'data')
    list_filter = ('tip_remonta', 'nalog', 'data')
    search_fields = ('brigada__nazvanie',)
