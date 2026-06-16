from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User

from apps.salary.models import SalarySchema

from .models import Employee, Role


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        label="Логин",
        widget=forms.TextInput(attrs={"class": "form-control", "autofocus": True}),
    )
    password = forms.CharField(
        label="Пароль",
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
    )


class EmployeeForm(forms.ModelForm):
    username = forms.CharField(label="Логин", max_length=150)
    password = forms.CharField(label="Пароль", widget=forms.PasswordInput, required=False)
    first_name = forms.CharField(label="Имя", required=False)
    last_name = forms.CharField(label="Фамилия", required=False)

    class Meta:
        model = Employee
        fields = [
            "role",
            "kitchen_section",
            "phone",
            "hired_date",
            "salary_schema",
            "advance_limit",
            "is_active",
            "notes",
        ]
        widgets = {
            "hired_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "notes": forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        labels_ru = {
            "role": "Роль",
            "kitchen_section": "Кухонная секция",
            "phone": "Телефон",
            "hired_date": "Дата приёма",
            "salary_schema": "Схема зарплаты",
            "advance_limit": "Лимит аванса",
            "is_active": "Активен",
            "notes": "Примечания",
        }
        for name, label in labels_ru.items():
            if name in self.fields:
                self.fields[name].label = label
        for name, field in self.fields.items():
            if name not in ("is_active",):
                if not isinstance(field.widget, forms.CheckboxInput):
                    field.widget.attrs.setdefault("class", "form-select" if isinstance(field, forms.ModelChoiceField) else "form-control")
        if "phone" in self.fields:
            self.fields["phone"].widget.attrs.setdefault("placeholder", "+996 …")
        if self.instance and self.instance.pk:
            self.fields["username"].initial = self.instance.user.username
            self.fields["first_name"].initial = self.instance.user.first_name
            self.fields["last_name"].initial = self.instance.user.last_name
            self.fields["password"].help_text = "Оставьте пустым, чтобы не менять"

    def save(self, commit=True):
        employee = super().save(commit=False)
        if employee.pk:
            user = employee.user
            user.username = self.cleaned_data["username"]
            user.first_name = self.cleaned_data.get("first_name", "")
            user.last_name = self.cleaned_data.get("last_name", "")
            if self.cleaned_data.get("password"):
                user.set_password(self.cleaned_data["password"])
            user.save()
        else:
            user = User.objects.create_user(
                username=self.cleaned_data["username"],
                password=self.cleaned_data["password"] or "changeme123",
                first_name=self.cleaned_data.get("first_name", ""),
                last_name=self.cleaned_data.get("last_name", ""),
            )
            employee.user = user
        if commit:
            employee.save()
            user = employee.user
            user.groups.clear()
            user.groups.add(employee.role.group)
        return employee
