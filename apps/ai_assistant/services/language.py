"""Определение и фиксация языка диалога (русский / кыргызский)."""
from __future__ import annotations

from ..models import Conversation

KYRGYZ_CHARS = set("өүң")

KYRGYZ_WORDS = {
    "салам", "саламат", "саламатсызбы", "salamatsizby", "кандай", "кайда", "качан",
    "канча", "керек", "жок", "ооба", "макул", "туура", "жардам", "боюнча", "эмне",
    "ким", "кайсы", "кабина", "кабин", "брондоо", "заказ", "заказда", "берейин", "бересизби",
    "керекпи", "барбы", "жокпу", "кайрда", "сизге", "бүгүн", "эрте", "конок",
    "коноктор", "атыныз", "жеткирүү", "коюңуз", "коюңуздар", "берчи", "берчиңиз",
    "эмес", "токто", "менюнар", "болобу", "берсем", "берем", "береби", "кыласыз",
    "кылалы", "кылса", "кандай", "кайсы", "керекби", "болот", "берейин", "айтып",
}

RUSSIAN_WORDS = {
    "здравствуйте", "привет", "забронируй", "забронируйте", "закажу", "заказать",
    "доставка", "самовывоз", "сколько", "какой", "какая", "какие", "адрес",
    "телефон", "имя", "гостей", "кабин", "кабинк", "стол", "июня", "июля", "завтра",
    "пожалуйста", "спасибо", "хочу", "можно", "нужно", "подтверждаю", "отмена",
    "рад", "видеть", "помочь", "сегодня", "конечно", "порций", "порция", "хотите",
}

KYRGYZ_SUFFIXES = (
    "бы", "би", "бу", "бү", "мын", "мин", "сыз", "сиз", "быз", "биз",
    "бус", "сем", "обу", "алы", "беби", "гo", "го", "дар", "нар",
)


def _tokenize(text: str) -> list[str]:
    raw = (text or "").lower().replace("ё", "е")
    for ch in ",.!?;:\"'()[]{}«»/\\|@#№":
        raw = raw.replace(ch, " ")
    return [t for t in raw.split() if t]


def score_language(text: str) -> tuple[int, int]:
    if not text:
        return 0, 0
    lower = text.lower()
    ky = sum(2 for ch in lower if ch in KYRGYZ_CHARS)
    ru = 0
    for token in _tokenize(text):
        if token in KYRGYZ_WORDS:
            ky += 2
        elif any(token.endswith(suffix) for suffix in KYRGYZ_SUFFIXES):
            ky += 1
        if token in RUSSIAN_WORDS:
            ru += 2
    if any(w in lower for w in ("уйте", "ите", "ете ", "ый ", "ая ", "ое ", "ые ", "ого ")):
        ru += 1
    if any(w in lower for w in ("саламат", "кандай", "жардам", "болобу", "берсем", "барбы", "менюнар")):
        ky += 2
    return ky, ru


def detect_language_from_texts(texts: list[str]) -> str:
    ky_total = 0
    ru_total = 0
    for i, text in enumerate(texts):
        ky, ru = score_language(text)
        weight = 3 if i == 0 else 1
        ky_total += ky * weight
        ru_total += ru * weight
    if ky_total > ru_total:
        return "ky"
    if ru_total > ky_total:
        return "ru"
    return "ru"


def resolve_conversation_language(conversation: Conversation, user_message: str = "") -> str:
    """Язык диалога: зафиксированный или определённый по всем сообщениям клиента."""
    if conversation.language in ("ru", "ky"):
        return conversation.language

    texts = list(
        conversation.messages.filter(role="user")
        .order_by("created_at")
        .values_list("content", flat=True)
    )
    if user_message and (not texts or texts[-1] != user_message):
        texts.append(user_message)

    return detect_language_from_texts(texts)


def ensure_conversation_language(conversation: Conversation, lang: str) -> str:
    """Зафиксировать язык диалога при первом определении."""
    if lang not in ("ru", "ky"):
        lang = "ru"
    if not conversation.language:
        conversation.language = lang
        conversation.save(update_fields=["language", "updated_at"])
    return conversation.language or lang


def detect_conversation_language(
    user_message: str,
    history: list[dict] | None = None,
    *,
    lookback_user_messages: int = 3,
) -> str:
    """Устаревший helper — для обратной совместимости."""
    texts: list[str] = []
    if history:
        for msg in history:
            if msg.get("role") == "user":
                texts.append(msg.get("content") or "")
    texts.append(user_message or "")
    return detect_language_from_texts(texts[-lookback_user_messages:])


