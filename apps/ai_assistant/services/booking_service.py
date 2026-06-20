from datetime import date, datetime, time

from django.db import transaction
from django.utils import timezone

from apps.tables.models import Table
from apps.tables.reservation_time import make_slot_end
from apps.tables.services import ReservationError, create_reservation

from ..models import AIBooking, ClientProfile
from .helpers import get_assistant_employee


def parse_table_number(draft_data: dict) -> int | None:
    """Номер кабинки из черновика (table_number, table, cabin)."""
    for key in ("table_number", "table", "cabin", "booth"):
        value = draft_data.get(key)
        if value is None or value == "":
            continue
        raw = str(value).strip().lower().lstrip("№#").replace("кабинка", "").replace("стол", "").strip()
        try:
            number = int(raw.split()[0])
            return number if number > 0 else None
        except (ValueError, IndexError):
            continue
    return None


class BookingService:
    def _parse_date(self, value: str) -> date:
        value = (value or "").strip()
        for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d.%m.%y"):
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
        raise ValueError(f"Неверная дата: {value}")

    def _parse_time(self, value: str) -> time:
        value = (value or "").strip().replace(".", ":")
        for fmt in ("%H:%M", "%H:%M:%S"):
            try:
                return datetime.strptime(value, fmt).time()
            except ValueError:
                continue
        raise ValueError(f"Неверное время: {value}")

    def _make_start(self, day: date, start_time: time) -> datetime:
        return timezone.make_aware(
            datetime.combine(day, start_time),
            timezone.get_current_timezone(),
        )

    def _slot_bounds(self, date_str: str, time_str: str) -> tuple[datetime, datetime]:
        start = self._make_start(self._parse_date(date_str), self._parse_time(time_str))
        return start, make_slot_end(start, None)

    def _table_fits(
        self, table: Table, start: datetime, end: datetime, guests: int
    ) -> str | None:
        """None если кабинка подходит, иначе код причины."""
        if guests > table.capacity:
            return "capacity"
        if not table.can_reserve_at(start, end):
            return "unavailable"
        return None

    def check_availability(
        self,
        date_str: str,
        time_str: str,
        guests: int,
        *,
        table_number: int | None = None,
    ) -> bool:
        try:
            start, end = self._slot_bounds(date_str, time_str)
        except ValueError:
            return False
        guests = max(1, int(guests or 1))

        if table_number is not None:
            table = Table.objects.filter(number=table_number).first()
            if table is None:
                return False
            return self._table_fits(table, start, end, guests) is None

        for table in Table.objects.order_by("number"):
            if self._table_fits(table, start, end, guests) is None:
                return True
        return False

    def _find_table(
        self,
        date_str: str,
        time_str: str,
        guests: int,
        *,
        table_number: int | None = None,
    ) -> tuple[Table | None, str | None]:
        start, end = self._slot_bounds(date_str, time_str)
        guests = max(1, int(guests or 1))

        if table_number is not None:
            table = Table.objects.filter(number=table_number).first()
            if table is None:
                return None, "not_found"
            reason = self._table_fits(table, start, end, guests)
            if reason:
                return None, reason
            return table, None

        for table in Table.objects.order_by("number"):
            if self._table_fits(table, start, end, guests) is None:
                return table, None
        return None, "unavailable"

    @transaction.atomic
    def create_from_draft(self, client: ClientProfile, draft_data: dict):
        date_str = draft_data.get("date", "")
        time_str = draft_data.get("time", "")
        guests = int(draft_data.get("guests") or 2)
        name = (draft_data.get("name") or client.name or "").strip()
        phone = (draft_data.get("phone") or client.phone or "").strip()
        comment = (draft_data.get("comment") or "").strip()
        table_number = parse_table_number(draft_data)

        if not name:
            return {"status": "error", "message": "Укажите имя для брони."}
        if not phone:
            return {"status": "error", "message": "Укажите телефон для брони."}

        if not self.check_availability(
            date_str, time_str, guests, table_number=table_number
        ):
            if table_number is not None:
                table = Table.objects.filter(number=table_number).first()
                if table is None:
                    return {
                        "status": "error",
                        "message": f"Кабинка №{table_number} не найдена.",
                    }
                try:
                    start, end = self._slot_bounds(date_str, time_str)
                except ValueError:
                    return {"status": "error", "message": "Неверная дата или время."}
                reason = self._table_fits(table, start, end, guests)
                if reason == "capacity":
                    return {
                        "status": "error",
                        "message": (
                            f"В кабинке №{table_number} только {table.capacity} мест, "
                            f"а гостей {guests}."
                        ),
                    }
                return {
                    "status": "unavailable",
                    "message": f"Кабинка №{table_number} занята на это время.",
                }
            return {"status": "unavailable"}

        table, reason = self._find_table(
            date_str, time_str, guests, table_number=table_number
        )
        if table is None:
            if reason == "not_found" and table_number is not None:
                return {
                    "status": "error",
                    "message": f"Кабинка №{table_number} не найдена.",
                }
            return {"status": "unavailable"}

        start, end = self._slot_bounds(date_str, time_str)

        try:
            employee = get_assistant_employee()
            reservation = create_reservation(
                table=table,
                guest_name=name,
                guest_phone=phone,
                guest_count=guests,
                reserved_for=start,
                reserved_until=end,
                comment=comment,
                employee=employee,
            )
        except ReservationError as exc:
            return {"status": "error", "message": str(exc)}

        AIBooking.objects.create(client=client, erp_reservation=reservation)

        if name and not client.name:
            client.name = name
        if phone and not client.phone:
            client.phone = phone
        client.save(update_fields=["name", "phone"])

        return {
            "booking_id": reservation.pk,
            "status": "confirmed",
            "table_number": table.number,
        }
