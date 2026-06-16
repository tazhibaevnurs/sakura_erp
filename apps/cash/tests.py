from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.cash.models import DailyCash
from apps.cash.services import (
    CashClosedError,
    close_daily_cash,
    is_day_closed,
    update_daily_cash_for_date,
)


class CashCloseTests(TestCase):
    def test_close_sets_flags(self):
        today = date.today()
        cash = close_daily_cash(today, employee=None)
        self.assertIsNotNone(cash.closed_at)
        self.assertTrue(is_day_closed(today))

    def test_double_close_raises(self):
        today = date.today()
        close_daily_cash(today, employee=None)
        with self.assertRaises(CashClosedError):
            close_daily_cash(today, employee=None)

    def test_update_skips_closed_day(self):
        today = date.today()
        cash, _ = DailyCash.objects.get_or_create(date=today)
        cash.total_revenue = Decimal("100")
        cash.closed_at = timezone.now()
        cash.save(update_fields=["total_revenue", "closed_at"])

        result = update_daily_cash_for_date(today)
        self.assertEqual(result.total_revenue, Decimal("100"))
