from django.contrib import admin

from .models import Table, TableReservation


@admin.register(Table)
class TableAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "display_type",
        "display_status",
        "capacity",
        "position_x",
        "position_y",
    )
    list_display_links = ("number",)
    list_filter = ("status", "type")
    search_fields = ("number",)
    ordering = ("number",)
    list_per_page = 100
    fieldsets = (
        (None, {"fields": ("number", "type", "capacity", "status")}),
        ("Расположение на схеме", {"fields": ("position_x", "position_y")}),
    )

    @admin.display(description="Тип", ordering="type")
    def display_type(self, obj):
        return obj.get_type_display()

    @admin.display(description="Статус", ordering="status")
    def display_status(self, obj):
        return obj.get_status_display()


@admin.register(TableReservation)
class TableReservationAdmin(admin.ModelAdmin):
    list_display = (
        "table",
        "guest_name",
        "guest_phone",
        "reserved_for",
        "reserved_until",
        "guest_count",
        "status",
        "created_by",
    )
    list_filter = ("status", "reserved_for")
    search_fields = ("guest_name", "guest_phone", "table__number")
    ordering = ("-reserved_for",)
    date_hierarchy = "reserved_for"
    readonly_fields = ("created_at",)
