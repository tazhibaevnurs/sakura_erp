import pytest
from unittest.mock import patch

from apps.assistant.models import AssistantSettings
from apps.assistant.telegram_bot import process_telegram_update


@pytest.fixture
def cfg(db):
    return AssistantSettings.objects.create(
        is_enabled=True,
        telegram_enabled=True,
        telegram_bot_token="test-token",
        welcome_message="Добро пожаловать!",
    )


@pytest.mark.django_db
def test_process_start_sends_welcome(cfg):
    update = {
        "update_id": 1,
        "message": {
            "message_id": 10,
            "chat": {"id": 12345},
            "from": {"first_name": "Test", "username": "testuser"},
            "text": "/start",
        },
    }
    with patch("apps.assistant.telegram_bot.send_telegram_message") as send:
        assert process_telegram_update(cfg, update) is True
        send.assert_called_once()
        assert send.call_args[0][2] == "Добро пожаловать!"


@pytest.mark.django_db
def test_process_text_asks_assistant(cfg):
    update = {
        "update_id": 2,
        "message": {
            "message_id": 11,
            "chat": {"id": 99},
            "from": {"first_name": "Guest"},
            "text": "привет",
        },
    }
    with (
        patch("apps.assistant.telegram_bot.ask_assistant", return_value="Здравствуйте!") as ask,
        patch("apps.assistant.telegram_bot.send_assistant_reply_telegram") as reply,
    ):
        assert process_telegram_update(cfg, update) is True
        ask.assert_called_once()
        reply.assert_called_once_with(cfg, 99, "Здравствуйте!")
