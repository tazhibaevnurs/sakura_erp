from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Table",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("number", models.PositiveSmallIntegerField(unique=True)),
                ("type", models.CharField(choices=[("booth", "Кабинка"), ("table", "Стол"), ("outdoor", "Улица")], default="table", max_length=20)),
                ("capacity", models.PositiveSmallIntegerField(default=4)),
                ("status", models.CharField(choices=[("free", "Свободен"), ("occupied", "Занят"), ("waiting_payment", "Ожидает оплаты"), ("reserved", "Зарезервирован")], default="free", max_length=20)),
                ("position_x", models.FloatField(default=0)),
                ("position_y", models.FloatField(default=0)),
            ],
            options={
                "verbose_name": "Столик",
                "verbose_name_plural": "Столики",
                "ordering": ["number"],
            },
        ),
    ]
