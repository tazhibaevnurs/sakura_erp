import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from apps.accounts.models import Employee, Role
from apps.assistant.actions import ActionContext, create_guest_order, execute_tool
from apps.menu.models import MenuCategory, MenuItem
from apps.orders.models import KitchenSection, Order, OrderItem
from apps.salary.models import SalarySchema

User = get_user_model()


@pytest.fixture
def employee(db):
    group, _ = Group.objects.get_or_create(name="Владелец-тест-orders")
    role, _ = Role.objects.get_or_create(
        slug="owner",
        defaults={"name": "Владелец", "group": group},
    )
    schema, _ = SalarySchema.objects.get_or_create(
        name="Тест orders",
        defaults={"percent_of_revenue": 0, "fixed_per_shift": 0, "fixed_monthly": 0},
    )
    user = User.objects.create_user("orders_user", password="x")
    return Employee.objects.create(
        user=user,
        role=role,
        hired_date="2026-01-01",
        salary_schema=schema,
    )


@pytest.fixture
def lagman(db):
    section = KitchenSection.objects.create(slug="hot-test", name="Горячий")
    cat = MenuCategory.objects.create(name="Супы", kitchen_section=section, order=1)
    return MenuItem.objects.create(category=cat, name="Лагман", price=40, is_available=True)


@pytest.mark.django_db
def test_create_takeaway_order(employee, lagman):
    ctx = ActionContext(channel="web_test", external_user_id="99")
    result = create_guest_order(
        order_type="takeaway",
        items=[{"name": "Лагман", "quantity": 2}],
        ctx=ctx,
    )
    assert result["success"] is True
    order = Order.objects.get(pk=result["order_id"])
    assert order.order_type == Order.OrderType.TAKEAWAY
    assert order.items.count() == 1
    assert order.status == Order.Status.SENT
    assert "🛒" in result["message"]


@pytest.mark.django_db
def test_create_delivery_requires_address(employee, lagman):
    result = create_guest_order(
        order_type="delivery",
        items=[{"name": "Лагман", "quantity": 1}],
        customer_name="Азамат",
        customer_phone="+996500000001",
        ctx=ActionContext(channel="web_test", external_user_id="1"),
    )
    assert result["success"] is False
    assert result["needs"] == "delivery_address"


@pytest.mark.django_db
def test_execute_tool_create_guest_order(employee, lagman):
    result = execute_tool(
        "create_guest_order",
        {
            "order_type": "takeaway",
            "items": [{"name": "Лагман", "quantity": 1}],
        },
        ActionContext(channel="web_test", external_user_id="42"),
    )
    assert result["success"] is True
    assert OrderItem.objects.filter(order_id=result["order_id"]).exists()
