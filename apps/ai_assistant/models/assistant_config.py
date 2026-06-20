from django.db import models

from ..services.prompts import DEFAULT_CUSTOM_INSTRUCTIONS, DEFAULT_WELCOME_MESSAGE


class AssistantConfig(models.Model):
    """Singleton: системный промпт и публичная информация о ресторане."""

    restaurant_name = models.CharField(max_length=200, default="Сакура", verbose_name="Название")
    restaurant_address = models.TextField(blank=True, verbose_name="Адрес")
    restaurant_phone = models.CharField(max_length=50, blank=True, verbose_name="Телефон")
    working_hours = models.TextField(
        default="Ежедневно 10:00–23:00",
        verbose_name="Часы работы",
    )
    about_restaurant = models.TextField(
        blank=True,
        verbose_name="О ресторане",
        help_text="Кухня, атмосфера",
    )
    delivery_info = models.TextField(blank=True, verbose_name="Доставка")
    booking_info = models.TextField(blank=True, verbose_name="Бронирование")
    promotions = models.TextField(blank=True, verbose_name="Акции")

    welcome_message = models.TextField(
        default=DEFAULT_WELCOME_MESSAGE,
        verbose_name="Приветствие (/start)",
    )
    custom_system_prompt = models.TextField(
        default=DEFAULT_CUSTOM_INSTRUCTIONS,
        verbose_name="Доп. инструкции для ИИ",
        help_text="Добавляются к базовому промпту. Правила безопасности и JSON-формат зафиксированы в коде.",
    )

    is_enabled = models.BooleanField(default=True, verbose_name="Ассистент включён")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Настройки ассистента"
        verbose_name_plural = "Настройки ассистента"

    def __str__(self):
        return f"Настройки — {self.restaurant_name}"

    @classmethod
    def load(cls) -> "AssistantConfig":
        obj, created = cls.objects.get_or_create(pk=1)
        if created:
            from django.conf import settings

            cfg = getattr(settings, "AI_ASSISTANT", {})
            obj.restaurant_phone = cfg.get("FALLBACK_PHONE", "")
            obj.restaurant_address = cfg.get("BUSINESS_ADDRESS", "")
            obj.working_hours = cfg.get("BUSINESS_HOURS", obj.working_hours)
            obj.promotions = cfg.get("BUSINESS_PROMOTIONS", "")
            obj.delivery_info = cfg.get("DELIVERY_INFO", "")
            obj.booking_info = cfg.get("BOOKING_INFO", "")
            obj.save()
        return obj
