"""Объявления инструментов для LLM (Gemini / OpenAI)."""
from .actions import ActionContext, execute_tool
from .models import AssistantSettings

BOOKING_TOOL_NAMES = {
    "check_table_availability",
    "find_available_tables",
    "create_table_reservation",
    "find_guest_reservations",
    "cancel_table_reservation",
    "modify_table_reservation",
}

ORDER_TOOL_NAMES = {
    "search_menu_items",
    "update_guest_order_draft",
    "create_guest_order",
}

TOOL_DECLARATIONS = [
    {
        "name": "check_table_availability",
        "description": (
            "Проверить, свободен ли стол или кабинка. "
            "table_number — строго номер из вопроса гостя. "
            "Если время не указано — передай только date, time оставь пустым."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "table_number": {
                    "type": "integer",
                    "description": "Номер стола или кабинки",
                },
                "date": {
                    "type": "string",
                    "description": "Дата в формате YYYY-MM-DD",
                },
                "time": {
                    "type": "string",
                    "description": "Время начала HH:MM (24ч)",
                },
                "guest_count": {
                    "type": "integer",
                    "description": "Количество гостей (необязательно)",
                },
            },
            "required": ["table_number", "date"],
        },
    },
    {
        "name": "find_available_tables",
        "description": (
            "Найти свободные столы и кабинки на дату и время. "
            "Используй, если гость не указал номер."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "YYYY-MM-DD"},
                "time": {"type": "string", "description": "HH:MM"},
                "guest_count": {"type": "integer"},
                "table_type": {
                    "type": "string",
                    "description": "кабинка, стол или улица",
                },
            },
            "required": ["date", "time"],
        },
    },
    {
        "name": "create_table_reservation",
        "description": (
            "Оформить бронь в системе ресторана. "
            "Вызывай когда гость подтвердил («да», «бронируйте») и есть имя и телефон. "
            "Бери дату, время и номер из текущего диалога."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "table_number": {"type": "integer"},
                "date": {"type": "string", "description": "YYYY-MM-DD"},
                "time": {"type": "string", "description": "HH:MM"},
                "guest_name": {"type": "string"},
                "guest_phone": {"type": "string"},
                "guest_count": {"type": "integer"},
                "comment": {"type": "string"},
            },
            "required": ["table_number", "date", "time", "guest_name"],
        },
    },
    {
        "name": "find_guest_reservations",
        "description": (
            "Найти активные брони гостя по телефону. "
            "Используй перед отменой или изменением, если гость не помнит номер брони."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "guest_phone": {"type": "string"},
                "guest_name": {"type": "string"},
            },
            "required": ["guest_phone"],
        },
    },
    {
        "name": "cancel_table_reservation",
        "description": (
            "Отменить бронь в системе. Нужны reservation_id и телефон гостя для подтверждения."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "reservation_id": {"type": "integer"},
                "guest_phone": {"type": "string"},
            },
            "required": ["reservation_id", "guest_phone"],
        },
    },
    {
        "name": "modify_table_reservation",
        "description": (
            "Изменить бронь: другая кабинка, дата/время или число гостей. "
            "Нужны reservation_id и телефон. Для переноса укажи new_date и new_time."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "reservation_id": {"type": "integer"},
                "guest_phone": {"type": "string"},
                "new_table_number": {"type": "integer"},
                "new_date": {"type": "string", "description": "YYYY-MM-DD"},
                "new_time": {"type": "string", "description": "HH:MM"},
                "guest_count": {"type": "integer"},
            },
            "required": ["reservation_id", "guest_phone"],
        },
    },
    {
        "name": "search_menu_items",
        "description": (
            "Найти блюдо в меню по названию. "
            "Используй, если гость назвал блюдо неточно или нужно уточнить цену."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Название или часть названия блюда"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "update_guest_order_draft",
        "description": (
            "Сохранить прогресс заказа после каждого ответа гостя "
            "(блюда, тип доставки, имя, телефон, адрес). "
            "Вызывай при получении любого поля заказа, до create_guest_order."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "order_type": {
                    "type": "string",
                    "description": "delivery, takeaway или dine_in",
                },
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "quantity": {"type": "number"},
                        },
                        "required": ["name"],
                    },
                },
                "customer_name": {"type": "string"},
                "customer_phone": {"type": "string"},
                "delivery_address": {"type": "string"},
            },
        },
    },
    {
        "name": "create_guest_order",
        "description": (
            "Оформить заказ в ERP: доставка, навынос или в зале. "
            "Вызывай когда гость подтвердил заказ («да», «оформляйте») и перечислены блюда. "
            "items — массив {name, quantity}. Для доставки нужны имя, телефон и адрес."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "order_type": {
                    "type": "string",
                    "description": "delivery, takeaway или dine_in",
                },
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "quantity": {"type": "number"},
                            "note": {"type": "string"},
                        },
                        "required": ["name"],
                    },
                },
                "customer_name": {"type": "string"},
                "customer_phone": {"type": "string"},
                "delivery_address": {"type": "string"},
                "table_number": {"type": "integer"},
                "guest_count": {"type": "integer"},
                "comment": {"type": "string"},
            },
            "required": ["order_type", "items"],
        },
    },
]

