from django.contrib import admin

from .models import KitchenSection, Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("pk", "table", "waiter", "status", "total", "created_at", "paid_at")
    list_filter = ("status", "order_type", "payment_method")
    search_fields = ("pk", "table__number")
    inlines = [OrderItemInline]


@admin.register(KitchenSection)
class KitchenSectionAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ("name",)}
