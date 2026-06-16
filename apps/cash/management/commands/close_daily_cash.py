from datetime import date

from django.core.management.base import BaseCommand

from apps.cash.services import CashClosedError, close_daily_cash


class Command(BaseCommand):
    help = "Закрыть кассу за указанную дату (по умолчанию сегодня)"

    def add_arguments(self, parser):
        parser.add_argument("--date", type=str, help="YYYY-MM-DD")

    def handle(self, *args, **options):
        day = date.fromisoformat(options["date"]) if options.get("date") else date.today()
        try:
            cash = close_daily_cash(day)
        except CashClosedError as exc:
            self.stdout.write(self.style.WARNING(str(exc)))
            return
        self.stdout.write(
            self.style.SUCCESS(f"Cash closed for {cash.date}: profit {cash.net_profit}")
        )
