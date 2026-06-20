from .models import Order, OrderItem


def sync_order_kitchen_status(order: Order):
    """Синхронизировать статус заказа по позициям на кухне."""
    items = order.items.exclude(status=OrderItem.Status.CANCELLED)
    if not items.exists():
        return

    if items.filter(status=OrderItem.Status.COOKING).exists():
        new_status = Order.Status.COOKING
    elif not items.filter(
        status__in=[OrderItem.Status.PENDING, OrderItem.Status.COOKING]
    ).exists():
        if items.filter(status=OrderItem.Status.READY).exists():
            new_status = Order.Status.READY
        else:
            return
    elif order.status in (Order.Status.SENT, Order.Status.COOKING, Order.Status.READY):
        new_status = Order.Status.SENT
    else:
        return

    if order.status != new_status:
        order.status = new_status
        order.save(update_fields=["status"])
