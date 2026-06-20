"""Обработка сообщения пользователя (общая логика для Celery и тестового чата)."""
from __future__ import annotations

from dataclasses import dataclass, field

from django.conf import settings
from django.db import transaction

from ..models import ClientProfile, Conversation, Message
from .ai_engine import AIEngine, AIEngineError
from .booking_hints import extract_booking_hints
from .booking_service import BookingService
from .draft_flow import (
    build_confirmation_summary,
    detect_flow,
    draft_for_create,
    get_missing_fields,
    missing_fields_message,
    next_field_question,
    normalize_order_type,
    normalize_user_action,
)
from .language import ensure_conversation_language, reply_has_confirmation, resolve_conversation_language
from .order_service import OrderService


def merge_draft(existing: dict, extracted: dict) -> dict:
    merged = dict(existing or {})
    for key, value in (extracted or {}).items():
        if value is not None and value != "":
            if key == "items" and isinstance(value, list):
                merged["items"] = value
            elif key == "type":
                normalized = normalize_order_type(value)
                if normalized:
                    merged["type"] = normalized
            elif key in ("table_number", "table", "cabin", "booth"):
                from .booking_service import parse_table_number

                parsed = parse_table_number({key: value})
                if parsed is not None:
                    merged["table_number"] = parsed
            else:
                merged[key] = value
    return merged


@dataclass
class ProcessResult:
    reply: str
    intent: str = ""
    action_required: str | None = None
    tokens_used: int = 0
    use_buttons: bool = False
    conversation_id: int = 0
    draft_data: dict = field(default_factory=dict)
    status: str = "active"
    language: str = "ru"


def _fallback_phone() -> str:
    return settings.AI_ASSISTANT.get("FALLBACK_PHONE", "")


def _user_lang(conversation: Conversation, text: str) -> str:
    lang = resolve_conversation_language(conversation, text)
    return ensure_conversation_language(conversation, lang)


def _simple_offline_reply(text: str, lang: str) -> str | None:
    t = (text or "").strip().lower()
    if lang == "ky" or t in {"салам", "саламатсызбы", "salamatsizby", "саламат"}:
        return (
            "Саламатсызбы! 🍵\n"
            "Мен «Сакура» чайханасынын жардамчысымын.\n"
            "Заказ, бронь, меню боюнча жардам берем.\n\n"
            "Командалар: /order /booking /history /help"
        )
    if t in {"привет", "здравствуйте", "hello", "hi"}:
        return (
            "Здравствуйте! 🍵\n"
            "Я помощник чайханы «Сакура».\n"
            "Могу принять заказ, забронировать стол или рассказать о меню.\n\n"
            "Команды: /order /booking /history /help"
        )
    return None


def _apply_create_result(
    *,
    client: ClientProfile,
    conversation: Conversation,
    reply: str,
    action: str,
    draft: dict,
    lang: str = "ru",
) -> tuple[str, str]:
    """Создать заказ или бронь. Возвращает (reply, status)."""
    if action == "create_order":
        order_result = OrderService().create_from_draft(client, draft)
        if order_result.get("status") == "created":
            if lang == "ky":
                reply += (
                    f"\n\n✅ Заказ #{order_result['order_id']} кабыл алынды! "
                    f"Жалпы: {order_result['total']} сом."
                )
            else:
                reply += (
                    f"\n\n✅ Заказ #{order_result['order_id']} принят! "
                    f"Итого: {order_result['total']} сом."
                )
            return reply, "completed"
        if order_result.get("status") == "error":
            default = (
                "Заказ түзүлбөй калды."
                if lang == "ky"
                else "Не удалось создать заказ."
            )
            reply += f"\n\n⚠️ {order_result.get('message', default)}"
            return reply, "waiting_confirm"

    if action == "create_booking":
        booking_result = BookingService().create_from_draft(client, draft)
        if booking_result.get("status") == "confirmed":
            table_num = booking_result.get("table_number", "")
            if lang == "ky":
                reply += f"\n\n✅ Бронь #{booking_result['booking_id']} тастыкталды!"
                if table_num:
                    reply += f" Кабина №{table_num}."
            else:
                reply += f"\n\n✅ Бронь #{booking_result['booking_id']} подтверждена!"
                if table_num:
                    reply += f" Кабинка №{table_num}."
            return reply, "completed"
        if booking_result.get("status") == "unavailable":
            msg = booking_result.get("message")
            default = (
                "Бул убакка бош орун жок. Башка убакыт сунуштайсызбы?"
                if lang == "ky"
                else "К сожалению, на это время нет свободных мест. Предложите другое время?"
            )
            reply += f"\n\n😔 {msg or default}"
            return reply, "active"
        if booking_result.get("status") == "error":
            default = (
                "Бронь түзүлбөй калды."
                if lang == "ky"
                else "Не удалось создать бронь."
            )
            reply += f"\n\n⚠️ {booking_result.get('message', default)}"
            return reply, "waiting_confirm"

    return reply, conversation.status


