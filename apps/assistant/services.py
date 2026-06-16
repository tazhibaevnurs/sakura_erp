import json
import logging
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse

from django.conf import settings as django_settings
from django.urls import reverse
from django.utils import timezone

from .actions import ActionContext
from .formatting import apply_reply_format, split_message
from .operator import (
    is_channel_paused,
    looks_like_operator_request,
    pause_channel_for_operator,
)
from .order_flow import clear_pending_order, try_order_flow_reply
from .parsing import try_direct_availability_reply, try_direct_booking_reply
from .llm import (
    AssistantLLMError,
    GEMINI_MODEL_ALIASES,
    _default_model,
    _resolve_api_key,
    _resolve_gemini_model,
    generate_reply,
)
from .guest_intent import build_llm_context_note, should_clear_pending_for_llm
from .language import msg, resolve_language, try_direct_greeting_reply
from .menu_format import format_menu_for_guest, looks_like_menu_request, parse_menu_category_filter
from .menu_items import menu_item_availability_reply
from .order_draft_sync import sync_order_draft
from .models import AssistantChatLog, AssistantSettings

logger = logging.getLogger("apps.assistant")



def _upgrade_deprecated_gemini_model(cfg: AssistantSettings) -> None:
    if cfg.ai_provider != AssistantSettings.AIProvider.GEMINI:
        return
    model = (cfg.ai_model or "").strip()
    alias = GEMINI_MODEL_ALIASES.get(model)
    if alias and alias != model:
        cfg.ai_model = alias
        cfg.save(update_fields=["ai_model", "updated_at"])


def get_settings() -> AssistantSettings:
    obj = AssistantSettings.objects.first()
    if not obj:
        obj = AssistantSettings.objects.create()
    _upgrade_deprecated_gemini_model(obj)
    return obj


def _looks_sensitive(text: str) -> bool:
    lowered = text.lower()
    blocked = (
        "выручк", "прибыл", "расход", "касс", "зарплат", "долг",
        "сколько заработ", "оборот", "финанс",
    )
    return any(word in lowered for word in blocked)


def get_assistant_status(cfg: AssistantSettings | None = None) -> dict:
    cfg = cfg or get_settings()
    issues = []
    if not cfg.is_enabled:
        issues.append("Ассистент выключен (включите «Включить ассистента»).")
    if not _resolve_api_key(cfg):
        if cfg.ai_provider == AssistantSettings.AIProvider.GEMINI:
            issues.append("Не указан Gemini API key.")
        else:
            issues.append("Не указан API-ключ ИИ.")
    if cfg.ai_provider == AssistantSettings.AIProvider.GEMINI:
        model = _resolve_gemini_model(cfg)
    else:
        model = _default_model(cfg)

    if cfg.telegram_enabled and cfg.telegram_bot_token:
        if not cfg.is_enabled:
            issues.append("Telegram включён, но ассистент выключен — бот не отвечает.")
        webhook = get_telegram_webhook_status(cfg)
        if webhook.get("is_local"):
            issues.append(
                "Локально запустите polling: python manage.py run_telegram_bot "
                "(в отдельном терминале, рядом с runserver)."
            )
        elif webhook.get("last_error"):
            issues.append(f"Telegram webhook: {webhook['last_error']}")
        elif webhook.get("configured_url") and webhook.get("configured_url") != webhook.get("url"):
            issues.append(
                "Webhook в Telegram не совпадает с текущим URL — нажмите «Подключить Telegram»."
            )

    return {
        "is_enabled": cfg.is_enabled,
        "has_api_key": bool(_resolve_api_key(cfg)),
        "provider": cfg.get_ai_provider_display(),
        "model": model,
        "temperature": cfg.ai_temperature,
        "voice_enabled": cfg.voice_messages_enabled,
        "operator_handoff": cfg.operator_handoff_enabled,
        "ready_for_guests": cfg.is_enabled and bool(_resolve_api_key(cfg)),
        "ready_for_test": bool(_resolve_api_key(cfg)),
        "issues": issues,
    }


def _is_within_business_hours(cfg: AssistantSettings) -> bool:
    if not cfg.business_hours_only:
        return True
    now = timezone.localtime()
    return 10 <= now.hour < 23


