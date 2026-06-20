from django.db import models


class ClientProfile(models.Model):
    CHANNEL_CHOICES = [
        ("telegram", "Telegram"),
        ("whatsapp", "WhatsApp"),
        ("instagram", "Instagram"),
        ("web_test", "Тест (ERP)"),
    ]
    ORDER_TYPE_CHOICES = [
        ("delivery", "Доставка"),
        ("takeaway", "Самовывоз"),
    ]

    telegram_id = models.CharField(max_length=64, unique=True, null=True, blank=True)
    whatsapp_phone = models.CharField(max_length=20, unique=True, null=True, blank=True)
    instagram_id = models.CharField(max_length=64, unique=True, null=True, blank=True)

    name = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=20, blank=True)

    preferred_channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, blank=True)
    preferred_order_type = models.CharField(max_length=20, choices=ORDER_TYPE_CHOICES, blank=True)
    total_orders = models.PositiveIntegerField(default=0)
    last_interaction = models.DateTimeField(auto_now=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Профиль клиента"
        verbose_name_plural = "Профили клиентов"

    def __str__(self):
        label = self.name or self.phone or self.telegram_id or self.whatsapp_phone or self.instagram_id
        return f"Клиент {label or self.pk}"
