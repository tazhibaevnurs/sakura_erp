"""Создание заказов из кода (ассистент, API)."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Employee
from apps.menu.models import MenuItem
from apps.tables.models import Table

from .models import Order, OrderItem

ACTIVE_ORDER_STATUSES = [
    Order.Status.OPEN,
    Order.Status.SENT,
    Order.Status.COOKING,
    Order.Status.READY,
    Order.Status.SERVED,
]


class OrderServiceError(Exception):
    pass


def _parse_quantity(value, default: Decimal = Decimal("1")) -> Decimal:
    try:
        qty = Decimal(str(value))
        if qty <= 0:
            return default
        return qty
    except (InvalidOperation, TypeError, ValueError):
        return default


def find_menu_item(name: str) -> MenuItem | None:
    """Найти блюдо по названию (точное или частичное совпадение)."""
    query = (name or "").strip()
    if not query:
        return None

    items = list(MenuItem.objects.filter(is_available=True).select_related("category"))
    lowered = query.lower()

    for item in items:
        if item.name.lower() == lowered:
            return item

    for item in items:
        item_lower = item.name.lower()
        if lowered in item_lower or item_lower in lowered:
            return item

    stem_len = min(len(lowered), 5)
    if stem_len >= 3:
        for item in items:
            item_lower = item.name.lower()
            if item_lower[:stem_len] == lowered[:stem_len]:
                return item

    return None


def resolve_order_lines(
    lines: list[dict],
) -> tuple[list[tuple[MenuItem, Decimal, str]], list[str]]:
    """Разобрать позиции заказа. lines: [{name, quantity?, note?}]."""
    resolved: list[tuple[MenuItem, Decimal, str]] = []
    errors: list[str] = []

    for line in lines or []:
        name = (line.get("name") or "").strip()
        if not name:
            continue
        menu_item = find_menu_item(name)
        if menu_item is None:
            errors.append(f"Блюдо «{name}» не найдено или нет в наличии.")
            continue
        qty = _parse_quantity(line.get("quantity", 1))
        note = (line.get("note") or "").strip()
        resolved.append((menu_item, qty, note))

    return resolved, errors


def _format_order_type(order_type: str) -> str:
    labels = {
        Order.OrderType.DELIVERY: "доставка",
        Order.OrderType.TAKEAWAY: "навынос",
        Order.OrderType.DINE_IN: "в зале",
    }
    return labels.get(order_type, order_type)


def format_order_summary(order: Order) -> str:
    lines = [
        f"🛒 Заказ №{order.pk} принят ({_format_order_type(order.order_type)})",
        "",
    ]
    for item in order.items.select_related("menu_item").order_by("pk"):
        price = int(item.price) if item.price == int(item.price) else item.price
        qty = int(item.quantity) if item.quantity == int(item.quantity) else item.quantity
        lines.append(f"  • {item.menu_item.name} × {qty} — {price} сом")
    total = int(order.total) if order.total == int(order.total) else order.total
    lines.extend(["", f"💰 Итого: {total} сом"])
    if order.order_type == Order.OrderType.DELIVERY and order.delivery_address:
        lines.append(f"📍 {order.delivery_address}")
    if order.customer_name and len(order.customer_name.strip()) >= 2:
        lines.append(f"👤 {order.customer_name}")
    if order.customer_phone and not order.customer_phone.startswith("web-test-"):
        lines.append(f"📞 {order.customer_phone}")
    if order.table_id:
        lines.append(f"🪑 Стол №{order.table.number}")
    lines.append("")
    lines.append("✅ Заказ передан на кухню. Спасибо!")
    return "\n".join(lines)


@transaction.atomic
def create_guest_order(
    employee: Employee,
    *,
    order_type: str,
    items: list[dict],
    customer_name: str = "",
    customer_phone: str = "",
    delivery_address: str = "",
    table: Table | None = None,
    guest_count: int = 1,
    comment: str = "",
    send_to_kitchen: bool = True,
) -> Order:
    if order_type not in Order.OrderType.values:
        raise OrderServiceError(f"Неизвестный тип заказа: {order_type}")

    resolved, errors = resolve_order_lines(items)
    if errors:
        raise OrderServiceError(" ".join(errors))
    if not resolved:
        raise OrderServiceError("Укажите хотя бы одно блюдо из меню.")

    name = (customer_name or "").strip()
    phone = (customer_phone or "").strip()
    address = (delivery_address or "").strip()

    if order_type == Order.OrderType.DELIVERY:
        missing = []
        if not name:
            missing.append("имя")
        if not phone:
            missing.append("телефон")
        if not address:
            missing.append("адрес доставки")
        if missing:
            raise OrderServiceError(
                f"Для доставки нужны: {', '.join(missing)}."
            )

    order = Order.objects.create(
        waiter=employee,
        order_type=order_type,
        table=table,
        guest_count=max(1, int(guest_count or 1)),
        customer_name=name,
        customer_phone=phone,
        delivery_address=address,
        comment=(comment or "").strip(),
    )

    now = timezone.now()
    for menu_item, quantity, note in resolved:
        OrderItem.objects.create(
            order=order,
            menu_item=menu_item,
            kitchen_section=menu_item.category.kitchen_section,
            quantity=quantity,
            price=menu_item.price,
            note=note,
            sent_at=now if send_to_kitchen else None,
        )

    if send_to_kitchen:
        order.status = Order.Status.SENT
        order.save(update_fields=["status"])
    else:
        order.recalculate_total()

    if table and order.status != Order.Status.OPEN:
        table.status = Table.Status.OCCUPIED
        table.save(update_fields=["status"])

    order.recalculate_total()
    return order


def find_active_order_by_phone(phone: str) -> Order | None:
    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) < 9:
        return None
    tail = digits[-9:]
    for order in (
        Order.objects.filter(status__in=ACTIVE_ORDER_STATUSES)
        .order_by("-created_at")[:30]
    ):
        stored = "".join(c for c in order.customer_phone if c.isdigit())
        if stored and stored[-9:] == tail:
            return order
    return None
