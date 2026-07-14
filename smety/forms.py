from django import forms
from django.forms import inlineformset_factory

from .models import Smeta, SmetaRabota


class SmetaForm(forms.ModelForm):
    class Meta:
        model = Smeta
        fields = ['nazvanie', 'adres', 'zakazchik', 'urovne_cen', 'srok_dney']
        widgets = {
            'nazvanie': forms.TextInput(attrs={'placeholder': 'Ремонт квартиры, ул. Мира 10'}),
            'adres': forms.TextInput(attrs={'placeholder': 'г. Тюмень, ул. Мира, д. 10, кв. 5'}),
            'zakazchik': forms.TextInput(attrs={'placeholder': 'Иванов Иван Иванович'}),
            'srok_dney': forms.NumberInput(attrs={'min': '1', 'placeholder': '14'}),
        }


class SmetaRabotaForm(forms.ModelForm):
    """
    Поля необязательны на уровне формы — так формсет корректно распознаёт
    полностью пустые «лишние» строки и не требует их заполнения (та же проблема
    и то же решение, что и в documents/forms.py::PoziciaForm).
    """

    class Meta:
        model = SmetaRabota
        fields = ['nazvanie', 'edinica', 'kolvo', 'cena']
        widgets = {
            'nazvanie': forms.TextInput(attrs={'placeholder': 'Штукатурка стен'}),
            'edinica': forms.TextInput(attrs={'placeholder': 'м²'}),
            'kolvo': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'cena': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.required = False


SmetaRabotaFormSet = inlineformset_factory(
    Smeta,
    SmetaRabota,
    form=SmetaRabotaForm,
    extra=5,
    can_delete=True,
)
