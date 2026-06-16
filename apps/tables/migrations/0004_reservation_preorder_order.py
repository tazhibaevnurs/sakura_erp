import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0001_initial"),
        ("tables", "0003_reservation_until"),
    ]

    operations = [
        migrations.AddField(
            model_name="tablereservation",
            name="order",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="table_reservation",
                to="orders.order",
                verbose_name="Предзаказ",
            ),
        ),
    ]
