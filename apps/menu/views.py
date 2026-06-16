from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import CreateView, ListView, UpdateView

from apps.core.mixins import RoleRequiredMixin

from .forms import MenuItemForm
from .models import MenuCategory, MenuItem


class MenuManageView(RoleRequiredMixin, ListView):
    model = MenuCategory
    template_name = "menu/manage.html"
    context_object_name = "categories"
    allowed_roles = ["admin", "owner"]

    def get_queryset(self):
        return MenuCategory.objects.prefetch_related("items").order_by("order")


class MenuItemCreateView(RoleRequiredMixin, CreateView):
    model = MenuItem
    form_class = MenuItemForm
    template_name = "menu/item_form.html"
    allowed_roles = ["admin", "owner"]

    def get_success_url(self):
        return reverse("menu:manage")

    def form_valid(self, form):
        messages.success(self.request, "Блюдо добавлено")
        return super().form_valid(form)


class MenuItemUpdateView(RoleRequiredMixin, UpdateView):
    model = MenuItem
    form_class = MenuItemForm
    template_name = "menu/item_form.html"
    allowed_roles = ["admin", "owner"]

    def get_success_url(self):
        return reverse("menu:manage")
