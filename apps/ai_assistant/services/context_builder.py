from django.conf import settings
from django.utils import timezone

from apps.menu.models import MenuCategory, MenuItem
from apps.tables.models import Table

from ..models import AssistantConfig, ClientProfile, Conversation, Message


class ContextBuilder:
    def _get_config(self) -> AssistantConfig:
        return AssistantConfig.load()

    def build_business_context(self) -> str:
        config = self._get_config()
        cfg = getattr(settings, "AI_ASSISTANT", {})

        lines = [f"Название: {config.restaurant_name or cfg.get('BUSINESS_NAME', 'Сакура')}"]
        address = config.restaurant_address or cfg.get("BUSINESS_ADDRESS", "")
        phone = config.restaurant_phone or cfg.get("FALLBACK_PHONE", "")
        hours = config.working_hours or cfg.get("BUSINESS_HOURS", "Ежедневно 10:00–23:00")

        if address:
            lines.append(f"Адрес: {address}")
        if phone:
            lines.append(f"Телефон: {phone}")
        lines.append(f"Часы работы: {hours}")

        if config.about_restaurant:
            lines.append(f"О заведении: {config.about_restaurant}")
        delivery = config.delivery_info or cfg.get("DELIVERY_INFO", "")
        booking = config.booking_info or cfg.get("BOOKING_INFO", "")
        promotions = config.promotions or cfg.get("BUSINESS_PROMOTIONS", "")
        if delivery:
            lines.append(f"Доставка: {delivery}")
        if booking:
            lines.append(f"Бронирование: {booking}")
        if promotions:
            lines.append(f"Акции: {promotions}")

        now = timezone.localtime()
        lines.extend(
            [
                "",
                f"Сейчас: {now.strftime('%d.%m.%Y %H:%M')}",
                "",
                "## Меню (только активные позиции)",
            ]
        )

        categories = MenuCategory.objects.prefetch_related("items").order_by("order", "name")
        has_items = False
        for category in categories:
            items = category.items.filter(is_available=True, is_stopped=False).order_by("order", "name")
            if not items.exists():
                continue
            has_items = True
            lines.append(f"\n### {category.name}")
            for item in items:
                price = int(item.price) if item.price == int(item.price) else item.price
                unit = item.get_unit_display()
                desc = f" — {item.description}" if item.description else ""
                lines.append(f"- {item.name}: {price} сом/{unit}{desc}")

        if not has_items:
            lines.append("Меню пока пусто. Уточняйте у администратора.")

        tables = list(Table.objects.order_by("number"))
        if tables:
            lines.extend(["", "## Кабинки / столы (номер для брони — table_number)"])
            for table in tables:
                type_label = table.get_type_display()
                lines.append(
                    f"- №{table.number} ({type_label}), {table.capacity} мест"
                )

        return "\n".join(lines)

    def build_client_context(self, client: ClientProfile) -> str:
        lines = []
        if client.name:
            lines.append(f"Имя: {client.name}")
        if client.phone:
            lines.append(f"Телефон: {client.phone}")
        if client.preferred_order_type:
            label = dict(ClientProfile.ORDER_TYPE_CHOICES).get(
                client.preferred_order_type, client.preferred_order_type
            )
            lines.append(f"Предпочитает: {label}")

        recent_orders = client.ai_orders.select_related("erp_order").order_by("-created_at")[:5]
        if recent_orders:
            lines.append("\nПоследние заказы:")
            for ai_order in recent_orders:
                order = ai_order.erp_order
                total = int(order.total) if order.total == int(order.total) else order.total
                items = ", ".join(
                    f"{item.menu_item.name} x{int(item.quantity)}"
                    for item in order.items.select_related("menu_item")[:5]
                )
                lines.append(f"- Заказ #{order.pk}: {items} — {total} сом")

        active = (
            client.conversations.filter(status__in=["active", "waiting_confirm"])
            .order_by("-updated_at")
            .first()
        )
        if active and active.draft_data:
            lines.append(f"\nТекущий черновик: {active.draft_data}")

        return "\n".join(lines) if lines else "Новый клиент, истории нет."

    def get_history_messages(self, conversation: Conversation, limit: int | None = None) -> list[dict]:
        cfg = getattr(settings, "AI_ASSISTANT", {})
        limit = limit or cfg.get("HISTORY_LIMIT", 15)
        qs = conversation.messages.exclude(role="system").order_by("-created_at")[:limit]
        history = []
        for msg in reversed(list(qs)):
            role = "assistant" if msg.role == "assistant" else "user"
            history.append({"role": role, "content": msg.content})
        return history
