"""Telegram: обработка обновлений и long polling для локальной разработки."""
from __future__ import annotations

import json
import logging
import time
import urllib.error

from .llm import AssistantLLMError
from .models import AssistantChatLog, AssistantSettings
from .services import (
    ask_assistant,
    delete_telegram_webhook,
    download_telegram_file,
    format_telegram_network_error,
    get_settings,
    send_assistant_reply_telegram,
    send_telegram_message,
    telegram_api,
    verify_telegram_connectivity,
)
from .voice import transcribe_audio

logger = logging.getLogger("apps.assistant")


def _guest_name(from_user: dict) -> str:
    return (
        f"{from_user.get('first_name', '')} {from_user.get('last_name', '')}".strip()
        or from_user.get("username", "")
    )


def process_telegram_update(cfg: AssistantSettings, update: dict) -> bool:
    """Обработать одно обновление Telegram. Возвращает True, если обработано."""
    message = update.get("message") or update.get("edited_message")
    if not message:
        return False

    chat_id = message["chat"]["id"]
    text = (message.get("text") or "").strip()

    if text in ("/start", "/help"):
        send_telegram_message(cfg.telegram_bot_token, chat_id, cfg.welcome_message, cfg)
        return True

    if not text and cfg.voice_messages_enabled and message.get("voice"):
        try:
            voice = message["voice"]
            audio = download_telegram_file(cfg.telegram_bot_token, voice["file_id"])
            text = transcribe_audio(
                audio,
                cfg,
                filename="voice.ogg",
                mime_type=voice.get("mime_type") or "audio/ogg",
            )
        except AssistantLLMError as exc:
            send_telegram_message(cfg.telegram_bot_token, chat_id, str(exc), cfg)
            return True

    if not text:
        return False

    from_user = message.get("from") or {}
    reply = ask_assistant(
        text,
        channel=AssistantChatLog.Channel.TELEGRAM,
        external_user_id=str(chat_id),
        guest_name=_guest_name(from_user),
    )
    try:
        send_assistant_reply_telegram(cfg, chat_id, reply)
    except Exception:
        logger.exception("Telegram send failed")
    return True


def telegram_get_updates(
    token: str,
    *,
    offset: int = 0,
    timeout: int = 30,
) -> dict:
    return telegram_api(
        token,
        "getUpdates",
        {
            "offset": offset,
            "timeout": timeout,
            "allowed_updates": ["message", "edited_message"],
        },
        timeout=timeout + 15,
    )


def run_telegram_polling(
    cfg: AssistantSettings | None = None,
    *,
    poll_timeout: int = 30,
    on_log=None,
) -> None:
    """Long polling — для localhost без webhook/ngrok."""
    cfg = cfg or get_settings()
    token = (cfg.telegram_bot_token or "").strip()
    if not token:
        raise RuntimeError("Не указан токен Telegram-бота.")
    if not cfg.telegram_enabled:
        raise RuntimeError("Telegram отключён в настройках ассистента.")
    if not cfg.is_enabled:
        raise RuntimeError("Ассистент выключен. Включите «Включить ассистента».")

    ok, msg = verify_telegram_connectivity(token)
    if not ok:
        raise RuntimeError(msg)
    if on_log:
        on_log(msg)

    ok, msg = delete_telegram_webhook(token)
    if on_log:
        on_log(msg if ok else f"Webhook: {msg}")

    offset = 0
    if on_log:
        on_log("Telegram polling запущен. Ожидаю сообщения… (Ctrl+C для остановки)")

    last_network_hint = ""
    while True:
        try:
            data = telegram_get_updates(token, offset=offset, timeout=poll_timeout)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            logger.warning("Telegram getUpdates HTTP %s: %s", exc.code, body[:200])
            if on_log:
                on_log(f"Ошибка Telegram API ({exc.code}). Повтор через 5 сек…")
            time.sleep(5)
            continue
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
            logger.warning("Telegram getUpdates failed: %s", exc)
            hint = format_telegram_network_error(exc)
            if on_log and hint != last_network_hint:
                on_log(hint)
                last_network_hint = hint
            elif on_log:
                on_log("Повтор подключения через 5 сек…")
            time.sleep(5)
            continue

        last_network_hint = ""

        if not data.get("ok"):
            description = data.get("description", "unknown error")
            logger.error("Telegram getUpdates: %s", description)
            if on_log:
                on_log(f"Ошибка getUpdates: {description}")
            time.sleep(5)
            continue

        for update in data.get("result") or []:
            offset = int(update["update_id"]) + 1
            try:
                process_telegram_update(cfg, update)
            except Exception:
                logger.exception("Telegram update processing failed")
