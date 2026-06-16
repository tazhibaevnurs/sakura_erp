"""Календарный приём заказов: день → время → стол."""
from calendar import Calendar, monthrange
from datetime import date, datetime, time, timedelta

from django.utils import timezone

from .models import Table, TableReservation
from .reservation_time import DEFAULT_DURATION, conflicting_reservations
from .services import intervals_contain_now


def _day_bounds(day: date):
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(day, time.min), tz)
    end = start + timedelta(days=1)
    return start, end


def reservations_for_date(day: date):
    start, end = _day_bounds(day)
    return (
        TableReservation.objects.filter(
            status=TableReservation.Status.ACTIVE,
            reserved_for__lt=end,
            reserved_until__gt=start,
        )
        .select_related("table")
        .order_by("reserved_for")
    )


def reservation_count_by_date(year: int, month: int) -> dict[date, int]:
    first = date(year, month, 1)
    _, last_day = monthrange(year, month)
    last = date(year, month, last_day)
    start, _ = _day_bounds(first)
    _, end = _day_bounds(last)
    counts: dict[date, int] = {}
    qs = (
        TableReservation.objects.filter(
            status=TableReservation.Status.ACTIVE,
            reserved_for__lt=end,
            reserved_until__gt=start,
        )
        .only("reserved_for", "reserved_until")
    )
    for reservation in qs:
        local_start = timezone.localtime(reservation.reserved_for).date()
        local_end = timezone.localtime(reservation.reserved_until).date()
        current = local_start
        while current <= local_end:
            if current.year == year and current.month == month:
                counts[current] = counts.get(current, 0) + 1
            current += timedelta(days=1)
    return counts


def build_month_grid(year: int, month: int, *, selected: date | None = None):
    """Сетка месяца для шаблона: недели из dict с ключами day, in_month, is_today, is_selected, count."""
    today = timezone.localdate()
    counts = reservation_count_by_date(year, month)
    cal = Calendar(firstweekday=0)
    weeks = []
    for week in cal.monthdatescalendar(year, month):
        row = []
        for day in week:
            row.append(
                {
                    "day": day,
                    "in_month": day.month == month,
                    "is_today": day == today,
                    "is_selected": selected == day,
                    "count": counts.get(day, 0),
                    "is_past": day < today,
                }
            )
        weeks.append(row)
    return weeks


def combine_slot(day: date, t_start, t_end=None):
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(day, t_start), tz)
    if t_end:
        end = timezone.make_aware(datetime.combine(day, t_end), tz)
        if t_end <= t_start:
            end += timedelta(days=1)
    else:
        end = start + DEFAULT_DURATION
    return start, end


def available_tables_for_slot(start, end, *, min_capacity: int | None = None):
    now = timezone.now()
    available = []
    for table in Table.objects.order_by("number"):
        if min_capacity and table.capacity < min_capacity:
            continue
        if conflicting_reservations(table, start, end).exists():
            continue
        if intervals_contain_now(start, end, now) and table.active_order:
            from .reservation_time import _preorder_reservation_for_table, is_reservation_current

            pre = _preorder_reservation_for_table(table)
            if not (pre and not is_reservation_current(pre)):
                continue
        available.append(table)
    return available


def booked_slots_json_for_date(day: date):
    slots = []
    for reservation in reservations_for_date(day):
        slots.append(
            {
                "start": reservation.reserved_for.isoformat(),
                "end": reservation.reserved_until.isoformat(),
                "guest": reservation.guest_name,
                "table": str(reservation.table.number),
            }
        )
    return slots
