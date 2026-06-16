"""Проверка блюд в меню и добавление в заказ."""
from __future__ import annotations

import re

from apps.menu.models import MenuItem
from apps.orders.services import find_menu_item

from .language import KY, RU, msg
from .order_parsing import ParsedOrderLine, _extract_items, _names_match

AVAILABILITY_MARKERS = (
    "барбы",
    "жокпу",
    "есть ли",
    "есть в",
    "у вас есть",
    "в меню",
    "ээлүүбү",
    "бар?",
    "бар ",
    "имеется",
    "имеются",
    " есть",
)

ADD_MARKERS = (
    "добав",
    "еще",
    "ещё",
    "кош",
    "дагы",
    "кошуу",
    "кошуп",
)


def _find_dish_words(text: str) -> list[str]:
    lowered = text.lower()
    words = re.findall(r"[а-яёңөүa-z\-]{3,}", lowered)
    skip = {
        "барбы", "жокпу", "есть", "меню", "добавьте", "добавь", "еще", "ещё",
        "заказ", "пожалуйста", "можно", "кандай", "привет", "салам", "дагы",
    }
    return [w for w in words if w not in skip]


def extract_dishes_from_text(text: str) -> list[ParsedOrderLine]:
    items = _extract_items(text)
    if items:
        return items

    found: list[ParsedOrderLine] = []
    for word in _find_dish_words(text):
        menu_item = find_menu_item(word)
        if menu_item is None:
            for name in MenuItem.objects.filter(is_available=True).values_list("name", flat=True):
                if _names_match(word, name):
                    menu_item = find_menu_item(name)
                    break
        if menu_item and not any(i.name == menu_item.name for i in found):
            found.append(ParsedOrderLine(name=menu_item.name, quantity=1))
    return found


def is_menu_item_availability_question(text: str) -> bool:
    lowered = text.lower()
    if not any(marker in lowered for marker in AVAILABILITY_MARKERS):
        return False
    return bool(extract_dishes_from_text(text))


def looks_like_add_item_request(text: str) -> bool:
    lowered = text.lower()
    if any(marker in lowered for marker in ADD_MARKERS):
        return True
    if looks_like_modify_order_items(text):
        return True
    return False


def looks_like_modify_order_items(text: str) -> bool:
    items = extract_dishes_from_text(text)
    if not items:
        return False
    lowered = text.lower()
    if _parse_order_type_in_text(lowered):
        return False
    if any(marker in lowered for marker in ADD_MARKERS):
        return True
    if any(marker in lowered for marker in AVAILABILITY_MARKERS):
        return False
    return bool(re.search(r"(добав|кош|дагы|еще|ещё)", lowered))


def _parse_order_type_in_text(lowered: str) -> bool:
    delivery = ("доставк", "привез", "жеткир")
    takeaway = ("навынос", "с собой", "өзүм", "алып кет")
    dine_in = ("кабин", "в зале", "кабинада")
    return (
        any(w in lowered for w in delivery)
        or any(w in lowered for w in takeaway)
        or any(w in lowered for w in dine_in)
        or lowered.strip() in {"1", "2", "3"}
    )


def lookup_menu_item(name: str) -> MenuItem | None:
    item = find_menu_item(name)
    if item and item.is_available:
        return item
    return None


def format_dish_price(item: MenuItem) -> str:
    price = int(item.price) if item.price == int(item.price) else item.price
    return str(price)


def menu_item_availability_reply(text: str, lang: str = RU) -> str | None:
    if not is_menu_item_availability_question(text):
        return None

    dishes = extract_dishes_from_text(text)
    if not dishes:
        return None

    lines = []
    for dish in dishes:
        item = lookup_menu_item(dish.name)
        if item:
            lines.append(
                msg("dish_yes", lang, name=item.name, price=format_dish_price(item))
            )
        else:
            lines.append(msg("dish_no", lang, name=dish.name))

    return "\n".join(lines)


def merge_pending_items(
    pending_items: list[dict],
    new_items: list[ParsedOrderLine],
) -> list[dict]:
    merged: dict[str, int] = {
        i["name"]: int(i.get("quantity", 1)) for i in pending_items
    }
    for item in new_items:
        merged[item.name] = merged.get(item.name, 0) + item.quantity
    return [{"name": name, "quantity": qty} for name, qty in merged.items()]


def apply_items_to_pending(
    pending: dict,
    text: str,
    lang: str,
) -> tuple[bool, str | None]:
    """Добавить блюда в незавершённый заказ. (changed, reply_if_any)."""
    if not looks_like_modify_order_items(text) and not looks_like_add_item_request(text):
        return False, None

    parsed = extract_dishes_from_text(text)
    if not parsed:
        raw_words = _find_dish_words(text)
        if raw_words and looks_like_add_item_request(text):
            return True, msg("dish_no", lang, name=raw_words[0].capitalize())
        return False, None

    added: list[str] = []
    missing: list[str] = []

    valid_items: list[ParsedOrderLine] = []
    for dish in parsed:
        item = lookup_menu_item(dish.name)
        if item:
            valid_items.append(ParsedOrderLine(name=item.name, quantity=dish.quantity))
            added.append(item.name)
        else:
            missing.append(dish.name)

    if not valid_items and missing:
        return True, msg("dish_no", lang, name=missing[0])

    if valid_items:
        pending["items"] = merge_pending_items(pending.get("items", []), valid_items)

    parts = []
    for name in added:
        parts.append(msg("dish_added", lang, name=name))
    for name in missing:
        parts.append(msg("dish_no", lang, name=name))

    return True, "\n".join(parts) if parts else None
