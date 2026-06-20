from django.db.models import Prefetch
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView, ListView, TemplateView

from apps.core.employees import user_has_elevated_access
from apps.core.mixins import RoleRequiredMixin
from apps.core.roles import KITCHEN_ROLES
from apps.orders.date_filters import day_datetime_bounds, parse_order_date_filter
from apps.orders.models import KitchenSection, Order, OrderItem

ACTIVE_ORDER_STATUSES = [
    Order.Status.OPEN,
    Order.Status.SENT,
    Order.Status.COOKING,
    Order.Status.READY,
    Order.Status.SERVED,
]


class KitchenDisplayView(RoleRequiredMixin, TemplateView):
    template_name = "kitchen/display.html"
    allowed_roles = KITCHEN_ROLES + ["admin", "owner"]

    def dispatch(self, request, *args, **kwargs):
        self.section = get_object_or_404(KitchenSection, slug=kwargs["section_slug"])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["section"] = self.section
        ctx["items"] = (
            OrderItem.objects.filter(
                kitchen_section=self.section,
                status__in=[
                    OrderItem.Status.PENDING,
                    OrderItem.Status.COOKING,
                ],
            )
            .select_related("order", "order__table", "order__waiter__user", "menu_item")
            .order_by("order__created_at")
        )
        section_items = OrderItem.objects.filter(
            kitchen_section=self.section
        ).select_related("menu_item", "ready_by__user")
        today_start, today_end = day_datetime_bounds(timezone.localdate())
        ctx["section_orders"] = (
            Order.objects.filter(
                items__kitchen_section=self.section,
                status__in=ACTIVE_ORDER_STATUSES,
                created_at__gte=today_start,
                created_at__lt=today_end,
            )
            .distinct()
            .select_related("table", "waiter__user")
            .prefetch_related(
                Prefetch("items", queryset=section_items, to_attr="section_items_list")
            )
            .order_by("-created_at")
        )
        return ctx


class KitchenOrdersHistoryAPIView(RoleRequiredMixin, View):
    allowed_roles = KITCHEN_ROLES + ["admin", "owner"]

    def get(self, request, section_slug):
        section = get_object_or_404(KitchenSection, slug=section_slug)
        day_filter = request.GET.get("date", "today")
        start_day, end_day = parse_order_date_filter(day_filter)
        start_dt, _ = day_datetime_bounds(start_day)
        _, end_dt = day_datetime_bounds(end_day)

        section_items = OrderItem.objects.filter(
            kitchen_section=section
        ).select_related("menu_item", "ready_by__user")

        qs = (
            Order.objects.filter(
                items__kitchen_section=section,
                created_at__gte=start_dt,
                created_at__lt=end_dt,
            )
            .distinct()
            .select_related("table", "waiter__user")
            .prefetch_related(
                Prefetch("items", queryset=section_items, to_attr="section_items_list")
            )
            .order_by("-created_at")
        )

        if day_filter == "today":
            qs = qs.filter(status__in=ACTIVE_ORDER_STATUSES)

        orders = []
        for o in qs:
            items = [
                {
                    "id": si.pk,
                    "name": si.menu_item.name,
                    "quantity": str(si.quantity),
                    "unit": si.menu_item.get_unit_display(),
                    "status": si.status,
                    "status_label": si.get_status_display(),
                }
                for si in getattr(o, "section_items_list", [])
            ]
            table_label = ""
            if o.table:
                table_label = f"№{o.table.number}"
            elif o.order_type == Order.OrderType.DELIVERY:
                table_label = o.customer_name or "Доставка"
            else:
                table_label = "Навынос"
            orders.append(
                {
                    "id": o.pk,
                    "order_type": o.get_order_type_display(),
                    "source": table_label,
                    "status": o.get_status_display(),
                    "created_at": o.created_at.strftime("%d.%m %H:%M"),
                    "items": items,
                    "detail_url": f"/orders/{o.pk}/",
                }
            )
        return JsonResponse({"orders": orders})


class KitchenCompletedOrdersView(RoleRequiredMixin, ListView):
    template_name = "kitchen/completed_orders.html"
    context_object_name = "orders"
    allowed_roles = KITCHEN_ROLES + ["admin", "owner"]
    paginate_by = 30

    def dispatch(self, request, *args, **kwargs):
        self.section = get_object_or_404(KitchenSection, slug=kwargs["section_slug"])
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        qs = Order.objects.filter(
            items__kitchen_section=self.section,
            items__status=OrderItem.Status.READY,
        ).distinct()
        if (
            hasattr(self.request.user, "employee")
            and not user_has_elevated_access(self.request.user)
        ):
            qs = qs.filter(items__ready_by=self.request.user.employee)
        section_items = OrderItem.objects.filter(
            kitchen_section=self.section,
            status=OrderItem.Status.READY,
        ).select_related("menu_item")
        return (
            qs.select_related("table", "waiter__user")
            .prefetch_related(Prefetch("items", queryset=section_items))
            .order_by("-created_at")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["section"] = self.section
        return ctx


class KitchenOrderDetailView(RoleRequiredMixin, DetailView):
    model = Order
    template_name = "kitchen/order_detail.html"
    context_object_name = "order"
    allowed_roles = KITCHEN_ROLES + ["admin", "owner"]

    def dispatch(self, request, *args, **kwargs):
        self.section = get_object_or_404(KitchenSection, slug=kwargs["section_slug"])
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        qs = Order.objects.filter(
            items__kitchen_section=self.section,
            items__status=OrderItem.Status.READY,
        )
        if (
            hasattr(self.request.user, "employee")
            and not user_has_elevated_access(self.request.user)
        ):
            qs = qs.filter(items__ready_by=self.request.user.employee)
        return qs.distinct().prefetch_related("items__menu_item")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["section"] = self.section
        items_qs = self.object.items.filter(kitchen_section=self.section)
        if (
            hasattr(self.request.user, "employee")
            and not user_has_elevated_access(self.request.user)
        ):
            items_qs = items_qs.filter(ready_by=self.request.user.employee)
        ctx["section_items"] = items_qs
        return ctx
