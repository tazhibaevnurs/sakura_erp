import json
from calendar import monthrange
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

from django.contrib import messages
from django.core.serializers.json import DjangoJSONEncoder
from django.db import IntegrityError, transaction
from django.db.models import Prefetch, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView, TemplateView

from apps.accounts.models import Employee
from apps.core.employees import get_acting_employee
from apps.core.mixins import RoleRequiredMixin
from apps.core.roles import FLOOR_STAFF_ROLES, WAITER_ROLES
from apps.menu.models import MenuItem
from apps.orders.models import OrderItem

from .calendar_order import (
    available_tables_for_slot,
    booked_slots_json_for_date,
    build_month_grid,
    combine_slot,
    reservations_for_date,
)
from .forms import CalendarOrderForm, QuickReserveTableForm
from .models import Table, TableReservation, TableWaiterAssignment
from .reservation_time import (
    DEFAULT_DURATION,
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


def _calendar_order_url_for_table(table):
    """Приём заказа: сегодня, ближайший слот, выбранная кабинка."""
    today = timezone.localdate()
    now_local = timezone.localtime()
    if today == now_local.date():
        rounded = now_local.replace(
            minute=(now_local.minute // 15) * 15, second=0, microsecond=0
        )
        time_start = rounded.time()
    else:
        time_start = datetime.strptime("12:00", "%H:%M").time()
    end_dt = datetime.combine(today, time_start) + DEFAULT_DURATION
    return _calendar_order_url(
        step="order",
        date=today.isoformat(),
        start=time_start.strftime("%H:%M"),
        end=end_dt.strftime("%H:%M"),
        table=table.pk,
    )


def _wants_json(request):
    return (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or "application/json" in request.headers.get("Accept", "")
    )


def _seats_label(capacity):
    if capacity == 1:
        return "1 место"
    if 2 <= capacity <= 4:
        return f"{capacity} места"
    return f"{capacity} мест"


def _employees_for_waiter_picker(table):
    """Официанты + уже назначенные на эту кабинку (чтобы не пропадали из списка)."""
    assigned_ids = table.waiter_assignments.filter(is_active=True).values_list(
        "waiter_id", flat=True
    )
    return (
        Employee.objects.filter(is_active=True)
        .filter(Q(role__slug__in=WAITER_ROLES) | Q(pk__in=assigned_ids))
        .select_related("user", "role")
        .order_by("user__last_name", "user__first_name", "pk")
        .distinct()
    )


def _table_status_payload(table):
    sync_table_reserved_status(table)
    order = table.active_order
    reservation = floor_reservation_for_table(table)
    card_style = floor_card_style(table)
    status_labels = dict(Table.Status.choices)
    if card_style == "booking_now":
        status_label = "Сейчас бронь"
    elif card_style == "booked":
        status_label = "Зарезервирован"
    else:
        status_label = status_labels.get(card_style, card_style)

    guest_name = ""
    time_range = ""
    show_reservation = card_style in ("booked", "booking_now") and reservation
    if show_reservation:
        guest_name = reservation.guest_name
        start = timezone.localtime(reservation.reserved_for)
        end = timezone.localtime(reservation.reserved_until)
        time_range = f"{start.strftime('%d.%m %H:%M')}–{end.strftime('%H:%M')}"

    waiters = table.assigned_waiters
    waiter_list = [{"id": w.pk, "name": str(w)} for w in waiters]

    return {
        "id": table.pk,
        "number": table.number,
        "status": card_style,
        "status_label": status_label,
        "order_id": order.pk if order else None,
        "reservation_id": reservation.pk if reservation else None,
        "guest_name": guest_name,
        "time_range": time_range,
        "show_reservation": show_reservation,
        "seats_label": _seats_label(table.capacity),
        "waiters": waiter_list,
        "hub_url": _booth_url(table),
    }


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
                Prefetch("reservations", queryset=active_res),
                Prefetch(
                    "waiter_assignments",
                    queryset=TableWaiterAssignment.objects.filter(
                        is_active=True
                    ).select_related("waiter__user"),
                ),
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
    """Кабинка: открыть заказ или перейти к приёму заказа."""
    model = Table
    template_name = "tables/booth_hub.html"
    context_object_name = "table"
    allowed_roles = FLOOR_STAFF_ROLES + ["admin", "owner"]

    def get_queryset(self):
        return Table.objects.prefetch_related(
            Prefetch(
                "waiter_assignments",
                queryset=TableWaiterAssignment.objects.filter(
                    is_active=True
                ).select_related("waiter__user"),
            )
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        table = self.object
        sync_table_reserved_status(table)
        ctx["active_order"] = table.active_order
        ctx["reservation"] = table.active_reservation
        ctx["upcoming"] = table.upcoming_reservations()
        ctx["can_reserve"] = True
        waiters = _employees_for_waiter_picker(table)
        ctx["waiters"] = waiters
        ctx["assigned_waiters"] = table.assigned_waiters
        assigned_ids = [w.pk for w in table.assigned_waiters]
        ctx["assigned_waiter_ids"] = assigned_ids
        ctx["assigned_waiter_ids_json"] = json.dumps(assigned_ids, cls=DjangoJSONEncoder)
        ctx["calendar_order_url"] = _calendar_order_url_for_table(table)
        return ctx


class AssignWaiterView(RoleRequiredMixin, View):
    allowed_roles = ["admin", "owner"]

    def post(self, request, pk):
        table = get_object_or_404(Table, pk=pk)
        waiter_ids_raw = request.POST.getlist("waiter_ids")
        if not waiter_ids_raw and request.POST.get("waiter_id"):
            waiter_ids_raw = [request.POST["waiter_id"]]
        selected_ids = {
            int(wid)
            for wid in waiter_ids_raw
            if wid and str(wid).isdigit()
        }
        employee = get_acting_employee(request.user)
        if not employee:
            msg = "Не удалось определить сотрудника."
            if _wants_json(request):
                return JsonResponse({"ok": False, "error": msg}, status=400)
            messages.error(request, msg)
            return redirect("tables:booth", pk=pk)

        if selected_ids:
            valid_ids = set(
                Employee.objects.filter(is_active=True, pk__in=selected_ids)
                .filter(
                    Q(role__slug__in=WAITER_ROLES)
                    | Q(table_assignments__table=table, table_assignments__is_active=True)
                )
                .values_list("pk", flat=True)
                .distinct()
            )
            invalid = selected_ids - valid_ids
            if invalid:
                msg = "Один или несколько официантов недоступны."
                if _wants_json(request):
                    return JsonResponse({"ok": False, "error": msg}, status=400)
                messages.error(request, msg)
                return redirect("tables:booth", pk=pk)
        else:
            valid_ids = set()

        TableWaiterAssignment.objects.filter(table=table, is_active=True).exclude(
            waiter_id__in=valid_ids
        ).update(is_active=False)

        for wid in valid_ids:
            assignment, created = TableWaiterAssignment.objects.get_or_create(
                table=table,
                waiter_id=wid,
                defaults={"assigned_by": employee, "is_active": True},
            )
            if not created and not assignment.is_active:
                assignment.is_active = True
                assignment.assigned_by = employee
                assignment.save(update_fields=["is_active", "assigned_by"])

        assigned = table.assigned_waiters
        if assigned:
            names = ", ".join(str(w) for w in assigned)
            msg = f"Кабинка {table.number}: {names}"
            level = "success"
        else:
            msg = f"С кабинки {table.number} сняты все официанты."
            level = "info"

        if _wants_json(request):
            return JsonResponse(
                {
                    "ok": True,
                    "message": msg,
                    "level": level,
                    "waiters": [{"id": w.pk, "name": str(w)} for w in assigned],
                }
            )

        if assigned:
            messages.success(request, msg)
        else:
            messages.info(request, msg)
        return redirect("tables:booth", pk=pk)


class ReserveTableView(RoleRequiredMixin, View):
    """Старая страница /reserve/ — редирект на календарный приём заказа."""

    allowed_roles = FLOOR_STAFF_ROLES + ["admin", "owner"]

    def get(self, request, pk, *args, **kwargs):
        table = get_object_or_404(Table, pk=pk)
        return redirect(_calendar_order_url_for_table(table))

    def post(self, request, pk, *args, **kwargs):
        return self.get(request, pk, *args, **kwargs)


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
        ctx["reservations"] = qs.order_by("-reserved_for", "-pk")
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
            with transaction.atomic():
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
                self._apply_order_extras(request, order)
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
        except IntegrityError:
            messages.error(
                request,
                "Не удалось привязать заказ к брони. Попробуйте ещё раз или закройте старый заказ по этому столу.",
            )
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
            f"Заказ принят: кабинка {form.table.number}, "
            f"{reservation.time_range_display}. Заказ #{order.pk}.",
        )
        return redirect(_calendar_order_url())

    def _apply_order_extras(self, request, order):
        cart_raw = request.POST.get("cart_json", "[]")
        try:
            cart = json.loads(cart_raw)
        except json.JSONDecodeError:
            cart = []
        for row in cart:
            menu_item = MenuItem.objects.filter(
                pk=row.get("menu_item_id"),
                is_available=True,
                is_stopped=False,
            ).first()
            if not menu_item:
                continue
            qty = row.get("quantity", 1)
            try:
                quantity = Decimal(str(qty))
            except (InvalidOperation, TypeError, ValueError):
                quantity = Decimal("1")
            OrderItem.objects.create(
                order=order,
                menu_item=menu_item,
                kitchen_section=menu_item.category.kitchen_section,
                quantity=quantity,
                price=menu_item.price,
                note=(row.get("note") or "")[:200],
            )
        order.recalculate_total()

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
        tables = Table.objects.all().order_by("number")
        data = [_table_status_payload(t) for t in tables]
        return JsonResponse({"tables": data})
