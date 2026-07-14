from django import forms

from .models import (
    Objekt, EtapGrafika, Material, OplataMontajnika, RashodMesyachny, DvizhenieDeneg,
)


class ObjektForm(forms.ModelForm):
    class Meta:
        model = Objekt
        fields = [
            'nazvanie', 'adres', 'zakazchik', 'master_otvetstvenny',
            'data_nachala', 'data_okonchania_plan', 'summa_dogovora',
            'avans_procent', 'srok_oplaty_posle_akta_dney',
            'garantiynoe_uderzhanie_procent', 'srok_vozvrata_garantii_dney',
        ]
        widgets = {
            'data_nachala': forms.DateInput(attrs={'type': 'date'}),
            'data_okonchania_plan': forms.DateInput(attrs={'type': 'date'}),
        }


class EtapGrafikaForm(forms.ModelForm):
    class Meta:
        model = EtapGrafika
        fields = ['nazvanie', 'edinica', 'plan_objem', 'rascenka', 'plan_data_nachala', 'plan_data_okonchania']
        widgets = {
            'plan_data_nachala': forms.DateInput(attrs={'type': 'date'}),
            'plan_data_okonchania': forms.DateInput(attrs={'type': 'date'}),
        }


class FactObjemForm(forms.ModelForm):
    """Ввод факта по этапу — единственный способ поднять fact_objem (раздел 16 ТЗ)."""
    class Meta:
        model = EtapGrafika
        fields = ['fact_objem']


class MaterialForm(forms.ModelForm):
    class Meta:
        model = Material
        fields = ['etap', 'nazvanie', 'srok_proizvodstva_dney', 'srok_dostavki_dney', 'bufer_dney', 'status']

    def __init__(self, *args, objekt=None, **kwargs):
        super().__init__(*args, **kwargs)
        if objekt is not None:
            self.fields['etap'].queryset = objekt.etapy.all()


class OplataMontajnikaForm(forms.ModelForm):
    class Meta:
        model = OplataMontajnika
        fields = ['montajnik_fio', 'rascenka', 'mesyats', 'plan_objem_mesyats', 'fact_objem_mesyats', 'summa_oplacheno', 'oplacheno_sverh_grafika']
        widgets = {'mesyats': forms.DateInput(attrs={'type': 'date'})}


class RashodMesyachnyForm(forms.ModelForm):
    class Meta:
        model = RashodMesyachny
        fields = ['mesyats', 'sutochnye', 'arenda_kvartiry', 'oplata_mastera', 'dolya_ofisa', 'prochee']
        widgets = {'mesyats': forms.DateInput(attrs={'type': 'date'})}


class DvizhenieDenegForm(forms.ModelForm):
    class Meta:
        model = DvizhenieDeneg
        fields = ['osnovanie', 'summa_nachislenie', 'data_plan', 'data_fakt', 'status', 'etap']
        widgets = {
            'data_plan': forms.DateInput(attrs={'type': 'date'}),
            'data_fakt': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, objekt=None, **kwargs):
        super().__init__(*args, **kwargs)
        if objekt is not None:
            self.fields['etap'].queryset = objekt.etapy.all()
        self.fields['etap'].required = False
        self.fields['data_fakt'].required = False
