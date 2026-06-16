"""Пошаговая квалификация заказа: тип → контакты → оформление."""
from __future__ import annotations

import json
import re

from apps.menu.models import MenuItem
from apps.orders.services import find_menu_item, resolve_order_lines

from .actions import ActionContext, create_guest_order
from .language import KY, RU, detect_guest_language, msg
from .guest_intent import is_general_information_question, is_order_flow_continuation
from .menu_items import apply_items_to_pending
from .models import AssistantChannelState
from .order_parsing import (
    OrderRequest,
    _parse_address,
    _parse_guest_name,
    _parse_phone,
    _parse_table_number,
    parse_order_request,
)

STEP_AWAITING_TYPE = "awaiting_type"
STEP_AWAITING_CONTACT = "awaiting_contact"
STEP_AWAITING_ADDRESS = "awaiting_address"

DELIVERY_WORDS = (
    "доставк",
    "привез",
    "курьер",
    "по адресу",
    "жеткир",
    "жеткири",
)
TAKEAWAY_WORDS = (
    "навынос",
    "с собой",
    "забрать",
    "самовывоз",
    "өзүм",
    "алып кет",
    "алып кетем",
)
DINE_IN_WORDS = (
    "кабин",
    "в зале",
    "зале",
    "стол",
    "ішим",
    "кушать",
    "еш",
    "кабинада",
)


def _lang(pending: dict, ctx: ActionContext) -> str:
    return pending.get("language") or ctx.language or RU


def _sync_language(pending: dict, ctx: ActionContext, text: str) -> str:
    lang = detect_guest_language(text, stored=pending.get("language") or ctx.language)
    pending["language"] = lang
    ctx.language = lang
    return lang


def _type_label(order_type: str, lang: str) -> str:
    keys = {
        "delivery": "order_type_delivery",
        "takeaway": "order_type_takeaway",
        "dine_in": "order_type_dine_in",
    }
    return msg(keys.get(order_type, "order_type_takeaway"), lang)


def _channel_key(ctx: ActionContext) -> tuple[str, str] | None:
    if not ctx.channel or not ctx.external_user_id:
        return None
    return ctx.channel, ctx.external_user_id


def load_pending_order(ctx: ActionContext) -> dict | None:
    key = _channel_key(ctx)
    if not key:
        return None
    state = AssistantChannelState.objects.filter(
        channel=key[0],
        external_user_id=key[1],
    ).first()
    if not state or not state.pending_order_json:
        return None
    try:
        data = json.loads(state.pending_order_json)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def save_pending_order(ctx: ActionContext, data: dict) -> None:
    key = _channel_key(ctx)
    if not key:
        return
    state, _ = AssistantChannelState.objects.get_or_create(
        channel=key[0],
        external_user_id=key[1],
    )
    state.pending_order_json = json.dumps(data, ensure_ascii=False)
    state.save(update_fields=["pending_order_json", "updated_at"])


def clear_pending_order(ctx: ActionContext) -> None:
    key = _channel_key(ctx)
    if not key:
        return
    AssistantChannelState.objects.filter(
        channel=key[0],
        external_user_id=key[1],
    ).update(pending_order_json="")


def _clean_name(name: str) -> str:
    name = (name or "").strip()
    if len(name) < 2:
        return ""
    if name.lower() in {"и", "мен", "я", "the", "на", "в", "у"}:
        return ""
    return name


def _parse_order_type_answer(text: str) -> str:
    lowered = text.lower()
    if any(word in lowered for word in DELIVERY_WORDS):
        return "delivery"
    if any(word in lowered for word in TAKEAWAY_WORDS):
        return "takeaway"
    if any(word in lowered for word in DINE_IN_WORDS):
        return "dine_in"
    if lowered.strip() in {"1", "2", "3"}:
        return {"1": "delivery", "2": "takeaway", "3": "dine_in"}[lowered.strip()]
    return ""


def _parse_name_and_phone(text: str) -> tuple[str, str]:
    phone = _parse_phone(text)
    name = _clean_name(_parse_guest_name(text))

    if not name and phone:
        remainder = text.replace(phone, "")
        remainder = re.sub(
            r"(?i)(имя|зовут|телефон|номер|атым|менин атым|аты|phone)",
            " ",
            remainder,
        )
        name = _clean_name(remainder.strip(" ,.-"))

    if not name:
        words = [
            w
            for w in re.findall(r"[А-ЯЁа-яA-Za-z\-]{2,}", text)
            if w.lower() not in {"имя", "зовут", "телефон", "номер", "phone"}
        ]
        if words:
            name = _clean_name(words[0])

    return name, phone


