import json
from calendar import monthrange
from datetime import date, datetime, timedelta
from urllib.parse import urlencode

from django.contrib import messages
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Prefetch
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView, FormView, TemplateView

from apps.core.employees import get_acting_employee
from apps.core.mixins import RoleRequiredMixin
from apps.core.roles import FLOOR_STAFF_ROLES

from .calendar_order import (
    available_tables_for_slot,
    booked_slots_json_for_date,
    build_month_grid,
    combine_slot,
    reservations_for_date,
)
from .forms import CalendarOrderForm, QuickReserveTableForm, TableReservationForm
from .models import Table, TableReservation
from .reservation_time import (
    effective_floor_status,
    floor_card_style,
    floor_reservation_for_table,
    sync_table_reserved_status,
)
from .services import (
    ReservationError,
    cancel_reservation,
    complete_reservation_arrival,
    create_preorder_for_reservation,
    create_reservation,
)


def _booth_url(table):
    return reverse("tables:booth", kwargs={"pk": table.pk})


def _calendar_order_url(**params):
    base = reverse("tables:calendar_order")
    qs = urlencode({k: v for k, v in params.items() if v not in (None, "")})
    return f"{base}?{qs}" if qs else base


class FloorPlanView(RoleRequiredMixin, TemplateView):
    template_name = "tables/floor_plan.html"
    allowed_roles = FLOOR_STAFF_ROLES + ["admin", "owner"]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        active_res = TableReservation.objects.filter(
            status=TableReservation.Status.ACTIVE
        )
        tables = list(
            Table.objects.prefetch_related(
                Prefetch("reservations", queryset=active_res)
            ).order_by("number")
        )
        for table in tables:
            sync_table_reserved_status(table)
        ctx["tables"] = tables
        now = timezone.now()
        ctx["upcoming_reservations"] = (
            TableReservation.objects.filter(
                status=TableReservation.Status.ACTIVE,
                reserved_until__gte=now,
            )
            .select_related("table", "created_by__user")
            .order_by("reserved_for")[:12]
        )
        return ctx


class TableHubView(RoleRequiredMixin, DetailView):
    """Кабинка: открыть заказ, забронировать или управлять бронью."""
    model = Table
    template_name = "tables/booth_hub.html"
    context_object_name = "table"
    allowed_roles = FLOOR_STAFF_ROLES + ["admin", "owner"]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        table = self.object
        sync_table_reserved_status(table)
        ctx["active_order"] = table.active_order
        ctx["reservation"] = table.active_reservation
        ctx["upcoming"] = table.upcoming_reservations()
        ctx["can_reserve"] = True
        return ctx


