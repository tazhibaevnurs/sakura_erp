from django.db import transaction

from apps.orders.models import Order
from apps.orders.services import OrderServiceError, create_guest_order, find_menu_item

from ..models import AIOrder, ClientProfile
from .helpers import get_assistant_employee


class OrderService:
    def validate_items(self, items: list) -> tuple[list, list]:
        valid_items = []
        not_found_items = []
        for item in items or []:
            name = (item.get("name") or "").strip()
            if not name:
                continue
            menu_item = find_menu_item(name)
            if menu_item is None:
                not_found_items.append(name)
                continue
            qty = item.get("qty") or item.get("quantity") or 1
            valid_items.append(
                {
                    "name": menu_item.name,
                    "menu_item_id": menu_item.pk,
                    "qty": qty,
                    "price": float(menu_item.price),
                    "quantity": qty,
                }
            )
        return valid_items, not_found_items

    @transaction.atomic
    def create_from_draft(self, client: ClientProfile, draft_data: dict):
        order_type_raw = (draft_data.get("type") or client.preferred_order_type or "takeaway").lower()
        type_map = {
            "delivery": Order.OrderType.DELIVERY,
            "takeaway": Order.OrderType.TAKEAWAY,
            "доставка": Order.OrderType.DELIVERY,
            "самовывоз": Order.OrderType.TAKEAWAY,
            "навынос": Order.OrderType.TAKEAWAY,
        }
        order_type = type_map.get(order_type_raw, Order.OrderType.TAKEAWAY)

        raw_items = draft_data.get("items") or []
        valid_items, not_found = self.validate_items(raw_items)
        if not_found:
            return {
                "status": "error",
                "message": f"Не найдены блюда: {', '.join(not_found)}",
            }
        if not valid_items:
            return {"status": "error", "message": "Укажите хотя бы одно блюдо из меню."}

        lines = [
            {"name": item["name"], "quantity": item["qty"], "note": draft_data.get("comment", "")}
            for item in valid_items
        ]

        name = (draft_data.get("name") or client.name or "").strip()
        phone = (draft_data.get("phone") or client.phone or "").strip()
        if phone.startswith("web-test-"):
            phone = ""
        address = (draft_data.get("address") or "").strip()
        comment = (draft_data.get("comment") or "").strip()
        if draft_data.get("delivery_time"):
            comment = f"{comment} Время: {draft_data['delivery_time']}".strip()

        missing = []
        if not name:
            missing.append("имя")
        if not phone or len("".join(c for c in phone if c.isdigit())) < 9:
            missing.append("телефон")
        if order_type == Order.OrderType.DELIVERY and not address:
            missing.append("адрес доставки")
        if missing:
            return {
                "status": "error",
                "message": f"Для заказа нужны: {', '.join(missing)}.",
            }

        try:
            employee = get_assistant_employee()
            order = create_guest_order(
                employee,
                order_type=order_type,
                items=lines,
                customer_name=name,
                customer_phone=phone,
                delivery_address=address,
                comment=comment,
            )
        except OrderServiceError as exc:
            return {"status": "error", "message": str(exc)}

        AIOrder.objects.create(client=client, erp_order=order)
        ClientProfile.objects.filter(pk=client.pk).update(total_orders=client.total_orders + 1)

        if name and not client.name:
            client.name = name
        if phone and not client.phone:
            client.phone = phone
        if order_type == Order.OrderType.DELIVERY:
            client.preferred_order_type = "delivery"
        elif order_type == Order.OrderType.TAKEAWAY:
            client.preferred_order_type = "takeaway"
        client.save(update_fields=["name", "phone", "preferred_order_type"])

        total = int(order.total) if order.total == int(order.total) else float(order.total)
        return {"order_id": order.pk, "total": total, "status": "created"}
