from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.orders.models import Order

from .models import Table, TableReservation
from .reservation_time import (
    conflicting_reservations,
    current_reservation_for_table,
    make_slot_end,
    sync_table_reserved_status,
)


class ReservationError(Exception):
    pass


def _validate_slot(table, start, end, exclude_id=None):
    if end <= start:
        raise ReservationError("Время окончания должно быть позже начала.")

    if start < timezone.now() - timedelta(minutes=5):
        raise ReservationError("Нельзя забронировать на прошедшее время.")

    conflicts = conflicting_reservations(table, start, end, exclude_id=exclude_id)
    if conflicts.exists():
        first = conflicts.first()
        raise ReservationError(
            f"Пересечение с бронью «{first.guest_name}» "
            f"({timezone.localtime(first.reserved_for).strftime('%d.%m %H:%M')}–"
            f"{timezone.localtime(first.reserved_until).strftime('%H:%M')})."
        )

    now = timezone.now()
    if intervals_contain_now(start, end, now) and table.active_order:
        from .reservation_time import _preorder_reservation_for_table, is_reservation_current

        pre = _preorder_reservation_for_table(table)
        if not (pre and not is_reservation_current(pre)):
            raise ReservationError(
                "Сейчас по этой кабинке открыт заказ. Забронируйте на другое время."
            )


def intervals_contain_now(start, end, now):
    return start <= now < end


@transaction.atomic
def create_reservation(
    *,
    table,
    guest_name,
    guest_phone,
    guest_count,
    reserved_for,
    reserved_until,
    comment,
    employee,
):
    end = make_slot_end(reserved_for, reserved_until)
    _validate_slot(table, reserved_for, end)

    reservation = TableReservation.objects.create(
        table=table,
        guest_name=guest_name,
        guest_phone=guest_phone or "",
        guest_count=guest_count,
        reserved_for=reserved_for,
        reserved_until=end,
        comment=comment or "",
        created_by=employee,
        status=TableReservation.Status.ACTIVE,
    )
    sync_table_reserved_status(table)
    return reservation


@transaction.atomic
def cancel_reservation(reservation):
    if reservation.status != TableReservation.Status.ACTIVE:
        raise ReservationError("Бронь уже закрыта.")

    table = reservation.table
    reservation.status = TableReservation.Status.CANCELLED
    reservation.save(update_fields=["status"])
    sync_table_reserved_status(table)


@transaction.atomic
def update_reservation(
    reservation,
    *,
    table=None,
    guest_count=None,
    reserved_for=None,
    reserved_until=None,
    comment=None,
):
    if reservation.status != TableReservation.Status.ACTIVE:
        raise ReservationError("Бронь уже закрыта.")

    if reservation.order_id:
        raise ReservationError(
            "У брони есть предзаказ — изменение только через администратора ресторана."
        )

    old_table = reservation.table
    new_table = table or old_table
    start = reserved_for if reserved_for is not None else reservation.reserved_for

    if reserved_for is not None:
        end = make_slot_end(reserved_for, reserved_until)
    elif reserved_until is not None:
        end = make_slot_end(reservation.reserved_for, reserved_until)
    else:
        end = reservation.reserved_until

    count = guest_count if guest_count is not None else reservation.guest_count
    if count > new_table.capacity:
        raise ReservationError(
            f"В {_table_capacity_label(new_table)} только {new_table.capacity} мест."
        )

    _validate_slot(new_table, start, end, exclude_id=reservation.pk)

    reservation.table = new_table
    reservation.guest_count = count
    reservation.reserved_for = start
    reservation.reserved_until = end
    if comment is not None:
        reservation.comment = comment
    reservation.save()

    sync_table_reserved_status(old_table)
    if new_table.pk != old_table.pk:
        sync_table_reserved_status(new_table)
    return reservation


def _table_capacity_label(table):
    return f"кабинке №{table.number}"


@transaction.atomic
def create_preorder_for_reservation(reservation, employee):
    """Создать заказ заранее: блюда на кухню до прихода гостя."""
    if reservation.status != TableReservation.Status.ACTIVE:
        raise ReservationError("Бронь уже закрыта.")

    if reservation.order_id:
        return reservation.order

    table = reservation.table
    other = (
        Order.objects.filter(table=table)
        .exclude(pk=reservation.order_id)
        .filter(
            status__in=[
                Order.Status.OPEN,
                Order.Status.SENT,
                Order.Status.COOKING,
                Order.Status.READY,
                Order.Status.SERVED,
            ]
        )
        .first()
    )
    if other:
        raise ReservationError(
            f"По кабинке уже есть заказ #{other.pk}. Откройте его или закройте перед предзаказом."
        )

    comment_parts = [
        f"Бронь: {reservation.guest_name}",
        f"Приход: {timezone.localtime(reservation.reserved_for).strftime('%d.%m %H:%M')}",
    ]
    if reservation.comment:
        comment_parts.append(reservation.comment)

    order = Order.objects.create(
        table=table,
        waiter=employee,
        guest_count=reservation.guest_count,
        comment=". ".join(comment_parts),
    )
    reservation.order = order
    reservation.save(update_fields=["order"])
    sync_table_reserved_status(table)
    return order


@transaction.atomic
def complete_reservation_arrival(reservation):
    if reservation.status != TableReservation.Status.ACTIVE:
        raise ReservationError("Бронь уже закрыта.")

    now = timezone.now()
    if now >= reservation.reserved_until:
        raise ReservationError("Время брони уже истекло.")

    has_preorder = bool(
        reservation.order_id and reservation.order.items.exists()
    )
    if not has_preorder:
        if not (reservation.reserved_for - timedelta(minutes=30) <= now):
            raise ReservationError(
                "Отметить прибытие можно не раньше чем за 30 минут до начала брони."
            )

    table = reservation.table
    reservation.status = TableReservation.Status.COMPLETED
    reservation.save(update_fields=["status"])

    if reservation.order_id:
        table.status = Table.Status.OCCUPIED
        table.save(update_fields=["status"])
    else:
        sync_table_reserved_status(table)

    return reservation.order
