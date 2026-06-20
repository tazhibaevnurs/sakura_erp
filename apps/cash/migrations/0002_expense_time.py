from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cash", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="expense",
            name="expense_time",
            field=models.TimeField(blank=True, null=True, verbose_name="Время"),
        ),
    ]
