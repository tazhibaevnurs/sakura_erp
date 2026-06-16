"""Действия ассистента в ERP: бронирование, заказы."""
from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.accounts.models import Employee, Role
from apps.menu.models import MenuItem
from apps.orders.models import Order
from apps.orders.services import (
    OrderServiceError,
    create_guest_order as create_guest_order_service,
    resolve_order_lines,
)

from .language import format_localized_order_summary
from apps.salary.models import SalarySchema
from apps.tables.models import Table, TableReservation
from apps.tables.reservation_time import make_slot_end
from apps.tables.services import (
    ReservationError,
    cancel_reservation,
    create_reservation,
    update_reservation,
)

User = get_user_model()

ASSISTANT_USERNAME = "ai_assistant"


class ActionContext:
    def __init__(
        self,
        *,
        channel: str = "",
        external_user_id: str = "",
        guest_phone: str = "",
        guest_name: str = "",
        language: str = "ru",
    ):
        self.channel = channel
        self.external_user_id = external_user_id
        self.guest_phone = guest_phone.strip()
        self.guest_name = guest_name.strip()
        self.language = language if language in ("ru", "ky") else "ru"


def get_assistant_employee() -> Employee:
    user, _ = User.objects.get_or_create(
        username=ASSISTANT_USERNAME,
        defaults={
            "is_active": True,
            "first_name": "ИИ-ассистент",
        },
    )
    if hasattr(user, "employee"):
        return user.employee

    role = Role.objects.filter(slug="owner").first()
    if role is None:
        raise ReservationError("Не настроена роль владельца для броней ассистента.")

    schema = SalarySchema.objects.order_by("pk").first()
    if schema is None:
        schema = SalarySchema.objects.create(
            name="По умолчанию",
            percent_of_revenue=0,
            fixed_per_shift=0,
            fixed_monthly=0,
        )

    return Employee.objects.create(
        user=user,
        role=role,
        hired_date=timezone.localdate(),
        salary_schema=schema,
    )


def _parse_date(value: str) -> date:
    value = (value or "").strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d.%m.%y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Неверная дата: {value}")


def _parse_time(value: str) -> time:
    value = (value or "").strip().replace(".", ":")
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(value, fmt).time()
        except ValueError:
            continue
    raise ValueError(f"Неверное время: {value}")


def _make_start(day: date, start_time: time) -> datetime:
    return timezone.make_aware(
        datetime.combine(day, start_time),
        timezone.get_current_timezone(),
    )


def _get_table(table_number: int) -> Table:
    try:
        return Table.objects.get(number=int(table_number))
    except (Table.DoesNotExist, TypeError, ValueError) as exc:
        raise ValueError(f"Стол/кабинка №{table_number} не найдена.") from exc


def _table_label(table: Table) -> str:
    return f"{table.get_type_display()} №{table.number}"


def _normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    return digits[-9:] if len(digits) >= 9 else digits


def _phones_match(stored: str, provided: str) -> bool:
    a = _normalize_phone(stored)
    b = _normalize_phone(provided)
    if not a or not b:
        return False
    return a == b or a.endswith(b) or b.endswith(a)


def _resolve_guest_phone(
    guest_phone: str = "",
    ctx: ActionContext | None = None,
) -> str:
    ctx = ctx or ActionContext()
    phone = (guest_phone or ctx.guest_phone or "").strip()
    if not phone and ctx.channel == "whatsapp":
        phone = ctx.external_user_id
    if not phone and ctx.channel == "web_test" and ctx.external_user_id:
        phone = f"web-test-{ctx.external_user_id}"
    return phone


def _get_active_reservation(
    reservation_id: int,
    guest_phone: str = "",
    ctx: ActionContext | None = None,
) -> TableReservation | dict:
    ctx = ctx or ActionContext()
    phone = _resolve_guest_phone(guest_phone, ctx)
    if not phone:
        return {
            "success": False,
            "needs": "guest_phone",
            "message": "Укажите телефон для подтверждения брони.",
        }
    try:
        reservation = TableReservation.objects.select_related("table").get(
            pk=int(reservation_id)
        )
    except (TableReservation.DoesNotExist, TypeError, ValueError):
        return {
            "success": False,
            "message": f"Бронь №{reservation_id} не найдена.",
        }
    if reservation.status != TableReservation.Status.ACTIVE:
        return {"success": False, "message": "Бронь уже отменена или завершена."}
    if not _phones_match(reservation.guest_phone, phone):
        return {
            "success": False,
            "message": "Телефон не совпадает с бронью. Проверьте номер брони и телефон.",
        }
    return reservation


