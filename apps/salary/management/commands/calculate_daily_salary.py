from datetime import date

from django.core.management.base import BaseCommand

from apps.salary.tasks import recalculate_shifts_salary


class Command(BaseCommand):
    help = "Пересчитать зарплату за день"

    def add_arguments(self, parser):
        parser.add_argument("--date", type=str, help="YYYY-MM-DD")

    def handle(self, *args, **options):
        day = options.get("date") or date.today().isoformat()
        recalculate_shifts_salary(day)
        self.stdout.write(self.style.SUCCESS(f"Salary recalculated for {day}"))
