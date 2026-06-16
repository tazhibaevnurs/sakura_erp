"""Определение языка гостя и локализация ответов."""
from __future__ import annotations

import re

from .models import AssistantChannelState

RU = "ru"
KY = "ky"

KY_CHARS = re.compile(r"[ңөү]", re.IGNORECASE)

KY_WORDS = (
    "салам",
    "кандай",
    "жардам",
    "рахмат",
    "жакшы",
    "кылайын",
    "берейин",
    "барбы",
    "жокпу",
    "ооба",
    "эмне",
    "кайда",
    "качан",
    "канча",
    "өзүм",
    "алып кет",
    "жеткир",
    "ишим",
    "кабин",
    "заказ кыл",
    "заказ бер",
    "керек",
    "болду",
    "жок",
    "ким",
    "аты",
    "атым",
    "менин",
    "сизге",
    "саламатсызбы",
    "кандайсыз",
)

RU_WORDS = (
    "привет",
    "здравств",
    "добрый",
    "доброе",
    "спасибо",
    "меню",
    "заказ",
    "можно",
    "хочу",
    "доставк",
    "навынос",
    "бронь",
    "бронир",
    "сколько",
    "пожалуйста",
    "хорошо",
    "добавьте",
    "добавь",
    "еще",
    "ещё",
    "кабинк",
    "стол",
    "свобод",
    "занят",
)

STRONG_RU = ("привет", "здравствуй", "здравствуйте", "добрый день", "доброе утро")
STRONG_KY = ("салам", "кандайсыз", "кандай", "барбы", "жокпу", "рахмат")