def _format_slot(start: datetime, end: datetime) -> str:
    local_start = timezone.localtime(start)
    local_end = timezone.localtime(end)
    return (
        f"{local_start.strftime('%d.%m.%Y %H:%M')}–{local_end.strftime('%H:%M')}"
    )


def check_table_day_availability(*, table_number: int, day: date) -> dict:
    """Свободные 2-часовые слоты за день (10:00–20:00)."""
    table = _get_table(table_number)
    free_slots = []
    now = timezone.now()

    for hour in range(10, 22, 2):
        start = _make_start(day, time(hour, 0))
        end = make_slot_end(start, None)
        if start < now - timedelta(minutes=5):
            continue
        if table.can_reserve_at(start, end):
            free_slots.append(f"{hour:02d}:00")

    if free_slots:
        return {
            "available": True,
            "table_number": table.number,
            "table_type": table.get_type_display(),
            "free_slots": free_slots,
            "date": day.isoformat(),
            "message": (
                f"{_table_label(table)} свободна {day.strftime('%d.%m.%Y')} "
                f"в: {', '.join(free_slots)}."
            ),
        }

    return {
        "available": False,
        "table_number": table.number,
        "table_type": table.get_type_display(),
        "free_slots": [],
        "date": day.isoformat(),
        "message": (
            f"{_table_label(table)} занята {day.strftime('%d.%m.%Y')} "
            "во всех проверенных слотах."
        ),
    }


def check_table_availability(
    *,
    table_number: int,
    date_str: str,
    time_str: str,
    guest_count: int | None = None,
) -> dict:
    table = _get_table(table_number)
    start = _make_start(_parse_date(date_str), _parse_time(time_str))
    end = make_slot_end(start, None)

    if guest_count and guest_count > table.capacity:
        return {
            "available": False,
            "table_number": table.number,
            "table_type": table.get_type_display(),
            "message": (
                f"{_table_label(table)} вмещает {table.capacity} гостей, "
                f"а указано {guest_count}."
            ),
        }

    if table.can_reserve_at(start, end):
        return {
            "available": True,
            "table_number": table.number,
            "table_type": table.get_type_display(),
            "capacity": table.capacity,
            "slot": _format_slot(start, end),
            "message": (
                f"{_table_label(table)} свободна {_format_slot(start, end)}."
            ),
        }

    return {
        "available": False,
        "table_number": table.number,
        "table_type": table.get_type_display(),
        "message": f"{_table_label(table)} занята или недоступна на это время.",
    }


def find_available_tables(
    *,
    date_str: str,
    time_str: str,
    guest_count: int | None = None,
    table_type: str | None = None,
) -> dict:
    start = _make_start(_parse_date(date_str), _parse_time(time_str))
    end = make_slot_end(start, None)
    tables = Table.objects.order_by("number")

    type_map = {
        "кабинка": Table.TableType.BOOTH,
        "booth": Table.TableType.BOOTH,
        "стол": Table.TableType.TABLE,
        "table": Table.TableType.TABLE,
        "улица": Table.TableType.OUTDOOR,
        "outdoor": Table.TableType.OUTDOOR,
    }
    if table_type:
        key = table_type.strip().lower()
        if key in type_map:
            tables = tables.filter(type=type_map[key])

    available = []
    for table in tables:
        if guest_count and guest_count > table.capacity:
            continue
        if table.can_reserve_at(start, end):
            available.append(
                {
                    "number": table.number,
                    "type": table.get_type_display(),
                    "capacity": table.capacity,
                }
            )

    return {
        "date": date_str,
        "time": time_str,
        "slot": _format_slot(start, end),
        "count": len(available),
        "tables": available[:12],
        "message": (
            f"Свободно {len(available)} мест на {_format_slot(start, end)}."
            if available
            else f"На {_format_slot(start, end)} свободных столов нет."
        ),
    }


