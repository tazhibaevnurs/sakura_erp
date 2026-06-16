from datetime import timedelta

from django.db import migrations, models


def fill_reserved_until(apps, schema_editor):
    TableReservation = apps.get_model("tables", "TableReservation")
    for reservation in TableReservation.objects.all():
        if not reservation.reserved_until:
            reservation.reserved_until = reservation.reserved_for + timedelta(hours=2)
            reservation.save(update_fields=["reserved_until"])


class Migration(migrations.Migration):
    dependencies = [
        ("tables", "0002_table_reservation"),
    ]

    operations = [
        migrations.AddField(
            model_name="tablereservation",
            name="reserved_until",
            field=models.DateTimeField(
                null=True,
                verbose_name="Окончание",
            ),
        ),
        migrations.RunPython(fill_reserved_until, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="tablereservation",
            name="reserved_for",
            field=models.DateTimeField(verbose_name="Начало"),
        ),
        migrations.AlterField(
            model_name="tablereservation",
            name="reserved_until",
            field=models.DateTimeField(verbose_name="Окончание"),
        ),
    ]
