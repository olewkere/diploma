from django import forms
from .models import Tariff


class TariffForm(forms.ModelForm):
    class Meta:
        model = Tariff
        fields = ['day_rate', 'night_rate']
        labels = {
            'day_rate': 'Денний тариф',
            'night_rate': 'Нічний тариф',
        }
        widgets = {
            'day_rate': forms.NumberInput(attrs={'step': '0.01'}),
            'night_rate': forms.NumberInput(attrs={'step': '0.01'}),
        }