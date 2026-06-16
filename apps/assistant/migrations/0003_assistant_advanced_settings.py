from django.db import migrations, models
import django.core.validators


def copy_extra_prompt_to_agent_instruction(apps, schema_editor):
    AssistantSettings = apps.get_model("assistant", "AssistantSettings")
    for cfg in AssistantSettings.objects.all():
        if cfg.extra_system_prompt and not cfg.agent_instruction:
            cfg.agent_instruction = cfg.extra_system_prompt
            cfg.save(update_fields=["agent_instruction"])


class Migration(migrations.Migration):
    dependencies = [
        ("assistant", "0002_upgrade_gemini_models"),
    ]

    operations = [
        migrations.CreateModel(
            name="AssistantChannelState",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("channel", models.CharField(max_length=20)),
                ("external_user_id", models.CharField(max_length=100)),
                ("ai_paused_until", models.DateTimeField(blank=True, null=True)),
                ("operator_requested_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Состояние канала",
                "verbose_name_plural": "Состояния каналов",
                "unique_together": {("channel", "external_user_id")},
            },
        ),
        migrations.AddField(
            model_name="assistantsettings",
            name="agent_instruction",
            field=models.TextField(
                blank=True,
                help_text="Главные правила поведения: тон, что можно/нельзя, сценарии",
                verbose_name="Инструкция для ИИ-агента",
            ),
        ),
        migrations.AddField(
            model_name="assistantsettings",
            name="ai_temperature",
            field=models.FloatField(
                default=0.4,
                help_text="0 — точные ответы, 1+ — более свободные. Рекомендуется 0.3–0.6",
                validators=[
                    django.core.validators.MinValueValidator(0.0),
                    django.core.validators.MaxValueValidator(2.0),
                ],
                verbose_name="Температура",
            ),
        ),
        migrations.AddField(
            model_name="assistantsettings",
            name="max_output_tokens",
            field=models.PositiveSmallIntegerField(default=800, verbose_name="Макс. длина ответа (токены)"),
        ),
        migrations.AddField(
            model_name="assistantsettings",
            name="max_history_turns",
            field=models.PositiveSmallIntegerField(
                default=8,
                help_text="Сколько последних пар сообщений помнит ассистент",
                verbose_name="Глубина памяти диалога",
            ),
        ),
        migrations.AddField(
            model_name="assistantsettings",
            name="operator_handoff_enabled",
            field=models.BooleanField(
                default=True,
                help_text="Передавать диалог человеку по ключевым словам",
                verbose_name="Контроль вмешательства оператора",
            ),
        ),
        migrations.AddField(
            model_name="assistantsettings",
            name="operator_handoff_keywords",
            field=models.TextField(
                blank=True,
                default="оператор, человек, менеджер, администратор, позовите",
                help_text="Через запятую",
                verbose_name="Слова для вызова оператора",
            ),
        ),
        migrations.AddField(
            model_name="assistantsettings",
            name="operator_handoff_message",
            field=models.TextField(
                default="Сейчас подключим сотрудника ресторана. Ожидайте ответа по телефону или в чате.",
                verbose_name="Сообщение при вызове оператора",
            ),
        ),
        migrations.AddField(
            model_name="assistantsettings",
            name="operator_pause_minutes",
            field=models.PositiveSmallIntegerField(
                default=30,
                help_text="На это время ассистент не отвечает в этом чате",
                verbose_name="Пауза ИИ после вызова оператора (мин)",
            ),
        ),
        migrations.AddField(
            model_name="assistantsettings",
            name="reply_format",
            field=models.CharField(
                choices=[
                    ("plain", "Обычный текст"),
                    ("markdown", "Markdown (Telegram)"),
                    ("telegram_html", "HTML (Telegram)"),
                ],
                default="plain",
                max_length=20,
                verbose_name="Форматирование текста",
            ),
        ),
        migrations.AddField(
            model_name="assistantsettings",
            name="use_emoji",
            field=models.BooleanField(default=True, verbose_name="Эмодзи в ответах"),
        ),
        migrations.AddField(
            model_name="assistantsettings",
            name="split_long_messages",
            field=models.BooleanField(
                default=True,
                help_text="Telegram/WhatsApp: отправка частями до 4000 символов",
                verbose_name="Делить длинные ответы",
            ),
        ),
        migrations.AddField(
            model_name="assistantsettings",
            name="voice_messages_enabled",
            field=models.BooleanField(
                default=False,
                help_text="Распознавание голоса в Telegram и WhatsApp",
                verbose_name="Голосовые сообщения",
            ),
        ),
        migrations.AddField(
            model_name="assistantsettings",
            name="voice_provider",
            field=models.CharField(
                choices=[
                    ("openai_whisper", "OpenAI Whisper"),
                    ("gemini", "Google Gemini"),
                ],
                default="openai_whisper",
                max_length=20,
                verbose_name="Сервис распознавания голоса",
            ),
        ),
        migrations.AddField(
            model_name="assistantsettings",
            name="voice_language",
            field=models.CharField(default="ru", max_length=10, verbose_name="Язык голоса"),
        ),
        migrations.AddField(
            model_name="assistantsettings",
            name="typing_indicator_enabled",
            field=models.BooleanField(default=True, verbose_name="Индикатор «печатает…» (Telegram)"),
        ),
        migrations.AddField(
            model_name="assistantsettings",
            name="response_delay_ms",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Имитация времени на ответ, 0 — без задержки",
                verbose_name="Задержка ответа (мс)",
            ),
        ),
        migrations.AddField(
            model_name="assistantsettings",
            name="business_hours_only",
            field=models.BooleanField(default=False, verbose_name="Отвечать только в часы работы"),
        ),
        migrations.AddField(
            model_name="assistantsettings",
            name="off_hours_message",
            field=models.TextField(
                blank=True,
                default="Сейчас ресторан закрыт. Мы ответим в рабочее время.",
                verbose_name="Сообщение вне часов работы",
            ),
        ),
        migrations.AddField(
            model_name="assistantsettings",
            name="fallback_message",
            field=models.TextField(
                blank=True,
                default="Не удалось обработать запрос. Позвоните в ресторан — мы поможем.",
                verbose_name="Сообщение при ошибке ИИ",
            ),
        ),
        migrations.RunPython(copy_extra_prompt_to_agent_instruction, migrations.RunPython.noop),
    ]
