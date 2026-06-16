from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.core.mixins import RoleRequiredMixin

from .forms import EmployeeForm, LoginForm
from .models import Employee


class ChaihanaLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm

    def get_success_url(self):
        user = self.request.user
        if hasattr(user, "employee"):
            role = user.employee.role.slug
            if role in ("cook", "baker", "salad", "bbq") and user.employee.kitchen_section:
                return reverse(
                    "kitchen:display",
                    kwargs={"section_slug": user.employee.kitchen_section.slug},
                )
        if user.is_superuser:
            return reverse("reports:dashboard")
        return reverse("tables:floor")


class ChaihanaLogoutView(LogoutView):
    next_page = reverse_lazy("accounts:login")


class StaffListView(RoleRequiredMixin, ListView):
    model = Employee
    template_name = "accounts/staff_list.html"
    context_object_name = "employees"
    allowed_roles = ["admin", "owner"]

    def get_queryset(self):
        return Employee.objects.select_related("user", "role").filter(is_active=True)


class EmployeeDetailView(RoleRequiredMixin, DetailView):
    model = Employee
    template_name = "accounts/employee_detail.html"
    context_object_name = "employee"
    allowed_roles = ["admin", "owner"]

    def get_context_data(self, **kwargs):
        from datetime import date

        from apps.salary.services import calculate_employee_salary

        ctx = super().get_context_data(**kwargs)
        today = date.today()
        ctx["salary"] = calculate_employee_salary(
            self.object,
            today.replace(day=1),
            today,
        )
        return ctx


class AddEmployeeView(RoleRequiredMixin, CreateView):
    model = Employee
    form_class = EmployeeForm
    template_name = "accounts/employee_form.html"
    allowed_roles = ["owner"]

    def form_valid(self, form):
        messages.success(self.request, "Сотрудник добавлен")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("staff_list")
