from datetime import date
from decimal import Decimal

from django.db.models import Sum

from apps.accounts.models import Employee
from apps.cash.services import update_daily_cash_for_date

from .models import SalaryPayment, Shift


def calculate_shift_accrual(shift: Shift) -> Decimal:
    """Начисление за одну смену (ставка за смену + % от выручки дня)."""
    if shift.shift_type != Shift.ShiftType.WORKED:
        return Decimal("0")
    schema = shift.employee.salary_schema
    revenue_part = shift.revenue_share_base * schema.percent_of_revenue / Decimal("100")
    return revenue_part + schema.fixed_per_shift


def recalculate_shift(shift: Shift) -> Shift:
    """Обновить базу выручки и начисление по смене."""
    if shift.shift_type == Shift.ShiftType.WORKED:
        cash = update_daily_cash_for_date(shift.date)
        shift.revenue_share_base = cash.total_revenue
        shift.calculated_salary = calculate_shift_accrual(shift)
    else:
        shift.calculated_salary = Decimal("0")
    shift.save(update_fields=["revenue_share_base", "calculated_salary"])
    return shift


def calculate_employee_salary(employee: Employee, date_from: date, date_to: date) -> dict:
    schema = employee.salary_schema
    shifts = employee.shifts.filter(
        date__range=(date_from, date_to),
        shift_type=Shift.ShiftType.WORKED,
    )
    worked_days = shifts.count()

    revenue_share = sum(
        shift.revenue_share_base * schema.percent_of_revenue / Decimal("100")
        for shift in shifts
    )

    fixed_shift = schema.fixed_per_shift * worked_days

    total_days_in_period = (date_to - date_from).days + 1
    fixed_monthly = (
        schema.fixed_monthly * worked_days / total_days_in_period
        if total_days_in_period
        else 0
    )

    accrued = revenue_share + fixed_shift + fixed_monthly

    bonus = (
        employee.payments.filter(
            date__range=(date_from, date_to),
            payment_type=SalaryPayment.PaymentType.BONUS,
        ).aggregate(total=Sum("amount"))["total"]
        or 0
    )

    penalty = (
        employee.payments.filter(
            date__range=(date_from, date_to),
            payment_type=SalaryPayment.PaymentType.PENALTY,
        ).aggregate(total=Sum("amount"))["total"]
        or 0
    )

    advances = (
        employee.payments.filter(
            date__range=(date_from, date_to),
            payment_type=SalaryPayment.PaymentType.ADVANCE,
        ).aggregate(total=Sum("amount"))["total"]
        or 0
    )

    net = accrued + bonus - penalty - advances

    return {
        "worked_days": worked_days,
        "revenue_share": revenue_share,
        "fixed_shift": fixed_shift,
        "fixed_monthly": fixed_monthly,
        "accrued": accrued,
        "bonus": bonus,
        "penalty": penalty,
        "advances": advances,
        "net_to_pay": net,
    }
