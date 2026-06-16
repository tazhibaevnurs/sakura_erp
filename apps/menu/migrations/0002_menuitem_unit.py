from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="menuitem",
            name="unit",
            field=models.CharField(
                choices=[("kg", "кг"), ("pcs", "шт")],
                default="pcs",
                max_length=10,
                verbose_name="Единица измерения",
            ),
        ),
    ]
