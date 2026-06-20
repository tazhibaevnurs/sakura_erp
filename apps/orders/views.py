import json
import logging
from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import DetailView, FormView, ListView, TemplateView

from apps.cash.services import is_day_closed
from apps.core.employees import get_acting_employee, user_effective_role, user_has_elevated_access
from apps.core.mixins import RoleRequiredMixin
from apps.core.roles import FLOOR_STAFF_ROLES, KITCHEN_ROLES
from apps.menu.models import MenuItem
from apps.menu.services import get_menu_categories
from apps.tables.models import Table
from apps.tables.reservation_time import current_reservation_for_table

from .forms import AddOrderItemForm, CancelOrderForm, DeliveryOrderForm, OrderForm, PayOrderForm
from .date_filters import day_datetime_bounds
from .models import Order, OrderItem

logger = logging.getLogger("chaihana.finance")


def _orders_for_user(user):
    qs = Order.objects.select_related("table", "waiter")
    if user_has_elevated_access(user):
        return qs
    if not hasattr(user, "employee"):
        return qs.none()
    role = user_effective_role(user)
    if role in ("owner", "admin") or role in KITCHEN_ROLES or role in FLOOR_STAFF_ROLES:
        return qs
    return qs.filter(waiter=user.employee)


def _parse_quantity(value, default=1):
    try:
        qty = Decimal(str(value))
        if qty <= 0:
            return Decimal(default)
        return qty
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)


def _get_waiter(user):
    return get_acting_employee(user)


ACTIVE_ORDER_STATUSES = [
    Order.Status.OPEN,
    Order.Status.SENT,
    Order.Status.COOKING,
    Order.Status.READY,
    Order.Status.SERVED,
]


def _active_order_for_table(table):
    return Order.objects.filter(
        table=table,
        status__in=ACTIVE_ORDER_STATUSES,
    ).first()


class OrderListView(RoleRequiredMixin, ListView):
    template_name = "orders/list.html"
    context_object_name = "orders"
    allowed_roles = FLOOR_STAFF_ROLES + ["admin", "owner"]
    paginate_by = 40

    def get_queryset(self):
        qs = (
            _orders_for_user(self.request.user)
            .select_related("table", "waiter__user")
            .prefetch_related("table_reservation")
            .annotate(
                ready_items_count=Count(
                    "items", filter=Q(items__status=OrderItem.Status.READY)
                ),
                active_items_count=Count(
                    "items",
                    filter=~Q(items__status=OrderItem.Status.CANCELLED),
                ),
            )
        )
        view_filter = self.request.GET.get("filter", "today")
        if view_filter == "today":
            start, end = day_datetime_bounds(timezone.localdate())
            qs = qs.filter(created_at__gte=start, created_at__lt=end)
        elif view_filter == "closed":
            qs = qs.filter(status__in=[Order.Status.PAID, Order.Status.CANCELLED])
        elif view_filter == "all":
            pass
        elif view_filter == "active":
            qs = qs.filter(status__in=ACTIVE_ORDER_STATUSES)
        else:
            start, end = day_datetime_bounds(timezone.localdate())
            qs = qs.filter(created_at__gte=start, created_at__lt=end)
        return qs.order_by("-created_at")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["order_filter"] = self.request.GET.get("filter", "today")
        base_qs = _orders_for_user(self.request.user)
        today_start, today_end = day_datetime_bounds(timezone.localdate())
        ctx["count_today"] = base_qs.filter(
            created_at__gte=today_start, created_at__lt=today_end
        ).count()
        ctx["count_active"] = base_qs.filter(status__in=ACTIVE_ORDER_STATUSES).count()
        ctx["count_closed"] = base_qs.filter(
            status__in=[Order.Status.PAID, Order.Status.CANCELLED]
        ).count()
        ctx["count_all"] = base_qs.count()
        return ctx


