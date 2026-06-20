from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0003_delivery_units_quantity"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="deposit",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                max_digits=10,
                verbose_name="Задаток",
            ),
        ),
        migrations.AddField(
            model_name="order",
            name="estimated_ready_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name="Примерная готовность",
            ),
        ),
    ]