MESSAGES: dict[str, dict[str, str]] = {
    "menu_empty": {
        RU: "Меню пока не заполнено. Уточните у администратора ресторана.",
        KY: "Меню азырынча толтурула элек. Администраторго кайрылыңыз.",
    },
    "menu_footer": {
        RU: "✨  Всё в наличии — готовим с душой!\n📋  {count} блюд на выбор\n📞  Спросите о брони или доставке",
        KY: "✨  Баары бар — жумуш пыштык!\n📋  {count} даана тамак\n📞  Бронь же доставка боюнча сураңыз",
    },
    "order_great": {
        RU: "🛒 Отлично! Ваш заказ:",
        KY: "🛒 Сонун! Сиздин заказыңыз:",
    },
    "order_subtotal": {
        RU: "💰 Предварительно: {total} сом",
        KY: "💰 Болжолдуу: {total} сом",
    },
    "order_how": {
        RU: (
            "Как вам удобнее?\n"
            "1️⃣ 🚚 Доставка\n"
            "2️⃣ 🥡 Навынос (самовывоз)\n"
            "3️⃣ 🪑 В кабинке (в зале)\n\n"
            "Напишите вариант: доставка, навынос или в кабинке."
        ),
        KY: (
            "Сизге кандай ыңгайлуу?\n"
            "1️⃣ 🚚 Жеткирүү\n"
            "2️⃣ 🥡 Өзү алуу\n"
            "3️⃣ 🪑 Кабинада\n\n"
            "Жазыңыз: жеткирүү, өзү алуу же кабинада."
        ),
    },
    "order_type_pick": {
        RU: "Пожалуйста, выберите вариант:\n🚚 доставка, 🥡 навынос или 🪑 в кабинке.",
        KY: "Сураныч, тандаңыз:\n🚚 жеткирүү, 🥡 өзү алуу же 🪑 кабинада.",
    },
    "order_accepted": {
        RU: "✅ Принято: {type_label}",
        KY: "✅ Кабыл алынды: {type_label}",
    },
    "order_contact": {
        RU: (
            "Кто заберёт / на чьё имя оформить заказ?\n"
            "Укажите, пожалуйста:\n"
            "👤 Имя\n"
            "📞 Номер телефона"
        ),
        KY: (
            "Заказды ким ала / чийин атына жазайын?\n"
            "Сураныч, жазыңыз:\n"
            "👤 Аты\n"
            "📞 Телефон номери"
        ),
    },
    "order_address": {
        RU: "📍 Укажите адрес доставки полностью\n(улица, дом, квартира, ориентир).",
        KY: "📍 Жеткирүү дарегин толук жазыңыз\n(көчө, үй, батир, ориентир).",
    },
    "order_need_contact": {
        RU: "Нужны имя и телефон для заказа.\nПример: Азамат, +996555123456",
        KY: "Заказ үчүн аты жана телефон керек.\nМисалы: Азамат, +996555123456",
    },
    "order_need_phone_only": {
        RU: "Спасибо, {name}! Теперь укажите номер телефона.",
        KY: "Рахмат, {name}! Эми телефон номериңизди жазыңыз.",
    },
    "assistant_retry": {
        RU: "Сейчас не получилось ответить. Повторите сообщение — я помогу с заказом.",
        KY: "Азыр жооп бере алган жокмун. Кайра жазыңыз — заказ боюнча жардам берем.",
    },
    "order_failed": {
        RU: "Не удалось оформить заказ.",
        KY: "Заказды түзүү мүмкүн болгон жок.",
    },
    "order_type_delivery": {
        RU: "🚚 Доставка",
        KY: "🚚 Жеткирүү",
    },
    "order_type_takeaway": {
        RU: "🥡 Навынос",
        KY: "🥡 Өзү алуу",
    },
    "order_type_dine_in": {
        RU: "🪑 В кабинке",
        KY: "🪑 Кабинада",
    },
    "order_accepted_title": {
        RU: "🛒 Заказ №{id} принят ({type})",
        KY: "🛒 №{id} заказ кабыл алынды ({type})",
    },
    "order_total": {
        RU: "💰 Итого: {total} сом",
        KY: "💰 Жалпы: {total} сом",
    },
    "order_sent_kitchen": {
        RU: "✅ Заказ передан на кухню. Спасибо!",
        KY: "✅ Заказ ашканага берилди. Рахмат!",
    },
    "order_type_label_delivery": {
        RU: "доставка",
        KY: "жеткирүү",
    },
    "order_type_label_takeaway": {
        RU: "навынос",
        KY: "өзү алуу",
    },
    "order_type_label_dine_in": {
        RU: "в зале",
        KY: "кабинада",
    },
    "greeting_ru": {
        RU: (
            "Здравствуйте! Чем могу помочь? "
            "Могу показать меню, оформить заказ или забронировать стол."
        ),
        KY: (
            "Здравствуйте! Чем могу помочь? "
            "Могу показать меню, оформить заказ или забронировать стол."
        ),
    },
    "greeting_ky": {
        RU: "Салам! Сизге кандай жардам бере алам? Меню, заказ же бронь боюнча жардам берем.",
        KY: "Салам! Сизге кандай жардам бере алам? Меню, заказ же бронь боюнча жардам берем.",
    },
    "dish_yes": {
        RU: "✅ {name} есть — {price} сом",
        KY: "✅ Ооба, {name} бар — {price} сом",
    },
    "dish_no": {
        RU: "❌ «{name}» нет в меню или нет в наличии",
        KY: "❌ «{name}» менюда жок же жок",
    },
    "dish_added": {
        RU: "✅ Добавлено: {name}",
        KY: "✅ Кошулду: {name}",
    },
    "order_updated": {
        RU: "Заказ обновлён:",
        KY: "Заказ жаңыланды:",
    },
    "financial_refusal": {
        RU: (
            "К сожалению, я не могу предоставить финансовую или конфиденциальную информацию. "
            "Позвоните в ресторан — мы поможем."
        ),
        KY: (
            "Кечиресиз, каржылык же жеке маалымат бере албайм. "
            "Ресторанга чалыңыз — жардам беребиз."
        ),
    },
}


def msg(key: str, lang: str = RU, **kwargs) -> str:
    lang = lang if lang in (RU, KY) else RU
    template = MESSAGES.get(key, {}).get(lang) or MESSAGES.get(key, {}).get(RU, key)
    if kwargs:
        return template.format(**kwargs)
    return template


def _score_text(text: str) -> tuple[int, int]:
    lowered = (text or "").lower()
    score_ru = 0
    score_ky = 0

    if KY_CHARS.search(lowered):
        score_ky += 4
    if re.search(r"[щъё]", lowered):
        score_ru += 2

    for word in KY_WORDS:
        if word in lowered:
            score_ky += 2
    for word in RU_WORDS:
        if word in lowered:
            score_ru += 2

    return score_ru, score_ky


