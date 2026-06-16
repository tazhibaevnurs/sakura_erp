from django.contrib import admin

from .models import DailyCash, Debt, Expense, ExpenseCategory


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "is_system")


@admin.register(DailyCash)
class DailyCashAdmin(admin.ModelAdmin):
    list_display = ("date", "total_revenue", "total_expenses", "net_profit", "closed_at")
    date_hierarchy = "date"


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ("date", "category", "amount", "payment_method", "added_by")
    list_filter = ("category", "date")


@admin.register(Debt)
class DebtAdmin(admin.ModelAdmin):
    list_display = ("debtor_name", "direction", "amount", "paid_amount", "status")
    list_filter = ("status", "direction")