def _deterministic_fallback(
    user_message: str,
    history: list[dict] | None,
    action_ctx: ActionContext,
    cfg: AssistantSettings,
    lang: str,
) -> str | None:
    if cfg.accept_orders_enabled:
        sync_order_draft(action_ctx, user_message, history, lang=lang)
        if order := try_order_flow_reply(user_message, history, action_ctx):
            return order

    if booking := try_direct_booking_reply(user_message, history, action_ctx):
        return booking
    if direct := try_direct_availability_reply(user_message):
        return direct
    if item := menu_item_availability_reply(user_message, lang):
        return item
    if looks_like_menu_request(user_message):
        return format_menu_for_guest(
            cfg,
            category_filter=parse_menu_category_filter(user_message),
            language=lang,
        )
    if greeting := try_direct_greeting_reply(user_message):
        return greeting
    return None


def ask_assistant(
    user_message: str,
    *,
    channel: str,
    external_user_id: str = "",
    history: list[dict] | None = None,
    allow_when_disabled: bool = False,
    guest_name: str = "",
    guest_phone: str = "",
) -> str:
    cfg = get_settings()
    if not cfg.is_enabled and not allow_when_disabled:
        return "Ассистент временно недоступен. Позвоните в ресторан."

    if channel and external_user_id and is_channel_paused(channel, external_user_id):
        return cfg.operator_handoff_message

    if not _is_within_business_hours(cfg):
        return cfg.off_hours_message or "Сейчас ресторан закрыт."

    if looks_like_operator_request(user_message, cfg):
        if channel and external_user_id:
            pause_channel_for_operator(channel, external_user_id, cfg)
        reply = cfg.operator_handoff_message
        _log_chat(channel, external_user_id, user_message, reply)
        return apply_reply_format(reply, cfg)

    if not _resolve_api_key(cfg):
        if cfg.ai_provider == AssistantSettings.AIProvider.GEMINI:
            return "Не настроен Gemini API key. Укажите ключ в настройках ассистента."
        return "Не настроен API-ключ ИИ. Укажите ключ в настройках ассистента."

    history_limit = max(1, int(cfg.max_history_turns or 8))
    if history is None and channel and external_user_id:
        history = get_chat_history(channel, external_user_id, limit=history_limit)

    action_ctx = ActionContext(
        channel=channel,
        external_user_id=external_user_id,
        guest_phone=guest_phone,
        guest_name=guest_name,
    )
    lang = resolve_language(action_ctx, user_message, history)
    action_ctx.language = lang

    if cfg.response_delay_ms:
        time.sleep(min(cfg.response_delay_ms, 10000) / 1000)

    if _looks_sensitive(user_message):
        reply = msg("financial_refusal", lang)
    else:
        if cfg.accept_orders_enabled:
            sync_order_draft(action_ctx, user_message, history, lang=lang)

        if should_clear_pending_for_llm(user_message, action_ctx):
            clear_pending_order(action_ctx)

        reply = None
        try:
            reply = generate_reply(
                cfg,
                user_message + build_llm_context_note(action_ctx),
                history=history,
                action_ctx=action_ctx,
            )
        except AssistantLLMError as exc:
            logger.warning("Assistant LLM failed: %s", exc)

        if not reply or not reply.strip():
            reply = _deterministic_fallback(
                user_message, history, action_ctx, cfg, lang
            )

        if not reply:
            reply = msg("assistant_retry", lang)

    reply = apply_reply_format(reply, cfg)
    _log_chat(channel, external_user_id, user_message, reply)
    return reply


def _log_chat(channel: str, external_user_id: str, user_message: str, reply: str) -> None:
    AssistantChatLog.objects.create(
        channel=channel or AssistantChatLog.Channel.WEB_TEST,
        external_user_id=external_user_id,
        user_message=user_message[:2000],
        assistant_reply=reply[:4000],
    )


def get_chat_history(channel: str, external_user_id: str, limit: int = 8) -> list[dict]:
    logs = (
        AssistantChatLog.objects.filter(channel=channel, external_user_id=external_user_id)
        .order_by("-created_at")[:limit]
    )
    history = []
    for log in reversed(list(logs)):
        history.append({"role": "user", "content": log.user_message})
        history.append({"role": "assistant", "content": log.assistant_reply})
    return history


