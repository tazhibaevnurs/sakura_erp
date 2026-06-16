import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
        ("orders", "0002_order_orderitem"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="customer_name",
            field=models.CharField(blank=True, max_length=200, verbose_name="Имя клиента"),
        ),
        migrations.AddField(
            model_name="order",
            name="customer_phone",
            field=models.CharField(blank=True, max_length=30, verbose_name="Телефон"),
        ),
        migrations.AddField(
            model_name="order",
            name="customer_phone_ext",
            field=models.CharField(blank=True, max_length=10, verbose_name="Добавочный номер"),
        ),
        migrations.AddField(
            model_name="order",
            name="delivery_address",
            field=models.TextField(blank=True, verbose_name="Адрес доставки"),
        ),
        migrations.AlterField(
            model_name="order",
            name="order_type",
            field=models.CharField(
                choices=[
                    ("dine_in", "В зале"),
                    ("takeaway", "Навынос"),
                    ("delivery", "Доставка"),
                ],
                default="dine_in",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="orderitem",
            name="quantity",
            field=models.DecimalField(decimal_places=3, default=1, max_digits=8),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="ready_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="completed_order_items",
                to="accounts.employee",
                verbose_name="Отпустил",
            ),
        ),
    ]
