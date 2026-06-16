import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from apps.accounts.models import Employee, Role
from apps.core.employees import ensure_employee_profile, get_acting_employee, user_effective_role
from apps.salary.models import SalarySchema

User = get_user_model()


@pytest.mark.django_db
def test_superuser_get_acting_employee_creates_profile():
    SalarySchema.objects.get_or_create(
        name="Тест",
        defaults={"percent_of_revenue": 0, "fixed_per_shift": 0, "fixed_monthly": 0},
    )
    Role.objects.get_or_create(
        slug="owner",
        defaults={"name": "Владелец", "group": Group.objects.create(name="Владелец-тест")},
    )
    user = User.objects.create_superuser("su", "su@test.com", "pass")
    assert not hasattr(user, "employee")
    emp = get_acting_employee(user)
    assert isinstance(emp, Employee)
    assert emp.user_id == user.pk
    user.refresh_from_db()
    assert hasattr(user, "employee")


@pytest.mark.django_db
def test_superuser_effective_role_is_owner():
    user = User.objects.create_superuser("su2", "su2@test.com", "pass")
    assert user_effective_role(user) == "owner"
