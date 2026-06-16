"""Профиль сотрудника для действий в ERP (заказы, касса и т.д.)."""
from datetime import date

from django.contrib.auth import get_user_model

User = get_user_model()

ELEVATED_ROLES = frozenset({"owner", "admin"})


def user_effective_role(user) -> str | None:
    """Роль пользователя: employee, группа Django или superuser → owner."""
    if not user.is_authenticated:
        return None
    if user.is_superuser:
        return "owner"
    if hasattr(user, "employee"):
        return user.employee.role.slug
    from apps.accounts.models import Role

    role = Role.objects.filter(group__in=user.groups.all()).first()
    return role.slug if role else None


def user_has_elevated_access(user) -> bool:
    return user_effective_role(user) in ELEVATED_ROLES


def ensure_employee_profile(user, role_slug: str = "owner"):
    """Создаёт Employee для superuser/admin без профиля (один раз)."""
    from apps.accounts.models import Employee, Role
    from apps.salary.models import SalarySchema

    if hasattr(user, "employee"):
        return user.employee

    role = Role.objects.get(slug=role_slug)
    schema = SalarySchema.objects.order_by("pk").first()
    if schema is None:
        schema = SalarySchema.objects.create(
            name="По умолчанию",
            percent_of_revenue=0,
            fixed_per_shift=0,
            fixed_monthly=0,
        )
    employee = Employee.objects.create(
        user=user,
        role=role,
        hired_date=date.today(),
        salary_schema=schema,
    )
    user.groups.add(role.group)
    return employee


def get_acting_employee(user):
    """Сотрудник для записи в заказ/расход; при необходимости создаёт профиль."""
    if hasattr(user, "employee"):
        return user.employee
    role = user_effective_role(user)
    if role in ELEVATED_ROLES:
        slug = "admin" if role == "admin" else "owner"
        return ensure_employee_profile(user, role_slug=slug)
    raise ValueError("У пользователя нет профиля сотрудника")
