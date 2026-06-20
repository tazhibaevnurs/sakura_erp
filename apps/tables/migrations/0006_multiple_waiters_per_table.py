import django.db.models.deletion
from django.db import migrations, models


def dedupe_waiter_assignments(apps, schema_editor):
    Assignment = apps.get_model("tables", "TableWaiterAssignment")
    keep_ids = set()
    for row in Assignment.objects.order_by(
        "table_id", "waiter_id", "-is_active", "-assigned_at", "-pk"
    ):
        key = (row.table_id, row.waiter_id)
        if key in keep_ids:
            row.delete()
        else:
            keep_ids.add(key)


class Migration(migrations.Migration):

    dependencies = [
        ("tables", "0005_tablewaiterassignment"),
    ]

    operations = [
        migrations.RunPython(dedupe_waiter_assignments, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name="tablewaiterassignment",
            name="unique_active_waiter_per_table",
        ),
        migrations.AddConstraint(
            model_name="tablewaiterassignment",
            constraint=models.UniqueConstraint(
                fields=("table", "waiter"),
                name="unique_waiter_assignment_per_table",
            ),
        ),
    ]
