from decimal import Decimal

from django import forms

from apps.menu.models import MenuItem

from .models import Order, OrderItem


class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ["guest_count", "comment", "order_type"]
        labels = {
            "guest_count": "Количество гостей",
            "comment": "Комментарий к заказу",
            "order_type": "Тип заказа",
        }
        widgets = {
            "guest_count": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "comment": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "order_type": forms.Select(attrs={"class": "form-select"}),
        }


class AddOrderItemForm(forms.Form):
    menu_item = forms.ModelChoiceField(
        queryset=MenuItem.objects.filter(is_available=True, is_stopped=False),
        label="Блюдо",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    quantity = forms.DecimalField(
        min_value=Decimal("0.001"),
        initial=1,
        label="Количество",
        widget=forms.NumberInput(
            attrs={"class": "form-control", "step": "0.001", "min": "0.001"}
        ),
    )
    note = forms.CharField(
        required=False,
        label="Примечание",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Без лука..."}),
    )


class DeliveryOrderForm(forms.Form):
    customer_name = forms.CharField(
        label="Имя",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Иванов Иван"}),
    )
    customer_phone = forms.CharField(
        label="Телефон",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "+996 …"}),
    )
    customer_phone_ext = forms.CharField(
        required=False,
        label="Добавочный номер",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "123"}),
    )
    delivery_address = forms.CharField(
        label="Адрес доставки",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}),
    )


class PayOrderForm(forms.Form):
    payment_method = forms.ChoiceField(
        choices=Order.PaymentMethod.choices,
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Способ оплаты",
    )


class CancelOrderForm(forms.Form):
    cancelled_reason = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        label="Причина отмены",
    )

