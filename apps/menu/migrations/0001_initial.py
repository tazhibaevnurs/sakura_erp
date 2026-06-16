import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ("orders", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="MenuCategory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100)),
                ("order", models.PositiveSmallIntegerField(default=0)),
                ("kitchen_section", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="orders.kitchensection")),
            ],
            options={
                "verbose_name": "Категория меню",
                "verbose_name_plural": "Категории меню",
                "ordering": ["order", "name"],
            },
        ),
        migrations.CreateModel(
            name="MenuItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=200)),
                ("price", models.DecimalField(decimal_places=2, max_digits=10)),
                ("description", models.TextField(blank=True)),
                ("is_available", models.BooleanField(default=True)),
                ("order", models.PositiveSmallIntegerField(default=0)),
                ("category", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="menu.menucategory")),
            ],
            options={
                "verbose_name": "Блюдо",
                "verbose_name_plural": "Блюда",
                "ordering": ["order", "name"],
            },
        ),
    ]
