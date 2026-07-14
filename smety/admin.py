from django.contrib import admin

from .models import BazaCen, Smeta, SmetaRabota


@admin.register(BazaCen)
class BazaCenAdmin(admin.ModelAdmin):
    list_display = ('nazvanie', 'edinica', 'kategoriya', 'region', 'cena_econom', 'cena_srednyaya', 'cena_premium')
    list_filter = ('kategoriya', 'region')
    search_fields = ('nazvanie',)


class SmetaRabotaInline(admin.TabularInline):
    model = SmetaRabota
    extra = 0


@admin.register(Smeta)
class SmetaAdmin(admin.ModelAdmin):
    list_display = ('nomer', 'nazvanie', 'brigada', 'status', 'itogo', 'data')
    list_filter = ('status', 'urovne_cen')
    search_fields = ('nomer', 'nazvanie', 'brigada__nazvanie', 'zakazchik')
    readonly_fields = ('nomer', 'data', 'data_izmeneniya')
    inlines = [SmetaRabotaInline]
