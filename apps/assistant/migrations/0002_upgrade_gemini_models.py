from django.db import migrations

GEMINI_MODEL_ALIASES = {
    "gemini-1.5-flash": "gemini-2.5-flash-lite",
    "gemini-1.5-flash-latest": "gemini-2.5-flash-lite",
    "gemini-1.5-flash-001": "gemini-2.5-flash-lite",
    "gemini-1.5-flash-002": "gemini-2.5-flash-lite",
    "gemini-1.5-flash-8b": "gemini-2.5-flash-lite",
    "gemini-1.5-pro": "gemini-2.5-flash",
    "gemini-1.5-pro-latest": "gemini-2.5-flash",
    "gemini-2.0-flash": "gemini-2.5-flash-lite",
}


def upgrade_gemini_models(apps, schema_editor):
    AssistantSettings = apps.get_model("assistant", "AssistantSettings")
    for cfg in AssistantSettings.objects.filter(ai_provider="gemini"):
        model = (cfg.ai_model or "").strip()
        alias = GEMINI_MODEL_ALIASES.get(model)
        if alias and alias != model:
            cfg.ai_model = alias
            cfg.save(update_fields=["ai_model"])


class Migration(migrations.Migration):
    dependencies = [
        ("assistant", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(upgrade_gemini_models, migrations.RunPython.noop),
    ]
