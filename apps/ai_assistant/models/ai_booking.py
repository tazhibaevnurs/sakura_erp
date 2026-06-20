from django.db import models


class AIBooking(models.Model):
    """Связь броней ERP с профилем клиента ассистента."""

    client = models.ForeignKey(
        "ClientProfile",
        on_delete=models.CASCADE,
        related_name="ai_bookings",
    )
    erp_reservation = models.ForeignKey(
        "tables.TableReservation",
        on_delete=models.CASCADE,
        related_name="ai_source",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Бронь через ассистента"
        verbose_name_plural = "Брони через ассистента"
        ordering = ["-created_at"]

    def __str__(self):
        return f"AI бронь #{self.erp_reservation_id} — {self.client}"
