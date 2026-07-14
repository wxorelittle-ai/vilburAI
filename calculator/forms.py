from django import forms

from .models import Raschet


class RaschetForm(forms.ModelForm):
    class Meta:
        model = Raschet
        fields = [
            'ploshad', 'tip_remonta', 'kolvo_rabochih', 'dni', 'stavka_v_den',
            'arenda', 'dostavka', 'rashodniki', 'nalog',
        ]
        widgets = {
            'ploshad': forms.NumberInput(attrs={'step': '0.1', 'min': '0', 'placeholder': '45'}),
            'kolvo_rabochih': forms.NumberInput(attrs={'min': '1'}),
            'dni': forms.NumberInput(attrs={'min': '1'}),
            'stavka_v_den': forms.NumberInput(attrs={'step': '100', 'min': '0'}),
            'arenda': forms.NumberInput(attrs={'step': '100', 'min': '0'}),
            'dostavka': forms.NumberInput(attrs={'step': '100', 'min': '0'}),
            'rashodniki': forms.NumberInput(attrs={'step': '100', 'min': '0'}),
        }
        labels = {
            'ploshad': 'Площадь помещения, м²',
        }

    def clean_ploshad(self):
        ploshad = self.cleaned_data['ploshad']
        if ploshad <= 0:
            raise forms.ValidationError('Площадь должна быть больше нуля.')
        return ploshad
