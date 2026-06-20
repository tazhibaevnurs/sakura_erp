"""Сбор заказа, самовывоза и брони: обязательные поля и подтверждение."""
from __future__ import annotations

from ..models import ClientProfile

ORDER_TYPE_ALIASES = {
    "delivery": "delivery",
    "доставка": "delivery",
    "takeaway": "takeaway",
    "самовывоз": "takeaway",
    "навынос": "takeaway",
    "вынос": "takeaway",
}

CONFIRM_TEXTS = {
    "confirm",
    "подтвердить",
    "подтверждаю",
    "да",
    "ок",
    "ok",
    "yes",
    "✅",
    "✅ подтвердить",
    "ооба",
    "макул",
    "туура",
}

CANCEL_TEXTS = {
    "cancel",
    "отменить",
    "отмена",
    "нет",
    "❌",
    "❌ отменить",
    "жок",
    "керек эмес",
    "токто",
}

FIELD_LABELS = {
    "type": "способ получения (доставка или самовывоз)",
    "items": "блюда из меню",
    "name": "имя",
    "phone": "телефон",
    "address": "адрес доставки",
    "date": "дата",
    "time": "время",
    "guests": "количество гостей",
    "table_number": "номер кабинки",
}

FIELD_LABELS_KY = {
    "type": "алуу ёлу (жеткирүү же өзү алуу)",
    "items": "менюдагы тамактар",
    "name": "аты",
    "phone": "телефон",
    "address": "жеткирүү дареги",
    "date": "дата",
    "time": "убакыт",
    "guests": "коноктор саны",
    "table_number": "кабина номери",
}

FIELD_QUESTIONS = {
    "type": "Доставка или самовывоз? 🚗 / 🏃",
    "items": "Что закажете из меню?",
    "name": "Как к вам обращаться?",
    "phone": "Укажите номер телефона для связи:",
    "address": "Куда доставить? Напишите адрес:",
    "date": "На какую дату забронировать стол?",
    "time": "На какое время?",
    "guests": "Сколько гостей будет?",
}

ORDER_FIELD_ORDER = {
    "order": ["items", "type", "name", "phone"],
    "order_delivery": ["items", "type", "address", "name", "phone"],
    "order_takeaway": ["items", "type", "name", "phone"],
    "booking": ["date", "time", "guests", "name", "phone"],
}


def normalize_order_type(value) -> str | None:
    if value is None:
        return None
    raw = str(value).strip().lower()
    return ORDER_TYPE_ALIASES.get(raw)


def normalize_user_action(text: str) -> str | None:
    t = (text or "").strip().lower()
    if not t:
        return None
    if t in CONFIRM_TEXTS or t.startswith("✅"):
        return "confirm"
    if t in CANCEL_TEXTS or t.startswith("❌"):
        return "cancel"
    return None


def has_items(draft: dict) -> bool:
    for item in draft.get("items") or []:
        if (item.get("name") or "").strip():
            return True
    return False


def effective_name(draft: dict, client: ClientProfile) -> str:
    name = (draft.get("name") or client.name or "").strip()
    return name if len(name) >= 2 else ""


def effective_phone(draft: dict, client: ClientProfile) -> str:
    phone = (draft.get("phone") or client.phone or "").strip()
    if not phone or phone.startswith("web-test-"):
        return ""
    digits = "".join(c for c in phone if c.isdigit())
    return phone if len(digits) >= 9 else ""


def detect_flow(draft: dict, current_intent: str) -> str | None:
    intent = (current_intent or "").lower()
    order_type = normalize_order_type(draft.get("type"))

    booking_signals = bool(draft.get("date") or draft.get("time") or draft.get("guests"))
    if intent == "booking" or (booking_signals and intent != "order"):
        return "booking"

    if intent == "order" or order_type or has_items(draft):
        if order_type == "delivery":
            return "order_delivery"
        if order_type == "takeaway":
            return "order_takeaway"
        return "order"

    return None


