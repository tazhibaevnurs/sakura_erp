import pytest
from django.test import RequestFactory

from apps.assistant.services import (
    get_webhook_urls,
    is_local_webhook_url,
    validate_webhook_url,
)


def test_localhost_webhook_is_invalid():
    ok, msg = validate_webhook_url("http://127.0.0.1:8000/assistant/webhook/telegram/")
    assert ok is False
    assert "localhost" in msg.lower() or "127.0.0.1" in msg


def test_https_public_webhook_is_valid():
    ok, msg = validate_webhook_url("https://erp.example.com/assistant/webhook/telegram/")
    assert ok is True
    assert msg == ""


def test_http_public_webhook_requires_https():
    ok, msg = validate_webhook_url("http://erp.example.com/assistant/webhook/telegram/")
    assert ok is False
    assert "https" in msg.lower()


@pytest.mark.django_db
def test_get_webhook_urls_uses_public_url(settings):
    settings.ASSISTANT_PUBLIC_URL = "https://tunnel.example.com"
    request = RequestFactory().get("/assistant/settings/")
    request.META["HTTP_HOST"] = "127.0.0.1:8000"
    urls = get_webhook_urls(request)
    assert urls["telegram"] == "https://tunnel.example.com/assistant/webhook/telegram/"


def test_is_local_detects_private_network():
    assert is_local_webhook_url("http://192.168.1.5/hook") is True
    assert is_local_webhook_url("https://mybot.example.com/hook") is False