class ReserveTableView(RoleRequiredMixin, FormView):
    template_name = "tables/reserve.html"
    form_class = TableReservationForm
    allowed_roles = FLOOR_STAFF_ROLES + ["admin", "owner"]

    def dispatch(self, request, *args, **kwargs):
        self.table = get_object_or_404(Table, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["table"] = self.table
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["table"] = self.table
        existing = self.table.reservations.filter(
            status=TableReservation.Status.ACTIVE
        ).order_by("reserved_for")
        ctx["existing_reservations"] = existing
        ctx["booked_slots_json"] = json.dumps(
            [
                {
                    "start": r.reserved_for.isoformat(),
                    "end": r.reserved_until.isoformat(),
                    "guest": r.guest_name,
                }
                for r in existing
            ],
            cls=DjangoJSONEncoder,
        )
        return ctx

    def form_valid(self, form):
        try:
            reservation = create_reservation(
                table=self.table,
                guest_name=form.cleaned_data["guest_name"],
                guest_phone=form.cleaned_data.get("guest_phone", ""),
                guest_count=form.cleaned_data["guest_count"],
                reserved_for=form.cleaned_data["reserved_for"],
                reserved_until=form.cleaned_data["reserved_until"],
                comment=form.cleaned_data.get("comment", ""),
                employee=get_acting_employee(self.request.user),
            )
        except ReservationError as e:
            form.add_error(None, str(e))
            return self.form_invalid(form)

        messages.success(
            self.request,
            f"Кабинка {self.table.number} забронирована на "
            f"{reservation.time_range_display}.",
        )
        return redirect("tables:reservation_detail", pk=reservation.pk)


class ReservationDetailView(RoleRequiredMixin, DetailView):
    model = TableReservation
    template_name = "tables/reservation_detail.html"
    context_object_name = "reservation"
    allowed_roles = FLOOR_STAFF_ROLES + ["admin", "owner"]

    def get_queryset(self):
        return TableReservation.objects.select_related(
            "table", "created_by__user", "order"
        )


class ReservationListView(RoleRequiredMixin, TemplateView):
    template_name = "tables/reservation_list.html"
    allowed_roles = FLOOR_STAFF_ROLES + ["admin", "owner"]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        qs = TableReservation.objects.select_related(
            "table", "created_by__user"
        ).filter(status=TableReservation.Status.ACTIVE)
        ctx["reservations"] = qs.order_by("reserved_for")
        ctx["quick_form"] = QuickReserveTableForm()
        return ctx


class CancelReservationView(RoleRequiredMixin, View):
    allowed_roles = FLOOR_STAFF_ROLES + ["admin", "owner"]

    def post(self, request, pk):
        reservation = get_object_or_404(TableReservation, pk=pk)
        try:
            cancel_reservation(reservation)
        except ReservationError as e:
            messages.error(request, str(e))
            return redirect("tables:reservation_detail", pk=pk)

        messages.info(request, f"Бронь кабинки {reservation.table.number} отменена.")
        return redirect("tables:floor")


class ArriveReservationView(RoleRequiredMixin, View):
    allowed_roles = FLOOR_STAFF_ROLES + ["admin", "owner"]

    def post(self, request, pk):
        reservation = get_object_or_404(
            TableReservation,
            pk=pk,
            status=TableReservation.Status.ACTIVE,
        )
        table = reservation.table
        try:
            order = complete_reservation_arrival(reservation)
        except ReservationError as e:
            messages.error(request, str(e))
            return redirect("tables:reservation_detail", pk=pk)
        if order:
            messages.success(
                request,
                f"Гость в кабинке {table.number}. Предзаказ #{order.pk} открыт.",
            )
            return redirect("orders:detail", pk=order.pk)

        messages.success(request, f"Гость в кабинке {table.number}. Соберите заказ.")
        return redirect("orders:create", table_id=table.pk)


class PreorderReservationView(RoleRequiredMixin, View):
    allowed_roles = FLOOR_STAFF_ROLES + ["admin", "owner"]

    def post(self, request, pk):
        reservation = get_object_or_404(
            TableReservation.objects.select_related("table", "order"),
            pk=pk,
            status=TableReservation.Status.ACTIVE,
        )
        employee = get_acting_employee(request.user)
        if not employee:
            messages.error(request, "Не удалось определить сотрудника.")
            return redirect("tables:reservation_detail", pk=pk)

        try:
            order = create_preorder_for_reservation(reservation, employee)
        except ReservationError as e:
            messages.error(request, str(e))
            return redirect("tables:reservation_detail", pk=pk)

        messages.success(
            request,
            f"Предзаказ #{order.pk}. Добавьте блюда и отправьте на кухню к приходу гостя.",
        )
        return redirect("orders:detail", pk=order.pk)


class CalendarOrderView(RoleRequiredMixin, View):
    """Приём заказа: календарный день → время → стол → предзаказ."""

    template_name = "tables/calendar_order.html"
    allowed_roles = FLOOR_STAFF_ROLES + ["admin", "owner"]

    def get(self, request):
        step = request.GET.get("step", "date")
        ctx = self._base_context(request, step)
        if step == "time":
            if not ctx.get("selected_date"):
                return redirect(_calendar_order_url())
            return self._render(request, ctx, step="time")
        if step == "table":
            slot = ctx.get("slot")
            if not slot:
                return redirect(
                    _calendar_order_url(
                        step="time",
                        date=ctx.get("date_param", ""),
                    )
                )
            ctx["available_tables"] = available_tables_for_slot(*slot)
            return self._render(request, ctx, step="table")
        if step == "order":
            table = ctx.get("selected_table")
            slot = ctx.get("slot")
            if not (table and slot):
                return redirect(_calendar_order_url())
            ctx["form"] = CalendarOrderForm(
                initial={
                    "table_id": table.pk,
                    "reserved_date": ctx["selected_date"],
                    "reserved_time_start": ctx["time_start"],
                    "reserved_time_end": ctx["time_end"],
                    "guest_count": min(2, table.capacity),
                }
            )
            return self._render(request, ctx, step="order")
        return self._render(request, ctx, step="date")

    def post(self, request):
        form = CalendarOrderForm(request.POST)
        if not form.is_valid():
            query = request.GET.copy()
            query["step"] = "order"
            if request.POST.get("table_id"):
                query["table"] = request.POST["table_id"]
            if request.POST.get("reserved_date"):
                query["date"] = request.POST["reserved_date"]
            if request.POST.get("reserved_time_start"):
                query["start"] = request.POST["reserved_time_start"]
            if request.POST.get("reserved_time_end"):
                query["end"] = request.POST["reserved_time_end"]
            ctx = self._base_context(request, "order", query=query)
            ctx["form"] = form
            return self._render(request, ctx, step="order")

        employee = get_acting_employee(request.user)
        if not employee:
            messages.error(request, "Не удалось определить сотрудника.")
            return redirect(_calendar_order_url())
        try:
            reservation = create_reservation(
                table=form.table,
                guest_name=form.cleaned_data["guest_name"],
                guest_phone=form.cleaned_data.get("guest_phone", ""),
                guest_count=form.cleaned_data["guest_count"],
                reserved_for=form.cleaned_data["reserved_for"],
                reserved_until=form.cleaned_data["reserved_until"],
                comment=form.cleaned_data.get("comment", ""),
                employee=employee,
            )
            order = create_preorder_for_reservation(reservation, employee)
        except ReservationError as e:
            messages.error(request, str(e))
            cd = form.cleaned_data
            end_val = cd.get("reserved_time_end")
            return redirect(
                _calendar_order_url(
                    step="order",
                    date=cd["reserved_date"].isoformat(),
                    start=cd["reserved_time_start"].strftime("%H:%M"),
                    end=end_val.strftime("%H:%M") if end_val else "",
                    table=cd["table_id"],
                )
            )

        messages.success(
            request,
            f"Заказ по календарю: кабинка {form.table.number}, "
            f"{reservation.time_range_display}. Добавьте блюда.",
        )
        return redirect("orders:detail", pk=order.pk)

    def _base_context(self, request, step, query=None):
        q = query if query is not None else request.GET
        today = timezone.localdate()
        month_param = q.get("month")
        if month_param:
            try:
                year, month = map(int, month_param.split("-"))
            except ValueError:
                year, month = today.year, today.month
        else:
            year, month = today.year, today.month

        date_param = q.get("date")
        selected_date = None
        if date_param:
            try:
                selected_date = date.fromisoformat(date_param)
            except ValueError:
                selected_date = None

        time_start_str = q.get("start", "")
        time_end_str = q.get("end", "")
        if selected_date and not time_start_str and step in ("time", "table", "order"):
            from .reservation_time import DEFAULT_DURATION

            if selected_date == today:
                now_local = timezone.localtime()
                rounded = now_local.replace(
                    minute=(now_local.minute // 15) * 15,
                    second=0,
                    microsecond=0,
                )
                time_start = rounded.time()
            else:
                time_start = datetime.strptime("12:00", "%H:%M").time()
            end_dt = datetime.combine(selected_date, time_start) + DEFAULT_DURATION
            time_end = end_dt.time()
            time_start_str = time_start.strftime("%H:%M")
            time_end_str = time_end.strftime("%H:%M")

        time_start = None
        time_end = None
        slot = None
        if selected_date and time_start_str:
            try:
                time_start = datetime.strptime(time_start_str, "%H:%M").time()
                time_end = (
                    datetime.strptime(time_end_str, "%H:%M").time()
                    if time_end_str
                    else None
                )
                slot = combine_slot(selected_date, time_start, time_end)
            except ValueError:
                slot = None

        table = None
        table_id = q.get("table")
        if table_id:
            table = Table.objects.filter(pk=table_id).first()

        prev_month = date(year, month, 1) - timedelta(days=1)
        next_month = date(year, month, monthrange(year, month)[1]) + timedelta(days=1)

        return {
            "step": step,
            "year": year,
            "month": month,
            "month_label": _month_label(year, month),
            "prev_month": f"{prev_month.year}-{prev_month.month:02d}",
            "next_month": f"{next_month.year}-{next_month.month:02d}",
            "weeks": build_month_grid(year, month, selected=selected_date),
            "selected_date": selected_date,
            "date_param": date_param or "",
            "time_start": time_start,
            "time_end": time_end,
            "time_start_str": time_start_str,
            "time_end_str": time_end_str,
            "slot": slot,
            "selected_table": table,
            "day_reservations": reservations_for_date(selected_date)
            if selected_date
            else [],
            "booked_slots_json": json.dumps(
                booked_slots_json_for_date(selected_date) if selected_date else [],
                cls=DjangoJSONEncoder,
            ),
        }

    def _render(self, request, ctx, step):
        ctx["step"] = step
        from django.shortcuts import render

        return render(request, self.template_name, ctx)


def _month_label(year, month):
    months = [
        "Январь",
        "Февраль",
        "Март",
        "Апрель",
        "Май",
        "Июнь",
        "Июль",
        "Август",
        "Сентябрь",
        "Октябрь",
        "Ноябрь",
        "Декабрь",
    ]
    return f"{months[month - 1]} {year}"


class TableStatusAPIView(RoleRequiredMixin, View):
    allowed_roles = FLOOR_STAFF_ROLES + ["admin", "owner"]

    def get(self, request):
        data = []
        for t in Table.objects.all():
            sync_table_reserved_status(t)
            order = t.active_order
            reservation = floor_reservation_for_table(t)
            card_style = floor_card_style(t)
            status_labels = dict(Table.Status.choices)
            if card_style == "booking_now":
                status_label = "Сейчас бронь"
            elif card_style == "booked":
                status_label = "Зарезервирован"
            else:
                status_label = status_labels.get(card_style, card_style)
            data.append(
                {
                    "id": t.pk,
                    "number": t.number,
                    "status": card_style,
                    "status_label": status_label,
                    "order_id": order.pk if order else None,
                    "reservation_id": reservation.pk if reservation else None,
                    "guest_name": reservation.guest_name if reservation else "",
                    "reserved_for": (
                        timezone.localtime(reservation.reserved_for).strftime("%H:%M")
                        if reservation
                        else ""
                    ),
                    "hub_url": _booth_url(t),
                }
            )
        return JsonResponse({"tables": data})
