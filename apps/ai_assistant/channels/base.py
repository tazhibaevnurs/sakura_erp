from abc import ABC, abstractmethod


class BaseChannelHandler(ABC):
    @abstractmethod
    def parse_incoming(self, raw_data: dict) -> dict | None:
        """
        Возвращает:
        {
          "channel_user_id": str,
          "text": str,
          "channel": str,
          "platform_message_id": str
        }
        """

    @abstractmethod
    def send_message(self, channel_user_id: str, text: str) -> bool:
        """Отправить текстовый ответ клиенту."""

    @abstractmethod
    def send_with_buttons(
        self, channel_user_id: str, text: str, buttons: list[dict]
    ) -> bool:
        """
        buttons: [{"text": "✅ Подтвердить", "callback": "confirm"}, ...]
        Для Instagram (нет кнопок) — добавить варианты в текст цифрами.
        """
