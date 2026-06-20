"""API и вспомогательные представления для заказов."""
import json
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views import View

from apps.core.employees import get_acting_employee
from apps.core.mixins import RoleRequiredMixin
from apps.core.roles import FLOOR_STAFF_ROLES, KITCHEN_ROLES
from apps.menu.models import MenuItem
from apps.menu.services import menu_categories_json

from .date_filters import day_datetime_bounds, parse_order_date_filter
from .models import Order, OrderItem


def _parse_decimal(value, default=0):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)


def _parse_quantity(value, default=1):
    try:
        qty = Decimal(str(value))
        if qty <= 0:
            return Decimal(default)
        return qty
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)


def _parse_ready_datetime(date_str, time_str):
    if not date_str or not time_str:
        return None
    try:
        d = date.fromisoformat(date_str)
        t = datetime.strptime(time_str, "%H:%M").time()
        return timezone.make_aware(
            datetime.combine(d, t),
            timezone.get_current_timezone(),
        )
    except ValueError:
        return None


def _serialize_order_list_item(order):
    ready_at = order.estimated_ready_at
    return {
        "id": order.pk,
        "total": str(order.total),
        "status": order.status,
        "status_label": order.kitchen_display_status(),
        "order_type": order.order_type,
        "order_type_label": order.get_order_type_display(),
        "customer_name": order.customer_name,
        "customer_phone": order.customer_phone,
        "customer_phone_ext": order.customer_phone_ext,
        "delivery_address": order.delivery_address,
        "deposit": str(order.deposit),
        "estimated_ready_at": (
            timezone.localtime(ready_at).strftime("%d.%m.%Y %H:%M") if ready_at else ""
        ),
        "created_at": timezone.localtime(order.created_at).strftime("%d.%m.%Y %H:%M"),
        "comment": order.comment,
        "items_count": order.items.exclude(status=OrderItem.Status.CANCELLED).count(),
        "detail_url": f"/orders/{order.pk}/",
    }


class MenuAPIView(RoleRequiredMixin, View):
    allowed_roles = FLOOR_STAFF_ROLES + ["admin", "owner"] + KITCHEN_ROLES

    def get(self, request):
        return JsonResponse({"categories": menu_categories_json()})


class TakeawayOrdersAPIView(RoleRequiredMixin, View):
    allowed_roles = FLOOR_STAFF_ROLES + ["admin", "owner"]

    def get(self, request):
        from .views import _orders_for_user

        day_filter = request.GET.get("date", "today")
        start_day, end_day = parse_order_date_filter(day_filter)
        start_dt, _ = day_datetime_bounds(start_day)
        _, end_dt = day_datetime_bounds(end_day)

        qs = (
            _orders_for_user(request.user)
            .filter(
                order_type=Order.OrderType.TAKEAWAY,
                created_at__gte=start_dt,
                created_at__lt=end_dt,
            )
            .select_related("waiter__user")
            .order_by("-created_at")
        )
        if day_filter == "today":
            qs = qs.filter(
                status__in=[
                    Order.Status.OPEN,
                    Order.Status.SENT,
                    Order.Status.COOKING,
                    Order.Status.READY,
                    Order.Status.SERVED,
                ]
            )
        return JsonResponse({"orders": [_serialize_order_list_item(o) for o in qs]})


class DeliveryOrdersAPIView(RoleRequiredMixin, View):
    allowed_roles = FLOOR_STAFF_ROLES + ["admin", "owner"]

    def get(self, request):
        from .views import _orders_for_user, ACTIVE_ORDER_STATUSES

        day_filter = request.GET.get("date", "today")
        start_day, end_day = parse_order_date_filter(day_filter)
        start_dt, _ = day_datetime_bounds(start_day)
        _, end_dt = day_datetime_bounds(end_day)

        qs = (
            _orders_for_user(request.user)
            .filter(
                order_type=Order.OrderType.DELIVERY,
                created_at__gte=start_dt,
                created_at__lt=end_dt,
            )
            .select_related("waiter__user")
            .order_by("-created_at")
        )
        if day_filter == "today":
            qs = qs.filter(status__in=ACTIVE_ORDER_STATUSES)
        return JsonResponse({"orders": [_serialize_order_list_item(o) for o in qs]})


