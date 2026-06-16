from datetime import date

import pytest

from apps.reports.services import get_period_report


@pytest.mark.django_db
def test_get_period_report_empty():
    report = get_period_report(date(2026, 5, 1), date(2026, 5, 7))
    assert report["revenue_total"] == 0
    assert report["daily_breakdown"] == []