def create_table_reservation(
    *,
    table_number: int,
    date_str: str,
    time_str: str,
    guest_name: str,
    guest_phone: str = "",
    guest_count: int = 2,
    comment: str = "",
    ctx: ActionContext | None = None,
) -> dict:
    ctx = ctx or ActionContext()
    name = (guest_name or ctx.guest_name or "").strip()
    phone = (guest_phone or ctx.guest_phone or "").strip()

    if not name:
        return {
            "success": False,
            "needs": "guest_name",
            "message": "Укажите имя для брони.",
        }
    if not phone and ctx.channel == "whatsapp":
        phone = ctx.guest_phone or ctx.external_user_id
    if not phone and ctx.channel == "web_test" and ctx.external_user_id:
        phone = f"web-test-{ctx.external_user_id}"
    if not phone:
        return {
            "success": False,
            "needs": "guest_phone",
            "message": "Укажите телефон для подтверждения брони.",
        }

    table = _get_table(table_number)
    start = _make_start(_parse_date(date_str), _parse_time(time_str))
    end = make_slot_end(start, None)

    if guest_count > table.capacity:
        return {
            "success": False,
            "message": (
                f"В {_table_label(table)} только {table.capacity} мест. "
                "Уменьшите число гостей или выберите другой стол."
            ),
        }

    if not table.can_reserve_at(start, end):
        return {
            "success": False,
            "message": (
                f"{_table_label(table)} уже занята на {_format_slot(start, end)}. "
                "Предложите другое время или стол."
            ),
        }

    try:
        reservation = create_reservation(
            table=table,
            guest_name=name,
            guest_phone=phone,
            guest_count=max(1, int(guest_count)),
            reserved_for=start,
            reserved_until=end,
            comment=(comment or "").strip() or f"Бронь через {ctx.channel or 'ассистент'}",
            employee=get_assistant_employee(),
        )
    except ReservationError as exc:
        return {"success": False, "message": str(exc)}
    except ValueError as exc:
        return {"success": False, "message": str(exc)}

    return {
        "success": True,
        "reservation_id": reservation.pk,
        "table_number": table.number,
        "table_type": table.get_type_display(),
        "guest_name": name,
        "guest_phone": phone,
        "guest_count": reservation.guest_count,
        "slot": _format_slot(reservation.reserved_for, reservation.reserved_until),
        "message": (
            f"Бронь №{reservation.pk} оформлена: {_table_label(table)}, "
            f"{_format_slot(reservation.reserved_for, reservation.reserved_until)}, "
            f"гостей {reservation.guest_count}, {name}, {phone}."
        ),
    }


def find_guest_reservations(
    *,
    guest_phone: str = "",
    guest_name: str = "",
    ctx: ActionContext | None = None,
) -> dict:
    ctx = ctx or ActionContext()
    phone = _resolve_guest_phone(guest_phone, ctx)
    if not phone:
        return {
            "success": False,
            "needs": "guest_phone",
            "message": "Укажите телефон, чтобы найти ваши брони.",
        }

    qs = TableReservation.objects.filter(
        status=TableReservation.Status.ACTIVE,
        reserved_until__gte=timezone.now(),
    ).select_related("table")

    matches = []
    for reservation in qs.order_by("reserved_for")[:50]:
        if not _phones_match(reservation.guest_phone, phone):
            continue
        if guest_name and guest_name.strip().lower() not in reservation.guest_name.lower():
            continue
        matches.append(
            {
                "reservation_id": reservation.pk,
                "table_number": reservation.table.number,
                "table_type": reservation.table.get_type_display(),
                "guest_count": reservation.guest_count,
                "slot": _format_slot(reservation.reserved_for, reservation.reserved_until),
            }
        )

    if not matches:
        return {
            "success": True,
            "count": 0,
            "reservations": [],
            "message": "Активных броней по этому телефону не найдено.",
        }

    return {
        "success": True,
        "count": len(matches),
        "reservations": matches[:10],
        "message": f"Найдено броней: {len(matches)}.",
    }