def _items_subtotal(items: list[dict]) -> int:
    total = 0
    resolved, _ = resolve_order_lines(items)
    for menu_item, qty, _note in resolved:
        total += int(menu_item.price * qty)
    return total


def _format_items_lines(items: list[dict]) -> list[str]:
    lines = []
    resolved, errors = resolve_order_lines(items)
    if errors:
        for item in items:
            menu_item = find_menu_item(item.get("name", ""))
            if menu_item:
                qty = int(item.get("quantity", 1))
                price = int(menu_item.price)
                lines.append(f"  • {menu_item.name} × {qty} — {price * qty} сом")
        return lines

    for menu_item, qty, _note in resolved:
        price = int(menu_item.price)
        q = int(qty) if qty == int(qty) else qty
        lines.append(f"  • {menu_item.name} × {q} — {price * int(qty)} сом")
    return lines


def _prompt_for_type(pending: dict, lang: str, *, prefix: str = "") -> str:
    lines = _format_items_lines(pending.get("items", []))
    subtotal = _items_subtotal(pending.get("items", []))
    body = "\n".join(lines) if lines else "  • ..."
    header = msg("order_great", lang)
    if prefix:
        header = f"{prefix}\n\n{header}"
    return (
        f"{header}\n"
        f"{body}\n\n"
        f"{msg('order_subtotal', lang, total=subtotal)}\n\n"
        f"{msg('order_how', lang)}"
    )


def _prompt_for_contact(pending: dict, lang: str) -> str:
    type_label = _type_label(pending.get("order_type", ""), lang)
    return f"{msg('order_accepted', lang, type_label=type_label)}\n\n{msg('order_contact', lang)}"


def _prompt_for_address(lang: str) -> str:
    return msg("order_address", lang)


def _initial_step(req: OrderRequest) -> str:
    if not req.order_type:
        return STEP_AWAITING_TYPE
    if not (_clean_name(req.customer_name) and req.customer_phone):
        return STEP_AWAITING_CONTACT
    if req.order_type == "delivery" and not req.delivery_address:
        return STEP_AWAITING_ADDRESS
    return "ready"


def _pending_from_request(req: OrderRequest, ctx: ActionContext) -> dict:
    return {
        "step": _initial_step(req),
        "language": ctx.language,
        "items": [{"name": i.name, "quantity": i.quantity} for i in req.items],
        "order_type": req.order_type if req.order_type else "",
        "customer_name": _clean_name(req.customer_name),
        "customer_phone": req.customer_phone,
        "delivery_address": req.delivery_address,
        "table_number": req.table_number,
        "comment": req.comment,
    }


def _try_finalize(pending: dict, ctx: ActionContext) -> str:
    lang = _lang(pending, ctx)
    order_type = pending.get("order_type") or "takeaway"
    name = _clean_name(pending.get("customer_name", ""))
    phone = (pending.get("customer_phone") or "").strip()
    if not phone and ctx.channel == "whatsapp":
        phone = (ctx.guest_phone or ctx.external_user_id or "").strip()
    address = (pending.get("delivery_address") or "").strip()

    if not name:
        pending["step"] = STEP_AWAITING_CONTACT
        save_pending_order(ctx, pending)
        return _prompt_for_contact(pending, lang)

    if not phone:
        pending["step"] = STEP_AWAITING_CONTACT
        save_pending_order(ctx, pending)
        return _prompt_for_contact(pending, lang)

    if order_type == "delivery" and not address:
        pending["step"] = STEP_AWAITING_ADDRESS
        save_pending_order(ctx, pending)
        return _prompt_for_address(lang)

    result = create_guest_order(
        order_type=order_type,
        items=pending.get("items", []),
        customer_name=name,
        customer_phone=phone,
        delivery_address=address,
        table_number=pending.get("table_number"),
        comment=pending.get("comment", ""),
        ctx=ctx,
    )
    clear_pending_order(ctx)
    return result.get("message", msg("order_failed", lang))


