from django.contrib import admin

from .models import SalaryPayment, SalarySchema, Shift


@admin.register(SalarySchema)
class SalarySchemaAdmin(admin.ModelAdmin):
    list_display = ("name", "percent_of_revenue", "fixed_per_shift", "fixed_monthly")


@admin.register(Shift)
class ShiftAdmin(admin.ModelAdmin):
    list_display = ("employee", "date", "shift_type", "calculated_salary")
    list_filter = ("shift_type", "date")


@admin.register(SalaryPayment)
class SalaryPaymentAdmin(admin.ModelAdmin):
    list_display = ("employee", "payment_type", "amount", "date")
    list_filter = ("payment_type",)
