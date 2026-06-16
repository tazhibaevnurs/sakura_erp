from django.db import models


class SalarySchema(models.Model):
    name = models.CharField(max_length=100)
    percent_of_revenue = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    fixed_per_shift = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    fixed_monthly = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = "Схема зарплаты"
        verbose_name_plural = "Схемы зарплаты"

    def __str__(self):
        return self.name


class Shift(models.Model):
    class ShiftType(models.TextChoices):
        WORKED = "worked", "Отработал"
        SICK = "sick", "Больничный"
        ABSENT = "absent", "Прогул"
        DAY_OFF = "day_off", "Выходной"

    employee = models.ForeignKey(
        "accounts.Employee",
        on_delete=models.CASCADE,
        related_name="shifts",
    )
    date = models.DateField()
    time_in = models.TimeField(null=True, blank=True)
    time_out = models.TimeField(null=True, blank=True)
    shift_type = models.CharField(
        max_length=20,
        choices=ShiftType.choices,
        default=ShiftType.WORKED,
    )
    revenue_share_base = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    calculated_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        unique_together = [("employee", "date")]
        ordering = ["-date"]
        verbose_name = "Смена"
        verbose_name_plural = "Смены"

    def __str__(self):
        return f"{self.employee} — {self.date}"


class SalaryPayment(models.Model):
    class PaymentType(models.TextChoices):
        ADVANCE = "advance", "Аванс"
        SALARY = "salary", "Зарплата"
        BONUS = "bonus", "Бонус"
        PENALTY = "penalty", "Штраф"

    employee = models.ForeignKey(
        "accounts.Employee",
        on_delete=models.CASCADE,
        related_name="payments",
    )
    payment_type = models.CharField(max_length=20, choices=PaymentType.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField()
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    comment = models.TextField(blank=True)
    paid_by = models.ForeignKey(
        "accounts.Employee",
        on_delete=models.PROTECT,
        related_name="payments_made",
    )

    class Meta:
        ordering = ["-date"]
        verbose_name = "Выплата"
        verbose_name_plural = "Выплаты"

    def __str__(self):
        return f"{self.get_payment_type_display()} — {self.amount}"
