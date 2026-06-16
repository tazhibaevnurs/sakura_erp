from datetime import date

from django.db.models import F, Sum

from apps.cash.models import DailyCash, Expense
from apps.orders.models import Order, OrderItem


def get_daily_summary(day: date) -> dict:
    from apps.cash.services import update_daily_cash_for_date

    cash = DailyCash.objects.filter(date=day).first()
    update = False
    if cash and cash.closed_at:
        pass
    elif not cash or cash.total_revenue == 0:
        cash = update_daily_cash_for_date(day)
        update = True
    else:
        cash = update_daily_cash_for_date(day)

    expenses = (
        Expense.objects.filter(date=day).aggregate(total=Sum("amount"))["total"] or 0
    )
    active_orders = Order.objects.filter(
        created_at__date=day,
        status__in=[
            Order.Status.OPEN,
            Order.Status.SENT,
            Order.Status.COOKING,
            Order.Status.READY,
            Order.Status.SERVED,
        ],
    ).count()
    top_items = (
        OrderItem.objects.filter(order__paid_at__date=day)
        .values("menu_item__name")
        .annotate(qty=Sum("quantity"), revenue=Sum(F("price") * F("quantity")))
        .order_by("-qty")[:10]
    )
    return {
        "date": day,
        "revenue": cash.total_revenue,
        "cash": cash.cash_revenue,
        "card": cash.card_revenue,
        "qr": cash.qr_revenue,
        "takeaway": cash.takeaway_revenue,
        "expenses": expenses,
        "net_profit": cash.total_revenue - expenses,
        "active_orders": active_orders,
        "top_items": list(top_items),
        "cash_updated": update,
    }


def get_period_report(date_from: date, date_to: date) -> dict:
    daily = DailyCash.objects.filter(
        date__range=(date_from, date_to),
        closed_at__isnull=False,
    )
    expenses_by_cat = (
        Expense.objects.filter(date__range=(date_from, date_to))
        .values("category__name")
        .annotate(total=Sum("amount"))
        .order_by("-total")
    )
    return {
        "revenue_total": daily.aggregate(t=Sum("total_revenue"))["t"] or 0,
        "expenses_total": daily.aggregate(t=Sum("total_expenses"))["t"] or 0,
        "net_total": daily.aggregate(t=Sum("net_profit"))["t"] or 0,
        "daily_breakdown": list(
            daily.values("date", "total_revenue", "total_expenses", "net_profit")
        ),
        "expenses_by_category": list(expenses_by_cat),
    }
