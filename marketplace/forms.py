from django import forms

from .models import Otzyv, IzlishekMateriala, Tender, TenderOtklik


class OtzyvForm(forms.ModelForm):
    class Meta:
        model = Otzyv
        fields = ['avtor_imya', 'ocenka', 'obekt', 'tekst']
        widgets = {
            'ocenka': forms.Select(choices=[(i, f'{i} ★') for i in range(5, 0, -1)]),
            'tekst': forms.Textarea(attrs={'rows': 4}),
        }


class IzlishekForm(forms.ModelForm):
    class Meta:
        model = IzlishekMateriala
        fields = ['nazvanie', 'kolvo', 'edinica', 'cena', 'region', 'opisanie', 'kontakt_telefon']
        widgets = {'opisanie': forms.Textarea(attrs={'rows': 3})}


class TenderForm(forms.ModelForm):
    class Meta:
        model = Tender
        fields = ['nazvanie', 'opisanie', 'region', 'byudzhet', 'srok_do']
        widgets = {
            'opisanie': forms.Textarea(attrs={'rows': 4}),
            'srok_do': forms.DateInput(attrs={'type': 'date'}),
        }


class OtklikForm(forms.ModelForm):
    class Meta:
        model = TenderOtklik
        fields = ['cena', 'srok_dney', 'kommentariy']
        widgets = {'kommentariy': forms.Textarea(attrs={'rows': 3})}
