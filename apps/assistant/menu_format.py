"""Красивое форматирование меню для гостей."""

from apps.menu.models import MenuCategory, MenuItem

from .models import AssistantSettings

MENU_SEPARATOR = "━━━━━━━━━━━━━━━━━━━━━━"

CATEGORY_EMOJI = {
    "суп": "🍲",
    "горяч": "🍛",
    "шашлык": "🍢",
    "мангал": "🍢",
    "салат": "🥗",
    "выпеч": "🥐",
    "чай": "🍵",
    "напит": "🥤",
    "десерт": "🍰",
    "завтрак": "🥞",
}

ITEM_EMOJI = (
    ("шорп", "🥣"),
    ("шурп", "🥣"),
    ("лагман", "🍜"),
    ("плов", "🍚"),
    ("мант", "🥟"),
    ("гуляш", "🥘"),
    ("баран", "🐑"),
    ("куриц", "🍗"),
    ("люля", "🧆"),
    ("кебаб", "🧆"),
    ("оливье", "🥔"),
    ("греческ", "🫒"),
    ("ачичук", "🥒"),
    ("самса", "🥟"),
    ("лепёш", "🫓"),
    ("лепеш", "🫓"),
    ("хачапури", "🧀"),
    ("зелён", "🍃"),
    ("зелен", "🍃"),
    ("чёрн", "☕"),
    ("черн", "☕"),
    ("сабза", "🌿"),
    ("компот", "🍹"),
    ("айран", "🥛"),
)

MENU_REQUEST_WORDS = (
    "меню",
    "что есть",
    "что у вас",
    "что пода",
    "блюд",
    "ассортимент",
    "прайс",
    "цены",
    "поесть",
    "кухн",
    "шашлык",
    "суп",
    "салат",
    "выпеч",
    "напит",
    "чай",
)


def _category_emoji(name: str) -> str:
    lowered = name.lower()
    for key, emoji in CATEGORY_EMOJI.items():
        if key in lowered:
            return emoji
    return "🍴"


def _item_emoji(name: str, category: str = "") -> str:
    lowered = name.lower()
    for key, emoji in ITEM_EMOJI:
        if key in lowered:
            return emoji
    return _category_emoji(category)


def _price_display(item: MenuItem) -> str:
    price = int(item.price) if item.price == int(item.price) else item.price
    unit = item.get_unit_display()
    if unit and unit != "шт":
        return f"{price} сом/{unit}"
    return f"{price} сом"


def _availability_badge(item: MenuItem) -> str:
    return "✅" if item.is_available else "⛔ нет в наличии"


def format_menu_for_guest(
    settings: AssistantSettings | None = None,
    *,
    category_filter: str = "",
    language: str = "ru",
) -> str:
    from .language import msg
    settings = settings or AssistantSettings.objects.first()
    name = settings.restaurant_name if settings else "Сакура"

    categories = (
        MenuCategory.objects.select_related("kitchen_section")
        .prefetch_related("items")
        .order_by("order", "name")
    )
    if category_filter:
        needle = category_filter.lower()
        categories = [c for c in categories if needle in c.name.lower()]

    lines = [
        f"🍽  Меню «{name}»",
        MENU_SEPARATOR,
        "",
    ]
    has_items = False

    for cat in categories:
        items = [i for i in cat.items.order_by("order", "name")]
        if not items:
            continue
        has_items = True
        emoji = _category_emoji(cat.name)
        lines.append(f"{emoji}  {cat.name}")
        lines.append("")
        for item in items:
            badge = _availability_badge(item)
            icon = _item_emoji(item.name, cat.name)
            price = _price_display(item)
            lines.append(f"   {icon}  {item.name}")
            lines.append(f"       💰 {price}  {badge}")
        lines.append("")
        lines.append(MENU_SEPARATOR)
        lines.append("")

    if not has_items:
        return msg("menu_empty", language)

    available_count = MenuItem.objects.filter(is_available=True).count()
    lines.append(msg("menu_footer", language, count=available_count))
    return "\n".join(lines).strip()


def looks_like_menu_request(text: str) -> bool:
    lowered = text.lower().strip()
    if len(lowered) > 120:
        return False
    return any(word in lowered for word in MENU_REQUEST_WORDS)


def parse_menu_category_filter(text: str) -> str:
    lowered = text.lower()
    for key in CATEGORY_EMOJI:
        if key in lowered:
            return key
    return ""
