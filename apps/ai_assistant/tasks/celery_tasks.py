import logging

from celery import shared_task
from django.conf import settings
from django.db import transaction

from ..channels.instagram_handler import InstagramHandler
from ..channels.telegram_handler import TelegramHandler
from ..channels.whatsapp_handler import WhatsAppHandler
from ..models import ClientProfile, Conversation, Message
from ..services.helpers import build_order_history_reply
from ..services.message_processor import process_user_message

logger = logging.getLogger("apps.ai_assistant")

HANDLERS = {
    "telegram": TelegramHandler,
    "whatsapp": WhatsAppHandler,
    "instagram": InstagramHandler,
}

CHANNEL_ID_FIELDS = {
    "telegram": "telegram_id",
    "whatsapp": "whatsapp_phone",
    "instagram": "instagram_id",
}


def _get_handler(channel: str):
    handler_cls = HANDLERS.get(channel)
    if handler_cls is None:
        raise ValueError(f"Unknown channel: {channel}")
    return handler_cls()


def _get_or_create_client(channel: str, channel_user_id: str, user_name: str = "") -> ClientProfile:
    field = CHANNEL_ID_FIELDS[channel]
    lookup = {field: channel_user_id}
    client, created = ClientProfile.objects.get_or_create(
        **lookup,
        defaults={"name": user_name, "preferred_channel": channel},
    )
    if not created:
        updates = {}
        if user_name and not client.name:
            updates["name"] = user_name
        if not client.preferred_channel:
            updates["preferred_channel"] = channel
        if updates:
            for key, value in updates.items():
                setattr(client, key, value)
            client.save(update_fields=list(updates.keys()))
    return client


def _get_or_create_conversation(client: ClientProfile, channel: str) -> Conversation:
    conversation = (
        client.conversations.filter(channel=channel, status__in=["active", "waiting_confirm"])
        .order_by("-updated_at")
        .first()
    )
    if conversation:
        return conversation
    return Conversation.objects.create(client=client, channel=channel, status="active")


@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def process_incoming_message(self, channel: str, raw_data: dict):
    try:
        handler = _get_handler(channel)
        parsed = handler.parse_incoming(raw_data)
        if not parsed:
            return

        channel_user_id = parsed["channel_user_id"]
        text = parsed.get("text", "")
        platform_message_id = parsed.get("platform_message_id", "")
        user_name = parsed.get("user_name", "")

        if not channel_user_id:
            return

        with transaction.atomic():
            client = _get_or_create_client(channel, channel_user_id, user_name)
            conversation = _get_or_create_conversation(client, channel)

            if platform_message_id:
                ids = list(conversation.platform_message_ids or [])
                if platform_message_id in ids:
                    return
                ids.append(platform_message_id)
                conversation.platform_message_ids = ids[-100:]
                conversation.save(update_fields=["platform_message_ids", "updated_at"])

            if channel == "telegram" and text.startswith("/"):
                cmd_reply = TelegramHandler().handle_command(text, channel_user_id, user_name)
                if cmd_reply is not None:
                    if text.startswith("/history"):
                        cmd_reply = build_order_history_reply(client)
                    Message.objects.create(conversation=conversation, role="user", content=text)
                    Message.objects.create(conversation=conversation, role="assistant", content=cmd_reply)
                    handler.send_message(channel_user_id, cmd_reply)
                    if text.startswith("/order"):
                        conversation.current_intent = "order"
                        conversation.save(update_fields=["current_intent", "updated_at"])
                    elif text.startswith("/booking"):
                        conversation.current_intent = "booking"
                        conversation.save(update_fields=["current_intent", "updated_at"])
                    return

            if not text:
                return

        result = process_user_message(client=client, conversation=conversation, text=text)

        if result.use_buttons:
            from ..services.language import confirmation_buttons

            conversation.refresh_from_db()
            lang = conversation.language or result.language or "ru"
            handler.send_with_buttons(
                channel_user_id,
                result.reply,
                confirmation_buttons(lang),
            )
        else:
            handler.send_message(channel_user_id, result.reply)

    except Exception as exc:
        logger.exception("process_incoming_message failed")
        raise self.retry(exc=exc)
