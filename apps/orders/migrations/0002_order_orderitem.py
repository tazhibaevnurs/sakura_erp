import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0001_initial"),
        ("accounts", "0001_initial"),
        ("menu", "0001_initial"),
        ("tables", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Order",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("open", "Открыт"), ("sent", "Отправлен на кухню"), ("cooking", "Готовится"), ("ready", "Готово"), ("served", "Подано"), ("paid", "Оплачен"), ("cancelled", "Отменён")], default="open", max_length=20)),
                ("order_type", models.CharField(choices=[("dine_in", "В зале"), ("takeaway", "Навынос")], default="dine_in", max_length=20)),
                ("payment_method", models.CharField(blank=True, choices=[("cash", "Наличные"), ("card", "Карта"), ("qr", "QR")], max_length=20)),
                ("total", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("guest_count", models.PositiveSmallIntegerField(default=1)),
                ("comment", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("paid_at", models.DateTimeField(blank=True, null=True)),
                ("cancelled_reason", models.TextField(blank=True)),
                ("table", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="orders", to="tables.table")),
                ("waiter", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="orders", to="accounts.employee")),
            ],
            options={
                "verbose_name": "Заказ",
                "verbose_name_plural": "Заказы",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="OrderItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity", models.PositiveSmallIntegerField(default=1)),
                ("price", models.DecimalField(decimal_places=2, max_digits=10)),
                ("status", models.CharField(choices=[("pending", "Ожидает"), ("cooking", "Готовится"), ("ready", "Готово"), ("served", "Подано"), ("cancelled", "Отменено")], default="pending", max_length=20)),
                ("note", models.CharField(blank=True, max_length=200)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("ready_at", models.DateTimeField(blank=True, null=True)),
                ("kitchen_section", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="orders.kitchensection")),
                ("menu_item", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="menu.menuitem")),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="orders.order")),
            ],
            options={
                "verbose_name": "Позиция заказа",
                "verbose_name_plural": "Позиции заказов",
            },
        ),
    ]
