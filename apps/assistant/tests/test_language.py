import pytest

from apps.assistant.language import KY, RU, detect_guest_language, msg


def test_detect_russian_greeting():
    assert detect_guest_language("привет") == RU
    assert detect_guest_language("привет", stored="ky") == RU


def test_detect_kyrgyz_greeting():
    assert detect_guest_language("кандайсыз") == KY
    assert detect_guest_language("плов барбы?") == KY
    assert detect_guest_language("Салам, кандай жардам бере алам?") == KY


def test_detect_kyrgyz_chars():
    assert detect_guest_language("рахмат") == KY


def test_msg_kyrgyz_order():
    text = msg("order_how", KY)
    assert "ыңгайлуу" in text
    assert "Жеткирүү" in text
