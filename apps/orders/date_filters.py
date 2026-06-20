from datetime import date, datetime, timedelta

from django.utils import timezone


def parse_order_date_filter(value: str | None) -> tuple[date, date]:
    """Вернуть (start_date, end_date) для фильтра заказов по дню."""
    today = timezone.localdate()
    if not value or value == "today":
        return today, today
    if value == "yesterday":
        d = today - timedelta(days=1)
        return d, d
    if value == "tomorrow":
        d = today + timedelta(days=1)
        return d, d
    try:
        d = date.fromisoformat(value)
        return d, d
    except ValueError:
        return today, today


def day_datetime_bounds(day: date):
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(day, datetime.min.time()), tz)
    end = start + timedelta(days=1)
    return start, end
