import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
        ("tables", "0004_reservation_preorder_order"),
    ]

    operations = [
        migrations.CreateModel(
            name="TableWaiterAssignment",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("is_active", models.BooleanField(default=True, verbose_name="Активно")),
                ("assigned_at", models.DateTimeField(auto_now_add=True)),
                (
                    "assigned_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="waiter_assignments_made",
                        to="accounts.employee",
                        verbose_name="Назначил",
                    ),
                ),
                (
                    "table",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="waiter_assignments",
                        to="tables.table",
                        verbose_name="Кабинка",
                    ),
                ),
                (
                    "waiter",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="table_assignments",
                        to="accounts.employee",
                        verbose_name="Официант",
                    ),
                ),
            ],
            options={
                "verbose_name": "Назначение официанта",
                "verbose_name_plural": "Назначения официантов",
            },
        ),
        migrations.AddConstraint(
            model_name="tablewaiterassignment",
            constraint=models.UniqueConstraint(
                condition=models.Q(("is_active", True)),
                fields=("table",),
                name="unique_active_waiter_per_table",
            ),
        ),
    ]
