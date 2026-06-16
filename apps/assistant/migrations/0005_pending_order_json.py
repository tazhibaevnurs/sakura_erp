from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("assistant", "0004_accept_orders_enabled"),
    ]

    operations = [
        migrations.AddField(
            model_name="assistantchannelstate",
            name="pending_order_json",
            field=models.TextField(
                blank=True,
                help_text="Пошаговая квалификация заказа (JSON)",
                verbose_name="Незавершённый заказ",
            ),
        ),
    ]
