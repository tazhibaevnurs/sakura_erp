from django import forms

from apps.accounts.models import Employee

from .models import Shift


class ShiftForm(forms.ModelForm):
    class Meta:
        model = Shift
        fields = ["employee", "date", "shift_type", "time_in", "time_out"]
        labels = {
            "employee": "Сотрудник",
            "date": "Дата",
            "shift_type": "Тип смены",
            "time_in": "Приход",
            "time_out": "Уход",
        }
        widgets = {
            "date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "time_in": forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
            "time_out": forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
            "employee": forms.Select(attrs={"class": "form-select"}),
            "shift_type": forms.Select(attrs={"class": "form-select"}),
        }
