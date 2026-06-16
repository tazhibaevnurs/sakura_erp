from datetime import date

from celery import shared_task

from .services import CashClosedError, close_daily_cash


@shared_task
def auto_close_daily_cash():
    try:
        close_daily_cash(date.today())
    except CashClosedError:
        pass
