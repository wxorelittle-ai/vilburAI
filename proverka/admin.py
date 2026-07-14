from django.contrib import admin

from .models import ProverkaZakazchika, ChyornySpisok


@admin.register(ChyornySpisok)
class ChyornySpisokAdmin(admin.ModelAdmin):
    list_display = ('telefon', 'inn', 'prichina', 'istochnik', 'kolvo_zhalob', 'data')
    list_filter = ('istochnik',)
    search_fields = ('telefon', 'inn', 'prichina')


@admin.register(ProverkaZakazchika)
class ProverkaZakazchikaAdmin(admin.ModelAdmin):
    list_display = ('znachenie', 'tip_poiska', 'status_riska', 'brigada', 'data')
    list_filter = ('status_riska', 'tip_poiska', 'demo_rezhim')
    search_fields = ('znachenie', 'brigada__nazvanie')
