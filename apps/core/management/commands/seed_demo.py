from datetime import date

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.accounts.models import Employee, Role
from apps.cash.models import ExpenseCategory
from apps.salary.models import SalarySchema


class Command(BaseCommand):
    help = "Базовые схемы зарплаты и категории расходов"

    def handle(self, *args, **options):
        schemas = [
            ("Официант", 2, 0, 0),
            ("Повар", 1.5, 50, 0),
            ("Администратор", 0, 0, 3000),
        ]
        for name, pct, shift, monthly in schemas:
            SalarySchema.objects.get_or_create(
                name=f"Схема: {name}",
                defaults={
                    "percent_of_revenue": pct,
                    "fixed_per_shift": shift,
                    "fixed_monthly": monthly,
                },
            )
        categories = [
            ("Закуп продуктов", True),
            ("Аренда", True),
            ("Коммуналка", True),
            ("Зарплата", True),
            ("Прочее", False),
        ]
        for name, is_system in categories:
            ExpenseCategory.objects.get_or_create(name=name, defaults={"is_system": is_system})

        owner_role = Role.objects.filter(slug="owner").first()
        admin_schema = SalarySchema.objects.first()
        if owner_role and admin_schema:
            User = get_user_model()
            for username in ("admin",):
                user = User.objects.filter(username=username).first()
                if user and not hasattr(user, "employee"):
                    Employee.objects.create(
                        user=user,
                        role=owner_role,
                        hired_date=date.today(),
                        salary_schema=admin_schema,
                    )
                    user.groups.add(owner_role.group)
                    self.stdout.write(f"Employee profile linked to {username}")

        self.stdout.write(self.style.SUCCESS("Demo data seeded"))
