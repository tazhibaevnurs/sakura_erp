from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

from apps.core.employees import user_effective_role, user_has_elevated_access


class RoleRequiredMixin(LoginRequiredMixin):
    allowed_roles = []

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        # Суперпользователь и администратор — полный доступ ко всем разделам
        if user_has_elevated_access(request.user):
            return super(LoginRequiredMixin, self).dispatch(request, *args, **kwargs)
        if not hasattr(request.user, "employee"):
            return redirect("accounts:login")
        role_slug = user_effective_role(request.user)
        if self.allowed_roles and role_slug not in self.allowed_roles + ["owner"]:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)
