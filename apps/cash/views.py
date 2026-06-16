from datetime import date, datetime

from django.contrib import messages
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import CreateView, ListView, TemplateView

from apps.core.employees import get_acting_employee
from apps.core.mixins import RoleRequiredMixin

from .forms import DebtForm, ExpenseForm
from .models import DailyCash, Debt, Expense
from .services import (
    CashClosedError,
    close_daily_cash,
    is_day_closed,
    update_daily_cash_for_date,
)


class CashTodayView(RoleRequiredMixin, TemplateView):
    template_name = "cash/today.html"
    allowed_roles = ["admin", "owner"]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = date.today()
        cash = DailyCash.objects.filter(date=today).first()
        if cash and cash.closed_at:
            ctx["is_closed"] = True
            ctx["cash"] = cash
            ctx["expenses"] = []
        else:
            cash = update_daily_cash_for_date(today)
            ctx["is_closed"] = False
            ctx["cash"] = cash
            ctx["expenses"] = Expense.objects.filter(date=today).select_related(
                "category"
            )
        return ctx

    def post(self, request, *args, **kwargs):
        if "close_cash" not in request.POST:
            return redirect("cash:today")

        today = date.today()
        if is_day_closed(today):
            messages.info(request, "Касса за сегодня уже закрыта.")
            return redirect("cash:today")

        employee = get_acting_employee(request.user)
        if not employee:
            messages.error(request, "Не удалось определить сотрудника.")
            return redirect("cash:today")

        try:
            close_daily_cash(today, employee)
        except CashClosedError as exc:
            messages.error(request, str(exc))
            return redirect("cash:today")

        messages.success(
            request,
            "Касса закрыта. Итоги сохранены в «Закрытые смены».",
        )
        return redirect("cash:closed_list")


class CashClosedListView(RoleRequiredMixin, TemplateView):
    template_name = "cash/closed_list.html"
    allowed_roles = ["admin", "owner"]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        shifts = (
            DailyCash.objects.filter(closed_at__isnull=False)
            .select_related("closed_by__user")
            .order_by("-date")
        )
        ctx["shifts"] = shifts
        ctx["totals"] = shifts.aggregate(
            revenue=Sum("total_revenue"),
            expenses=Sum("total_expenses"),
            profit=Sum("net_profit"),
        )
        ctx["today_closed"] = is_day_closed(date.today())
        return ctx


class CashDayView(RoleRequiredMixin, TemplateView):
    template_name = "cash/day.html"
    allowed_roles = ["admin", "owner"]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        day = datetime.strptime(self.kwargs["date"], "%Y-%m-%d").date()
        cash = get_object_or_404(DailyCash, date=day, closed_at__isnull=False)
        ctx["cash"] = cash
        ctx["date"] = day
        ctx["expenses"] = Expense.objects.filter(date=day).select_related("category")
        return ctx


class ExpenseListView(RoleRequiredMixin, ListView):
    model = Expense
    template_name = "cash/expense_list.html"
    context_object_name = "expenses"
    paginate_by = 50
    allowed_roles = ["admin", "owner"]

    def get_queryset(self):
        return Expense.objects.select_related("category", "added_by").order_by("-date")


class AddExpenseView(RoleRequiredMixin, CreateView):
    model = Expense
    form_class = ExpenseForm
    template_name = "cash/expense_form.html"
    allowed_roles = ["admin", "owner"]

    def dispatch(self, request, *args, **kwargs):
        if is_day_closed(date.today()):
            messages.error(
                request,
                "Касса за сегодня закрыта. Новые расходы добавить нельзя.",
            )
            return redirect("cash:today")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        if is_day_closed(form.instance.date):
            messages.error(
                self.request,
                "Касса за выбранный день закрыта. Расход нельзя добавить.",
            )
            return self.form_invalid(form)
        form.instance.added_by = self.request.user.employee
        response = super().form_valid(form)
        update_daily_cash_for_date(form.instance.date)
        messages.success(self.request, "Расход добавлен")
        return response

    def get_success_url(self):
        return reverse("cash:today")


class DebtListView(RoleRequiredMixin, ListView):
    model = Debt
    template_name = "cash/debt_list.html"
    context_object_name = "debts"
    allowed_roles = ["admin", "owner"]

    def get_queryset(self):
        return Debt.objects.exclude(status=Debt.Status.CLOSED)


class AddDebtView(RoleRequiredMixin, CreateView):
    model = Debt
    form_class = DebtForm
    template_name = "cash/debt_form.html"
    allowed_roles = ["admin", "owner"]

    def form_valid(self, form):
        form.instance.created_by = get_acting_employee(self.request.user)
        messages.success(self.request, "Долг записан")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("cash:debts")