class TakeawayOrderAPIView(RoleRequiredMixin, View):
    allowed_roles = FLOOR_STAFF_ROLES + ["admin", "owner"]

    @transaction.atomic
    def post(self, request):
        from .views import _get_waiter, _orders_for_user

        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "invalid_json"}, status=400)

        order_id = payload.get("order_id")
        items = payload.get("items", [])
        customer_name = (payload.get("customer_name") or "").strip()
        customer_phone = (payload.get("customer_phone") or "").strip()
        deposit = _parse_decimal(payload.get("deposit", 0))
        ready_at = _parse_ready_datetime(
            payload.get("ready_date"), payload.get("ready_time")
        )

        if order_id:
            order = get_object_or_404(
                _orders_for_user(request.user),
                pk=order_id,
                order_type=Order.OrderType.TAKEAWAY,
            )
            order.customer_name = customer_name or order.customer_name
            order.customer_phone = customer_phone or order.customer_phone
            if deposit > 0:
                order.deposit = deposit
            if ready_at:
                order.estimated_ready_at = ready_at
            order.save(
                update_fields=[
                    "customer_name",
                    "customer_phone",
                    "deposit",
                    "estimated_ready_at",
                ]
            )
        else:
            if not customer_name or not customer_phone:
                return JsonResponse(
                    {"error": "Укажите имя и телефон клиента"}, status=400
                )
            if deposit <= 0 or not ready_at:
                return JsonResponse(
                    {"error": "Задаток и время готовности обязательны"}, status=400
                )
            if not items:
                return JsonResponse({"error": "Добавьте блюда в заказ"}, status=400)
            order = Order.objects.create(
                waiter=_get_waiter(request.user),
                order_type=Order.OrderType.TAKEAWAY,
                customer_name=customer_name,
                customer_phone=customer_phone,
                deposit=deposit,
                estimated_ready_at=ready_at,
            )

        for row in items:
            menu_item = get_object_or_404(
                MenuItem,
                pk=row.get("menu_item_id"),
                is_available=True,
                is_stopped=False,
            )
            OrderItem.objects.create(
                order=order,
                menu_item=menu_item,
                kitchen_section=menu_item.category.kitchen_section,
                quantity=_parse_quantity(row.get("quantity", 1)),
                price=menu_item.price,
                note=(row.get("note") or "")[:200],
            )
        order.recalculate_total()
        return JsonResponse({"ok": True, "order_id": order.pk, "total": str(order.total)})


class DeliveryOrderAPIView(RoleRequiredMixin, View):
    allowed_roles = FLOOR_STAFF_ROLES + ["admin", "owner"]

    @transaction.atomic
    def post(self, request):
        from .views import _get_waiter, _orders_for_user

        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "invalid_json"}, status=400)

        order_id = payload.get("order_id")
        items = payload.get("items", [])
        customer_name = (payload.get("customer_name") or "").strip()
        customer_phone = (payload.get("customer_phone") or "").strip()
        customer_phone_ext = (payload.get("customer_phone_ext") or "").strip()
        delivery_address = (payload.get("delivery_address") or "").strip()
        deposit = _parse_decimal(payload.get("deposit", 0))
        ready_at = _parse_ready_datetime(
            payload.get("ready_date"), payload.get("ready_time")
        )

        if order_id:
            order = get_object_or_404(
                _orders_for_user(request.user),
                pk=order_id,
                order_type=Order.OrderType.DELIVERY,
            )
            order.customer_name = customer_name or order.customer_name
            order.customer_phone = customer_phone or order.customer_phone
            order.customer_phone_ext = customer_phone_ext
            order.delivery_address = delivery_address or order.delivery_address
            if deposit > 0:
                order.deposit = deposit
            if ready_at:
                order.estimated_ready_at = ready_at
            order.save(
                update_fields=[
                    "customer_name",
                    "customer_phone",
                    "customer_phone_ext",
                    "delivery_address",
                    "deposit",
                    "estimated_ready_at",
                ]
            )
        else:
            if not all([customer_name, customer_phone, delivery_address]):
                return JsonResponse(
                    {"error": "Заполните имя, телефон и адрес доставки"}, status=400
                )
            if deposit <= 0 or not ready_at:
                return JsonResponse(
                    {"error": "Задаток и время готовности обязательны"}, status=400
                )
            if not items:
                return JsonResponse({"error": "Добавьте блюда в заказ"}, status=400)
            order = Order.objects.create(
                waiter=_get_waiter(request.user),
                order_type=Order.OrderType.DELIVERY,
                customer_name=customer_name,
                customer_phone=customer_phone,
                customer_phone_ext=customer_phone_ext,
                delivery_address=delivery_address,
                deposit=deposit,
                estimated_ready_at=ready_at,
            )

        for row in items:
            menu_item = get_object_or_404(
                MenuItem,
                pk=row.get("menu_item_id"),
                is_available=True,
                is_stopped=False,
            )
            OrderItem.objects.create(
                order=order,
                menu_item=menu_item,
                kitchen_section=menu_item.category.kitchen_section,
                quantity=_parse_quantity(row.get("quantity", 1)),
                price=menu_item.price,
                note=(row.get("note") or "")[:200],
            )
        order.recalculate_total()
        return JsonResponse({"ok": True, "order_id": order.pk, "total": str(order.total)})
