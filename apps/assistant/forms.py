from django import forms

from .models import AssistantSettings


class AssistantSettingsForm(forms.ModelForm):
    class Meta:
        model = AssistantSettings
        fields = [
            "is_enabled",
            "accept_orders_enabled",
            "restaurant_name",
            "restaurant_address",
            "restaurant_phone",
            "working_hours",
            "about_restaurant",
            "delivery_info",
            "booking_info",
            "welcome_message",
            "ai_provider",
            "ai_api_key",
            "ai_model",
            "ai_base_url",
            "agent_instruction",
            "ai_temperature",
            "max_output_tokens",
            "max_history_turns",
            "operator_handoff_enabled",
            "operator_handoff_keywords",
            "operator_handoff_message",
            "operator_pause_minutes",
            "reply_format",
            "use_emoji",
            "split_long_messages",
            "voice_messages_enabled",
            "voice_provider",
            "voice_language",
            "typing_indicator_enabled",
            "response_delay_ms",
            "business_hours_only",
            "off_hours_message",
            "fallback_message",
            "telegram_enabled",
            "telegram_bot_token",
            "whatsapp_enabled",
            "whatsapp_phone_number_id",
            "whatsapp_access_token",
            "whatsapp_verify_token",
        ]
        widgets = {
            "is_enabled": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "accept_orders_enabled": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "restaurant_name": forms.TextInput(attrs={"class": "form-control"}),
            "restaurant_address": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "restaurant_phone": forms.TextInput(attrs={"class": "form-control"}),
            "working_hours": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "about_restaurant": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "delivery_info": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "booking_info": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "welcome_message": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "ai_provider": forms.Select(attrs={"class": "form-select", "id": "id_ai_provider"}),
            "ai_api_key": forms.PasswordInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Оставьте пустым, чтобы не менять",
                    "id": "id_ai_api_key",
                },
                render_value=True,
            ),
            "ai_model": forms.TextInput(
                attrs={"class": "form-control", "id": "id_ai_model", "placeholder": "gpt-4o-mini"}
            ),
            "ai_base_url": forms.TextInput(
                attrs={"class": "form-control", "id": "id_ai_base_url"}
            ),
            "agent_instruction": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 6,
                    "placeholder": "Например: отвечай вежливо, предлагай бронь, не обсуждай конкурентов…",
                }
            ),
            "ai_temperature": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.1",
                    "min": "0",
                    "max": "2",
                    "id": "id_ai_temperature",
                }
            ),
            "max_output_tokens": forms.NumberInput(
                attrs={"class": "form-control", "min": "100", "max": "4000"}
            ),
            "max_history_turns": forms.NumberInput(
                attrs={"class": "form-control", "min": "1", "max": "20"}
            ),
            "operator_handoff_enabled": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "operator_handoff_keywords": forms.TextInput(attrs={"class": "form-control"}),
            "operator_handoff_message": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "operator_pause_minutes": forms.NumberInput(
                attrs={"class": "form-control", "min": "5", "max": "240"}
            ),
            "reply_format": forms.Select(attrs={"class": "form-select"}),
            "use_emoji": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "split_long_messages": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "voice_messages_enabled": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "voice_provider": forms.Select(attrs={"class": "form-select"}),
            "voice_language": forms.TextInput(attrs={"class": "form-control", "placeholder": "ru"}),
            "typing_indicator_enabled": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "response_delay_ms": forms.NumberInput(
                attrs={"class": "form-control", "min": "0", "max": "10000", "step": "100"}
            ),
            "business_hours_only": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "off_hours_message": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "fallback_message": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "telegram_enabled": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "telegram_bot_token": forms.PasswordInput(
                attrs={"class": "form-control"},
                render_value=True,
            ),
            "whatsapp_enabled": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "whatsapp_phone_number_id": forms.TextInput(attrs={"class": "form-control"}),
            "whatsapp_access_token": forms.PasswordInput(
                attrs={"class": "form-control"},
                render_value=True,
            ),
            "whatsapp_verify_token": forms.TextInput(attrs={"class": "form-control"}),
        }
        labels = {
            "is_enabled": "Включить ассистента",
            "accept_orders_enabled": "Принимать заказы через ассистента",
            "ai_api_key": "API-ключ ИИ",
            "ai_model": "Модель ИИ",
            "ai_base_url": "URL API (OpenRouter / свой сервер)",
            "agent_instruction": "Инструкция для ИИ-агента",
            "telegram_enabled": "Включить Telegram",
            "telegram_bot_token": "Токен бота Telegram",
            "whatsapp_enabled": "Включить WhatsApp",
        }
        help_texts = {
            "agent_instruction": (
                "Основные правила для бота: стиль общения, приоритеты, запреты. "
                "Дополняет автоматическую базу знаний ресторана."
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        provider = (
            self.data.get("ai_provider")
            if self.is_bound
            else getattr(self.instance, "ai_provider", AssistantSettings.AIProvider.OPENAI)
        )
        self._apply_provider_hints(provider)
        if self.instance and self.instance.pk:
            for field in ("ai_api_key", "telegram_bot_token", "whatsapp_access_token"):
                if getattr(self.instance, field):
                    self.fields[field].help_text = (
                        "Заполнено. Оставьте пустым, чтобы не менять."
                    )

    def _apply_provider_hints(self, provider):
        if provider == AssistantSettings.AIProvider.GEMINI:
            self.fields["ai_api_key"].label = "Gemini API key"
            self.fields["ai_api_key"].help_text = (
                "Ключ из Google AI Studio (aistudio.google.com). "
                "Или задайте ASSISTANT_GEMINI_API_KEY в .env."
            )
            self.fields["ai_model"].help_text = (
                "Рекомендуется gemini-2.5-flash-lite. Также: gemini-2.5-flash"
            )
            self.fields["ai_model"].widget.attrs["placeholder"] = "gemini-2.5-flash-lite"
            self.fields["ai_base_url"].help_text = "Для Gemini не требуется"
        else:
            self.fields["ai_api_key"].label = "API-ключ ИИ"
            self.fields["ai_model"].widget.attrs["placeholder"] = "gpt-4o-mini"
            self.fields["ai_base_url"].help_text = "Для OpenRouter или своего сервера"

    def clean_ai_temperature(self):
        value = self.cleaned_data["ai_temperature"]
        if value < 0 or value > 2:
            raise forms.ValidationError("Температура должна быть от 0 до 2.")
        return round(float(value), 1)

    def save(self, commit=True):
        from .llm import GEMINI_MODEL_ALIASES

        instance = super().save(commit=False)
        for field in ("ai_api_key", "telegram_bot_token", "whatsapp_access_token"):
            if not self.cleaned_data.get(field) and self.instance.pk:
                setattr(instance, field, getattr(self.instance, field))
        if instance.ai_provider == AssistantSettings.AIProvider.GEMINI:
            alias = GEMINI_MODEL_ALIASES.get((instance.ai_model or "").strip())
            if alias:
                instance.ai_model = alias
        instance.extra_system_prompt = instance.agent_instruction
        if commit:
            instance.save()
        return instance


class TestChatForm(forms.Form):
    message = forms.CharField(
        label="Сообщение",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}),
    )
