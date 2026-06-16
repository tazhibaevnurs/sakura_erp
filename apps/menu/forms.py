from django import forms

from .models import MenuItem


class MenuItemForm(forms.ModelForm):
    class Meta:
        model = MenuItem
        fields = ["category", "name", "price", "unit", "description", "is_available", "order"]
        labels = {
            "category": "Категория",
            "name": "Название",
            "price": "Цена",
            "unit": "Единица измерения",
            "description": "Описание",
            "is_available": "В наличии",
            "order": "Порядок сортировки",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2, "class": "form-control"}),
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "price": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "order": forms.NumberInput(attrs={"class": "form-control"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "unit": forms.Select(attrs={"class": "form-select"}),
        }
