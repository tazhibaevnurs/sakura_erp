"""Проверка пересечений броней по времени."""
from datetime import datetime, timedelta

from django.utils import timezone

DEFAULT_DURATION = timedelta(hours=2)
BUFFER_BEFORE = timedelta(minutes=15)


def make_slot_end(start: datetime, end: datetime | None = None) -> datetime:
    if end is not None and end > start:
        return end
    return start + DEFAULT_DURATION


def intervals_overlap(start_a, end_a, start_b, end_b) -> bool:
    return start_a < end_b and end_a > start_b


def conflicting_reservations(table, start, end, exclude_id=None):
    from .models import TableReservation

    qs = TableReservation.objects.filter(
        table=table,
        status=TableReservation.Status.ACTIVE,
        reserved_for__lt=end,
        reserved_until__gt=start,
    )
    if exclude_id:
        qs = qs.exclude(pk=exclude_id)
    return qs


def is_reservation_current(reservation, at=None) -> bool:
    """Сейчас идёт окно брони (с небольшим запасом до начала)."""
    at = at or timezone.now()
    window_start = reservation.reserved_for - BUFFER_BEFORE
    return window_start <= at < reservation.reserved_until


def current_reservation_for_table(table, at=None):
    from .models import TableReservation

    at = at or timezone.now()
    for reservation in table.reservations.filter(status=TableReservation.Status.ACTIVE):
        if is_reservation_current(reservation, at):
            return reservation
    return None


def upcoming_reservations_for_table(table, at=None, limit=5):
    from .models import TableReservation

    at = at or timezone.now()
    return (
        table.reservations.filter(
            status=TableReservation.Status.ACTIVE,
            reserved_until__gt=at,
        )
        .order_by("reserved_for")[:limit]
    )


def _preorder_reservation_for_table(table):
    """Активная бронь с предзаказом до прихода гостя."""
    from .models import TableReservation

    if not table.active_order:
        return None
    return (
        TableReservation.objects.filter(
            table=table,
            status=TableReservation.Status.ACTIVE,
            order=table.active_order,
        )
        .select_related("order")
        .first()
    )


def sync_table_reserved_status(table):
    """Статус «Резерв» только пока идёт текущее окно брони."""
    from .models import Table

    if table.active_order:
        pre = _preorder_reservation_for_table(table)
        if pre and not is_reservation_current(pre):
            if table.status != Table.Status.RESERVED:
                table.status = Table.Status.RESERVED
                table.save(update_fields=["status"])
            return
        return
    current = current_reservation_for_table(table)
    if current and table.status != Table.Status.RESERVED:
        table.status = Table.Status.RESERVED
        table.save(update_fields=["status"])
    elif not current and table.status == Table.Status.RESERVED:
        table.status = Table.Status.FREE
        table.save(update_fields=["status"])


def floor_reservation_for_table(table, at=None):
    """Ближайшая активная бронь для карточки на схеме зала."""
    from .models import TableReservation

    at = at or timezone.now()
    current = current_reservation_for_table(table, at)
    if current:
        return current
    return (
        table.reservations.filter(
            status=TableReservation.Status.ACTIVE,
            reserved_until__gt=at,
        )
        .order_by("reserved_for")
        .first()
    )


def floor_card_style(table) -> str:
    """CSS-класс карточки: booked (будущая бронь) / booking_now (окно брони)."""
    from .models import Table

    display = effective_floor_status(table)
    if display != Table.Status.RESERVED:
        return display

    reservation = floor_reservation_for_table(table)
    if reservation and is_reservation_current(reservation):
        return "booking_now"
    return "booked"


def effective_floor_status(table) -> str:
    """Статус для отображения на схеме (с учётом времени брони)."""
    from .models import Table

    if table.active_order:
        pre = _preorder_reservation_for_table(table)
        if pre and not is_reservation_current(pre):
            return Table.Status.RESERVED
        return table.status

    if table.status in (Table.Status.OCCUPIED, Table.Status.WAITING_PAYMENT):
        return table.status

    if floor_reservation_for_table(table):
        return Table.Status.RESERVED

    if table.status == Table.Status.RESERVED:
        return Table.Status.FREE
    return table.status
