from django import forms

from .models import AssistantConfig


class AssistantConfigForm(forms.ModelForm):
    class Meta:
        model = AssistantConfig
        fields = [
            "is_enabled",
            "restaurant_name",
            "restaurant_address",
            "restaurant_phone",
            "working_hours",
            "about_restaurant",
            "delivery_info",
            "booking_info",
            "promotions",
            "welcome_message",
            "custom_system_prompt",
        ]
        widgets = {
            "restaurant_address": forms.Textarea(attrs={"rows": 2}),
            "working_hours": forms.Textarea(attrs={"rows": 2}),
            "about_restaurant": forms.Textarea(attrs={"rows": 3}),
            "delivery_info": forms.Textarea(attrs={"rows": 3}),
            "booking_info": forms.Textarea(attrs={"rows": 3}),
            "promotions": forms.Textarea(attrs={"rows": 2}),
            "welcome_message": forms.Textarea(attrs={"rows": 5}),
            "custom_system_prompt": forms.Textarea(attrs={"rows": 10, "class": "font-monospace"}),
        }
