"""Разбор запросов гостя без LLM — точные ответы по столам и датам."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

from django.utils import timezone

from .actions import (
    ActionContext,
    check_table_availability,
    check_table_day_availability,
    create_table_reservation,
    looks_like_booking_confirmation,
)

MONTHS = {
    "январ": 1,
    "феврал": 2,
    "март": 3,
    "апрел": 4,
    "мая": 5,
    "май": 5,
    "июн": 6,
    "июл": 7,
    "август": 8,
    "сентябр": 9,
    "октябр": 10,
    "ноябр": 11,
    "декабр": 12,
}

AVAILABILITY_WORDS = (
    "свобод",
    "занят",
    "доступ",
    "есть место",
    "можно",
    "брон",
)


@dataclass
class AvailabilityQuery:
    table_number: int
    day: date
    time_str: str | None = None


@dataclass
class BookingRequest:
    table_number: int
    day: date
    time_str: str
    guest_name: str = ""
    guest_phone: str = ""
    guest_count: int = 2


BOOKING_CREATE_WORDS = (
    "забронир",
    "оформите брон",
    "оформ брон",
    "запишите",
    "хочу брон",
    "нужна брон",
)

ASSISTANT_SLOT_RE = re.compile(
    r"кабин(?:ка|у)?\s*№?\s*(\d{1,3}).*?(\d{2}\.\d{2}\.\d{4}).*?(?:в\s*)?(\d{1,2}:\d{2})",
    re.IGNORECASE,
)


def _resolve_year(month: int, day_num: int, explicit_year: int | None = None) -> int:
    if explicit_year:
        return explicit_year
    today = timezone.localdate()
    year = today.year
    try:
        candidate = date(year, month, day_num)
    except ValueError:
        return year
    if candidate < today:
        return year + 1
    return year


def _parse_russian_date(text: str) -> date | None:
    lowered = text.lower()
    for month_key, month_num in MONTHS.items():
        match = re.search(
            rf"(\d{{1,2}})\s+{month_key}[а-я]*(?:\s+(\d{{4}}))?",
            lowered,
        )
        if match:
            day_num = int(match.group(1))
            year = _resolve_year(
                month_num,
                day_num,
                int(match.group(2)) if match.group(2) else None,
            )
            try:
                return date(year, month_num, day_num)
            except ValueError:
                continue

    match = re.search(r"(\d{1,2})\.(\d{1,2})(?:\.(\d{2,4}))?", text)
    if match:
        day_num = int(match.group(1))
        month_num = int(match.group(2))
        year_raw = match.group(3)
        if year_raw:
            year = int(year_raw)
            if year < 100:
                year += 2000
        else:
            year = _resolve_year(month_num, day_num)
        try:
            return date(year, month_num, day_num)
        except ValueError:
            return None
    return None


def _parse_table_number(text: str) -> int | None:
    lowered = text.lower()
    patterns = (
        r"(?:кабин[а-я]*|стол[а-я]*)\s*(?:№|#|n)?\s*(\d{1,3})",
        r"(\d{1,3})\s*(?:-?я)?\s*(?:кабин[а-я]*|стол[а-я]*)",
        r"№\s*(\d{1,3})",
        r"#\s*(\d{1,3})",
    )
    for pattern in patterns:
        match = re.search(pattern, lowered)
        if match:
            return int(match.group(1))
    return None


def _parse_time(text: str) -> str | None:
    match = re.search(r"(?:в|на)\s*(\d{1,2})[:\.](\d{2})", text.lower())
    if match:
        return f"{int(match.group(1)):02d}:{match.group(2)}"
    match = re.search(r"\b(\d{1,2})[:\.](\d{2})\b", text)
    if match:
        hour = int(match.group(1))
        if 8 <= hour <= 23:
            return f"{hour:02d}:{match.group(2)}"
    return None


def _looks_like_booking_create(text: str) -> bool:
    lowered = text.lower()
    return any(word in lowered for word in BOOKING_CREATE_WORDS)


def _parse_phone(text: str) -> str:
    match = re.search(r"(\+?\d[\d\s\-()]{8,}\d)", text)
    return match.group(1).strip() if match else ""


def _parse_guest_name(text: str) -> str:
    match = re.search(
        r"(?:,\s*|^|\s)([А-ЯЁа-яA-Za-z][А-ЯЁа-яA-Za-z\s\-]{0,40}?)\s*,\s*\+?\d",
        text,
    )
    if match:
        return match.group(1).strip()
    match = re.search(
        r"забронир[а-я]*[^,]*,\s*([А-ЯЁа-яA-Za-z][А-ЯЁа-яA-Za-z\s\-]{0,40}?)\s*,",
        text,
        re.IGNORECASE,
    )
    if match:
        return match.group(1).strip()
    return ""


def _parse_guest_count(text: str) -> int | None:
    match = re.search(r"(\d{1,2})\s*(?:гост|человек|персон)", text.lower())
    if match:
        return int(match.group(1))
    return None


def parse_full_booking_request(text: str) -> BookingRequest | None:
    table_number = _parse_table_number(text)
    day = _parse_russian_date(text)
    time_str = _parse_time(text)
    if table_number is None or day is None or not time_str:
        return None
    return BookingRequest(
        table_number=table_number,
        day=day,
        time_str=time_str,
        guest_name=_parse_guest_name(text),
        guest_phone=_parse_phone(text),
        guest_count=_parse_guest_count(text) or 2,
    )


def _booking_from_assistant_text(text: str) -> BookingRequest | None:
    match = ASSISTANT_SLOT_RE.search(text)
    if not match:
        return None
    day = datetime.strptime(match.group(2), "%d.%m.%Y").date()
    hour, minute = match.group(3).split(":")
    return BookingRequest(
        table_number=int(match.group(1)),
        day=day,
        time_str=f"{int(hour):02d}:{minute}",
    )


def _booking_from_history(history: list[dict] | None) -> BookingRequest | None:
    if not history:
        return None

    name = ""
    phone = ""
    guest_count = 2
    slot: BookingRequest | None = None

    for item in reversed(history):
        text = item["content"]
        if item["role"] == "user":
            req = parse_full_booking_request(text)
            if req:
                slot = req
                if req.guest_name:
                    name = req.guest_name
                if req.guest_phone:
                    phone = req.guest_phone
                if req.guest_count:
                    guest_count = req.guest_count
            if not name:
                name = _parse_guest_name(text) or name
            if not phone:
                phone = _parse_phone(text) or phone
            count = _parse_guest_count(text)
            if count:
                guest_count = count
        elif item["role"] == "assistant" and slot is None:
            slot = _booking_from_assistant_text(text)

    if slot is None:
        return None

    return BookingRequest(
        table_number=slot.table_number,
        day=slot.day,
        time_str=slot.time_str,
        guest_name=name,
        guest_phone=phone,
        guest_count=guest_count,
    )


def _looks_like_availability_question(text: str) -> bool:
    if _looks_like_booking_create(text) and _parse_phone(text):
        return False
    lowered = text.lower()
    return any(word in lowered for word in AVAILABILITY_WORDS)


def parse_availability_query(text: str) -> AvailabilityQuery | None:
    if not _looks_like_availability_question(text):
        return None
    table_number = _parse_table_number(text)
    day = _parse_russian_date(text)
    if table_number is None or day is None:
        return None
    return AvailabilityQuery(
        table_number=table_number,
        day=day,
        time_str=_parse_time(text),
    )


def format_availability_reply(result: dict, query: AvailabilityQuery) -> str:
    table_number = result.get("table_number", query.table_number)
    if result.get("available"):
        if query.time_str:
            return (
                f"Да, кабинка №{table_number} свободна "
                f"{query.day.strftime('%d.%m.%Y')} в {query.time_str}."
            )
        slots = result.get("free_slots") or []
        if slots:
            return (
                f"Кабинка №{table_number} свободна {query.day.strftime('%d.%m.%Y')} "
                f"в слоты: {', '.join(slots)}. Уточните время для брони."
            )
        return result.get("message", f"Кабинка №{table_number} свободна.")
    if query.time_str:
        return (
            f"К сожалению, кабинка №{table_number} занята "
            f"{query.day.strftime('%d.%m.%Y')} в {query.time_str}."
        )
    return (
        f"К сожалению, кабинка №{table_number} занята "
        f"{query.day.strftime('%d.%m.%Y')} во всех проверенных слотах (10:00–20:00)."
    )


def try_direct_booking_reply(
    user_message: str,
    history: list[dict] | None,
    ctx: ActionContext | None = None,
) -> str | None:
    ctx = ctx or ActionContext()
    req = parse_full_booking_request(user_message)
    if req is None and looks_like_booking_confirmation(user_message):
        req = _booking_from_history(history)
    if req is None:
        return None

    if not req.guest_name:
        req.guest_name = ctx.guest_name
    if not req.guest_phone:
        req.guest_phone = ctx.guest_phone or _parse_phone(user_message)

    result = create_table_reservation(
        table_number=req.table_number,
        date_str=req.day.isoformat(),
        time_str=req.time_str,
        guest_name=req.guest_name,
        guest_phone=req.guest_phone,
        guest_count=req.guest_count,
        ctx=ctx,
    )
    return result.get("message")


def try_direct_availability_reply(user_message: str) -> str | None:
    if _looks_like_booking_create(user_message) and parse_full_booking_request(user_message):
        return None
    query = parse_availability_query(user_message)
    if not query:
        return None
    try:
        if query.time_str:
            result = check_table_availability(
                table_number=query.table_number,
                date_str=query.day.isoformat(),
                time_str=query.time_str,
            )
        else:
            result = check_table_day_availability(
                table_number=query.table_number,
                day=query.day,
            )
    except ValueError as exc:
        return str(exc)
    return format_availability_reply(result, query)
