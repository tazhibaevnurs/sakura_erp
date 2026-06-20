from django.db import models


class Conversation(models.Model):
    CHANNEL_CHOICES = [
        ("telegram", "Telegram"),
        ("whatsapp", "WhatsApp"),
        ("instagram", "Instagram"),
        ("web_test", "Тест (ERP)"),
    ]
    STATUS_CHOICES = [
        ("active", "Активен"),
        ("waiting_confirm", "Ожидает подтверждения"),
        ("completed", "Завершён"),
        ("escalated", "Передан оператору"),
    ]
    LANGUAGE_CHOICES = [
        ("ru", "Русский"),
        ("ky", "Кыргызский"),
    ]

    client = models.ForeignKey(
        "ClientProfile",
        on_delete=models.CASCADE,
        related_name="conversations",
    )
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    language = models.CharField(
        max_length=2,
        choices=LANGUAGE_CHOICES,
        blank=True,
        verbose_name="Язык диалога",
    )
    current_intent = models.CharField(max_length=50, blank=True)
    draft_data = models.JSONField(default=dict, blank=True)
    platform_message_ids = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Диалог"
        verbose_name_plural = "Диалоги"
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Диалог #{self.pk} ({self.get_channel_display()})"
