from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Brigada


class RegistrationForm(UserCreationForm):
    """
    Форма регистрации бригады: создаёт User + Brigada одной формой.
    Валидация пароля — стандартные Django-валидаторы (8+ символов, буква+цифра, см. settings.py).
    """

    nazvanie = forms.CharField(
        label='Название бригады',
        max_length=255,
        widget=forms.TextInput(attrs={'placeholder': 'Например: Бригада Иванова'}),
    )
    telefon = forms.CharField(
        label='Телефон',
        max_length=20,
        widget=forms.TextInput(attrs={'placeholder': '+79991234567'}),
    )
    region = forms.CharField(
        label='Регион',
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Например: Тюменская область'}),
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            Brigada.objects.create(
                user=user,
                nazvanie=self.cleaned_data['nazvanie'],
                telefon=self.cleaned_data['telefon'],
                region=self.cleaned_data.get('region', ''),
            )
        return user


class BrigadaProfileForm(forms.ModelForm):
    """Редактирование профиля бригады в личном кабинете."""

    class Meta:
        model = Brigada
        fields = ['nazvanie', 'telefon', 'rekvizity', 'logo', 'region']
        widgets = {
            'rekvizity': forms.Textarea(attrs={'rows': 4}),
        }
