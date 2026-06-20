import logging

import httpx
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

logger = logging.getLogger("apps.ai_assistant")


class Command(BaseCommand):
    help = "Зарегистрировать Telegram webhook для ИИ-ассистента"

    def handle(self, *args, **options):
        token = settings.TELEGRAM_BOT_TOKEN
        if not token:
            raise CommandError("TELEGRAM_BOT_TOKEN не задан в .env")

        public_url = getattr(settings, "ASSISTANT_PUBLIC_URL", "").strip().rstrip("/")
        if not public_url:
            raise CommandError(
                "ASSISTANT_PUBLIC_URL не задан. Пример: https://your-domain.com"
            )

        webhook_url = f"{public_url}/ai-assistant/webhook/telegram/"
        base_url = getattr(settings, "TELEGRAM_API_BASE_URL", "https://api.telegram.org")
        api_url = f"{base_url}/bot{token}/setWebhook"

        payload = {"url": webhook_url}
        secret = settings.TELEGRAM_WEBHOOK_SECRET
        if secret:
            payload["secret_token"] = secret

        self.stdout.write(f"Регистрация webhook: {webhook_url}")

        try:
            response = httpx.post(api_url, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
        except Exception as exc:
            raise CommandError(f"Ошибка Telegram API: {exc}") from exc

        if not result.get("ok"):
            raise CommandError(f"Telegram вернул ошибку: {result}")

        self.stdout.write(self.style.SUCCESS("Webhook успешно зарегистрирован."))
