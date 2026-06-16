import pytest

from apps.assistant.actions import ActionContext
from apps.assistant.order_draft_sync import sync_order_draft
from apps.assistant.order_flow import clear_pending_order, load_pending_order, try_order_flow_reply
from apps.menu.models import MenuCategory, MenuItem
from apps.orders.models import KitchenSection


@pytest.fixture
def ctx():
    return ActionContext(channel="web_test", external_user_id="sync-1")


@pytest.fixture
def menu_items(db):
    section = KitchenSection.objects.create(slug="hot-sync", name="Горячий")
    hot = MenuCategory.objects.create(name="Горячее", kitchen_section=section, order=1)
    MenuItem.objects.create(category=hot, name="Плов", price=45, is_available=True)


@pytest.mark.django_db
def test_sync_from_dialog_history(menu_items, ctx):
    clear_pending_order(ctx)
    history = [
        {"role": "user", "content": "плов 1"},
        {"role": "assistant", "content": "Как вам удобнее — доставка или навынос?"},
        {"role": "user", "content": "доставка"},
        {"role": "assistant", "content": "Укажите имя и телефон"},
        {"role": "user", "content": "нурсултан"},
    ]

    sync_order_draft(ctx, "+996509055056", history, lang="ru")
    pending = load_pending_order(ctx)
    assert pending is not None
    assert pending["order_type"] == "delivery"
    assert pending["customer_name"] == "нурсултан"
    assert pending["customer_phone"] == "+996509055056"
    assert pending["step"] == "awaiting_address"

    reply = try_order_flow_reply("+996509055056", history, ctx)
    assert reply is not None
    assert "адрес" in reply.lower()
