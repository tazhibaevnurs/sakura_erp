import logging

import httpx
from django.conf import settings

from .base import BaseChannelHandler

logger = logging.getLogger("apps.ai_assistant")
GRAPH_API = "https://graph.facebook.com/v18.0"


class InstagramHandler(BaseChannelHandler):
    channel = "instagram"

    def __init__(self):
        self.access_token = settings.WHATSAPP_ACCESS_TOKEN
        self.verify_token = settings.INSTAGRAM_VERIFY_TOKEN

    def verify_webhook(self, params: dict) -> str | None:
        mode = params.get("hub.mode")
        token = params.get("hub.verify_token")
        challenge = params.get("hub.challenge")
        if mode == "subscribe" and token == self.verify_token:
            return challenge
        return None

    def parse_incoming(self, raw_data: dict) -> dict | None:
        for entry in raw_data.get("entry", []):
            for messaging in entry.get("messaging", []):
                sender = messaging.get("sender", {}).get("id", "")
                message = messaging.get("message", {})
                text = (message.get("text") or "").strip()
                if not text:
                    continue
                return {
                    "channel_user_id": sender,
                    "text": text,
                    "channel": self.channel,
                    "platform_message_id": message.get("mid", ""),
                }
        return None

    def send_message(self, channel_user_id: str, text: str) -> bool:
        if not self.access_token:
            logger.error("Instagram/Meta access token not configured")
            return False
        url = f"{GRAPH_API}/me/messages"
        payload = {
            "recipient": {"id": channel_user_id},
            "message": {"text": text[:1000]},
        }
        headers = {"Authorization": f"Bearer {self.access_token}"}
        try:
            response = httpx.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            return True
        except Exception:
            logger.exception("Instagram send_message failed")
            return False

    def send_with_buttons(
        self, channel_user_id: str, text: str, buttons: list[dict]
    ) -> bool:
        numbered = text + "\n\n"
        for idx, btn in enumerate(buttons, start=1):
            numbered += f"{idx}. {btn['text']}\n"
        numbered += "\nОтветьте номером варианта."
        return self.send_message(channel_user_id, numbered.strip())
