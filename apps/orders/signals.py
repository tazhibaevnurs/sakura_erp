import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from apps.cash.services import update_daily_cash_for_date
from apps.tables.models import Table

from .models import Order, OrderItem

logger = logging.getLogger("chaihana.finance")


def _serialize_order_item(item: OrderItem) -> dict:
    order = item.order
    table = order.table
    return {
        "id": item.pk,
        "order_id": order.pk,
        "table_number": table.number if table else None,
        "table_type": table.get_type_display() if table else None,
        "table_capacity": table.capacity if table else None,
        "order_type": order.order_type,
        "customer_name": order.customer_name,
        "delivery_address": order.delivery_address[:40] if order.delivery_address else "",
        "waiter": str(order.waiter),
        "menu_item": item.menu_item.name,
        "quantity": str(item.quantity),
        "unit": item.menu_item.get_unit_display(),
        "note": item.note,
        "status": item.status,
        "created_at": order.created_at.isoformat(),
    }


def _notify_kitchen(item: OrderItem):
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    async_to_sync(channel_layer.group_send)(
        f"kitchen_{item.kitchen_section.slug}",
        {
            "type": "new_order_item",
            "data": _serialize_order_item(item),
        },
    )


def _order_ready_stats(order_id: int) -> tuple[int, int]:
    from django.db.models import Count, Q

    stats = (
        OrderItem.objects.filter(order_id=order_id)
        .exclude(status=OrderItem.Status.CANCELLED)
        .aggregate(
            total=Count("id"),
            ready=Count("id", filter=Q(status=OrderItem.Status.READY)),
        )
    )
    return stats["ready"] or 0, stats["total"] or 0


def _serialize_ready_notification(item: OrderItem) -> dict:
    ready_count, total_count = _order_ready_stats(item.order_id)
    return {
        "id": item.pk,
        "order_id": item.order_id,
        "menu_item": item.menu_item.name,
        "quantity": str(item.quantity),
        "unit": item.menu_item.get_unit_display(),
        "kitchen_section": item.kitchen_section.name,
        "ready_by": str(item.ready_by) if item.ready_by_id else "",
        "status_label": item.get_status_display(),
        "ready_count": ready_count,
        "total_count": total_count,
        "all_ready": ready_count > 0 and ready_count == total_count,
    }


def _notify_order_item_ready(item: OrderItem):
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    item = OrderItem.objects.select_related(
        "menu_item", "kitchen_section", "ready_by"
    ).get(pk=item.pk)
    data = _serialize_ready_notification(item)
    async_to_sync(channel_layer.group_send)(
        f"order_{item.order_id}",
        {"type": "item_ready", "data": data},
    )
    async_to_sync(channel_layer.group_send)(
        "orders_list",
        {"type": "item_ready", "data": data},
    )


@receiver(post_save, sender=OrderItem)
def order_item_post_save(sender, instance, created, **kwargs):
    if created or instance.status in (
        OrderItem.Status.PENDING,
        OrderItem.Status.COOKING,
    ):
        _notify_kitchen(instance)


@receiver(post_save, sender=Order)
def order_post_save(sender, instance, **kwargs):
    if instance.status == Order.Status.PAID and instance.paid_at:
        update_daily_cash_for_date(instance.paid_at.date())
        logger.info("Order %s paid, daily cash updated", instance.pk)
        if instance.table:
            instance.table.status = Table.Status.FREE
            instance.table.save(update_fields=["status"])
    elif instance.status in (
        Order.Status.OPEN,
        Order.Status.SENT,
        Order.Status.COOKING,
        Order.Status.READY,
        Order.Status.SERVED,
    ):
        if instance.table:
            if instance.status == Order.Status.SERVED:
                instance.table.status = Table.Status.WAITING_PAYMENT
            else:
                instance.table.status = Table.Status.OCCUPIED
            instance.table.save(update_fields=["status"])


@receiver(pre_save, sender=OrderItem)
def order_item_track_status(sender, instance, **kwargs):
    if instance.pk:
        try:
            instance._previous_status = (
                OrderItem.objects.only("status").get(pk=instance.pk).status
            )
        except OrderItem.DoesNotExist:
            instance._previous_status = None
    else:
        instance._previous_status = None


@receiver(pre_save, sender=OrderItem)
def order_item_pre_save(sender, instance, **kwargs):
    if instance.pk:
        return
    if not instance.price:
        instance.price = instance.menu_item.price
    if not instance.kitchen_section_id:
        instance.kitchen_section = instance.menu_item.category.kitchen_section


@receiver(post_save, sender=OrderItem)
def order_item_status_change(sender, instance, **kwargs):
    if instance.status == OrderItem.Status.READY and not instance.ready_at:
        OrderItem.objects.filter(pk=instance.pk).update(ready_at=timezone.now())
    prev = getattr(instance, "_previous_status", None)
    if instance.status == OrderItem.Status.READY and prev != OrderItem.Status.READY:
        _notify_order_item_ready(instance)
    instance.order.recalculate_total()
