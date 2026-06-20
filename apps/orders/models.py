from django.db import models


class KitchenSection(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)

    class Meta:
        verbose_name = "Кухонная секция"
        verbose_name_plural = "Кухонные секции"

    def __str__(self):
        return self.name


class Order(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Открыт"
        SENT = "sent", "Отправлен на кухню"
        COOKING = "cooking", "Готовится"
        READY = "ready", "Готово"
        SERVED = "served", "Подано"
        PAID = "paid", "Оплачен"
        CANCELLED = "cancelled", "Отменён"

    class OrderType(models.TextChoices):
        DINE_IN = "dine_in", "В зале"
        TAKEAWAY = "takeaway", "Навынос"
        DELIVERY = "delivery", "Доставка"

    class PaymentMethod(models.TextChoices):
        CASH = "cash", "Наличные"
        CARD = "card", "Карта"
        QR = "qr", "QR"

    table = models.ForeignKey(
        "tables.Table",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="orders",
    )
    waiter = models.ForeignKey(
        "accounts.Employee",
        on_delete=models.PROTECT,
        related_name="orders",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
    )
    order_type = models.CharField(
        max_length=20,
        choices=OrderType.choices,
        default=OrderType.DINE_IN,
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        blank=True,
    )
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    guest_count = models.PositiveSmallIntegerField(default=1)
    customer_name = models.CharField(max_length=200, blank=True, verbose_name="Имя клиента")
    customer_phone = models.CharField(max_length=30, blank=True, verbose_name="Телефон")
    customer_phone_ext = models.CharField(
        max_length=10, blank=True, verbose_name="Добавочный номер"
    )
    delivery_address = models.TextField(blank=True, verbose_name="Адрес доставки")
    deposit = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Задаток",
    )
    estimated_ready_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Примерная готовность",
    )
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    cancelled_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"

    def __str__(self):
        if self.table:
            return f"Заказ #{self.pk} — стол {self.table.number}"
        if self.order_type == self.OrderType.DELIVERY:
            return f"Заказ #{self.pk} (доставка)"
        return f"Заказ #{self.pk} (навынос)"

    def recalculate_total(self):
        from django.db.models import F, Sum

        total = (
            self.items.exclude(status=OrderItem.Status.CANCELLED).aggregate(
                t=Sum(F("price") * F("quantity"))
            )["t"]
            or 0
        )
        self.total = total
        self.save(update_fields=["total"])

    def kitchen_display_status(self):
        """Статус для официанта по позициям на кухне."""
        items = self.items.exclude(status=OrderItem.Status.CANCELLED)
        if not items.exists():
            return self.get_status_display()
        if items.filter(status=OrderItem.Status.COOKING).exists():
            return "Готовится"
        if items.filter(status=OrderItem.Status.READY).exists():
            if items.filter(
                status__in=[OrderItem.Status.PENDING, OrderItem.Status.COOKING]
            ).exists():
                return "Частично готово"
            return "Готово"
        if self.status == Order.Status.SENT:
            return "На кухне"
        return self.get_status_display()

    def requires_ready_at(self):
        return self.order_type in (
            self.OrderType.TAKEAWAY,
            self.OrderType.DELIVERY,
        )

    def requires_guest_fields(self):
        return self.requires_ready_at()

    def guest_fields_complete(self):
        if not self.requires_guest_fields():
            return True
        if not self.customer_name.strip():
            return False
        if not self.customer_phone.strip():
            return False
        if self.order_type == self.OrderType.DELIVERY and not self.delivery_address.strip():
            return False
        if self.deposit <= 0:
            return False
        if not self.estimated_ready_at:
            return False
        return True

    def can_send_to_kitchen(self):
        items = self.items.exclude(status=OrderItem.Status.CANCELLED)
        if not items.exists():
            return False
        if self.requires_guest_fields():
            return self.guest_fields_complete()
        return True


class OrderItem(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Ожидает"
        COOKING = "cooking", "Готовится"
        READY = "ready", "Готово"
        SERVED = "served", "Подано"
        CANCELLED = "cancelled", "Отменено"

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    menu_item = models.ForeignKey("menu.MenuItem", on_delete=models.PROTECT)
    kitchen_section = models.ForeignKey(KitchenSection, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=8, decimal_places=3, default=1)
    ready_by = models.ForeignKey(
        "accounts.Employee",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="completed_order_items",
        verbose_name="Отпустил",
    )
    price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    note = models.CharField(max_length=200, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    ready_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Позиция заказа"
        verbose_name_plural = "Позиции заказов"

    def __str__(self):
        return f"{self.menu_item.name} x{self.quantity}"