def cancel_table_reservation(
    *,
    reservation_id: int,
    guest_phone: str = "",
    ctx: ActionContext | None = None,
) -> dict:
    ctx = ctx or ActionContext()
    found = _get_active_reservation(reservation_id, guest_phone, ctx)
    if isinstance(found, dict):
        return found

    try:
        cancel_reservation(found)
    except ReservationError as exc:
        return {"success": False, "message": str(exc)}

    return {
        "success": True,
        "reservation_id": found.pk,
        "message": (
            f"Бронь №{found.pk} отменена: {_table_label(found.table)}, "
            f"{_format_slot(found.reserved_for, found.reserved_until)}."
        ),
    }


def modify_table_reservation(
    *,
    reservation_id: int,
    guest_phone: str = "",
    new_table_number: int | None = None,
    new_date: str = "",
    new_time: str = "",
    guest_count: int | None = None,
    ctx: ActionContext | None = None,
) -> dict:
    ctx = ctx or ActionContext()
    found = _get_active_reservation(reservation_id, guest_phone, ctx)
    if isinstance(found, dict):
        return found

    new_table = None
    if new_table_number is not None:
        new_table = _get_table(new_table_number)

    reserved_for = found.reserved_for
    reserved_until = found.reserved_until
    if new_date and new_time:
        reserved_for = _make_start(_parse_date(new_date), _parse_time(new_time))
        reserved_until = make_slot_end(reserved_for, None)
    elif new_date or new_time:
        return {
            "success": False,
            "message": "Для переноса укажите и дату, и время.",
        }

    if (
        new_table is None
        and guest_count is None
        and new_date == ""
        and new_time == ""
    ):
        return {
            "success": False,
            "message": "Укажите, что изменить: кабинку, дату/время или число гостей.",
        }

    try:
        reservation = update_reservation(
            found,
            table=new_table,
            guest_count=guest_count,
            reserved_for=reserved_for if (new_date and new_time) else None,
            reserved_until=reserved_until if (new_date and new_time) else None,
        )
    except ReservationError as exc:
        return {"success": False, "message": str(exc)}
    except ValueError as exc:
        return {"success": False, "message": str(exc)}

    table = reservation.table
    return {
        "success": True,
        "reservation_id": reservation.pk,
        "table_number": table.number,
        "table_type": table.get_type_display(),
        "guest_count": reservation.guest_count,
        "slot": _format_slot(reservation.reserved_for, reservation.reserved_until),
        "message": (
            f"Бронь №{reservation.pk} изменена: {_table_label(table)}, "
            f"{_format_slot(reservation.reserved_for, reservation.reserved_until)}, "
            f"гостей {reservation.guest_count}."
        ),
    }


def search_menu_items(*, query: str) -> dict:
    query = (query or "").strip()
    if not query:
        return {"success": False, "message": "Укажите название блюда для поиска."}

    items = list(MenuItem.objects.filter(is_available=True).order_by("name"))
    lowered = query.lower()
    matches = []
    for item in items:
        name_lower = item.name.lower()
        if lowered in name_lower or name_lower in lowered:
            price = int(item.price) if item.price == int(item.price) else item.price
            matches.append(
                {
                    "id": item.pk,
                    "name": item.name,
                    "price": str(price),
                    "category": item.category.name,
                }
            )

    if not matches:
        return {
            "success": True,
            "count": 0,
            "items": [],
            "message": f"Блюда по запросу «{query}» не найдены.",
        }

    return {
        "success": True,
        "count": len(matches),
        "items": matches[:8],
        "message": f"Найдено блюд: {len(matches)}.",
    }


