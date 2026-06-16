from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils import timezone

from apps.accounts.models import Employee, Role
from apps.assistant.actions import ActionContext
from apps.assistant.parsing import (
    parse_full_booking_request,
    try_direct_booking_reply,
)
from apps.salary.models import SalarySchema
from apps.tables.models import Table, TableReservation

User = get_user_model()


@pytest.fixture
def employee(db):
    group, _ = Group.objects.get_or_create(name="Владелец-тест-booking-parse")
    role, _ = Role.objects.get_or_create(
        slug="owner",
        defaults={"name": "Владелец", "group": group},
    )
    schema, _ = SalarySchema.objects.get_or_create(
        name="Тест booking parse",
        defaults={"percent_of_revenue": 0, "fixed_per_shift": 0, "fixed_monthly": 0},
    )
    user = User.objects.create_user("booking_parse_user", password="x")
    return Employee.objects.create(
        user=user,
        role=role,
        hired_date=timezone.localdate(),
        salary_schema=schema,
    )


def test_parse_full_booking_request():
    req = parse_full_booking_request(
        "Забронируйте кабинку 10 на 14 июня в 18:00, Иван, +996509055056"
    )
    assert req is not None
    assert req.table_number == 10
    assert req.day.month == 6
    assert req.day.day == 14
    assert req.time_str == "18:00"
    assert req.guest_name == "Иван"
    assert "996509055056" in req.guest_phone.replace(" ", "")


@pytest.mark.django_db
def test_direct_booking_creates_in_database(employee):
    Table.objects.create(number=10, capacity=4, type=Table.TableType.BOOTH)
    day = (timezone.now() + timedelta(days=10)).date()
    month_name = {
        1: "января", 2: "февраля", 3: "марта", 4: "апреля", 5: "мая", 6: "июня",
        7: "июля", 8: "августа", 9: "сентября", 10: "октября", 11: "ноября", 12: "декабря",
    }[day.month]
    msg = (
        f"Забронируйте кабинку 10 на {day.day} {month_name} в 18:00, "
        "Иван, +996509055056"
    )
    ctx = ActionContext(channel="web_test", external_user_id="99")
    reply = try_direct_booking_reply(msg, [], ctx)
    assert reply is not None
    assert "оформлена" in reply.lower()
    assert TableReservation.objects.filter(
        table__number=10,
        guest_name="Иван",
        status=TableReservation.Status.ACTIVE,
    ).exists()


@pytest.mark.django_db
def test_confirmation_from_history_creates_booking(employee):
    Table.objects.create(number=10, capacity=4)
    day = (timezone.now() + timedelta(days=11)).date()
    history = [
        {
            "role": "user",
            "content": (
                f"Забронируйте кабинку 10 на {day.strftime('%d.%m.%Y')} "
                "в 18:00, Иван, +996509055056"
            ),
        },
        {
            "role": "assistant",
            "content": f"Да, кабинка №10 свободна {day.strftime('%d.%m.%Y')} в 18:00.",
        },
    ]
    ctx = ActionContext(channel="web_test", external_user_id="100")
    reply = try_direct_booking_reply("Забронируйте", history, ctx)
    assert reply is not None
    assert TableReservation.objects.filter(table__number=10).exists()
