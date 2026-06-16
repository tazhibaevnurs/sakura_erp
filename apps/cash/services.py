from datetime import date
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from apps.orders.models import Order

from .models import DailyCash, Expense


class CashClosedError(Exception):
    """Касса за этот день уже закрыта."""


def is_day_closed(day: date) -> bool:
    return DailyCash.objects.filter(date=day, closed_at__isnull=False).exists()


def get_closed_shift(day: date) -> DailyCash | None:
    return DailyCash.objects.filter(date=day, closed_at__isnull=False).first()


def update_daily_cash_for_date(day: date) -> DailyCash:
    cash, _ = DailyCash.objects.get_or_create(date=day)
    if cash.closed_at:
        return cash

    paid = Order.objects.filter(status=Order.Status.PAID, paid_at__date=day)
    cash.cash_revenue = (
        paid.filter(payment_method=Order.PaymentMethod.CASH).aggregate(t=Sum("total"))["t"]
        or Decimal("0")
    )
    cash.card_revenue = (
        paid.filter(payment_method=Order.PaymentMethod.CARD).aggregate(t=Sum("total"))["t"]
        or Decimal("0")
    )
    cash.qr_revenue = (
        paid.filter(payment_method=Order.PaymentMethod.QR).aggregate(t=Sum("total"))["t"]
        or Decimal("0")
    )
    cash.takeaway_revenue = (
        paid.filter(order_type=Order.OrderType.TAKEAWAY).aggregate(t=Sum("total"))["t"]
        or Decimal("0")
    )
    cash.total_revenue = paid.aggregate(t=Sum("total"))["t"] or Decimal("0")
    cash.total_expenses = (
        Expense.objects.filter(date=day).aggregate(t=Sum("amount"))["t"] or Decimal("0")
    )
    cash.net_profit = cash.total_revenue - cash.total_expenses
    cash.save()
    return cash


def close_daily_cash(day: date, employee=None) -> DailyCash:
    cash, _ = DailyCash.objects.get_or_create(date=day)
    if cash.closed_at:
        raise CashClosedError(f"Касса за {day.strftime('%d.%m.%Y')} уже закрыта.")

    cash = update_daily_cash_for_date(day)
    cash.closed_at = timezone.now()
    cash.closed_by = employee
    cash.save(update_fields=["closed_at", "closed_by"])
    return cash


def ensure_day_open(day: date) -> None:
    if is_day_closed(day):
        raise CashClosedError(
            f"Касса за {day.strftime('%d.%m.%Y')} закрыта. Операция недоступна."
        )