def update_guest_order_draft(
    *,
    order_type: str = "",
    items: list[dict] | None = None,
    customer_name: str = "",
    customer_phone: str = "",
    delivery_address: str = "",
    ctx: ActionContext | None = None,
) -> dict:
    from .order_draft_sync import _compute_step
    from .order_flow import load_pending_order, save_pending_order

    ctx = ctx or ActionContext()
    pending = load_pending_order(ctx) or {
        "step": "awaiting_type",
        "items": [],
        "language": ctx.language,
        "order_type": "",
        "customer_name": "",
        "customer_phone": "",
        "delivery_address": "",
    }

    if order_type:
        pending["order_type"] = order_type.strip().lower()
    if items:
        from .menu_items import merge_pending_items
        from .order_parsing import ParsedOrderLine

        parsed = [
            ParsedOrderLine(name=i.get("name", ""), quantity=int(i.get("quantity", 1) or 1))
            for i in items
            if i.get("name")
        ]
        if parsed:
            pending["items"] = merge_pending_items(pending.get("items", []), parsed)
    if customer_name:
        pending["customer_name"] = customer_name.strip()
    if customer_phone:
        pending["customer_phone"] = customer_phone.strip()
    if delivery_address:
        pending["delivery_address"] = delivery_address.strip()

    pending["step"] = _compute_step(pending)
    pending["language"] = ctx.language
    save_pending_order(ctx, pending)

    missing = []
    if not pending.get("items"):
        missing.append("items")
    if not pending.get("order_type"):
        missing.append("order_type")
    if not pending.get("customer_name"):
        missing.append("customer_name")
    if not pending.get("customer_phone"):
        missing.append("customer_phone")
    if pending.get("order_type") == "delivery" and not pending.get("delivery_address"):
        missing.append("delivery_address")

    return {
        "success": True,
        "step": pending["step"],
        "missing": missing,
        "draft": pending,
        "message": "Черновик заказа сохранён.",
    }


def create_guest_order(
    *,
    order_type: str,
    items: list[dict],
    customer_name: str = "",
    customer_phone: str = "",
    delivery_address: str = "",
    table_number: int | None = None,
    guest_count: int = 1,
    comment: str = "",
    ctx: ActionContext | None = None,
) -> dict:
    ctx = ctx or ActionContext()
    name = (customer_name or "").strip()
    phone = (customer_phone or ctx.guest_phone or "").strip()

    if not phone and ctx.channel == "whatsapp":
        phone = ctx.guest_phone or ctx.external_user_id
    if not phone and ctx.channel == "web_test" and ctx.external_user_id:
        phone = f"web-test-{ctx.external_user_id}"

    order_type = (order_type or "takeaway").strip().lower()
    type_map = {
        "доставка": Order.OrderType.DELIVERY,
        "delivery": Order.OrderType.DELIVERY,
        "навынос": Order.OrderType.TAKEAWAY,
        "takeaway": Order.OrderType.TAKEAWAY,
        "в зале": Order.OrderType.DINE_IN,
        "dine_in": Order.OrderType.DINE_IN,
    }
    normalized_type = type_map.get(order_type, order_type)

    if normalized_type == Order.OrderType.DELIVERY:
        if not name:
            return {
                "success": False,
                "needs": "customer_name",
                "message": "Для доставки укажите имя.",
            }
        if not phone:
            return {
                "success": False,
                "needs": "customer_phone",
                "message": "Для доставки укажите телефон.",
            }
        if not (delivery_address or "").strip():
            return {
                "success": False,
                "needs": "delivery_address",
                "message": "Для доставки укажите адрес.",
            }

    table = None
    if table_number is not None:
        try:
            table = _get_table(int(table_number))
        except ValueError as exc:
            return {"success": False, "message": str(exc)}

    resolved, errors = resolve_order_lines(items)
    if errors:
        return {"success": False, "message": " ".join(errors)}
    if not resolved:
        return {
            "success": False,
            "message": "Укажите блюда из меню (название и количество).",
        }

    try:
        order = create_guest_order_service(
            get_assistant_employee(),
            order_type=normalized_type,
            items=items,
            customer_name=name,
            customer_phone=phone,
            delivery_address=(delivery_address or "").strip(),
            table=table,
            guest_count=guest_count,
            comment=(comment or "").strip()
            or f"Заказ через {ctx.channel or 'ассистент'}",
            send_to_kitchen=True,
        )
    except OrderServiceError as exc:
        return {"success": False, "message": str(exc)}

    return {
        "success": True,
        "order_id": order.pk,
        "order_type": order.order_type,
        "total": str(order.total),
        "message": format_localized_order_summary(order, ctx.language),
    }


