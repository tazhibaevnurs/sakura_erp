"""Синхронизация черновика заказа из диалога (для LLM и fallback)."""
from __future__ import annotations

import re

from .actions import ActionContext
from .language import detect_guest_language
from .menu_items import merge_pending_items
from .order_flow import (
    STEP_AWAITING_ADDRESS,
    STEP_AWAITING_CONTACT,
    STEP_AWAITING_TYPE,
    _clean_name,
    _parse_order_type_answer,
    load_pending_order,
    save_pending_order,
)
from .order_parsing import (
    ParsedOrderLine,
    _parse_guest_name,
    _parse_phone,
    parse_order_request,
)


def _compute_step(pending: dict) -> str:
    if not pending.get("items"):
        return STEP_AWAITING_TYPE
    if not pending.get("order_type"):
        return STEP_AWAITING_TYPE
    name = _clean_name(pending.get("customer_name", ""))
    phone = (pending.get("customer_phone") or "").strip()
    if not name or not phone:
        return STEP_AWAITING_CONTACT
    if pending.get("order_type") == "delivery" and not (
        pending.get("delivery_address") or ""
    ).strip():
        return STEP_AWAITING_ADDRESS
    return "ready"


def _looks_like_address_message(text: str, pending: dict) -> bool:
    if pending.get("order_type") != "delivery":
        return False
    if not _clean_name(pending.get("customer_name", "")):
        return False
    if not (pending.get("customer_phone") or "").strip():
        return False

    stripped = text.strip()
    if len(stripped) < 5:
        return False
    if _parse_order_type_answer(text):
        return False
    if parse_order_request(text):
        return False

    phone = _parse_phone(text)
    if phone and stripped.replace(" ", "") == phone.replace(" ", ""):
        return False
    if phone and not re.search(r"[а-яёa-z]", stripped.lower().replace("+", "")):
        return False
    return True


def _merge_items(pending: dict, lines: list[ParsedOrderLine]) -> None:
    if not lines:
        return
    pending["items"] = merge_pending_items(
        pending.get("items", []),
        lines,
    )


def sync_order_draft(
    ctx: ActionContext,
    user_message: str,
    history: list[dict] | None,
    *,
    lang: str = "",
) -> dict | None:
    """Сохранить прогресс заказа из истории и текущего сообщения."""
    if not ctx.channel or not ctx.external_user_id:
        return load_pending_order(ctx)

    lang = lang or detect_guest_language(user_message, history, stored=ctx.language)
    pending = load_pending_order(ctx) or {
        "step": STEP_AWAITING_TYPE,
        "items": [],
        "language": lang,
        "order_type": "",
        "customer_name": "",
        "customer_phone": "",
        "delivery_address": "",
    }

    user_texts = [user_message]
    for item in reversed(history or []):
        if item.get("role") == "user" and item.get("content"):
            user_texts.append(item["content"])

    for text in user_texts:
        req = parse_order_request(text)
        if req and req.items:
            _merge_items(pending, req.items)

        order_type = _parse_order_type_answer(text)
        if order_type:
            pending["order_type"] = order_type

        phone = _parse_phone(text)
        if phone:
            pending["customer_phone"] = phone

        name = _clean_name(_parse_guest_name(text))
        if (
            not name
            and re.fullmatch(r"[А-ЯЁа-яA-Za-z\-]{2,40}", text.strip())
            and not _parse_order_type_answer(text)
            and not _parse_phone(text)
        ):
            name = _clean_name(text.strip())
        if name:
            pending["customer_name"] = name

        if _looks_like_address_message(text, pending):
            pending["delivery_address"] = text.strip()

    pending["step"] = _compute_step(pending)
    pending["language"] = lang

    if pending.get("items"):
        save_pending_order(ctx, pending)
        return pending

    if load_pending_order(ctx):
        save_pending_order(ctx, pending)
        return pending

    return None
