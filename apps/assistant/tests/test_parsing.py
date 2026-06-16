import pytest
from django.utils import timezone

from apps.assistant.parsing import parse_availability_query, try_direct_availability_reply
from apps.tables.models import Table


@pytest.mark.django_db
def test_parse_six_cabin_june_12():
    query = parse_availability_query("12 июня 6 кабина свободно ?")
    assert query is not None
    assert query.table_number == 6
    assert query.day.month == 6
    assert query.day.day == 12
    assert query.time_str is None


@pytest.mark.django_db
def test_direct_reply_uses_correct_table_number():
    Table.objects.create(number=6, capacity=4, type=Table.TableType.BOOTH)
    year = timezone.localdate().year
    if timezone.localdate().month > 6 or (
        timezone.localdate().month == 6 and timezone.localdate().day > 12
    ):
        year += 1
    reply = try_direct_availability_reply(f"12 июня 6 кабина свободно ?")
    assert reply is not None
    assert "№6" in reply
    assert "№10" not in reply


def test_parse_cabin_with_time():
    query = parse_availability_query("кабинка 10 на 12 июня в 18:00 свободна?")
    assert query is not None
    assert query.table_number == 10
    assert query.time_str == "18:00"