def detect_guest_language(
    message: str,
    history: list[dict] | None = None,
    stored: str = "",
) -> str:
    lowered = (message or "").lower().strip()

    for phrase in STRONG_RU:
        if phrase in lowered:
            return RU
    for phrase in STRONG_KY:
        if phrase in lowered:
            return KY

    ru_cur, ky_cur = _score_text(message)
    if ru_cur >= 2 and ru_cur > ky_cur:
        return RU
    if ky_cur >= 2 and ky_cur > ru_cur:
        return KY

    score_ru = ru_cur * 5
    score_ky = ky_cur * 5

    if history:
        for item in reversed(history[-4:]):
            if item.get("role") != "user":
                continue
            ru, ky = _score_text(item["content"])
            score_ru += ru
            score_ky += ky

    if score_ky > score_ru:
        return KY
    if score_ru > score_ky:
        return RU
    if stored in (RU, KY):
        return stored
    return RU


def try_direct_greeting_reply(message: str) -> str | None:
    lowered = (message or "").lower().strip()
    if not lowered or len(lowered) > 40:
        return None
    if any(phrase in lowered for phrase in STRONG_RU):
        return msg("greeting_ru", RU)
    if any(phrase in lowered for phrase in STRONG_KY):
        return msg("greeting_ky", KY)
    if lowered in {"привет", "привет!", "здравствуйте", "здравствуй"}:
        return msg("greeting_ru", RU)
    if lowered in {"салам", "салам!", "кандайсыз", "кандайсыз!"}:
        return msg("greeting_ky", KY)
    return None


def language_system_hint(lang: str) -> str:
    if lang == KY:
        return (
            "ТЕКУЩИЙ ЯЗЫК ГОСТЯ: кыргызский. Отвечай ТОЛЬКО на кыргызском языке "
            "(кириллица). Не переходи на русский, если гость не попросил."
        )
    return (
        "ТЕКУЩИЙ ЯЗЫК ГОСТЯ: русский. Отвечай ТОЛЬКО на русском языке. "
        "Не переходи на кыргызский, если гость не попросил."
    )


def get_channel_language(channel: str = "", external_user_id: str = "") -> str:
    if not channel or not external_user_id:
        return ""
    state = AssistantChannelState.objects.filter(
        channel=channel,
        external_user_id=external_user_id,
    ).first()
    if state and state.guest_language in (RU, KY):
        return state.guest_language
    return ""


def set_channel_language(channel: str, external_user_id: str, lang: str) -> None:
    if not channel or not external_user_id:
        return
    if lang not in (RU, KY):
        return
    state, _ = AssistantChannelState.objects.get_or_create(
        channel=channel,
        external_user_id=external_user_id,
    )
    state.guest_language = lang
    state.save(update_fields=["guest_language", "updated_at"])


def resolve_language(ctx, message: str, history: list[dict] | None = None) -> str:
    stored = get_channel_language(ctx.channel, ctx.external_user_id)
    lang = detect_guest_language(message, history, stored=stored)
    set_channel_language(ctx.channel, ctx.external_user_id, lang)
    ctx.language = lang
    return lang


def format_localized_order_summary(order, lang: str = RU) -> str:
    from apps.orders.models import Order

    type_keys = {
        Order.OrderType.DELIVERY: "order_type_label_delivery",
        Order.OrderType.TAKEAWAY: "order_type_label_takeaway",
        Order.OrderType.DINE_IN: "order_type_label_dine_in",
    }
    type_label = msg(type_keys.get(order.order_type, "order_type_label_takeaway"), lang)
    lines = [
        msg("order_accepted_title", lang, id=order.pk, type=type_label),
        "",
    ]
    for item in order.items.select_related("menu_item").order_by("pk"):
        price = int(item.price) if item.price == int(item.price) else item.price
        qty = int(item.quantity) if item.quantity == int(item.quantity) else item.quantity
        lines.append(f"  • {item.menu_item.name} × {qty} — {price} сом")
    total = int(order.total) if order.total == int(order.total) else order.total
    lines.extend(["", msg("order_total", lang, total=total)])
    if order.order_type == Order.OrderType.DELIVERY and order.delivery_address:
        lines.append(f"📍 {order.delivery_address}")
    if order.customer_name and len(order.customer_name.strip()) >= 2:
        lines.append(f"👤 {order.customer_name}")
    if order.customer_phone and not order.customer_phone.startswith("web-test-"):
        lines.append(f"📞 {order.customer_phone}")
    if order.table_id:
        lines.append(f"🪑 №{order.table.number}")
    lines.extend(["", msg("order_sent_kitchen", lang)])
    return "\n".join(lines)
