from apps.core.roles import KITCHEN_ROLES



NAV_ITEMS = {

    "owner": [

        ("reports:dashboard", "Дашборд", "speedometer2"),

        ("tables:floor", "Кабинки", "columns-gap"),

        ("tables:calendar_order", "Приём заказа", "calendar-event"),

        ("tables:reservation_list", "Брони", "calendar-week"),

        ("orders:list", "Заказы", "receipt"),

        ("orders:takeaway", "Навынос", "bag"),

        ("orders:delivery", "Доставка", "truck"),

        ("cash:today", "Касса", "cash-stack"),

        ("cash:closed_list", "Закрытые смены", "journal-check"),

        ("salary:list", "Зарплата", "wallet2"),

        ("reports:export", "Экспорт", "file-earmark-excel"),

        ("staff_list", "Персонал", "people"),

        ("menu:manage", "Меню", "book"),

        ("assistant:dialogs", "Диалоги", "chat-left-text"),

        ("assistant:settings", "ИИ-ассистент", "robot"),

    ],

    "admin": [

        ("reports:dashboard", "Дашборд", "speedometer2"),

        ("tables:floor", "Кабинки", "columns-gap"),

        ("tables:calendar_order", "Приём заказа", "calendar-event"),

        ("tables:reservation_list", "Брони", "calendar-week"),

        ("orders:list", "Заказы", "receipt"),

        ("orders:takeaway", "Навынос", "bag"),

        ("orders:delivery", "Доставка", "truck"),

        ("cash:today", "Касса", "cash-stack"),

        ("cash:closed_list", "Закрытые смены", "journal-check"),

        ("salary:timesheet", "Табель", "calendar3"),

        ("staff_list", "Персонал", "people"),

        ("menu:manage", "Меню", "book"),

        ("assistant:dialogs", "Диалоги", "chat-left-text"),

        ("assistant:settings", "ИИ-ассистент", "robot"),

    ],

    "waiter": [

        ("tables:floor", "Кабинки", "columns-gap"),

        ("tables:calendar_order", "Приём заказа", "calendar-event"),

        ("tables:reservation_list", "Брони", "calendar-week"),

        ("orders:list", "Заказы", "receipt"),

        ("orders:takeaway", "Навынос", "bag"),

        ("orders:delivery", "Доставка", "truck"),

    ],

    "cook": [],

    "baker": [],

    "salad": [],

    "bbq": [],

}





def _kitchen_nav(section):
    return [
        (
            "kitchen:display",
            "Дашборд",
            "speedometer2",
            {"section_slug": section.slug},
        ),
        (
            "kitchen:completed_orders",
            "Мои заказы",
            "list-check",
            {"section_slug": section.slug},
        ),
    ]





def navigation(request):

    if not request.user.is_authenticated:

        return {}

    from apps.core.employees import user_effective_role



    role = user_effective_role(request.user)

    if role in ("owner", "admin") and not hasattr(request.user, "employee"):

        nav_key = "owner" if role == "owner" else "admin"

        return {"nav_items": NAV_ITEMS[nav_key], "user_role": role}

    if not hasattr(request.user, "employee"):

        return {}

    role = request.user.employee.role.slug

    items = list(NAV_ITEMS.get(role, []))

    section = request.user.employee.kitchen_section

    if role in KITCHEN_ROLES and section:

        items = _kitchen_nav(section)

    return {"nav_items": items, "user_role": role}


