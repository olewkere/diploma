from django import forms
from .models import Task


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = [
            'title',
            'description',
            'brand',
            'line',
            'quantity',
            'moisture',
            'deadline',
            'status'
        ]
        widgets = {
            'deadline': forms.DateTimeInput(
                attrs={'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M'
            )
        }
        moisture = forms.FloatField(
            widget=forms.NumberInput(attrs={
                'step': '0.1',
                'min': '0.2',
                'max': '0.9'
            }),
            label="Вологість",
            help_text="Введіть значення від 0.2 до 0.9"
        )


class TaskEditForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['title', 'description', 'deadline']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.status != 'new':
            for field in self.fields:
                self.fields[field].disabled = True