from django.db import models


class ExpenseCategory(models.Model):
    name = models.CharField(max_length=100)
    is_system = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Категория расхода"
        verbose_name_plural = "Категории расходов"

    def __str__(self):
        return self.name


class DailyCash(models.Model):
    date = models.DateField(unique=True)
    total_revenue = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    cash_revenue = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    card_revenue = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    qr_revenue = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    takeaway_revenue = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_expenses = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    net_profit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    deposit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    closed_by = models.ForeignKey(
        "accounts.Employee",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-date"]
        verbose_name = "Касса за день"
        verbose_name_plural = "Касса по дням"

    def __str__(self):
        return str(self.date)

    @property
    def is_closed(self):
        return self.closed_at is not None

    def recalculate(self):
        from django.db.models import Sum

        from apps.orders.models import Order

        paid = Order.objects.filter(
            status=Order.Status.PAID,
            paid_at__date=self.date,
        )
        self.cash_revenue = sum(
            o.total for o in paid.filter(payment_method=Order.PaymentMethod.CASH)
        ) or 0
        self.card_revenue = sum(
            o.total for o in paid.filter(payment_method=Order.PaymentMethod.CARD)
        ) or 0
        self.qr_revenue = sum(
            o.total for o in paid.filter(payment_method=Order.PaymentMethod.QR)
        ) or 0
        self.takeaway_revenue = sum(
            o.total
            for o in paid.filter(order_type=Order.OrderType.TAKEAWAY)
        ) or 0
        self.total_revenue = paid.aggregate(t=Sum("total"))["t"] or 0
        self.total_expenses = (
            Expense.objects.filter(date=self.date).aggregate(t=Sum("amount"))["t"] or 0
        )
        self.net_profit = self.total_revenue - self.total_expenses


class Expense(models.Model):
    class PaymentMethod(models.TextChoices):
        CASH = "cash", "Наличные"
        TRANSFER = "transfer", "Перевод"

    date = models.DateField()
    expense_time = models.TimeField(verbose_name="Время", null=True, blank=True)
    category = models.ForeignKey(ExpenseCategory, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    comment = models.TextField()
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices)
    added_by = models.ForeignKey("accounts.Employee", on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created_at"]
        verbose_name = "Расход"
        verbose_name_plural = "Расходы"

    def __str__(self):
        return f"{self.category} — {self.amount}"


class Debt(models.Model):
    class Direction(models.TextChoices):
        THEY_OWE_US = "they_owe", "Нам должны"
        WE_OWE_THEM = "we_owe", "Мы должны"

    class Status(models.TextChoices):
        ACTIVE = "active", "Активен"
        PARTIAL = "partial", "Частично оплачен"
        CLOSED = "closed", "Закрыт"

    debtor_name = models.CharField(max_length=200)
    direction = models.CharField(max_length=20, choices=Direction.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    due_date = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey("accounts.Employee", on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Долг"
        verbose_name_plural = "Долги"

    def __str__(self):
        return f"{self.debtor_name} — {self.amount}"

    @property
    def remaining(self):
        return self.amount - self.paid_amount
