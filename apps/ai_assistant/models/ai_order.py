from django.db import models


class AIOrder(models.Model):
    """Связь заказов ERP с профилем клиента ассистента."""

    client = models.ForeignKey(
        "ClientProfile",
        on_delete=models.CASCADE,
        related_name="ai_orders",
    )
    erp_order = models.ForeignKey(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="ai_source",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Заказ через ассистента"
        verbose_name_plural = "Заказы через ассистента"
        ordering = ["-created_at"]

    def __str__(self):
        return f"AI заказ #{self.erp_order_id} — {self.client}"