def _advance_pending(pending: dict, text: str, ctx: ActionContext) -> str | None:
    if is_general_information_question(text):
        return None
    if not is_order_flow_continuation(text, pending):
        return None

    lang = _sync_language(pending, ctx, text)
    step = pending.get("step", STEP_AWAITING_TYPE)

    changed, add_reply = apply_items_to_pending(pending, text, lang)
    if changed:
        save_pending_order(ctx, pending)
        if step == STEP_AWAITING_TYPE:
            return _prompt_for_type(pending, lang, prefix=add_reply or "")
        if add_reply:
            return f"{add_reply}\n\n{_prompt_for_contact(pending, lang) if step == STEP_AWAITING_CONTACT else _prompt_for_address(lang) if step == STEP_AWAITING_ADDRESS else _prompt_for_type(pending, lang)}"

    if step == STEP_AWAITING_TYPE:
        order_type = _parse_order_type_answer(text)
        if not order_type:
            return msg("order_type_pick", lang)
        pending["order_type"] = order_type
        pending["table_number"] = _parse_table_number(text) or pending.get("table_number")
        pending["step"] = STEP_AWAITING_CONTACT
        save_pending_order(ctx, pending)
        return _prompt_for_contact(pending, lang)

    if step == STEP_AWAITING_CONTACT:
        name, phone = _parse_name_and_phone(text)
        if not name and re.fullmatch(r"[А-ЯЁа-яA-Za-z\-]{2,40}", text.strip()):
            name = _clean_name(text.strip())
        if not phone:
            phone = _parse_phone(text)

        if name and not phone:
            pending["customer_name"] = name
            save_pending_order(ctx, pending)
            return msg("order_need_phone_only", lang, name=name)

        if phone and not name:
            name = _clean_name(pending.get("customer_name", ""))

        if not name or not phone:
            return msg("order_need_contact", lang)

        pending["customer_name"] = name
        pending["customer_phone"] = phone
        if pending.get("order_type") == "delivery":
            pending["step"] = STEP_AWAITING_ADDRESS
            save_pending_order(ctx, pending)
            return _prompt_for_address(lang)
        save_pending_order(ctx, pending)
        return _try_finalize(pending, ctx)

    if step == STEP_AWAITING_ADDRESS:
        address = text.strip()
        if len(address) < 5:
            return _prompt_for_address(lang)
        pending["delivery_address"] = address
        save_pending_order(ctx, pending)
        return _try_finalize(pending, ctx)

    return _prompt_for_type(pending, lang)


def _prompt_for_current_step(pending: dict, ctx: ActionContext) -> str | None:
    step = pending.get("step", STEP_AWAITING_TYPE)
    lang = _lang(pending, ctx)
    if step == STEP_AWAITING_TYPE:
        return _prompt_for_type(pending, lang)
    if step == STEP_AWAITING_CONTACT:
        name = _clean_name(pending.get("customer_name", ""))
        phone = (pending.get("customer_phone") or "").strip()
        if name and not phone:
            return msg("order_need_phone_only", lang, name=name)
        return _prompt_for_contact(pending, lang)
    if step == STEP_AWAITING_ADDRESS:
        return _prompt_for_address(lang)
    if step == "ready":
        return _try_finalize(pending, ctx)
    return None


def try_order_flow_reply(
    user_message: str,
    history: list[dict] | None,
    ctx: ActionContext | None = None,
) -> str | None:
    ctx = ctx or ActionContext()
    ctx.language = detect_guest_language(
        user_message,
        history,
        stored=ctx.language,
    )
    pending = load_pending_order(ctx)

    if pending:
        advanced = _advance_pending(pending, user_message, ctx)
        if advanced is not None:
            return advanced
        pending = load_pending_order(ctx)
        if pending:
            return _prompt_for_current_step(pending, ctx)
        return None

    from .guest_intent import is_dish_or_menu_question

    if is_dish_or_menu_question(user_message) or is_general_information_question(
        user_message
    ):
        return None

    req = parse_order_request(user_message)
    if req is None:
        return None

    pending = _pending_from_request(req, ctx)
    pending["language"] = ctx.language
    save_pending_order(ctx, pending)
    lang = _lang(pending, ctx)

    step = pending.get("step", STEP_AWAITING_TYPE)
    if step == STEP_AWAITING_TYPE:
        return _prompt_for_type(pending, lang)
    if step == STEP_AWAITING_CONTACT:
        return _prompt_for_contact(pending, lang)
    if step == STEP_AWAITING_ADDRESS:
        return _prompt_for_address(lang)
    if step == "ready":
        return _try_finalize(pending, ctx)
    return _prompt_for_type(pending, lang)
