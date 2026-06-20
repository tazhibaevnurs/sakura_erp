"""Сериализация моделей для API и отладки (без DRF)."""

from .models import ClientProfile, Conversation, Message


def serialize_message(message: Message) -> dict:
    return {
        "id": message.pk,
        "role": message.role,
        "content": message.content,
        "intent_detected": message.intent_detected,
        "tokens_used": message.tokens_used,
        "created_at": message.created_at.isoformat(),
    }


def serialize_conversation(conversation: Conversation, *, include_messages: bool = False) -> dict:
    data = {
        "id": conversation.pk,
        "client_id": conversation.client_id,
        "channel": conversation.channel,
        "status": conversation.status,
        "current_intent": conversation.current_intent,
        "draft_data": conversation.draft_data,
        "created_at": conversation.created_at.isoformat(),
        "updated_at": conversation.updated_at.isoformat(),
    }
    if include_messages:
        data["messages"] = [
            serialize_message(m) for m in conversation.messages.order_by("created_at")
        ]
    return data


def serialize_client_profile(client: ClientProfile) -> dict:
    return {
        "id": client.pk,
        "telegram_id": client.telegram_id,
        "whatsapp_phone": client.whatsapp_phone,
        "instagram_id": client.instagram_id,
        "name": client.name,
        "phone": client.phone,
        "preferred_channel": client.preferred_channel,
        "preferred_order_type": client.preferred_order_type,
        "total_orders": client.total_orders,
        "last_interaction": client.last_interaction.isoformat(),
        "created_at": client.created_at.isoformat(),
    }
