from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from django.views.generic import DetailView, ListView, TemplateView

from apps.core.employees import user_has_elevated_access
from apps.core.mixins import RoleRequiredMixin
from apps.core.roles import KITCHEN_ROLES
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
        ctx["section_orders"] = (
            Order.objects.filter(
                items__kitchen_section=self.section,
                status__in=ACTIVE_ORDER_STATUSES,
            )
            .distinct()
            .select_related("table", "waiter__user")
            .prefetch_related(
                Prefetch("items", queryset=section_items, to_attr="section_items_list")
            )
            .order_by("-created_at")
        )
        return ctx


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
