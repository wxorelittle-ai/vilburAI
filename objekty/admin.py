from django.contrib import admin

from .models import (
    Objekt, EtapGrafika, Material, OplataMontajnika, RashodMesyachny,
    DvizhenieDeneg, AiZapros,
)


class EtapInline(admin.TabularInline):
    model = EtapGrafika
    extra = 0


class MaterialInline(admin.TabularInline):
    model = Material
    extra = 0


@admin.register(Objekt)
class ObjektAdmin(admin.ModelAdmin):
    list_display = ('nazvanie', 'brigada', 'status', 'data_nachala', 'data_okonchania_plan', 'summa_dogovora')
    list_filter = ('status',)
    search_fields = ('nazvanie', 'adres', 'zakazchik', 'brigada__nazvanie')
    inlines = [EtapInline, MaterialInline]


@admin.register(EtapGrafika)
class EtapGrafikaAdmin(admin.ModelAdmin):
    list_display = ('nazvanie', 'objekt', 'plan_objem', 'fact_objem', 'plan_data_nachala', 'plan_data_okonchania')
    search_fields = ('nazvanie',)


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ('nazvanie', 'objekt', 'etap', 'status', 'data_zakaza_fakt')
    list_filter = ('status',)


@admin.register(OplataMontajnika)
class OplataMontajnikaAdmin(admin.ModelAdmin):
    list_display = ('montajnik_fio', 'objekt', 'mesyats', 'plan_objem_mesyats', 'fact_objem_mesyats', 'summa_oplacheno')


@admin.register(RashodMesyachny)
class RashodMesyachnyAdmin(admin.ModelAdmin):
    list_display = ('objekt', 'mesyats', 'itogo')


@admin.register(DvizhenieDeneg)
class DvizhenieDenegAdmin(admin.ModelAdmin):
    list_display = ('osnovanie', 'objekt', 'summa_nachislenie', 'data_plan', 'status')
    list_filter = ('status',)


@admin.register(AiZapros)
class AiZaprosAdmin(admin.ModelAdmin):
    list_display = ('objekt', 'vopros', 'demo_rezhim', 'data')
    list_filter = ('demo_rezhim',)