def format_telegram_network_error(exc: BaseException) -> str:
    err = str(exc).lower()
    if "getaddrinfo" in err or "11001" in err or "name or service not known" in err:
        return (
            "Не удаётся найти api.telegram.org (ошибка DNS). "
            "Проверьте интернет, перезагрузите Wi‑Fi или включите VPN — "
            "без доступа к Telegram API polling не работает."
        )
    if "timed out" in err or "timeout" in err:
        return "Таймаут соединения с Telegram. Проверьте интернет или VPN."
    if "certificate" in err or "ssl" in err:
        return "Ошибка SSL при подключении к Telegram. Проверьте дату/время на ПК."
    return f"Сеть Telegram недоступна: {exc}"


def telegram_api(
    token: str,
    method: str,
    payload: dict | None = None,
    *,
    timeout: int = 30,
) -> dict:
    base = getattr(django_settings, "TELEGRAM_API_BASE_URL", "https://api.telegram.org")
    url = f"{base.rstrip('/')}/bot{token}/{method}"
    data = json.dumps(payload or {}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def verify_telegram_connectivity(token: str) -> tuple[bool, str]:
    """Проверка токена и доступности Telegram API."""
    try:
        result = telegram_api(token, "getMe", timeout=15)
        if result.get("ok"):
            username = (result.get("result") or {}).get("username", "")
            if username:
                return True, f"Бот @{username} доступен"
            return True, "Telegram API доступен"
        return False, result.get("description", "Ошибка getMe")
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            return False, "Неверный токен бота. Проверьте токен в настройках ассистента."
        body = exc.read().decode("utf-8", errors="replace")
        return False, f"Telegram API HTTP {exc.code}: {body[:200]}"
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
        return False, format_telegram_network_error(exc)


def send_telegram_typing(token: str, chat_id: int | str) -> None:
    try:
        telegram_api(token, "sendChatAction", {"chat_id": chat_id, "action": "typing"})
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError):
        pass


def send_telegram_message(
    token: str,
    chat_id: int | str,
    text: str,
    cfg: AssistantSettings | None = None,
) -> None:
    cfg = cfg or get_settings()
    parts = split_message(text, 4000) if cfg.split_long_messages else [text[:4096]]
    payload_base: dict = {"chat_id": chat_id}
    if cfg.reply_format == AssistantSettings.ReplyFormat.MARKDOWN:
        payload_base["parse_mode"] = "Markdown"
    elif cfg.reply_format == AssistantSettings.ReplyFormat.TELEGRAM_HTML:
        payload_base["parse_mode"] = "HTML"
    for part in parts:
        telegram_api(token, "sendMessage", {**payload_base, "text": part})


def download_telegram_file(token: str, file_id: str) -> bytes:
    from .llm import AssistantLLMError as LLMError

    meta = telegram_api(token, "getFile", {"file_id": file_id})
    file_path = meta.get("result", {}).get("file_path")
    if not file_path:
        raise LLMError("Не удалось получить голосовой файл Telegram.")
    url = f"https://api.telegram.org/file/bot{token}/{file_path}"
    base = getattr(django_settings, "TELEGRAM_API_BASE_URL", "https://api.telegram.org")
    if base.rstrip("/") != "https://api.telegram.org":
        url = url.replace("https://api.telegram.org", base.rstrip("/"), 1)
    with urllib.request.urlopen(url, timeout=60) as resp:
        return resp.read()


def send_assistant_reply_telegram(cfg: AssistantSettings, chat_id: int | str, reply: str) -> None:
    if cfg.typing_indicator_enabled:
        send_telegram_typing(cfg.telegram_bot_token, chat_id)
    send_telegram_message(cfg.telegram_bot_token, chat_id, reply, cfg)


def send_assistant_reply_whatsapp(cfg: AssistantSettings, to: str, reply: str) -> None:
    parts = split_message(reply, 4000) if cfg.split_long_messages else [reply[:4096]]
    for part in parts:
        send_whatsapp_message(cfg, to, part)


def _public_base_url(request) -> str:
    public = getattr(django_settings, "ASSISTANT_PUBLIC_URL", "").strip().rstrip("/")
    if public:
        return public
    return request.build_absolute_uri("/").rstrip("/")


def is_local_webhook_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    if not host:
        return True
    if host in {"127.0.0.1", "localhost", "::1"}:
        return True
    if host.startswith("192.168.") or host.startswith("10.") or host.endswith(".local"):
        return True
    return False


def validate_webhook_url(url: str) -> tuple[bool, str]:
    parsed = urlparse(url)
    if is_local_webhook_url(url):
        return (
            False,
            "Webhook не может быть localhost — Telegram не достучится до вашего компьютера. "
            "Укажите ASSISTANT_PUBLIC_URL в .env (ngrok или домен сервера) и переподключите бота.",
        )
    if parsed.scheme != "https":
        return (
            False,
            "Telegram принимает только HTTPS webhook. Используйте https://…",
        )
    return True, ""


