"""Контроль вмешательства оператора в диалог."""
from datetime import timedelta

from django.utils import timezone

from .models import AssistantChannelState, AssistantSettings


def _keywords_list(cfg: AssistantSettings) -> list[str]:
    raw = (cfg.operator_handoff_keywords or "").strip()
    if not raw:
        return []
    return [w.strip().lower() for w in raw.split(",") if w.strip()]


def looks_like_operator_request(text: str, cfg: AssistantSettings) -> bool:
    if not cfg.operator_handoff_enabled:
        return False
    lowered = text.lower()
    return any(word in lowered for word in _keywords_list(cfg))


def is_channel_paused(channel: str, external_user_id: str) -> bool:
    if not channel or not external_user_id:
        return False
    state = AssistantChannelState.objects.filter(
        channel=channel,
        external_user_id=external_user_id,
    ).first()
    if not state or not state.ai_paused_until:
        return False
    if state.ai_paused_until <= timezone.now():
        state.ai_paused_until = None
        state.save(update_fields=["ai_paused_until", "updated_at"])
        return False
    return True


def pause_channel_for_operator(
    channel: str,
    external_user_id: str,
    cfg: AssistantSettings,
) -> None:
    until = timezone.now() + timedelta(minutes=max(1, cfg.operator_pause_minutes))
    state, _ = AssistantChannelState.objects.get_or_create(
        channel=channel,
        external_user_id=external_user_id,
    )
    state.ai_paused_until = until
    state.operator_requested_at = timezone.now()
    state.save(update_fields=["ai_paused_until", "operator_requested_at", "updated_at"])
