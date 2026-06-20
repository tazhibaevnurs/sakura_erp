from django.db import models


class Message(models.Model):
    ROLE_CHOICES = [
        ("user", "Клиент"),
        ("assistant", "Ассистент"),
        ("system", "Система"),
    ]

    conversation = models.ForeignKey(
        "Conversation",
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    intent_detected = models.CharField(max_length=50, blank=True)
    tokens_used = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "Сообщение"
        verbose_name_plural = "Сообщения"

    def __str__(self):
        return f"{self.get_role_display()}: {self.content[:50]}"
