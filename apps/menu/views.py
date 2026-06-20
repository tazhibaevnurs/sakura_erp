from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
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


class ToggleStopListView(RoleRequiredMixin, View):
    allowed_roles = ["admin", "owner"]

    def post(self, request, pk):
        item = get_object_or_404(MenuItem, pk=pk)
        item.is_stopped = not item.is_stopped
        item.save(update_fields=["is_stopped"])
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"ok": True, "is_stopped": item.is_stopped})
        state = "в стоп-листе" if item.is_stopped else "доступно"
        messages.success(request, f"«{item.name}» — {state}")
        return redirect("menu:manage")


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
