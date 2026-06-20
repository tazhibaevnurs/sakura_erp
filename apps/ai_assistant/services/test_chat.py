"""Тестовый диалог в ERP (без Telegram/WhatsApp)."""
from __future__ import annotations

from django.contrib.auth.models import User
from django.db import transaction

from ..channels.telegram_handler import TelegramHandler
from ..models import ClientProfile, Conversation, Message
from .helpers import build_order_history_reply
from .message_processor import process_user_message


TEST_CHANNEL = "web_test"
TEST_ID_PREFIX = "web-test-"


def test_client_id(user: User) -> str:
    return f"{TEST_ID_PREFIX}{user.pk}"


def get_test_client(user: User) -> ClientProfile:
    name = user.get_full_name() or user.username
    client, _ = ClientProfile.objects.get_or_create(
        telegram_id=test_client_id(user),
        defaults={
            "name": name,
            "phone": f"web-test-{user.pk}",
            "preferred_channel": TEST_CHANNEL,
        },
    )
    return client


def get_test_conversation(user: User) -> Conversation:
    client = get_test_client(user)
    conversation = (
        client.conversations.filter(
            channel=TEST_CHANNEL,
            status__in=["active", "waiting_confirm"],
        )
        .order_by("-updated_at")
        .first()
    )
    if conversation:
        return conversation
    return Conversation.objects.create(
        client=client,
        channel=TEST_CHANNEL,
        status="active",
    )


def get_test_messages(user: User) -> list[dict]:
    conversation = (
        Conversation.objects.filter(
            client__telegram_id=test_client_id(user),
            channel=TEST_CHANNEL,
        )
        .order_by("-updated_at")
        .first()
    )
    if not conversation:
        return []
    return [
        {
            "role": msg.role,
            "content": msg.content,
            "intent": msg.intent_detected,
            "created_at": msg.created_at.strftime("%H:%M"),
        }
        for msg in conversation.messages.order_by("created_at")
    ]


@transaction.atomic
def reset_test_conversation(user: User) -> None:
    client = get_test_client(user)
    Conversation.objects.filter(client=client, channel=TEST_CHANNEL).update(
        status="completed"
    )


def _response_payload(conversation: Conversation, **extra) -> dict:
    data = {
        "status": conversation.status,
        "status_display": conversation.get_status_display(),
        "conversation_id": conversation.pk,
        "draft_data": conversation.draft_data or {},
        "intent": conversation.current_intent,
    }
    data.update(extra)
    return data


def send_test_message(user: User, text: str) -> dict:
    text = (text or "").strip()
    if not text:
        return {"ok": False, "error": "Введите сообщение."}

    client = get_test_client(user)
    conversation = get_test_conversation(user)
    user_name = user.get_full_name() or user.username

    if text.startswith("/"):
        if text.startswith("/history"):
            cmd_reply = build_order_history_reply(client)
        else:
            cmd_reply = TelegramHandler().handle_command(text, test_client_id(user), user_name)

        if cmd_reply is not None:
            Message.objects.create(conversation=conversation, role="user", content=text)
            Message.objects.create(conversation=conversation, role="assistant", content=cmd_reply)
            if text.startswith("/order"):
                conversation.current_intent = "order"
                conversation.save(update_fields=["current_intent", "updated_at"])
            elif text.startswith("/booking"):
                conversation.current_intent = "booking"
                conversation.save(update_fields=["current_intent", "updated_at"])
            return {
                "ok": True,
                "reply": cmd_reply,
                "use_buttons": False,
                **_response_payload(conversation),
            }

    result = process_user_message(client=client, conversation=conversation, text=text)
    conversation.refresh_from_db()
    return {
        "ok": True,
        "reply": result.reply,
        "use_buttons": result.use_buttons,
        "tokens_used": result.tokens_used,
        "intent": result.intent or conversation.current_intent,
        "status": conversation.status,
        "status_display": conversation.get_status_display(),
        "draft_data": conversation.draft_data or {},
        "conversation_id": conversation.pk,
        "language": result.language or conversation.language or "ru",
    }
