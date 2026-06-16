from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils import timezone

from apps.accounts.models import Employee, Role
from apps.assistant.actions import (
    ActionContext,
    cancel_table_reservation,
    check_table_availability,
    create_table_reservation,
    execute_tool,
    looks_like_booking_confirmation,
    modify_table_reservation,
)
from apps.salary.models import SalarySchema
from apps.tables.models import Table, TableReservation

User = get_user_model()


@pytest.fixture
def employee(db):
    group, _ = Group.objects.get_or_create(name="Владелец-тест-actions")
    role, _ = Role.objects.get_or_create(
        slug="owner",
        defaults={"name": "Владелец", "group": group},
    )
    schema, _ = SalarySchema.objects.get_or_create(
        name="Тест actions",
        defaults={"percent_of_revenue": 0, "fixed_per_shift": 0, "fixed_monthly": 0},
    )
    user = User.objects.create_user("actions_user", password="x")
    return Employee.objects.create(
        user=user,
        role=role,
        hired_date=timezone.localdate(),
        salary_schema=schema,
    )


@pytest.mark.django_db
def test_check_table_availability_free(employee):
    table = Table.objects.create(number=91, capacity=6, type=Table.TableType.BOOTH)
    day = (timezone.now() + timedelta(days=3)).date()
    result = check_table_availability(
        table_number=91,
        date_str=day.isoformat(),
        time_str="18:00",
    )
    assert result["available"] is True
    assert result["table_number"] == 91


@pytest.mark.django_db
def test_create_table_reservation_success(employee):
    table = Table.objects.create(number=92, capacity=4)
    day = (timezone.now() + timedelta(days=4)).date()
    ctx = ActionContext(channel="web_test", guest_phone="+996500000000")
    result = create_table_reservation(
        table_number=92,
        date_str=day.isoformat(),
        time_str="19:00",
        guest_name="Тест Гость",
        guest_count=2,
        ctx=ctx,
    )
    assert result["success"] is True
    assert TableReservation.objects.filter(table=table, guest_name="Тест Гость").exists()


@pytest.mark.django_db
def test_execute_tool_requires_name():
    day = (timezone.now() + timedelta(days=5)).date()
    result = execute_tool(
        "create_table_reservation",
        {
            "table_number": 1,
            "date": day.isoformat(),
            "time": "18:00",
            "guest_name": "",
        },
    )
    assert result["success"] is False
    assert result["needs"] == "guest_name"


@pytest.mark.django_db
def test_cancel_and_modify_reservation(employee):
    table_a = Table.objects.create(number=93, capacity=4)
    table_b = Table.objects.create(number=94, capacity=4)
    day = (timezone.now() + timedelta(days=6)).date()
    phone = "+996700111222"
    ctx = ActionContext(channel="whatsapp", guest_phone=phone, external_user_id=phone)

    created = create_table_reservation(
        table_number=93,
        date_str=day.isoformat(),
        time_str="18:00",
        guest_name="Айгуль",
        guest_phone=phone,
        ctx=ctx,
    )
    reservation_id = created["reservation_id"]

    modified = modify_table_reservation(
        reservation_id=reservation_id,
        guest_phone=phone,
        new_table_number=94,
        ctx=ctx,
    )
    assert modified["success"] is True
    assert modified["table_number"] == 94

    cancelled = cancel_table_reservation(
        reservation_id=reservation_id,
        guest_phone=phone,
        ctx=ctx,
    )
    assert cancelled["success"] is True
    assert (
        TableReservation.objects.get(pk=reservation_id).status
        == TableReservation.Status.CANCELLED
    )


def test_looks_like_booking_confirmation():
    assert looks_like_booking_confirmation("Бронируйте")
    assert looks_like_booking_confirmation("да, подтверждаю")
    assert not looks_like_booking_confirmation("какое меню?")
