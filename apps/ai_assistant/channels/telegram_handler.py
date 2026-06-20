import asyncio
import logging

from django.conf import settings
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

from .base import BaseChannelHandler

logger = logging.getLogger("apps.ai_assistant")


class TelegramHandler(BaseChannelHandler):
    channel = "telegram"

    def __init__(self):
        self.token = settings.TELEGRAM_BOT_TOKEN
        base_url = getattr(settings, "TELEGRAM_API_BASE_URL", "https://api.telegram.org")
        self._api_base = f"{base_url.rstrip('/')}/bot"
        self._bot = Bot(token=self.token, base_url=self._api_base) if self.token else None

    def _run(self, coro):
        return asyncio.run(coro)

    def parse_incoming(self, raw_data: dict) -> dict | None:
        message = raw_data.get("message") or raw_data.get("edited_message")
        callback = raw_data.get("callback_query")

        if callback:
            from_user = callback.get("from") or {}
            chat_id = callback.get("message", {}).get("chat", {}).get("id")
            data = callback.get("data", "")
            return {
                "channel_user_id": str(chat_id or from_user.get("id", "")),
                "text": data,
                "channel": self.channel,
                "platform_message_id": str(callback.get("id", "")),
                "user_name": self._guest_name(from_user),
            }

        if not message:
            return None

        chat = message.get("chat") or {}
        from_user = message.get("from") or {}
        text = (message.get("text") or "").strip()

        return {
            "channel_user_id": str(chat.get("id", "")),
            "text": text,
            "channel": self.channel,
            "platform_message_id": str(message.get("message_id", "")),
            "user_name": self._guest_name(from_user),
        }

    def send_message(self, channel_user_id: str, text: str) -> bool:
        if not self._bot:
            logger.error("TELEGRAM_BOT_TOKEN не настроен")
            return False
        try:
            self._run(
                self._bot.send_message(chat_id=int(channel_user_id), text=text[:4096])
            )
            return True
        except Exception:
            logger.exception("Telegram send_message failed")
            return False

    def send_with_buttons(
        self, channel_user_id: str, text: str, buttons: list[dict]
    ) -> bool:
        if not self._bot:
            return False
        keyboard = [
            [InlineKeyboardButton(btn["text"], callback_data=btn["callback"])]
            for btn in buttons
        ]
        markup = InlineKeyboardMarkup(keyboard)
        try:
            self._run(
                self._bot.send_message(
                    chat_id=int(channel_user_id),
                    text=text[:4096],
                    reply_markup=markup,
                )
            )
            return True
        except Exception:
            logger.exception("Telegram send_with_buttons failed")
            return False

    def handle_command(self, command: str, channel_user_id: str, user_name: str = "") -> str | None:
        from ..models import AssistantConfig

        config = AssistantConfig.load()
        cmd = command.split()[0].lower()
        phone = config.restaurant_phone or getattr(settings, "AI_ASSISTANT", {}).get("FALLBACK_PHONE", "")

        if cmd == "/start":
            if config.welcome_message.strip():
                greeting = config.welcome_message.strip()
                if user_name and "{name}" in greeting:
                    greeting = greeting.replace("{name}", user_name)
                elif user_name and "Здравствуйте" in greeting and "," not in greeting[:20]:
                    greeting = f"Здравствуйте, {user_name}! 🍵\n{greeting}"
                return greeting
            greeting = f"Здравствуйте{', ' + user_name if user_name else ''}! 🍵\n"
            greeting += (
                "Мен «Сакура» жардамчысымын / Я помощник чайханы «Сакура».\n"
                "Заказ, бронь, меню / заказ, бронь, вопросы о меню.\n\n"
                "Команды:\n/order — заказ\n/booking — бронь\n/history — заказдар\n/help — жардам"
            )
            return greeting

        if cmd == "/help":
            return (
                "🍵 Чем могу помочь:\n"
                "• Заказ на доставку или самовывоз — /order\n"
                "• Бронь столика — /booking\n"
                "• История заказов — /history\n"
                f"• Телефон ресторана: {phone or 'уточняйте в чате'}"
            )

        if cmd == "/order":
            return (
                "Отлично! Оформим заказ 🍽\n"
                "1) Напишите блюда из меню\n"
                "2) Укажите: доставка или самовывоз\n"
                "3) Имя и телефон (для доставки — ещё адрес)"
            )

        if cmd == "/booking":
            return (
                "Забронируем столик 🪑\n"
                "Нужны: дата, время, число гостей, имя и телефон."
            )

        if cmd == "/history":
            return None

        return None

    @staticmethod
    def _guest_name(from_user: dict) -> str:
        return (
            f"{from_user.get('first_name', '')} {from_user.get('last_name', '')}".strip()
            or from_user.get("username", "")
        )