def _save_assistant_message(conversation, reply, intent, tokens_used=0):
    Message.objects.create(
        conversation=conversation,
        role="assistant",
        content=reply,
        intent_detected=intent,
        tokens_used=tokens_used,
    )


@transaction.atomic
def process_user_message(
    *,
    client: ClientProfile,
    conversation: Conversation,
    text: str,
) -> ProcessResult:
    Message.objects.create(conversation=conversation, role="user", content=text)

    lang = _user_lang(conversation, text)
    booking_hints = extract_booking_hints(text)
    if booking_hints:
        conversation.draft_data = merge_draft(conversation.draft_data, booking_hints)
        if any(k in booking_hints for k in ("date", "time", "table_number", "guests")):
            conversation.current_intent = "booking"

    user_action = normalize_user_action(text)

    if user_action == "cancel":
        conversation.draft_data = {}
        conversation.status = "active"
        conversation.current_intent = ""
        conversation.save(update_fields=["draft_data", "status", "current_intent", "updated_at"])
        reply = (
            "Жок, токтоттум. Дагы кандай жардам берейин?"
            if lang == "ky"
            else "Хорошо, отменил оформление. Чем ещё помочь? 🍵"
        )
        _save_assistant_message(conversation, reply, "cancel")
        return ProcessResult(
            reply=reply,
            intent="cancel",
            conversation_id=conversation.pk,
            status=conversation.status,
            language=lang,
        )

    flow = detect_flow(conversation.draft_data, conversation.current_intent)

    if user_action == "confirm" and flow:
        missing = get_missing_fields(conversation.draft_data, client, flow)
        if missing:
            reply = missing_fields_message(missing, lang)
            next_q = next_field_question(
                missing, flow, lang, draft=conversation.draft_data, reply=reply
            )
            if next_q:
                reply = f"{reply}\n\n{next_q}"
            conversation.status = "active"
            conversation.save(update_fields=["status", "updated_at"])
            _save_assistant_message(conversation, reply, "confirm")
            return ProcessResult(
                reply=reply,
                intent="confirm",
                conversation_id=conversation.pk,
                draft_data=conversation.draft_data or {},
                status=conversation.status,
                language=lang,
            )

        draft = draft_for_create(conversation.draft_data, client)
        action = "create_order" if flow.startswith("order") else "create_booking"
        reply = (
            "Жакшы, даярдап жатам…"
            if lang == "ky"
            else "Отлично, оформляю…"
        )
        reply, new_status = _apply_create_result(
            client=client,
            conversation=conversation,
            reply=reply,
            action=action,
            draft=draft,
            lang=lang,
        )
        conversation.status = new_status
        if new_status == "completed":
            conversation.draft_data = {}
            conversation.current_intent = ""
        conversation.save(
            update_fields=["draft_data", "status", "current_intent", "updated_at"]
        )
        _save_assistant_message(conversation, reply, "confirm")
        return ProcessResult(
            reply=reply,
            intent="confirm",
            action_required=action,
            conversation_id=conversation.pk,
            draft_data=conversation.draft_data or {},
            status=conversation.status,
            language=lang,
        )

    try:
        engine = AIEngine()
        result = engine.get_response(conversation, text)
    except AIEngineError:
        phone = _fallback_phone()
        flow = detect_flow(conversation.draft_data, conversation.current_intent)
        missing = get_missing_fields(conversation.draft_data, client, flow) if flow else []
        offline = _simple_offline_reply(text, lang)
        if offline:
            reply = offline
        elif flow and missing:
            prefix = (
                "ИИ менен байланышуу мүмкүн эмес. "
                if lang == "ky"
                else "Не удалось связаться с ИИ. "
            )
            reply = prefix + missing_fields_message(missing, lang)
            next_q = next_field_question(
                missing, flow, lang, draft=conversation.draft_data, reply=reply
            )
            if next_q:
                reply = f"{reply}\n\n{next_q}"
        else:
            reply = (
                (
                    "Азыр ИИ менен байланышуу мүмкүн эмес (API чеги же жүктөө). "
                    f"Бир мүнөттөн кийин кайра аракет кылыңыз же чалыңыз: {phone}"
                )
                if lang == "ky"
                else (
                    "Сейчас не получается связаться с ИИ (лимит API или перегрузка). "
                    f"Попробуйте через минуту или позвоните: {phone}"
                )
            )
        _save_assistant_message(conversation, reply, conversation.current_intent or "other")
        return ProcessResult(
            reply=reply,
            conversation_id=conversation.pk,
            draft_data=conversation.draft_data or {},
            status=conversation.status,
            language=lang,
        )

    reply = result["reply"]
    intent = result.get("intent", "")
    extracted = result.get("extracted_data") or {}
    tokens_used = result.get("tokens_used", 0)

    if intent in ("order", "booking"):
        conversation.current_intent = intent
    elif intent == "cancel":
        conversation.draft_data = {}
        conversation.status = "active"
        conversation.current_intent = ""
        conversation.save(
            update_fields=["current_intent", "draft_data", "status", "updated_at"]
        )
        _save_assistant_message(conversation, reply, intent, tokens_used)
        return ProcessResult(
            reply=reply,
            intent=intent,
            conversation_id=conversation.pk,
            status=conversation.status,
            language=lang,
        )

    conversation.draft_data = merge_draft(conversation.draft_data, extracted)
    flow = detect_flow(conversation.draft_data, conversation.current_intent)
    missing = get_missing_fields(conversation.draft_data, client, flow) if flow else []

    action_required = None
    use_buttons = False
    confirmed = user_action == "confirm" or intent == "confirm"

    if flow and not missing:
        summary = build_confirmation_summary(conversation.draft_data, client, flow, lang)
        if confirmed:
            action_required = "create_order" if flow.startswith("order") else "create_booking"
            conversation.status = "active"
        else:
            conversation.status = "waiting_confirm"
            if summary and summary not in reply and not reply_has_confirmation(reply, lang):
                reply = f"{reply.rstrip()}\n\n{summary}".strip()
            use_buttons = True
    elif flow and missing:
        conversation.status = "active"
        next_q = next_field_question(
            missing, flow, lang, draft=conversation.draft_data, reply=reply
        )
        if next_q and next_q not in reply:
            reply = f"{reply.rstrip()}\n\n{next_q}".strip()
    else:
        conversation.status = "active"

    if action_required:
        draft = draft_for_create(conversation.draft_data, client)
        reply, new_status = _apply_create_result(
            client=client,
            conversation=conversation,
            reply=reply,
            action=action_required,
            draft=draft,
            lang=lang,
        )
        conversation.status = new_status
        if new_status == "completed":
            conversation.draft_data = {}
            conversation.current_intent = ""
        use_buttons = False

    conversation.save(
        update_fields=["current_intent", "draft_data", "status", "updated_at"]
    )

    _save_assistant_message(conversation, reply, intent, tokens_used)

    use_buttons = (
        use_buttons
        or (
            conversation.status == "waiting_confirm"
            and not action_required
            and bool(conversation.draft_data)
        )
    )

    return ProcessResult(
        reply=reply,
        intent=intent or conversation.current_intent,
        action_required=action_required,
        tokens_used=tokens_used,
        use_buttons=use_buttons,
        conversation_id=conversation.pk,
        draft_data=conversation.draft_data or {},
        status=conversation.status,
        language=lang,
    )