def language_instruction(lang: str) -> str:
    if lang == "ky":
        return (
            "ЯЗЫК ДИАЛОГА ЗАФИКСИРОВАН — КЫРГЫЗСКИЙ НА ВСЁ ОБЩЕНИЕ:\n"
            "- Поле reply только на кыргызском, все реплики до конца диалога\n"
            "- НЕ переключайся на русский, даже если блюдо названо по-русски (гуляш, лагман)\n"
            "- ЗАПРЕЩЕНО: «Да, конечно! Сколько порций…» — это русский, так нельзя\n"
            "- НУЖНО: «Ооба, албетте! Гуляштан канча порция заказ кыласыз? 🍵»\n"
            "- Названия блюд из меню можно оставить как в меню"
        )
    return (
        "ЯЗЫК ДИАЛОГА ЗАФИКСИРОВАН — РУССКИЙ НА ВСЁ ОБЩЕНИЕ:\n"
        "- Поле reply только на русском, все реплики до конца диалога\n"
        "- НЕ переключайся на кыргызский"
    )


FIELD_QUESTIONS_RU = {
    "type": "Доставка или самовывоз? 🚗 / 🏃",
    "items": "Что закажете из меню?",
    "name": "Как к вам обращаться?",
    "phone": "Укажите номер телефона для связи:",
    "address": "Куда доставить? Напишите адрес:",
    "date": "На какую дату забронировать стол?",
    "time": "На какое время?",
    "guests": "Сколько гостей будет?",
}

FIELD_QUESTIONS_KY = {
    "type": "Жеткирүүбү, же өзүңүз алып кетеби? 🚗 / 🏃",
    "items": "Менюдан эмне заказ кыласыз?",
    "name": "Атыңыз ким?",
    "phone": "Байланыш телефонуңузду жазыңыз:",
    "address": "Кайда жеткирилиши керек? Дарегин жазыңыз:",
    "date": "Кайсы датага бронь кылалы?",
    "time": "Кайсы убакка?",
    "guests": "Канча конок болот?",
}


def field_question(field: str, lang: str, *, extra_items: bool = False) -> str:
    if field == "items" and extra_items:
        if lang == "ky":
            return "Менюдан башка эмне заказ кыласыз?"
        return "Что ещё закажете из меню?"
    table = FIELD_QUESTIONS_KY if lang == "ky" else FIELD_QUESTIONS_RU
    return table.get(field, FIELD_QUESTIONS_RU.get(field, ""))


NAME_QUESTION_MARKERS = {
    "ru": ("обращаться", "ваше имя", "как к вам", "вашего имени", "имя?"),
    "ky": ("атыңыз", "atingiz", "аты ким", "сиздин аты", "аты-жөн"),
}

ITEMS_ACK_MARKERS = (
    "заказ кыл",
    "заказ кылдыңыз",
    "заказ кылдың",
    "порция",
    "порций",
    "×",
    " x ",
    "заказда",
    "заказ бер",
)


def reply_acknowledges_order_items(reply: str) -> bool:
    lower = (reply or "").lower()
    return any(marker in lower for marker in ITEMS_ACK_MARKERS)


def reply_asks_field(reply: str, field: str, lang: str = "ru") -> bool:
    lower = (reply or "").lower()
    if field == "name":
        markers = NAME_QUESTION_MARKERS.get(lang, ()) + NAME_QUESTION_MARKERS["ru"]
        return any(marker in lower for marker in markers)
    question = field_question(field, lang)
    if question and question.lower() in lower:
        return True
    if field == "items" and lang == "ky":
        return "менюдан" in lower and "заказ" in lower
    if field == "items":
        return "меню" in lower or "закажете" in lower
    return False


def confirm_prompt(lang: str = "ru") -> str:
    if lang == "ky":
        return (
            "\nБардыгы туурабы? «ооба» деп жазыңыз же «Тастыктоо» баскычын басыңыз."
        )
    return "\nВсё верно? Напишите «да» или нажмите «Подтвердить»."


def reply_has_confirmation(reply: str, lang: str = "ru") -> bool:
    lower = (reply or "").lower()
    if lang == "ky":
        return any(
            marker in lower
            for marker in (
                "текшериңиз",
                "тастыкт",
                "туурабы",
                "тастыктоого",
                "заказды тастыкт",
            )
        )
    return any(
        marker in lower
        for marker in ("проверьте заказ", "проверьте бронь", "всё верно")
    )


def confirm_bar_label(lang: str = "ru") -> str:
    if lang == "ky":
        return "Заказды же бронду тастыктоо:"
    return "Подтвердите заказ или бронь:"


def confirmation_buttons(lang: str = "ru") -> list[dict]:
    if lang == "ky":
        return [
            {"text": "✅ Тастыктоо", "callback": "confirm"},
            {"text": "❌ Токтотуу", "callback": "cancel"},
        ]
    return [
        {"text": "✅ Подтвердить", "callback": "confirm"},
        {"text": "❌ Отменить", "callback": "cancel"},
    ]