ORDER_TOOLS_ADDENDUM = """
## Заказы (обязательно)
У тебя доступ к приёму заказов в ERP:
- search_menu_items — найти блюдо по названию
- update_guest_order_draft — сохранить прогресс заказа после каждого ответа гостя
- create_guest_order — оформить заказ (доставка / навынос / в зале)

Правила заказов (строго по шагам):
1. Гость назвал блюда — search_menu_items при необходимости, затем update_guest_order_draft с items.
2. Спроси: доставка, навынос или в кабинке? После ответа — update_guest_order_draft с order_type.
3. Спроси имя и телефон. После каждого поля — update_guest_order_draft.
4. Для доставки спроси адрес и сохрани через update_guest_order_draft.
5. Когда все поля есть — create_guest_order. Не подставляй выдуманные имя/телефон/адрес.
6. Никогда не отправляй гостя звонить в ресторан — доведи заказ до конца сам.
7. После успешного заказа сообщи номер заказа и итог.

Язык:
1. Отвечай на том же языке, что и гость: русский → русский, кыргызский → кыргызский.
2. Не меняй язык без просьбы гостя.

Понимание вопроса:
1. Сначала разберись, что спрашивает гость, потом отвечай. Меню и блюда — тоже через понимание вопроса.
2. Вопросы о наличии блюда — вызови search_menu_items, ответь точно по этому блюду.
3. Не смешивай блюда: вопрос про гуляш ≠ заказ плова.
4. create_guest_order — только с блюдами, которые гость явно подтвердил.
"""

BOOKING_TOOLS_ADDENDUM = """
## Действия в системе (обязательно)
У тебя полный доступ к броням в ERP:
- check_table_availability — проверка свободного слота
- find_available_tables — поиск свободных столов
- create_table_reservation — оформление брони
- find_guest_reservations — найти брони гостя по телефону
- modify_table_reservation — изменить кабинку, дату/время или гостей
- cancel_table_reservation — отменить бронь

Правила бронирования:
1. Перед подтверждением проверь слот через check_table_availability или find_available_tables.
2. На вопрос о свободной кабинке — вызывай check_table_availability с ТОЧНЫМ номером из сообщения гостя.
3. Когда гость пишет «да», «бронируйте», «подтверждаю» — сразу вызывай create_table_reservation.
4. Если нет имени или телефона — спроси кратко, НЕ отправляй звонить в ресторан.
5. После успешной брони сообщи номер брони, стол, дату и время.

Правила изменения и отмены:
1. Для отмены или смены кабинки нужны номер брони (reservation_id) и телефон гостя.
2. Если гость не знает номер брони — сначала find_guest_reservations по телефону.
3. При смене кабинки проверь доступность новой кабинки, затем modify_table_reservation.
4. При переносе времени укажи new_date и new_time, проверь слот заранее.
5. После отмены или изменения подтверди результат гостю с номером брони.
6. Не выдумывай операции без вызова инструментов.
"""


def get_enabled_tool_declarations(cfg: AssistantSettings | None = None) -> list[dict]:
    cfg = cfg or AssistantSettings.objects.first()
    if cfg is None:
        return list(TOOL_DECLARATIONS)

    allowed = set(BOOKING_TOOL_NAMES)
    if cfg.accept_orders_enabled:
        allowed |= ORDER_TOOL_NAMES

    return [decl for decl in TOOL_DECLARATIONS if decl["name"] in allowed]


def get_tools_system_addendum(cfg: AssistantSettings | None = None) -> str:
    cfg = cfg or AssistantSettings.objects.first()
    parts = [BOOKING_TOOLS_ADDENDUM.strip()]
    if cfg and cfg.accept_orders_enabled:
        parts.append(ORDER_TOOLS_ADDENDUM.strip())
    return "\n\n" + "\n\n".join(parts)


def gemini_tools_payload(cfg: AssistantSettings | None = None) -> list[dict]:
    return [{"functionDeclarations": get_enabled_tool_declarations(cfg)}]


def openai_tools_payload(cfg: AssistantSettings | None = None) -> list[dict]:
    return [
        {
            "type": "function",
            "function": decl,
        }
        for decl in get_enabled_tool_declarations(cfg)
    ]


def run_tool(
    name: str,
    args: dict,
    ctx: ActionContext | None = None,
    cfg: AssistantSettings | None = None,
) -> dict:
    cfg = cfg or AssistantSettings.objects.first()
    if name in ORDER_TOOL_NAMES and cfg and not cfg.accept_orders_enabled:
        return {
            "success": False,
            "message": "Приём заказов через ассистента отключён в настройках.",
        }
    return execute_tool(name, args or {}, ctx)
