import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name="SalarySchema",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100)),
                ("percent_of_revenue", models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ("fixed_per_shift", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("fixed_monthly", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("notes", models.TextField(blank=True)),
            ],
            options={
                "verbose_name": "Схема зарплаты",
                "verbose_name_plural": "Схемы зарплаты",
            },
        ),
    ]
