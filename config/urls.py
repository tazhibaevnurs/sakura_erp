from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from apps.core.views import health

admin.site.site_header = "Сакура — администрирование"
admin.site.site_title = "Сакура"
admin.site.index_title = "Панель управления"

urlpatterns = [
    path("health/", health, name="health"),
    path("admin/", admin.site.urls),
    path("", include("apps.tables.urls")),
    path("auth/", include("apps.accounts.urls")),
    path("orders/", include("apps.orders.urls")),
    path("kitchen/", include("apps.kitchen.urls")),
    path("cash/", include("apps.cash.urls")),
    path("salary/", include("apps.salary.urls")),
    path("menu/", include("apps.menu.urls")),
    path("reports/", include("apps.reports.urls")),
    path("assistant/", include("apps.ai_assistant.urls", namespace="ai_assistant")),
    path("ai-assistant/", include("apps.ai_assistant.webhook_urls")),
    path("staff/", include("apps.accounts.staff_urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    try:
        import debug_toolbar

        urlpatterns = [path("__debug__/", include(debug_toolbar.urls))] + urlpatterns
    except ImportError:
        pass
