from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("assistant", "0005_pending_order_json"),
    ]

    operations = [
        migrations.AddField(
            model_name="assistantchannelstate",
            name="guest_language",
            field=models.CharField(
                blank=True,
                default="",
                help_text="ru или ky — язык последних сообщений гостя",
                max_length=5,
                verbose_name="Язык гостя",
            ),
        ),
    ]
