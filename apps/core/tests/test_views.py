"""Проверка доступности всех страниц (шаблоны без ошибок)."""
from datetime import date

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.accounts.models import Employee, Role
from apps.menu.models import MenuCategory, MenuItem
from apps.orders.models import KitchenSection, Order
from apps.salary.models import SalarySchema
from apps.tables.models import Table

User = get_user_model()


@pytest.fixture
def owner_client(db, client):
    from django.contrib.auth.models import Group

    group, _ = Group.objects.get_or_create(name="Владелец")
    role, _ = Role.objects.get_or_create(
        slug="owner",
        defaults={"name": "Владелец", "group": group},
    )
    if role.group_id != group.pk:
        role.group = group
        role.save(update_fields=["group"])
    schema, _ = SalarySchema.objects.get_or_create(
        name="Тест",
        defaults={"percent_of_revenue": 0, "fixed_per_shift": 0, "fixed_monthly": 0},
    )
    user, _ = User.objects.get_or_create(
        username="testowner",
        defaults={"password": "testpass123"},
    )
    user.set_password("testpass123")
    user.save()
    Employee.objects.get_or_create(
        user=user,
        defaults={
            "role": role,
            "hired_date": date.today(),
            "salary_schema": schema,
        },
    )
    client.login(username="testowner", password="testpass123")
    return client


@pytest.mark.django_db
def test_public_login_page(client):
    r = client.get(reverse("accounts:login"))
    assert r.status_code == 200


@pytest.mark.django_db
def test_all_authenticated_pages(owner_client):
    section, _ = KitchenSection.objects.get_or_create(slug="hot", defaults={"name": "Горячий"})
    table, _ = Table.objects.get_or_create(number=99, defaults={"position_x": 10, "position_y": 10})
    cat, _ = MenuCategory.objects.get_or_create(
        name="Тест",
        kitchen_section=section,
        defaults={"order": 0},
    )
    MenuItem.objects.get_or_create(
        category=cat,
        name="Тест блюдо",
        defaults={"price": 100, "is_available": True},
    )
    emp = Employee.objects.get(user__username="testowner")
    item = MenuItem.objects.filter(category=cat).first()

    pages_before_order = [
        reverse("tables:floor"),
        reverse("tables:reservation_list"),
        reverse("orders:list"),
        reverse("orders:takeaway"),
        reverse("orders:create", kwargs={"table_id": table.pk}),
        reverse("cash:today"),
        reverse("cash:closed_list"),
        reverse("cash:expenses"),
        reverse("cash:expense_add"),
        reverse("cash:debts"),
        reverse("cash:debt_add"),
        reverse("salary:list"),
        reverse("salary:timesheet"),
        reverse("salary:period", kwargs={"period": "2026-05"}),
        reverse("menu:manage"),
        reverse("menu:item_add"),
        reverse("reports:dashboard"),
        reverse("reports:export"),
        reverse("staff_list"),
        reverse("staff_add"),
        reverse("staff_detail", kwargs={"pk": emp.pk}),
        reverse("kitchen:display", kwargs={"section_slug": section.slug}),
    ]
    for url in pages_before_order:
        r = owner_client.get(url)
        assert r.status_code == 200, f"{url} -> {r.status_code}"

    order = Order.objects.create(table=table, waiter=emp)
    pages_with_order = [
        reverse("orders:detail", kwargs={"pk": order.pk}),
        reverse("orders:pay", kwargs={"pk": order.pk}),
        reverse("orders:cancel", kwargs={"pk": order.pk}),
        reverse("orders:create", kwargs={"table_id": table.pk}) + "?force_new=1",
        reverse("menu:item_edit", kwargs={"pk": item.pk}),
    ]
    for url in pages_with_order:
        r = owner_client.get(url)
        assert r.status_code == 200, f"{url} -> {r.status_code}"

    from apps.cash.services import close_daily_cash

    close_daily_cash(date.today(), emp)
    r = owner_client.get(reverse("cash:day", kwargs={"date": date.today().isoformat()}))
    assert r.status_code == 200
