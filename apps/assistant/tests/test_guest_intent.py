import pytest

from apps.assistant.actions import ActionContext
from apps.assistant.guest_intent import (
    is_dish_or_menu_question,
    is_general_information_question,
    is_order_flow_continuation,
    should_clear_pending_for_llm,
    should_use_llm_first,
)
from apps.assistant.order_flow import clear_pending_order, save_pending_order
from apps.menu.models import MenuCategory, MenuItem
from apps.orders.models import KitchenSection


@pytest.fixture
def ctx():
    return ActionContext(channel="web_test", external_user_id="intent-1")


@pytest.fixture
def gulyash_menu(db):
    section = KitchenSection.objects.create(slug="hot-intent", name="Горячий")
    hot = MenuCategory.objects.create(name="Горячее", kitchen_section=section, order=1)
    MenuItem.objects.create(category=hot, name="Плов", price=45, is_available=True)
    MenuItem.objects.create(category=hot, name="Гуляш", price=50, is_available=True)


def test_address_is_general_question():
    assert is_general_information_question("адрес какой у вас ?") is True


def test_gulyash_availability_is_dish_question(gulyash_menu):
    assert is_dish_or_menu_question("Гуляш у вас есть") is True


@pytest.mark.django_db
def test_takeaway_is_order_continuation():
    pending = {"step": "awaiting_type", "items": [{"name": "Плов", "quantity": 1}]}
    assert is_order_flow_continuation("навынос", pending) is True


@pytest.mark.django_db
def test_gulyash_question_not_order_continuation_with_pending_plov(gulyash_menu):
    pending = {"step": "awaiting_type", "items": [{"name": "Плов", "quantity": 1}]}
    assert is_order_flow_continuation("Гуляш у вас есть", pending) is False


@pytest.mark.django_db
def test_pending_order_address_goes_to_llm(ctx):
    clear_pending_order(ctx)
    save_pending_order(
        ctx,
        {
            "step": "awaiting_type",
            "items": [{"name": "Плов", "quantity": 1}],
            "language": "ru",
        },
    )
    assert should_use_llm_first("адрес какой у вас ?", ctx) is True


@pytest.mark.django_db
def test_gulyash_clears_stale_pending_and_uses_llm(ctx, gulyash_menu):
    clear_pending_order(ctx)
    save_pending_order(
        ctx,
        {
            "step": "awaiting_type",
            "items": [{"name": "Плов", "quantity": 1}],
            "language": "ru",
        },
    )
    assert should_use_llm_first("Гуляш у вас есть", ctx) is True
    assert should_clear_pending_for_llm("Гуляш у вас есть", ctx) is True
