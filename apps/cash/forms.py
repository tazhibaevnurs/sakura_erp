from django import forms

from .models import Debt, Expense, ExpenseCategory
from .services import is_day_closed


class ExpenseForm(forms.ModelForm):
    def clean_date(self):
        day = self.cleaned_data["date"]
        if is_day_closed(day):
            raise forms.ValidationError("Касса за этот день уже закрыта.")
        return day

    class Meta:
        model = Expense
        fields = ["date", "category", "amount", "comment", "payment_method"]
        labels = {
            "date": "Дата",
            "category": "Категория",
            "amount": "Сумма",
            "comment": "Комментарий",
            "payment_method": "Способ оплаты",
        }
        widgets = {
            "date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "amount": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "comment": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "payment_method": forms.Select(attrs={"class": "form-select"}),
        }


class DebtForm(forms.ModelForm):
    class Meta:
        model = Debt
        fields = [
            "debtor_name",
            "direction",
            "amount",
            "due_date",
            "description",
        ]
        labels = {
            "debtor_name": "Контрагент",
            "direction": "Направление",
            "amount": "Сумма",
            "due_date": "Срок оплаты",
            "description": "Описание",
        }
        widgets = {
            "debtor_name": forms.TextInput(attrs={"class": "form-control"}),
            "amount": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "due_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "direction": forms.Select(attrs={"class": "form-select"}),
        }
