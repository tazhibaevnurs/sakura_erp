import pytest

from apps.assistant.menu_format import (
    format_menu_for_guest,
    looks_like_menu_request,
    parse_menu_category_filter,
)
from apps.menu.models import MenuCategory, MenuItem
from apps.orders.models import KitchenSection


@pytest.mark.django_db
def test_format_menu_with_emoji():
    section = KitchenSection.objects.create(slug="hot", name="Горячий цех")
    cat = MenuCategory.objects.create(name="Супы", kitchen_section=section, order=1)
    MenuItem.objects.create(category=cat, name="Лагман", price=40, is_available=True)

    text = format_menu_for_guest()
    assert "🍽" in text
    assert "🍲" in text
    assert "Лагман" in text
    assert "40 сом" in text
    assert "✅" in text
    assert "━━━━━━━━" in text
    assert "💰" in text


def test_looks_like_menu_request():
    assert looks_like_menu_request("Покажите меню")
    assert looks_like_menu_request("Что есть в кафе?")
    assert not looks_like_menu_request("Забронируйте стол на 6 человек")


def test_parse_menu_category_filter():
    assert parse_menu_category_filter("какие супы есть") == "суп"
    assert parse_menu_category_filter("меню") == ""
