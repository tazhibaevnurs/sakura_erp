from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ai_assistant", "0002_assistantconfig"),
    ]

    operations = [
        migrations.AddField(
            model_name="conversation",
            name="language",
            field=models.CharField(
                blank=True,
                choices=[("ru", "Русский"), ("ky", "Кыргызский")],
                max_length=2,
                verbose_name="Язык диалога",
            ),
        ),
    ]
