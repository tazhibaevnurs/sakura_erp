"""Понимание намерения гостя: заказ vs общий вопрос."""
from __future__ import annotations

import re

from .menu_items import looks_like_add_item_request, looks_like_modify_order_items
from .order_parsing import _parse_guest_name, _parse_phone, parse_order_request

STEP_AWAITING_TYPE = "awaiting_type"
STEP_AWAITING_CONTACT = "awaiting_contact"
STEP_AWAITING_ADDRESS = "awaiting_address"

GENERAL_INFO_PATTERNS = (
    r"адрес\s+(какой|у вас|где|не)",
    r"(какой|где)\s+(у вас\s+)?адрес",
    r"где\s+(вы\s+)?находит",
    r"как\s+добраться",
    r"ваш\s+телефон",
    r"номер\s+телефон",
    r"часы\s+работ",
    r"когда\s+открыт",
    r"когда\s+работа",
    r"о\s+ресторан",
    r"расскаж(ите|и)\s+о",
    r"дарег(иңиз|иниз)?",
    r"кайда\s+жайгашкан",
    r"телефон(уңуз|уңар)?",
    r"иштейси",
    r"качан\s+ачыл",
    r"жумуш\s+убакыт",
)

GENERAL_INFO_WORDS = (
    "адрес",
    "телефон",
    "часы работы",
    "о ресторане",
    "где находит",
    "как добраться",
    "дарег",
    "кайда",
    "иштейси",
    "жумуш убак",
)


def is_general_information_question(text: str) -> bool:
    lowered = (text or "").lower().strip()
    if not lowered:
        return False
    for pattern in GENERAL_INFO_PATTERNS:
        if re.search(pattern, lowered):
            return True
    if any(word in lowered for word in GENERAL_INFO_WORDS):
        if parse_order_request(text) is None:
            return True
    return False


def is_dish_or_menu_question(text: str) -> bool:
    from .menu_format import looks_like_menu_request
    from .menu_items import extract_dishes_from_text, is_menu_item_availability_question

    if looks_like_menu_request(text):
        return True
    if is_menu_item_availability_question(text):
        return True

    lowered = (text or "").lower()
    dish_markers = (
        "есть",
        "барбы",
        "жокпу",
        "имеется",
        "в меню",
        "ээлүүбү",
        "сколько стоит",
        "канча",
        "баасы",
    )
    if any(marker in lowered for marker in dish_markers) and extract_dishes_from_text(text):
        return True
    return False


def is_order_flow_continuation(text: str, pending: dict) -> bool:
    from .order_flow import _parse_order_type_answer

    step = pending.get("step", STEP_AWAITING_TYPE)

    if is_dish_or_menu_question(text) and step == STEP_AWAITING_TYPE:
        return False

    if step == STEP_AWAITING_TYPE:
        if _parse_order_type_answer(text):
            return True
        if looks_like_add_item_request(text):
            return True
        return False

    if looks_like_add_item_request(text):
        return True

    if step == STEP_AWAITING_CONTACT:
        if _parse_phone(text):
            return True
        if re.fullmatch(r"[А-ЯЁа-яA-Za-z\-]{2,40}", text.strip()):
            return True
        name, phone = _parse_guest_name(text), _parse_phone(text)
        if name or phone:
            return True
        return False

    if step == STEP_AWAITING_ADDRESS:
        phone = _parse_phone(text)
        stripped = text.strip()
        if phone and stripped.replace(" ", "") == phone.replace(" ", ""):
            return False
        if phone and not re.search(r"[а-яёa-z]", stripped.lower().replace("+", "")):
            return False
        return len(stripped) >= 5

    return False


def should_use_llm_first(text: str, ctx) -> bool:
    """Почти все сообщения — через LLM; прямой сценарий только для шагов оформления."""
    if is_dish_or_menu_question(text):
        return True
    if is_general_information_question(text):
        return True

    from .order_flow import load_pending_order

    pending = load_pending_order(ctx)
    if not pending:
        return True

    if is_order_flow_continuation(text, pending):
        return False

    return True


def should_clear_pending_for_llm(text: str, ctx) -> bool:
    """Сбросить устаревший заказ при вопросе о другом блюде или меню."""
    if not is_dish_or_menu_question(text) and not is_general_information_question(text):
        return False
    from .order_flow import load_pending_order

    pending = load_pending_order(ctx)
    if not pending:
        return False
    return not is_order_flow_continuation(text, pending)


def build_llm_context_note(ctx) -> str:
    from .order_flow import load_pending_order

    pending = load_pending_order(ctx)
    if not pending:
        return ""

    items = ", ".join(
        f"{i.get('name')}×{i.get('quantity', 1)}"
        for i in pending.get("items", [])
    )
    step = pending.get("step", "")
    step_labels = {
        STEP_AWAITING_TYPE: "выбор типа (доставка/навынос/кабинка)",
        STEP_AWAITING_CONTACT: "ожидание имени и телефона",
        STEP_AWAITING_ADDRESS: "ожидание адреса доставки",
        "ready": "все данные собраны — можно оформить заказ",
    }
    step_label = step_labels.get(step, step)
    type_label = pending.get("order_type") or "не выбран"
    name = pending.get("customer_name") or "—"
    phone = pending.get("customer_phone") or "—"
    address = pending.get("delivery_address") or "—"

    return (
        f"\n\n[Контекст ERP — незавершённый заказ]\n"
        f"Блюда: {items or 'нет'}\n"
        f"Тип: {type_label}\n"
        f"Имя: {name}\n"
        f"Телефон: {phone}\n"
        f"Адрес: {address}\n"
        f"Шаг: {step_label}\n"
        f"Продолжай оформление сам: спроси только недостающее поле. "
        f"Не отправляй гостя звонить в ресторан. "
        f"Когда все данные есть — вызови create_guest_order. "
        f"Если гость задал другой вопрос — сначала ответь на него.]"
    )