class CreateOrderView(RoleRequiredMixin, FormView):
    template_name = "orders/create.html"
    form_class = OrderForm
    allowed_roles = ["waiter", "admin", "owner"]

    def dispatch(self, request, *args, **kwargs):
        self.table = get_object_or_404(Table, pk=kwargs.get("table_id"))
        active = _active_order_for_table(self.table)
        if request.method == "GET" and active and "force_new" not in request.GET:
            return redirect("orders:detail", pk=active.pk)
        current_res = current_reservation_for_table(self.table)
        if request.method == "GET" and current_res:
            if current_res.order_id:
                return redirect("orders:detail", pk=current_res.order.pk)
            messages.info(
                request,
                "Сейчас действует бронь на это время. Отметьте прибытие гостя или отмените бронь.",
            )
            return redirect("tables:reservation_detail", pk=current_res.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["table"] = self.table
        ctx["menu_categories"] = get_menu_categories()
        ctx["menu_items"] = MenuItem.objects.filter(
            is_available=True, is_stopped=False
        ).select_related("category").order_by("category__order", "order")
        ctx["order"] = _active_order_for_table(self.table)
        ctx["add_form"] = AddOrderItemForm()
        return ctx

    def form_valid(self, form):
        order = _active_order_for_table(self.table)
        if not order:
            order = form.save(commit=False)
            order.table = self.table
            order.waiter = _get_waiter(self.request.user)
            order.save()
            self.table.status = Table.Status.OCCUPIED
            self.table.save(update_fields=["status"])
        else:
            order.guest_count = form.cleaned_data.get("guest_count", order.guest_count)
            order.comment = form.cleaned_data.get("comment", "")
            order.save(update_fields=["guest_count", "comment"])
        return redirect("orders:detail", pk=order.pk)

    def post(self, request, *args, **kwargs):
        if "add_item" in request.POST or request.POST.get("menu_item_id"):
            return self._add_item(request)
        return super().post(request, *args, **kwargs)

    def _add_item(self, request):
        menu_item_id = request.POST.get("menu_item_id")
        if menu_item_id:
            menu_item = get_object_or_404(
                MenuItem, pk=menu_item_id, is_available=True, is_stopped=False
            )
            quantity = _parse_quantity(request.POST.get("quantity", 1))
            note = request.POST.get("note", "")
        else:
            form = AddOrderItemForm(request.POST)
            if not form.is_valid():
                messages.error(request, "Ошибка добавления блюда")
                return redirect("orders:create", table_id=self.table.pk)
            menu_item = form.cleaned_data["menu_item"]
            quantity = form.cleaned_data["quantity"]
            note = form.cleaned_data.get("note", "")

        order = _active_order_for_table(self.table)
        if not order:
            guest_count = int(request.POST.get("guest_count", 1))
            order = Order.objects.create(
                table=self.table,
                waiter=_get_waiter(request.user),
                guest_count=guest_count,
            )
            self.table.status = Table.Status.OCCUPIED
            self.table.save(update_fields=["status"])

        OrderItem.objects.create(
            order=order,
            menu_item=menu_item,
            kitchen_section=menu_item.category.kitchen_section,
            quantity=quantity,
            price=menu_item.price,
            note=note,
        )
        order.recalculate_total()
        messages.success(request, f"Добавлено: {menu_item.name}")
        return redirect("orders:create", table_id=self.table.pk)


class OrderDetailView(RoleRequiredMixin, DetailView):
    model = Order
    template_name = "orders/detail.html"
    context_object_name = "order"
    allowed_roles = FLOOR_STAFF_ROLES + ["admin", "owner"]

    def get_queryset(self):
        return _orders_for_user(self.request.user).prefetch_related(
            "items__menu_item"
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["add_form"] = AddOrderItemForm()
        ctx["menu_categories"] = get_menu_categories()
        ctx["menu_items"] = MenuItem.objects.filter(
            is_available=True, is_stopped=False
        ).select_related("category")
        ctx["cash_closed"] = is_day_closed(date.today())
        ctx["kitchen_status"] = self.object.kitchen_display_status()
        ctx["can_send_kitchen"] = self.object.can_send_to_kitchen()
        return ctx

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if "add_item" in request.POST:
            form = AddOrderItemForm(request.POST)
            if form.is_valid():
                menu_item = form.cleaned_data["menu_item"]
                OrderItem.objects.create(
                    order=self.object,
                    menu_item=menu_item,
                    kitchen_section=menu_item.category.kitchen_section,
                    quantity=form.cleaned_data["quantity"],
                    price=menu_item.price,
                    note=form.cleaned_data.get("note", ""),
                )
                self.object.recalculate_total()
                if self.object.status == Order.Status.OPEN:
                    self.object.status = Order.Status.SENT
                    self.object.save(update_fields=["status"])
        elif "send_kitchen" in request.POST:
            if not self.object.can_send_to_kitchen():
                messages.error(
                    request,
                    "Добавьте блюда"
                    + (
                        " и заполните данные клиента (задаток, время готовности)."
                        if self.object.requires_guest_fields()
                        else "."
                    ),
                )
                return redirect("orders:detail", pk=self.object.pk)
            self.object.status = Order.Status.SENT
            self.object.save(update_fields=["status"])
            now = timezone.now()
            self.object.items.filter(sent_at__isnull=True).update(sent_at=now)
            messages.success(request, "Заказ отправлен на кухню")
        elif "save_guest_info" in request.POST:
            if self.object.order_type in (
                Order.OrderType.TAKEAWAY,
                Order.OrderType.DELIVERY,
            ):
                self.object.customer_name = request.POST.get("customer_name", "").strip()
                self.object.customer_phone = request.POST.get(
                    "customer_phone", ""
                ).strip()
                self.object.customer_phone_ext = request.POST.get(
                    "customer_phone_ext", ""
                ).strip()
                self.object.delivery_address = request.POST.get(
                    "delivery_address", ""
                ).strip()
                self.object.deposit = _parse_quantity(request.POST.get("deposit", 0))
                ready_date = request.POST.get("ready_date")
                ready_time = request.POST.get("ready_time")
                if ready_date and ready_time:
                    from datetime import datetime as dt

                    try:
                        d = date.fromisoformat(ready_date)
                        t = dt.strptime(ready_time, "%H:%M").time()
                        self.object.estimated_ready_at = timezone.make_aware(
                            dt.combine(d, t),
                            timezone.get_current_timezone(),
                        )
                    except ValueError:
                        pass
                self.object.save(
                    update_fields=[
                        "customer_name",
                        "customer_phone",
                        "customer_phone_ext",
                        "delivery_address",
                        "deposit",
                        "estimated_ready_at",
                    ]
                )
                messages.success(request, "Данные клиента сохранены")
        return redirect("orders:detail", pk=self.object.pk)


class PayOrderView(RoleRequiredMixin, FormView):
    template_name = "orders/pay.html"
    form_class = PayOrderForm
    allowed_roles = ["waiter", "admin", "owner"]

    def dispatch(self, request, *args, **kwargs):
        self.order = get_object_or_404(_orders_for_user(request.user), pk=kwargs["pk"])
        if is_day_closed(date.today()):
            messages.error(
                request,
                "Касса за сегодня закрыта. Оплата заказов недоступна.",
            )
            return redirect("orders:detail", pk=self.order.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["order"] = self.order
        return ctx

    @transaction.atomic
    def form_valid(self, form):
        self.order.payment_method = form.cleaned_data["payment_method"]
        self.order.status = Order.Status.PAID
        self.order.paid_at = timezone.now()
        self.order.save()
        logger.info("Order %s paid via %s", self.order.pk, self.order.payment_method)
        messages.success(self.request, "Заказ оплачен")
        return redirect("tables:floor")


class CancelOrderView(RoleRequiredMixin, FormView):
    template_name = "orders/cancel.html"
    form_class = CancelOrderForm
    allowed_roles = ["admin", "owner"]

    def dispatch(self, request, *args, **kwargs):
        self.order = get_object_or_404(Order, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["order"] = self.order
        return ctx

    def form_valid(self, form):
        self.order.status = Order.Status.CANCELLED
        self.order.cancelled_reason = form.cleaned_data["cancelled_reason"]
        self.order.save()
        if self.order.table:
            self.order.table.status = Table.Status.FREE
            self.order.table.save(update_fields=["status"])
        messages.warning(self.request, "Заказ отменён")
        return redirect("tables:floor")


class TakeawayOrderView(RoleRequiredMixin, TemplateView):
    template_name = "orders/takeaway.html"
    allowed_roles = FLOOR_STAFF_ROLES + ["admin", "owner"]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["today"] = timezone.localdate().isoformat()
        return ctx


class DeliveryOrderView(RoleRequiredMixin, TemplateView):
    template_name = "orders/delivery.html"
    allowed_roles = FLOOR_STAFF_ROLES + ["admin", "owner"]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["today"] = timezone.localdate().isoformat()
        return ctx


def _kitchen_item_guard(request, item):
    if user_has_elevated_access(request.user):
        return None
    if not hasattr(request.user, "employee"):
        return JsonResponse({"error": "forbidden"}, status=403)
    emp = request.user.employee
    if emp.kitchen_section_id and item.kitchen_section_id != emp.kitchen_section_id:
        return JsonResponse({"error": "forbidden"}, status=403)
    return None


@method_decorator(csrf_exempt, name="dispatch")
class OrderItemCookingAPIView(RoleRequiredMixin, View):
    allowed_roles = KITCHEN_ROLES + ["admin", "owner"]

    def post(self, request, pk):
        item = get_object_or_404(OrderItem, pk=pk)
        denied = _kitchen_item_guard(request, item)
        if denied:
            return denied
        if item.status != OrderItem.Status.PENDING:
            return JsonResponse({"error": "invalid_status"}, status=400)
        item.status = OrderItem.Status.COOKING
        item.save(update_fields=["status"])
        from .order_status import sync_order_kitchen_status

        sync_order_kitchen_status(item.order)
        return JsonResponse({"ok": True, "id": item.pk, "status": item.status})


@method_decorator(csrf_exempt, name="dispatch")
class OrderItemReadyAPIView(RoleRequiredMixin, View):
    allowed_roles = KITCHEN_ROLES + ["admin", "owner"]

    def post(self, request, pk):
        item = get_object_or_404(OrderItem, pk=pk)
        denied = _kitchen_item_guard(request, item)
        if denied:
            return denied
        if item.status not in (OrderItem.Status.PENDING, OrderItem.Status.COOKING):
            return JsonResponse({"error": "invalid_status"}, status=400)
        item.status = OrderItem.Status.READY
        item.ready_at = timezone.now()
        if hasattr(request.user, "employee"):
            item.ready_by = request.user.employee
        item.save(update_fields=["status", "ready_at", "ready_by"])
        from .order_status import sync_order_kitchen_status

        sync_order_kitchen_status(item.order)
        return JsonResponse({"ok": True, "id": item.pk, "status": item.status})
