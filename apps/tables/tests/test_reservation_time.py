from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import Employee, Role
from apps.salary.models import SalarySchema
from apps.tables.models import Table, TableReservation
from apps.tables.reservation_time import (
    conflicting_reservations,
    effective_floor_status,
    floor_card_style,
    intervals_overlap,
)
from apps.tables.services import ReservationError, create_reservation
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

User = get_user_model()


@pytest.mark.django_db
def test_intervals_overlap():
    a_start = timezone.now()
    a_end = a_start + timedelta(hours=2)
    b_start = a_start + timedelta(hours=1)
    b_end = b_start + timedelta(hours=2)
    assert intervals_overlap(a_start, a_end, b_start, b_end)
    assert not intervals_overlap(
        a_start,
        a_start + timedelta(hours=1),
        a_start + timedelta(hours=2),
        a_start + timedelta(hours=3),
    )


@pytest.mark.django_db
def test_multiple_reservations_same_table_different_times():
    group, _ = Group.objects.get_or_create(name="Владелец-тест")
    role, _ = Role.objects.get_or_create(
        slug="owner",
        defaults={"name": "Владелец", "group": group},
    )
    schema, _ = SalarySchema.objects.get_or_create(
        name="Тест",
        defaults={"percent_of_revenue": 0, "fixed_per_shift": 0, "fixed_monthly": 0},
    )
    user = User.objects.create_user("ruser", password="x")
    emp = Employee.objects.create(
        user=user,
        role=role,
        hired_date=timezone.localdate(),
        salary_schema=schema,
    )
    table = Table.objects.create(number=50, capacity=6)

    base = timezone.now() + timedelta(days=1)
    base = base.replace(hour=12, minute=0, second=0, microsecond=0)
    create_reservation(
        table=table,
        guest_name="Утро",
        guest_phone="",
        guest_count=2,
        reserved_for=base,
        reserved_until=base + timedelta(hours=2),
        comment="",
        employee=emp,
    )
    create_reservation(
        table=table,
        guest_name="Вечер",
        guest_phone="",
        guest_count=4,
        reserved_for=base + timedelta(hours=4),
        reserved_until=base + timedelta(hours=6),
        comment="",
        employee=emp,
    )
    assert TableReservation.objects.filter(table=table, status="active").count() == 2

    with pytest.raises(ReservationError):
        create_reservation(
            table=table,
            guest_name="Конфликт",
            guest_phone="",
            guest_count=2,
            reserved_for=base + timedelta(hours=1),
            reserved_until=base + timedelta(hours=3),
            comment="",
            employee=emp,
        )

    assert conflicting_reservations(
        table,
        base + timedelta(hours=1),
        base + timedelta(hours=3),
    ).count() == 1


@pytest.mark.django_db
def test_future_reservation_shows_reserved_on_floor():
    group, _ = Group.objects.get_or_create(name="Владелец-тест-floor")
    role, _ = Role.objects.get_or_create(
        slug="owner",
        defaults={"name": "Владелец", "group": group},
    )
    schema, _ = SalarySchema.objects.get_or_create(
        name="Тест floor",
        defaults={"percent_of_revenue": 0, "fixed_per_shift": 0, "fixed_monthly": 0},
    )
    user = User.objects.create_user("floor_user", password="x")
    emp = Employee.objects.create(
        user=user,
        role=role,
        hired_date=timezone.localdate(),
        salary_schema=schema,
    )
    table = Table.objects.create(number=51, capacity=4, status=Table.Status.FREE)
    start = timezone.now() + timedelta(days=3)
    start = start.replace(hour=18, minute=0, second=0, microsecond=0)
    create_reservation(
        table=table,
        guest_name="Иван",
        guest_phone="+996500000001",
        guest_count=2,
        reserved_for=start,
        reserved_until=start + timedelta(hours=2),
        comment="",
        employee=emp,
    )
    table.refresh_from_db()
    assert table.status == Table.Status.FREE
    assert effective_floor_status(table) == Table.Status.RESERVED
    assert floor_card_style(table) == "booked"


@pytest.mark.django_db
def test_current_reservation_uses_booking_now_style():
    group, _ = Group.objects.get_or_create(name="Владелец-тест-now")
    role, _ = Role.objects.get_or_create(
        slug="owner",
        defaults={"name": "Владелец", "group": group},
    )
    schema, _ = SalarySchema.objects.get_or_create(
        name="Тест now",
        defaults={"percent_of_revenue": 0, "fixed_per_shift": 0, "fixed_monthly": 0},
    )
    user = User.objects.create_user("now_user", password="x")
    emp = Employee.objects.create(
        user=user,
        role=role,
        hired_date=timezone.localdate(),
        salary_schema=schema,
    )
    table = Table.objects.create(number=52, capacity=4)
    start = timezone.now() + timedelta(minutes=10)
    start = start.replace(second=0, microsecond=0)
    create_reservation(
        table=table,
        guest_name="Сейчас",
        guest_phone="",
        guest_count=2,
        reserved_for=start,
        reserved_until=start + timedelta(hours=2),
        comment="",
        employee=emp,
    )
    assert floor_card_style(table) == "booking_now"
