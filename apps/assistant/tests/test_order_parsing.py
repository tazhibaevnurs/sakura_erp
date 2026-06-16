import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from apps.accounts.models import Employee, Role
from apps.assistant.actions import ActionContext
from apps.assistant.order_flow import (
    clear_pending_order,
    load_pending_order,
    try_order_flow_reply,
)
from apps.assistant.order_parsing import parse_order_request
from apps.menu.models import MenuCategory, MenuItem
from apps.orders.models import KitchenSection, Order
from apps.salary.models import SalarySchema

User = get_user_model()


@pytest.fixture
def employee(db):
    group, _ = Group.objects.get_or_create(name="Владелец-тест-parse")
    role, _ = Role.objects.get_or_create(
        slug="owner",
        defaults={"name": "Владелец", "group": group},
    )
    schema, _ = SalarySchema.objects.get_or_create(
        name="Тест parse",
        defaults={"percent_of_revenue": 0, "fixed_per_shift": 0, "fixed_monthly": 0},
    )
    user = User.objects.create_user("parse_user", password="x")
    return Employee.objects.create(
        user=user,
        role=role,
        hired_date="2026-01-01",
        salary_schema=schema,
    )


@pytest.fixture
def menu_items(db):
    section = KitchenSection.objects.create(slug="hot-parse", name="Горячий")
    hot = MenuCategory.objects.create(name="Горячее", kitchen_section=section, order=1)
    baker = MenuCategory.objects.create(name="Выпечка", kitchen_section=section, order=2)
    MenuItem.objects.create(category=hot, name="Плов", price=45, is_available=True)
    MenuItem.objects.create(category=hot, name="Лагман", price=40, is_available=True)
    MenuItem.objects.create(category=baker, name="Самса", price=12, is_available=True)
    MenuItem.objects.create(category=hot, name="Шурпа", price=35, is_available=True)
    MenuItem.objects.create(category=hot, name="Гуляш", price=50, is_available=True)


@pytest.fixture
def ctx():
    return ActionContext(channel="web_test", external_user_id="flow-1")


@pytest.mark.django_db
def test_parse_kyrgyz_multi_item_order(menu_items):
    req = parse_order_request("плов 1 порция и 1шт самсы заказ кылайынчы")
    assert req is not None
    assert req.order_type == ""
    names = {i.name for i in req.items}
    assert "Плов" in names
    assert "Самса" in names


@pytest.mark.django_db
def test_order_flow_asks_type_first(menu_items, ctx):
    clear_pending_order(ctx)
    reply = try_order_flow_reply("2 лагмана", None, ctx)
    assert reply is not None
    assert "Как вам удобнее" in reply or "доставка" in reply.lower()
    assert Order.objects.count() == 0
    pending = load_pending_order(ctx)
    assert pending is not None
    assert pending["step"] == "awaiting_type"


@pytest.mark.django_db
def test_order_flow_full_takeaway(menu_items, employee, ctx):
    clear_pending_order(ctx)
    try_order_flow_reply("плов 1 и 1 самса", None, ctx)
    try_order_flow_reply("навынос", None, ctx)
    reply = try_order_flow_reply("Азамат, +996555123456", None, ctx)
    assert reply is not None
    assert "Заказ" in reply
    assert Order.objects.filter(order_type="takeaway").exists()
    order = Order.objects.latest("pk")
    assert order.customer_name == "Азамат"
    assert order.items.count() == 2
    assert load_pending_order(ctx) is None


@pytest.mark.django_db
def test_order_flow_name_then_phone(menu_items, employee, ctx):
    clear_pending_order(ctx)
    try_order_flow_reply("плов 1", None, ctx)
    try_order_flow_reply("доставка", None, ctx)
    reply_name = try_order_flow_reply("нурс", None, ctx)
    assert reply_name is not None
    assert "телефон" in reply_name.lower()
    pending = load_pending_order(ctx)
    assert pending["customer_name"] == "нурс"
    try_order_flow_reply("+996506055056", None, ctx)
    reply_addr = try_order_flow_reply("токтогула 56 кв 15", None, ctx)
    assert reply_addr is not None
    order = Order.objects.latest("pk")
    assert order.customer_name == "нурс"
    assert order.delivery_address == "токтогула 56 кв 15"
    assert order.items.filter(menu_item__name="Плов").exists()
    assert not order.items.filter(menu_item__name="Гуляш").exists()
