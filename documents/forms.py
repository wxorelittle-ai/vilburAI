from django import forms
from django.forms import inlineformset_factory

from .models import Dokument, DokumentPozicia


BASE_WIDGETS = {
    'zakazchik': forms.TextInput(attrs={'placeholder': 'Иванов Иван Иванович'}),
    'zakazchik_telefon': forms.TextInput(attrs={'placeholder': '+79991234567'}),
    'adres_obekta': forms.TextInput(attrs={'placeholder': 'г. Тюмень, ул. Ленина, д. 1, кв. 25'}),
    'srok_nachala': forms.DateInput(attrs={'type': 'date'}),
    'srok_okonchania': forms.DateInput(attrs={'type': 'date'}),
}


class DogovorForm(forms.ModelForm):
    """Договор подряда: оплата 30/40/30 рассчитывается автоматически от summa."""

    class Meta:
        model = Dokument
        fields = ['zakazchik', 'zakazchik_telefon', 'adres_obekta', 'summa', 'srok_nachala', 'srok_okonchania']
        widgets = BASE_WIDGETS

    def clean(self):
        cleaned = super().clean()
        nachalo = cleaned.get('srok_nachala')
        okonchanie = cleaned.get('srok_okonchania')
        if nachalo and okonchanie and okonchanie < nachalo:
            raise forms.ValidationError('Дата окончания не может быть раньше даты начала.')
        return cleaned


class RaspiskaForm(forms.ModelForm):
    """Расписка об авансе."""

    class Meta:
        model = Dokument
        fields = ['zakazchik', 'zakazchik_telefon', 'adres_obekta', 'avans_summa', 'srok_nachala']
        widgets = {**BASE_WIDGETS, 'srok_nachala': forms.DateInput(attrs={'type': 'date'})}
        labels = {'srok_nachala': 'Дата получения аванса'}


class AktPriemkiForm(forms.ModelForm):
    """Акт приёмки этапа — чек-лист заполняется автоматически из DEFAULT_CHECKLIST."""

    class Meta:
        model = Dokument
        fields = ['zakazchik', 'adres_obekta', 'etap_nazvanie']
        widgets = {
            'zakazchik': BASE_WIDGETS['zakazchik'],
            'adres_obekta': BASE_WIDGETS['adres_obekta'],
            'etap_nazvanie': forms.TextInput(attrs={'placeholder': 'Например: Черновая штукатурка стен'}),
        }


class AktVkrForm(forms.ModelForm):
    """Акт выполненных работ (ВКР) — шапка; позиции заполняются через formset."""

    class Meta:
        model = Dokument
        fields = ['zakazchik', 'adres_obekta', 'srok_okonchania']
        widgets = {
            'zakazchik': BASE_WIDGETS['zakazchik'],
            'adres_obekta': BASE_WIDGETS['adres_obekta'],
            'srok_okonchania': forms.DateInput(attrs={'type': 'date'}),
        }
        labels = {'srok_okonchania': 'Дата акта'}


class PoziciaForm(forms.ModelForm):
    """
    Явная форма позиции: поля необязательны на уровне формы, чтобы Django формсет
    корректно распознавал полностью пустые «лишние» строки (extra) и не требовал их
    заполнения — модельные default-значения (edinica='м²', kolvo=0) иначе триггерят
    has_changed() и ломают этот механизм.
    """

    class Meta:
        model = DokumentPozicia
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


PoziciaFormSet = inlineformset_factory(
    Dokument,
    DokumentPozicia,
    form=PoziciaForm,
    extra=3,
    can_delete=True,
)
