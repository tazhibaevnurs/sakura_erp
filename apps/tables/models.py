from django.db import models
from django.utils import timezone

from .reservation_time import (
    current_reservation_for_table,
    effective_floor_status,
    floor_card_style,
    floor_reservation_for_table,
    upcoming_reservations_for_table,
)


class Table(models.Model):
    class TableType(models.TextChoices):
        BOOTH = "booth", "Кабинка"
        TABLE = "table", "Стол"
        OUTDOOR = "outdoor", "Улица"

    class Status(models.TextChoices):
        FREE = "free", "Свободен"
        OCCUPIED = "occupied", "Занят"
        WAITING_PAYMENT = "waiting_payment", "Ожидает оплаты"
        RESERVED = "reserved", "Зарезервирован"

    number = models.PositiveSmallIntegerField(unique=True, verbose_name="Номер")
    type = models.CharField(
        max_length=20,
        choices=TableType.choices,
        default=TableType.TABLE,
        verbose_name="Тип",
    )
    capacity = models.PositiveSmallIntegerField(default=4, verbose_name="Мест")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.FREE,
        verbose_name="Статус",
    )
    position_x = models.FloatField(default=0, verbose_name="Позиция X")
    position_y = models.FloatField(default=0, verbose_name="Позиция Y")

    class Meta:
        ordering = ["number"]
        verbose_name = "Кабинка"
        verbose_name_plural = "Кабинки"

    def __str__(self):
        return f"Кабинка {self.number}"

    @property
    def active_order(self):
        return (
            self.orders.filter(
                status__in=[
                    "open",
                    "sent",
                    "cooking",
                    "ready",
                    "served",
                ]
            )
            .order_by("-created_at")
            .first()
        )

    @property
    def active_reservation(self):
        """Бронь, актуальная прямо сейчас (по времени)."""
        return current_reservation_for_table(self)

    @property
    def floor_reservation(self):
        """Текущая или ближайшая бронь для схемы зала."""
        return floor_reservation_for_table(self)

    @property
    def display_status(self):
        return effective_floor_status(self)

    @property
    def floor_card_style(self):
        return floor_card_style(self)

    def upcoming_reservations(self, limit=10):
        return upcoming_reservations_for_table(self, limit=limit)

    @property
    def assigned_waiters(self):
        return [
            a.waiter
            for a in self.waiter_assignments.filter(is_active=True)
            .select_related("waiter__user")
            .order_by("assigned_at", "pk")
        ]

    @property
    def assigned_waiter(self):
        waiters = self.assigned_waiters
        return waiters[0] if waiters else None

    def can_reserve_at(self, start, end):
        from datetime import timedelta

        from .reservation_time import conflicting_reservations

        if end <= start:
            return False
        now = timezone.now()
        if self.active_order and start <= now < end:
            return False
        if start < now - timedelta(minutes=5):
            return False
        return not conflicting_reservations(self, start, end).exists()


class TableReservation(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Активна"
        CANCELLED = "cancelled", "Отменена"
        COMPLETED = "completed", "Гость пришёл"

    table = models.ForeignKey(
        Table,
        on_delete=models.CASCADE,
        related_name="reservations",
        verbose_name="Кабинка",
    )
    guest_name = models.CharField(max_length=200, verbose_name="Имя гостя")
    guest_phone = models.CharField(max_length=30, blank=True, verbose_name="Телефон")
    guest_count = models.PositiveSmallIntegerField(default=2, verbose_name="Гостей")
    reserved_for = models.DateTimeField(verbose_name="Начало")
    reserved_until = models.DateTimeField(verbose_name="Окончание")
    comment = models.TextField(blank=True, verbose_name="Комментарий")
    created_by = models.ForeignKey(
        "accounts.Employee",
        on_delete=models.PROTECT,
        related_name="table_reservations",
        verbose_name="Оформил",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        verbose_name="Статус брони",
    )
    order = models.OneToOneField(
        "orders.Order",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="table_reservation",
        verbose_name="Предзаказ",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создана")

    class Meta:
        ordering = ["reserved_for"]
        verbose_name = "Бронь кабинки"
        verbose_name_plural = "Брони кабинок"

    def __str__(self):
        return f"Бронь #{self.pk} — кабинка {self.table.number}, {self.guest_name}"

    @property
    def is_past(self):
        return self.reserved_until < timezone.now()

    @property
    def is_current(self):
        from .reservation_time import is_reservation_current

        return is_reservation_current(self)

    @property
    def has_preorder(self):
        return bool(self.order_id)

    @property
    def can_mark_arrival(self):
        if self.status != self.Status.ACTIVE:
            return False
        now = timezone.now()
        if now >= self.reserved_until:
            return False
        from .reservation_time import is_reservation_current

        return is_reservation_current(self)

    @property
    def time_range_display(self):
        start = timezone.localtime(self.reserved_for)
        end = timezone.localtime(self.reserved_until)
        if start.date() == end.date():
            return f"{start.strftime('%d.%m.%Y %H:%M')} – {end.strftime('%H:%M')}"
        return f"{start.strftime('%d.%m %H:%M')} – {end.strftime('%d.%m %H:%M')}"


class TableWaiterAssignment(models.Model):
    table = models.ForeignKey(
        Table,
        on_delete=models.CASCADE,
        related_name="waiter_assignments",
        verbose_name="Кабинка",
    )
    waiter = models.ForeignKey(
        "accounts.Employee",
        on_delete=models.CASCADE,
        related_name="table_assignments",
        verbose_name="Официант",
    )
    assigned_by = models.ForeignKey(
        "accounts.Employee",
        on_delete=models.PROTECT,
        related_name="waiter_assignments_made",
        verbose_name="Назначил",
    )
    is_active = models.BooleanField(default=True, verbose_name="Активно")
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Назначение официанта"
        verbose_name_plural = "Назначения официантов"
        constraints = [
            models.UniqueConstraint(
                fields=["table", "waiter"],
                name="unique_waiter_assignment_per_table",
            )
        ]

    def __str__(self):
        return f"Кабинка {self.table.number} — {self.waiter}"
