from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("assistant", "0003_assistant_advanced_settings"),
    ]

    operations = [
        migrations.AddField(
            model_name="assistantsettings",
            name="accept_orders_enabled",
            field=models.BooleanField(
                default=True,
                help_text="Ассистент оформляет заказы: доставка, навынос, в зале",
                verbose_name="Принимать заказы",
            ),
        ),
    ]
