import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("salary", "0001_initial"),
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Shift",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField()),
                ("time_in", models.TimeField(blank=True, null=True)),
                ("time_out", models.TimeField(blank=True, null=True)),
                ("shift_type", models.CharField(choices=[("worked", "Отработал"), ("sick", "Больничный"), ("absent", "Прогул"), ("day_off", "Выходной")], default="worked", max_length=20)),
                ("revenue_share_base", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("calculated_salary", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("employee", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="shifts", to="accounts.employee")),
            ],
            options={
                "verbose_name": "Смена",
                "verbose_name_plural": "Смены",
                "ordering": ["-date"],
                "unique_together": {("employee", "date")},
            },
        ),
        migrations.CreateModel(
            name="SalaryPayment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("payment_type", models.CharField(choices=[("advance", "Аванс"), ("salary", "Зарплата"), ("bonus", "Бонус"), ("penalty", "Штраф")], max_length=20)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("date", models.DateField()),
                ("period_start", models.DateField(blank=True, null=True)),
                ("period_end", models.DateField(blank=True, null=True)),
                ("comment", models.TextField(blank=True)),
                ("employee", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="payments", to="accounts.employee")),
                ("paid_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="payments_made", to="accounts.employee")),
            ],
            options={
                "verbose_name": "Выплата",
                "verbose_name_plural": "Выплаты",
                "ordering": ["-date"],
            },
        ),
    ]
