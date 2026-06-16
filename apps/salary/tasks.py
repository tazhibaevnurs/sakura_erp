from datetime import date

from celery import shared_task

from apps.accounts.models import Employee
from apps.cash.services import update_daily_cash_for_date

from .models import Shift
from .services import recalculate_shift


@shared_task
def recalculate_shifts_salary(date_str: str):
    day = date.fromisoformat(date_str)
    cash = update_daily_cash_for_date(day)
    revenue_base = cash.total_revenue

    for employee in Employee.objects.filter(is_active=True):
        shift, _ = Shift.objects.get_or_create(employee=employee, date=day)
        if shift.shift_type == Shift.ShiftType.WORKED:
            shift.revenue_share_base = revenue_base
            recalculate_shift(shift)