def execute_tool(name: str, args: dict, ctx: ActionContext | None = None) -> dict:
    ctx = ctx or ActionContext()
    try:
        if name == "check_table_availability":
            time_str = (args.get("time") or "").strip()
            date_str = args.get("date", "")
            table_number = args.get("table_number")
            if time_str:
                return check_table_availability(
                    table_number=table_number,
                    date_str=date_str,
                    time_str=time_str,
                    guest_count=args.get("guest_count"),
                )
            return check_table_day_availability(
                table_number=table_number,
                day=_parse_date(date_str),
            )
        if name == "find_available_tables":
            return find_available_tables(
                date_str=args.get("date", ""),
                time_str=args.get("time", ""),
                guest_count=args.get("guest_count"),
                table_type=args.get("table_type"),
            )
        if name == "create_table_reservation":
            return create_table_reservation(
                table_number=args.get("table_number"),
                date_str=args.get("date", ""),
                time_str=args.get("time", ""),
                guest_name=args.get("guest_name", ""),
                guest_phone=args.get("guest_phone", ""),
                guest_count=args.get("guest_count", 2),
                comment=args.get("comment", ""),
                ctx=ctx,
            )
        if name == "find_guest_reservations":
            return find_guest_reservations(
                guest_phone=args.get("guest_phone", ""),
                guest_name=args.get("guest_name", ""),
                ctx=ctx,
            )
        if name == "cancel_table_reservation":
            return cancel_table_reservation(
                reservation_id=args.get("reservation_id"),
                guest_phone=args.get("guest_phone", ""),
                ctx=ctx,
            )
        if name == "modify_table_reservation":
            new_table = args.get("new_table_number")
            if new_table is not None:
                new_table = int(new_table)
            guest_count = args.get("guest_count")
            if guest_count is not None:
                guest_count = int(guest_count)
            return modify_table_reservation(
                reservation_id=args.get("reservation_id"),
                guest_phone=args.get("guest_phone", ""),
                new_table_number=new_table,
                new_date=args.get("new_date", ""),
                new_time=args.get("new_time", ""),
                guest_count=guest_count,
                ctx=ctx,
            )
        if name == "search_menu_items":
            return search_menu_items(query=args.get("query", ""))
        if name == "update_guest_order_draft":
            return update_guest_order_draft(
                order_type=args.get("order_type", ""),
                items=args.get("items") or [],
                customer_name=args.get("customer_name", ""),
                customer_phone=args.get("customer_phone", ""),
                delivery_address=args.get("delivery_address", ""),
                ctx=ctx,
            )
        if name == "create_guest_order":
            table_number = args.get("table_number")
            if table_number is not None:
                table_number = int(table_number)
            guest_count = args.get("guest_count", 1)
            if guest_count is not None:
                guest_count = int(guest_count)
            return create_guest_order(
                order_type=args.get("order_type", "takeaway"),
                items=args.get("items") or [],
                customer_name=args.get("customer_name", ""),
                customer_phone=args.get("customer_phone", ""),
                delivery_address=args.get("delivery_address", ""),
                table_number=table_number,
                guest_count=guest_count,
                comment=args.get("comment", ""),
                ctx=ctx,
            )
        return {"error": f"Неизвестный инструмент: {name}"}
    except (ValueError, TypeError) as exc:
        return {"success": False, "message": str(exc)}


def looks_like_booking_confirmation(text: str) -> bool:
    lowered = text.lower().strip()
    patterns = (
        r"^бронир",
        r"^да[,!.\s]",
        r"^подтверж",
        r"^оформ",
        r"^забронир",
        r"^запис",
        r"^соглас",
        r"^ок$",
        r"^окей$",
        r"^хорошо$",
        r"^давайте$",
    )
    return any(re.search(p, lowered) for p in patterns)


def looks_like_order_confirmation(text: str) -> bool:
    lowered = text.lower().strip()
    if any(
        word in lowered
        for word in ("заказ", "закаж", "оформ заказ", "подтверждаю заказ")
    ):
        return True
    patterns = (
        r"^да[,!.\s]",
        r"^подтверж",
        r"^оформ",
        r"^соглас",
        r"^ок$",
        r"^окей$",
        r"^хорошо$",
        r"^давайте$",
        r"^верно$",
    )
    return any(re.search(p, lowered) for p in patterns)
