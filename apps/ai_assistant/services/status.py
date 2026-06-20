"""Статус каналов и webhook для панели управления."""
from __future__ import annotations

import httpx
from django.conf import settings


def _mask(value: str, visible: int = 4) -> str:
    value = (value or "").strip()
    if not value:
        return "—"
    if len(value) <= visible * 2:
        return "••••"
    return f"{value[:visible]}…{value[-visible:]}"


def get_telegram_webhook_info() -> dict:
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        return {"configured": False, "url": "", "pending": 0, "error": "Токен не задан"}

    base_url = getattr(settings, "TELEGRAM_API_BASE_URL", "https://api.telegram.org")
    url = f"{base_url.rstrip('/')}/bot{token}/getWebhookInfo"
    try:
        response = httpx.get(url, timeout=15)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        return {"configured": True, "url": "", "pending": 0, "error": str(exc)}

    if not data.get("ok"):
        return {"configured": True, "url": "", "pending": 0, "error": data.get("description", "Ошибка API")}

    result = data.get("result") or {}
    return {
        "configured": True,
        "url": result.get("url") or "",
        "pending": result.get("pending_update_count", 0),
        "error": "",
    }


def get_assistant_status() -> dict:
    cfg = getattr(settings, "AI_ASSISTANT", {})
    public_url = getattr(settings, "ASSISTANT_PUBLIC_URL", "").strip().rstrip("/")
    expected_webhook = f"{public_url}/ai-assistant/webhook/telegram/" if public_url else ""

    telegram = get_telegram_webhook_info()
    webhook_ok = bool(
        telegram.get("url")
        and expected_webhook
        and telegram["url"].rstrip("/") == expected_webhook.rstrip("/")
    )

    return {
        "provider": cfg.get("PROVIDER", "gemini"),
        "ai_configured": bool(
            cfg.get("GEMINI_API_KEY") if cfg.get("PROVIDER", "gemini") == "gemini"
            else cfg.get("OPENAI_API_KEY")
        ),
        "openai_configured": bool(cfg.get("OPENAI_API_KEY")),
        "gemini_configured": bool(cfg.get("GEMINI_API_KEY")),
        "telegram_configured": bool(settings.TELEGRAM_BOT_TOKEN),
        "whatsapp_configured": bool(settings.WHATSAPP_ACCESS_TOKEN and settings.WHATSAPP_PHONE_NUMBER_ID),
        "instagram_configured": bool(settings.WHATSAPP_ACCESS_TOKEN),
        "public_url": public_url or "—",
        "expected_webhook": expected_webhook or "—",
        "business_phone": cfg.get("FALLBACK_PHONE") or "—",
        "business_name": cfg.get("BUSINESS_NAME") or "Сакура",
        "model": cfg.get("MODEL", "gemini-2.5-flash"),
        "telegram_token_masked": _mask(settings.TELEGRAM_BOT_TOKEN),
        "gemini_key_masked": _mask(cfg.get("GEMINI_API_KEY", "")),
        "openai_key_masked": _mask(cfg.get("OPENAI_API_KEY", "")),
        "telegram_webhook": telegram,
        "webhook_ok": webhook_ok,
        "celery_eager": getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False),
    }