def get_missing_fields(draft: dict, client: ClientProfile, flow: str | None) -> list[str]:
    if not flow:
        return []

    missing: list[str] = []

    if flow.startswith("order"):
        if not has_items(draft):
            missing.append("items")
        order_type = normalize_order_type(draft.get("type"))
        if flow == "order" and not order_type:
            missing.append("type")
        needs_address = flow == "order_delivery" or (
            flow == "order" and order_type == "delivery"
        )
        if needs_address and not (draft.get("address") or "").strip():
            missing.append("address")
        if not effective_name(draft, client):
            missing.append("name")
        if not effective_phone(draft, client):
            missing.append("phone")
        effective_flow = flow
        if flow == "order" and order_type == "delivery":
            effective_flow = "order_delivery"
        elif flow == "order" and order_type == "takeaway":
            effective_flow = "order_takeaway"
        return _ordered_missing(missing, effective_flow)

    if flow == "booking":
        if not (draft.get("date") or "").strip():
            missing.append("date")
        if not (draft.get("time") or "").strip():
            missing.append("time")
        if not draft.get("guests"):
            missing.append("guests")
        if not effective_name(draft, client):
            missing.append("name")
        if not effective_phone(draft, client):
            missing.append("phone")
        return _ordered_missing(missing, flow)

    return missing


def _ordered_missing(missing: list[str], flow: str) -> list[str]:
    order = ORDER_FIELD_ORDER.get(flow, [])
    return [field for field in order if field in missing] + [
        field for field in missing if field not in order
    ]


def next_field_question(
    missing: list[str],
    flow: str,
    lang: str = "ru",
    *,
    draft: dict | None = None,
    reply: str = "",
) -> str:
    from .language import field_question, reply_acknowledges_order_items, reply_asks_field

    draft = draft or {}
    ordered = _ordered_missing(missing, flow)
    for field in ordered:
        if field == "items":
            if has_items(draft):
                continue
            if reply_acknowledges_order_items(reply):
                continue
        if reply_asks_field(reply, field, lang):
            continue
        extra_items = field == "items" and has_items(draft)
        return field_question(field, lang, extra_items=extra_items)
    return ""


def missing_fields_message(missing: list[str], lang: str = "ru") -> str:
    labels_table = FIELD_LABELS_KY if lang == "ky" else FIELD_LABELS
    labels = [labels_table.get(field, field) for field in missing]
    if lang == "ky":
        return "Даярдоо үчүн дагы керек: " + ", ".join(labels) + "."
    return "Для оформления ещё нужно: " + ", ".join(labels) + "."


def build_confirmation_summary(
    draft: dict,
    client: ClientProfile,
    flow: str,
    lang: str = "ru",
) -> str:
    from .language import confirm_prompt

    if flow.startswith("order"):
        order_type = normalize_order_type(draft.get("type"))
        if lang == "ky":
            type_label = "Жеткирүү" if order_type == "delivery" else "Самовывоз"
            lines = [f"📋 Заказды текшериңиз ({type_label}):"]
        else:
            type_label = "Доставка" if order_type == "delivery" else "Самовывоз"
            lines = [f"📋 Проверьте заказ ({type_label}):"]
        for item in draft.get("items") or []:
            name = (item.get("name") or "").strip()
            if not name:
                continue
            qty = item.get("qty") or item.get("quantity") or 1
            lines.append(f"  • {name} × {qty}")
        if order_type == "delivery" and draft.get("address"):
            lines.append(f"📍 {draft['address'].strip()}")
        if draft.get("delivery_time"):
            lines.append(f"🕐 {draft['delivery_time']}")
        if draft.get("comment"):
            lines.append(f"💬 {draft['comment']}")
        lines.append(f"👤 {effective_name(draft, client)}")
        lines.append(f"📞 {effective_phone(draft, client)}")
        lines.append(confirm_prompt(lang))
        return "\n".join(lines)

    if flow == "booking":
        if lang == "ky":
            lines = [
                "📋 Бронду текшериңиз:",
                f"📅 {draft.get('date', '—')} · {draft.get('time', '—')}",
                f"👥 {draft.get('guests', '—')} конок",
            ]
            table_label = "🪑 Кабина №"
        else:
            lines = [
                "📋 Проверьте бронь:",
                f"📅 {draft.get('date', '—')} в {draft.get('time', '—')}",
                f"👥 {draft.get('guests', '—')} гост(ей)",
            ]
            table_label = "🪑 Кабинка №"
        table_num = draft.get("table_number")
        if table_num:
            lines.append(f"{table_label}{table_num}")
        lines.extend([
            f"👤 {effective_name(draft, client)}",
            f"📞 {effective_phone(draft, client)}",
        ])
        if draft.get("comment"):
            lines.append(f"💬 {draft['comment']}")
        lines.append(confirm_prompt(lang))
        return "\n".join(lines)

    return ""


def draft_for_create(draft: dict, client: ClientProfile) -> dict:
    """Черновик с подставленными именем и телефоном клиента."""
    data = dict(draft or {})
    name = effective_name(data, client)
    if name:
        data["name"] = name
    phone = effective_phone(data, client)
    if phone:
        data["phone"] = phone
    return data
