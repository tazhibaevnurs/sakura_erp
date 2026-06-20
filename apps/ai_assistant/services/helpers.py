"""Вспомогательные функции для сервисов ассистента."""
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.accounts.models import Employee, Role
from apps.salary.models import SalarySchema

User = get_user_model()
ASSISTANT_USERNAME = "ai_assistant"


def get_assistant_employee() -> Employee:
    user, _ = User.objects.get_or_create(
        username=ASSISTANT_USERNAME,
        defaults={
            "is_active": True,
            "first_name": "ИИ-ассистент",
        },
    )
    if hasattr(user, "employee"):
        return user.employee

    role = Role.objects.filter(slug="owner").first()
    if role is None:
        raise RuntimeError("Не настроена роль владельца для заказов ассистента.")

    schema = SalarySchema.objects.order_by("pk").first()
    if schema is None:
        schema = SalarySchema.objects.create(
            name="По умолчанию",
            percent_of_revenue=0,
            fixed_per_shift=0,
            fixed_monthly=0,
        )

    return Employee.objects.create(
        user=user,
        role=role,
        hired_date=timezone.localdate(),
        salary_schema=schema,
    )


def build_order_history_reply(client) -> str:
    from ..models import ClientProfile

    if not isinstance(client, ClientProfile):
        return "У вас пока нет заказов через ассистента 🍵"
    orders = client.ai_orders.select_related("erp_order").order_by("-created_at")[:5]
    if not orders:
        return "У вас пока нет заказов через ассистента 🍵"
    lines = ["Ваши последние заказы:\n"]
    for ai_order in orders:
        order = ai_order.erp_order
        total = int(order.total) if order.total == int(order.total) else order.total
        lines.append(f"• Заказ #{order.pk} — {total} сом")
    return "\n".join(lines)


INTENT_LABELS = {
    "order": "Заказ",
    "booking": "Бронь",
    "question": "Вопрос",
    "confirm": "Подтверждение",
    "cancel": "Отмена",
    "other": "Другое",
}

DRAFT_FIELD_LABELS = {
    "type": "Способ получения",
    "items": "Блюда",
    "address": "Адрес",
    "delivery_time": "Время доставки",
    "comment": "Комментарий",
    "name": "Имя",
    "phone": "Телефон",
    "date": "Дата",
    "time": "Время",
    "guests": "Гостей",
    "table_number": "Кабинка №",
}

ORDER_TYPE_LABELS = {
    "delivery": "Доставка",
    "takeaway": "Самовывоз",
}


def get_intent_label(intent: str) -> str:
    return INTENT_LABELS.get((intent or "").strip().lower(), intent or "—")


def format_draft_display(draft: dict | None) -> list[dict]:
    if not draft:
        return []

    lines: list[dict] = []
    for key, value in draft.items():
        if value in (None, "", [], {}):
            continue
        label = DRAFT_FIELD_LABELS.get(key, key)

        if key == "type":
            value = ORDER_TYPE_LABELS.get(str(value).lower(), value)
        elif key == "items" and isinstance(value, list):
            parts = []
            for item in value:
                name = (item.get("name") or "?").strip()
                qty = item.get("qty") or item.get("quantity") or 1
                parts.append(f"{name} × {qty}")
            value = ", ".join(parts) if parts else "—"
        elif isinstance(value, (dict, list)):
            continue

        lines.append({"label": label, "value": value})

    return lines


def format_client_phone(phone: str) -> str:
    phone = (phone or "").strip()
    if not phone:
        return "—"
    if phone.startswith("web-test-"):
        return "Тестовый (ERP)"
    return phone
