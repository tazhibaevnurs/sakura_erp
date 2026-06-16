"""Сбор публичной базы знаний для ИИ (без финансов и персональных данных)."""
from datetime import timedelta

from django.utils import timezone

from apps.cash.services import is_day_closed
from apps.menu.models import MenuCategory, MenuItem
from apps.orders.models import KitchenSection
from apps.tables.models import Table, TableReservation

from .menu_format import _availability_badge, _category_emoji, _price_display
from .models import AssistantSettings


def build_knowledge_context(settings: AssistantSettings | None = None) -> str:
    settings = settings or AssistantSettings.objects.first()
    now = timezone.localtime()
    today = now.date()
    lines = [
        "# База знаний ресторана",
        "",
        "## Ресторан",
        f"Название: {settings.restaurant_name if settings else 'Сакура'}",
    ]
    if settings:
        if settings.restaurant_address:
            lines.append(f"Адрес: {settings.restaurant_address}")
        if settings.restaurant_phone:
            lines.append(f"Телефон: {settings.restaurant_phone}")
        lines.append(f"Часы работы: {settings.working_hours}")
        if settings.about_restaurant:
            lines.append(f"О заведении: {settings.about_restaurant}")
        if settings.delivery_info:
            lines.append(f"Доставка: {settings.delivery_info}")
        if settings.booking_info:
            lines.append(f"Бронирование: {settings.booking_info}")

    lines.extend(
        [
            "",
            f"Сейчас: {now.strftime('%d.%m.%Y %H:%M')} ({timezone.get_current_timezone()})",
            f"Смена сегодня: {'закрыта' if is_day_closed(today) else 'открыта'} (без сумм)",
            "",
            "## Типы заказов",
            "- В зале (стол/кабинка)",
            "- Навынос",
            "- Доставка",
            "",
            "## Кухонные цеха",
        ]
    )
    for section in KitchenSection.objects.order_by("name"):
        lines.append(f"- {section.name} (slug: {section.slug})")

    lines.extend(
        [
            "",
            "## Меню (для гостя оформляй с эмодзи по категориям)",
            "При показе меню: заголовок 🍽, категории с эмодзи, блюда списком «• Название — цена ✅».",
        ]
    )
    categories = MenuCategory.objects.select_related("kitchen_section").prefetch_related(
        "items"
    ).order_by("order", "name")
    for cat in categories:
        emoji = _category_emoji(cat.name)
        lines.append(f"\n### {emoji} {cat.name}")
        for item in cat.items.order_by("order", "name"):
            desc = f" ({item.description})" if item.description else ""
            lines.append(
                f"- {item.name}: {_price_display(item)}, {_availability_badge(item)}{desc}"
            )

    lines.extend(["", "## Столы и кабинки"])
    status_labels = dict(Table.Status.choices)
    type_labels = dict(Table.TableType.choices)
    for table in Table.objects.order_by("number"):
        ds = table.display_status
        lines.append(
            f"- №{table.number}, {type_labels.get(table.type, table.type)}, "
            f"{table.capacity} мест, статус: {status_labels.get(ds, ds)}"
        )

    lines.extend(
        [
            "",
            "## Ближайшие брони (справочно, без имён гостей)",
            "ВАЖНО: на вопрос «свободна ли кабинка N на дату» отвечай ТОЛЬКО через инструмент "
            "check_table_availability с номером N из вопроса гостя. "
            "Не подставляй другой номер из этого списка.",
        ]
    )
    upcoming = (
        TableReservation.objects.filter(
            status=TableReservation.Status.ACTIVE,
            reserved_until__gte=now,
        )
        .select_related("table")
        .order_by("reserved_for")[:20]
    )
    if upcoming:
        for r in upcoming:
            start = timezone.localtime(r.reserved_for)
            end = timezone.localtime(r.reserved_until)
            lines.append(
                f"- Стол №{r.table.number} ({r.table.get_type_display()}), "
                f"{start.strftime('%d.%m %H:%M')}–{end.strftime('%H:%M')}, "
                f"гостей: {r.guest_count}"
            )
    else:
        lines.append("- Нет активных броней в ближайшее время")

    lines.extend(["", "## Свободные слоты сегодня (примерно)"])
    for table in Table.objects.order_by("number")[:8]:
        slots = _free_slots_today(table, now)
        if slots:
            lines.append(f"- Стол №{table.number}: свободно {', '.join(slots[:3])}")

    lines.extend(
        [
            "",
            "## ЗАПРЕЩЕНО сообщать гостю",
            "- Выручка, прибыль, расходы, касса, зарплаты",
            "- Имена, телефоны и адреса других гостей",
            "- Детали заказов других гостей и суммы их чеков",
            "- Долги, зарплата персонала, внутренние финансы",
            "- Любая конфиденциальная информация о сотрудниках",
            "",
            "На вопросы о финансах и конфиденциальном — вежливо откажи и предложи позвонить в ресторан.",
        ]
    )
    return "\n".join(lines)


def _free_slots_today(table, now):
    """Короткий список свободных окон на сегодня."""
    from datetime import datetime, time

    day = now.date()
    tz = timezone.get_current_timezone()
    slots = []
    for hour in range(10, 22, 2):
        start = timezone.make_aware(datetime.combine(day, time(hour, 0)), tz)
        end = start + timedelta(hours=2)
        if end <= now:
            continue
        if table.can_reserve_at(start, end):
            slots.append(f"{hour:02d}:00–{(hour + 2) % 24:02d}:00")
    return slots


def build_system_prompt(settings: AssistantSettings, *, language: str = "ru") -> str:
    from .language import language_system_hint

    order_line = ""
    if settings.accept_orders_enabled:
        order_line = (
            "Ты принимаешь заказы (доставка, навынос, в зале) и оформляешь их в системе ресторана.\n"
        )
    return f"""Ты — дружелюбный ИИ-ассистент ресторана «{settings.restaurant_name}».
{language_system_hint(language)}
Отвечай кратко и по делу на языке гостя.
Сначала пойми вопрос гостя и ответь по сути (адрес, телефон, часы, меню, наличие блюд).
Меню и вопросы о блюдах («гуляш есть?», «сколько стоит лагман?») — отвечай через базу знаний и search_menu_items.
Не подставляй другое блюдо: если спрашивают про гуляш — отвечай про гуляш, не про плов.
Оформляй заказ через create_guest_order только с теми блюдами, которые гость явно заказал.
Помогай гостям: меню, цены, бронь, столы, время работы, доставка, навынос.
{order_line}Используй только факты из базы знаний ниже. Не выдумывай блюда и цены.
На вопрос о меню отвечай красиво: эмодзи, категории, маркер ✅ у блюд в наличии.
Учитывай предыдущие сообщения в диалоге — не начинай заново с приветствия.
{settings.get_agent_instruction()}

{build_knowledge_context(settings)}
"""
