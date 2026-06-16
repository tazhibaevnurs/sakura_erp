import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from apps.accounts.models import Employee, Role
from apps.assistant.actions import ActionContext
from apps.assistant.language import KY, RU, try_direct_greeting_reply
from apps.assistant.menu_items import (
    apply_items_to_pending,
    menu_item_availability_reply,
)
from apps.assistant.order_flow import clear_pending_order, try_order_flow_reply
from apps.menu.models import MenuCategory, MenuItem
from apps.orders.models import KitchenSection
from apps.salary.models import SalarySchema

User = get_user_model()


@pytest.fixture
def employee(db):
    group, _ = Group.objects.get_or_create(name="Владелец-тест-menu-items")
    role, _ = Role.objects.get_or_create(
        slug="owner",
        defaults={"name": "Владелец", "group": group},
    )
    schema, _ = SalarySchema.objects.get_or_create(
        name="Тест menu items",
        defaults={"percent_of_revenue": 0, "fixed_per_shift": 0, "fixed_monthly": 0},
    )
    user = User.objects.create_user("menu_items_user", password="x")
    return Employee.objects.create(
        user=user,
        role=role,
        hired_date="2026-01-01",
        salary_schema=schema,
    )


@pytest.fixture
def menu_items(db):
    section = KitchenSection.objects.create(slug="hot-items", name="Горячий")
    hot = MenuCategory.objects.create(name="Горячее", kitchen_section=section, order=1)
    baker = MenuCategory.objects.create(name="Выпечка", kitchen_section=section, order=2)
    MenuItem.objects.create(category=hot, name="Плов", price=45, is_available=True)
    MenuItem.objects.create(category=hot, name="Гуляш", price=42, is_available=True)
    MenuItem.objects.create(category=baker, name="Самса", price=12, is_available=True)


@pytest.fixture
def ctx():
    return ActionContext(channel="web_test", external_user_id="items-1")


def test_greeting_russian():
    reply = try_direct_greeting_reply("привет")
    assert reply is not None
    assert "Здравствуйте" in reply


def test_availability_kyrgyz(menu_items):
    reply = menu_item_availability_reply("плов барбы?", KY)
    assert reply is not None
    assert "Ооба" in reply
    assert "Плов" in reply


@pytest.mark.django_db
def test_add_item_during_pending_order(menu_items, employee, ctx):
    clear_pending_order(ctx)
    try_order_flow_reply("плов 1", None, ctx)
    reply = try_order_flow_reply("еще самса добавьте", None, ctx)
    assert reply is not None
    assert "Самса" in reply or "Кошулду" in reply or "Добавлено" in reply
    assert "доставка" in reply.lower() or "Жеткирүү" in reply or "ыңгайлуу" in reply


@pytest.mark.django_db
def test_add_missing_item(menu_items, ctx):
    pending = {"items": [{"name": "Плов", "quantity": 1}], "step": "awaiting_type", "language": RU}
    changed, reply = apply_items_to_pending(pending, "добавьте суши", RU)
    assert changed is True
    assert "нет в меню" in reply or "жок" in reply
