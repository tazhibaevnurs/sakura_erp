from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0002_menuitem_unit"),
    ]

    operations = [
        migrations.AddField(
            model_name="menuitem",
            name="is_stopped",
            field=models.BooleanField(
                default=False,
                help_text="Временно недоступно для заказа",
                verbose_name="Стоп-лист",
            ),
        ),
    ]
