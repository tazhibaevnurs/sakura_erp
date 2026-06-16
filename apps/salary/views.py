from datetime import date, datetime

from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import FormView, ListView, TemplateView

from apps.accounts.models import Employee
from apps.core.mixins import RoleRequiredMixin

from .forms import ShiftForm
from .models import Shift
from .services import calculate_employee_salary, recalculate_shift


class SalaryListView(RoleRequiredMixin, TemplateView):
    template_name = "salary/list.html"
    allowed_roles = ["owner"]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = date.today()
        period_start = today.replace(day=1)
        employees = Employee.objects.filter(is_active=True).select_related("user")
        rows = []
        for emp in employees:
            calc = calculate_employee_salary(emp, period_start, today)
            rows.append({"employee": emp, **calc})
        ctx["rows"] = rows
        ctx["period_start"] = period_start
        ctx["period_end"] = today
        return ctx


class SalaryPeriodView(RoleRequiredMixin, TemplateView):
    template_name = "salary/period.html"
    allowed_roles = ["owner"]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        period = self.kwargs["period"]
        if len(period) == 7:
            year, month = map(int, period.split("-"))
            date_from = date(year, month, 1)
            if month == 12:
                date_to = date(year + 1, 1, 1)
            else:
                date_to = date(year, month + 1, 1)
            from datetime import timedelta

            date_to = date_to - timedelta(days=1)
        else:
            date_from = date_to = date.today()
        employees = Employee.objects.filter(is_active=True)
        ctx["rows"] = [
            {
                "employee": emp,
                **calculate_employee_salary(emp, date_from, date_to),
            }
            for emp in employees
        ]
        ctx["period"] = period
        return ctx


class TimesheetView(RoleRequiredMixin, FormView):
    template_name = "salary/timesheet.html"
    form_class = ShiftForm
    allowed_roles = ["admin", "owner"]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        shifts = list(
            Shift.objects.select_related("employee__user", "employee__salary_schema").filter(
                date__month=date.today().month,
                date__year=date.today().year,
            )[:100]
        )
        for shift in shifts:
            if shift.shift_type == Shift.ShiftType.WORKED and shift.calculated_salary == 0:
                recalculate_shift(shift)
        ctx["shifts"] = shifts
        return ctx

    def form_valid(self, form):
        shift = form.save(commit=False)
        shift.save()
        if shift.shift_type == Shift.ShiftType.WORKED:
            recalculate_shift(shift)
        messages.success(self.request, "Смена сохранена")
        return redirect("salary:timesheet")
