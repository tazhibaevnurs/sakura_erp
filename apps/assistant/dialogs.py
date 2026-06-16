"""Сводки и выборка диалогов ассистента."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Count, Max, Q

from .models import AssistantChannelState, AssistantChatLog

User = get_user_model()

CHANNEL_LABELS = {
    AssistantChatLog.Channel.TELEGRAM: "Telegram",
    AssistantChatLog.Channel.WHATSAPP: "WhatsApp",
    AssistantChatLog.Channel.WEB_TEST: "Тест на сайте",
}


def _guest_label(channel: str, external_user_id: str) -> str:
    if channel == AssistantChatLog.Channel.WEB_TEST and external_user_id.isdigit():
        user = User.objects.filter(pk=int(external_user_id)).first()
        if user:
            return user.get_full_name() or user.get_username()
        return f"Тест #{external_user_id}"
    if channel == AssistantChatLog.Channel.WHATSAPP:
        return f"+{external_user_id}" if not external_user_id.startswith("+") else external_user_id
    if channel == AssistantChatLog.Channel.TELEGRAM:
        return f"Chat {external_user_id}"
    return external_user_id or "—"


def get_dialog_summaries(
    *,
    channel: str = "",
    search: str = "",
    page: int = 1,
    per_page: int = 30,
):
    qs = AssistantChatLog.objects.all()
    if channel:
        qs = qs.filter(channel=channel)
    if search:
        qs = qs.filter(
            Q(user_message__icontains=search)
            | Q(assistant_reply__icontains=search)
            | Q(external_user_id__icontains=search)
        )

    groups = (
        qs.values("channel", "external_user_id")
        .annotate(message_count=Count("pk"), last_at=Max("created_at"))
        .order_by("-last_at")
    )

    paginator = Paginator(groups, per_page)
    page_obj = paginator.get_page(page)

    channel_keys = {(row["channel"], row["external_user_id"]) for row in page_obj.object_list}
    states = {
        (s.channel, s.external_user_id): s
        for s in AssistantChannelState.objects.filter(
            channel__in={k[0] for k in channel_keys},
            external_user_id__in={k[1] for k in channel_keys},
        )
    }

    summaries = []
    for row in page_obj.object_list:
        key = (row["channel"], row["external_user_id"])
        last_log = (
            qs.filter(channel=key[0], external_user_id=key[1])
            .order_by("-created_at")
            .first()
        )
        state = states.get(key)
        summaries.append(
            {
                "channel": row["channel"],
                "channel_label": CHANNEL_LABELS.get(row["channel"], row["channel"]),
                "external_user_id": row["external_user_id"],
                "guest_label": _guest_label(row["channel"], row["external_user_id"]),
                "message_count": row["message_count"],
                "last_at": row["last_at"],
                "last_user_message": last_log.user_message if last_log else "",
                "last_assistant_reply": last_log.assistant_reply if last_log else "",
                "is_paused": bool(state and state.ai_paused_until),
                "has_pending_order": bool(state and state.pending_order_json),
            }
        )

    return page_obj, summaries


def get_dialog_messages(channel: str, external_user_id: str):
    return list(
        AssistantChatLog.objects.filter(
            channel=channel,
            external_user_id=external_user_id,
        ).order_by("created_at")
    )


def get_dialog_state(channel: str, external_user_id: str) -> AssistantChannelState | None:
    return AssistantChannelState.objects.filter(
        channel=channel,
        external_user_id=external_user_id,
    ).first()
