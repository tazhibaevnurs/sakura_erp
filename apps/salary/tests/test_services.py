from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group, User

from apps.accounts.models import Employee, Role
from apps.salary.models import SalaryPayment, SalarySchema, Shift
from apps.salary.services import calculate_employee_salary, calculate_shift_accrual


@pytest.mark.django_db
def test_calculate_employee_salary():
    schema = SalarySchema.objects.create(
        name="Test",
        percent_of_revenue=Decimal("10"),
        fixed_per_shift=Decimal("100"),
        fixed_monthly=Decimal("3000"),
    )
    group = Group.objects.create(name="Waiter test")
    role = Role.objects.create(name="Waiter", slug="waiter_test", group=group)
    user = User.objects.create_user("waiter1", password="test")
    employee = Employee.objects.create(
        user=user,
        role=role,
        hired_date=date.today(),
        salary_schema=schema,
    )
    Shift.objects.create(
        employee=employee,
        date=date(2026, 5, 1),
        shift_type=Shift.ShiftType.WORKED,
        revenue_share_base=Decimal("10000"),
    )
    shift = Shift.objects.get(employee=employee, date=date(2026, 5, 1))
    assert calculate_shift_accrual(shift) == Decimal("1100")

    result = calculate_employee_salary(employee, date(2026, 5, 1), date(2026, 5, 31))
    assert result["worked_days"] == 1
    assert result["revenue_share"] == Decimal("1000")
    assert result["fixed_shift"] == Decimal("100")


@pytest.mark.django_db
def test_shift_accrual_after_save():
    schema = SalarySchema.objects.create(
        name="Waiter",
        percent_of_revenue=Decimal("2"),
        fixed_per_shift=Decimal("500"),
    )
    group = Group.objects.create(name="Waiter test 2")
    role = Role.objects.create(name="Waiter", slug="waiter_test2", group=group)
    user = User.objects.create_user("waiter2", password="test")
    employee = Employee.objects.create(
        user=user,
        role=role,
        hired_date=date.today(),
        salary_schema=schema,
    )
    shift = Shift.objects.create(
        employee=employee,
        date=date(2026, 5, 29),
        shift_type=Shift.ShiftType.WORKED,
        revenue_share_base=Decimal("10000"),
    )
    assert calculate_shift_accrual(shift) == Decimal("700")