def get_telegram_webhook_info(token: str) -> dict:
    if not token:
        return {}
    try:
        result = telegram_api(token, "getWebhookInfo", {})
        return result.get("result") or {}
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError):
        return {}


def get_telegram_webhook_status(cfg: AssistantSettings, request=None) -> dict:
    path = reverse("assistant:telegram_webhook")
    if request is not None:
        url = _public_base_url(request) + path
    elif cfg.telegram_bot_token:
        info = get_telegram_webhook_info(cfg.telegram_bot_token)
        url = info.get("url") or ""
        if not url:
            public = getattr(django_settings, "ASSISTANT_PUBLIC_URL", "").strip().rstrip("/")
            url = f"{public}{path}" if public else ""
    else:
        url = ""

    info = get_telegram_webhook_info(cfg.telegram_bot_token) if cfg.telegram_bot_token else {}
    configured_url = info.get("url") or ""
    last_error = info.get("last_error_message") or ""
    local = is_local_webhook_url(url) if url else True
    public_url_set = bool(getattr(django_settings, "ASSISTANT_PUBLIC_URL", "").strip())

    return {
        "url": url,
        "configured_url": configured_url,
        "is_local": local,
        "public_url_set": public_url_set,
        "pending_updates": info.get("pending_update_count", 0),
        "last_error": last_error,
        "last_error_date": info.get("last_error_date"),
        "ok": bool(
            cfg.telegram_bot_token
            and not local
            and configured_url
            and configured_url.rstrip("/") == url.rstrip("/")
            and not last_error
        ),
    }


def delete_telegram_webhook(token: str, *, drop_pending_updates: bool = False) -> tuple[bool, str]:
    if not token:
        return False, "Токен не указан"
    try:
        result = telegram_api(
            token,
            "deleteWebhook",
            {"drop_pending_updates": drop_pending_updates},
        )
        if result.get("ok"):
            return True, "Webhook отключён — режим polling активен"
        return False, result.get("description", "Ошибка deleteWebhook")
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
        return False, format_telegram_network_error(exc)


def setup_telegram_webhook(token: str, webhook_url: str) -> tuple[bool, str]:
    ok, message = validate_webhook_url(webhook_url)
    if not ok:
        return False, message
    try:
        result = telegram_api(token, "setWebhook", {"url": webhook_url})
        if result.get("ok"):
            return True, f"Webhook Telegram установлен: {webhook_url}"
        return False, result.get("description", "Ошибка Telegram")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(body)
            return False, data.get("description", body[:200])
        except json.JSONDecodeError:
            return False, body[:200]
    except (urllib.error.URLError, json.JSONDecodeError) as exc:
        return False, str(exc)


def get_webhook_urls(request) -> dict:
    base = _public_base_url(request)
    return {
        "telegram": base + reverse("assistant:telegram_webhook"),
        "whatsapp": base + reverse("assistant:whatsapp_webhook"),
    }


def download_whatsapp_media(cfg: AssistantSettings, media_id: str) -> bytes:
    from .llm import AssistantLLMError as LLMError

    if not cfg.whatsapp_access_token:
        raise LLMError("WhatsApp не настроен")
    meta_url = f"https://graph.facebook.com/v19.0/{media_id}"
    req = urllib.request.Request(
        meta_url,
        headers={"Authorization": f"Bearer {cfg.whatsapp_access_token}"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        meta = json.loads(resp.read().decode("utf-8"))
    media_url = meta.get("url")
    if not media_url:
        raise LLMError("Не удалось получить голосовой файл WhatsApp.")
    req = urllib.request.Request(
        media_url,
        headers={"Authorization": f"Bearer {cfg.whatsapp_access_token}"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def send_whatsapp_message(cfg: AssistantSettings, to: str, text: str) -> None:
    if not (cfg.whatsapp_access_token and cfg.whatsapp_phone_number_id):
        raise AssistantLLMError("WhatsApp не настроен")
    url = (
        f"https://graph.facebook.com/v19.0/{cfg.whatsapp_phone_number_id}/messages"
    )
    payload = json.dumps(
        {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": text[:4096]},
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cfg.whatsapp_access_token}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        json.loads(resp.read().decode("utf-8"))
