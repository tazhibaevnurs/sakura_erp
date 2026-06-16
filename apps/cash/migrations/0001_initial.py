import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ExpenseCategory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100)),
                ("is_system", models.BooleanField(default=False)),
            ],
            options={
                "verbose_name": "Категория расхода",
                "verbose_name_plural": "Категории расходов",
            },
        ),
        migrations.CreateModel(
            name="DailyCash",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField(unique=True)),
                ("total_revenue", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("cash_revenue", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("card_revenue", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("qr_revenue", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("takeaway_revenue", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("total_expenses", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("net_profit", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("deposit", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("notes", models.TextField(blank=True)),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                ("closed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="accounts.employee")),
            ],
            options={
                "verbose_name": "Касса за день",
                "verbose_name_plural": "Касса по дням",
                "ordering": ["-date"],
            },
        ),
        migrations.CreateModel(
            name="Debt",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("debtor_name", models.CharField(max_length=200)),
                ("direction", models.CharField(choices=[("they_owe", "Нам должны"), ("we_owe", "Мы должны")], max_length=20)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("paid_amount", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("status", models.CharField(choices=[("active", "Активен"), ("partial", "Частично оплачен"), ("closed", "Закрыт")], default="active", max_length=20)),
                ("due_date", models.DateField(blank=True, null=True)),
                ("description", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="accounts.employee")),
            ],
            options={
                "verbose_name": "Долг",
                "verbose_name_plural": "Долги",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="Expense",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField()),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("comment", models.TextField()),
                ("payment_method", models.CharField(choices=[("cash", "Наличные"), ("transfer", "Перевод")], max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("added_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="accounts.employee")),
                ("category", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="cash.expensecategory")),
            ],
            options={
                "verbose_name": "Расход",
                "verbose_name_plural": "Расходы",
                "ordering": ["-date", "-created_at"],
            },
        ),
    ]
