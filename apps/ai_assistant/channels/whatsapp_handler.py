import logging

import httpx
from django.conf import settings

from .base import BaseChannelHandler

logger = logging.getLogger("apps.ai_assistant")
GRAPH_API = "https://graph.facebook.com/v18.0"


class WhatsAppHandler(BaseChannelHandler):
    channel = "whatsapp"

    def __init__(self):
        self.access_token = settings.WHATSAPP_ACCESS_TOKEN
        self.phone_number_id = settings.WHATSAPP_PHONE_NUMBER_ID
        self.verify_token = settings.WHATSAPP_VERIFY_TOKEN

    def verify_webhook(self, params: dict) -> str | None:
        mode = params.get("hub.mode")
        token = params.get("hub.verify_token")
        challenge = params.get("hub.challenge")
        if mode == "subscribe" and token == self.verify_token:
            return challenge
        return None

    def parse_incoming(self, raw_data: dict) -> dict | None:
        for entry in raw_data.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                for message in value.get("messages", []):
                    if message.get("type") != "text":
                        continue
                    text = message.get("text", {}).get("body", "").strip()
                    return {
                        "channel_user_id": message.get("from", ""),
                        "text": text,
                        "channel": self.channel,
                        "platform_message_id": message.get("id", ""),
                    }
        return None

    def send_message(self, channel_user_id: str, text: str) -> bool:
        if not self.access_token or not self.phone_number_id:
            logger.error("WhatsApp credentials not configured")
            return False
        url = f"{GRAPH_API}/{self.phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": channel_user_id,
            "type": "text",
            "text": {"body": text[:4096]},
        }
        headers = {"Authorization": f"Bearer {self.access_token}"}
        try:
            response = httpx.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            return True
        except Exception:
            logger.exception("WhatsApp send_message failed")
            return False

    def send_with_buttons(
        self, channel_user_id: str, text: str, buttons: list[dict]
    ) -> bool:
        if not self.access_token or not self.phone_number_id:
            return False
        url = f"{GRAPH_API}/{self.phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": channel_user_id,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": text[:1024]},
                "action": {
                    "buttons": [
                        {
                            "type": "reply",
                            "reply": {"id": btn["callback"], "title": btn["text"][:20]},
                        }
                        for btn in buttons[:3]
                    ]
                },
            },
        }
        headers = {"Authorization": f"Bearer {self.access_token}"}
        try:
            response = httpx.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            return True
        except Exception:
            logger.exception("WhatsApp send_with_buttons failed")
            return False
