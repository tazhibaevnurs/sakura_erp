from django.core.validators import MaxValueValidator, MinValueValidator

from django.db import models





class AssistantSettings(models.Model):

    class AIProvider(models.TextChoices):

        OPENAI = "openai", "OpenAI"

        GEMINI = "gemini", "Google Gemini"

        OPENROUTER = "openrouter", "OpenRouter"

        CUSTOM = "custom", "Свой API (OpenAI-совместимый)"



    class ReplyFormat(models.TextChoices):

        PLAIN = "plain", "Обычный текст"

        MARKDOWN = "markdown", "Markdown (Telegram)"

        TELEGRAM_HTML = "telegram_html", "HTML (Telegram)"



    class VoiceProvider(models.TextChoices):

        OPENAI_WHISPER = "openai_whisper", "OpenAI Whisper"

        GEMINI = "gemini", "Google Gemini"



    is_enabled = models.BooleanField(default=False, verbose_name="Ассистент включён")

    accept_orders_enabled = models.BooleanField(

        default=True,

        verbose_name="Принимать заказы",

        help_text="Ассистент оформляет заказы: доставка, навынос, в зале",

    )

    restaurant_name = models.CharField(max_length=200, default="Сакура", verbose_name="Название")

    restaurant_address = models.TextField(blank=True, verbose_name="Адрес")

    restaurant_phone = models.CharField(max_length=50, blank=True, verbose_name="Телефон")

    working_hours = models.TextField(

        default="Ежедневно 10:00–23:00",

        verbose_name="Часы работы",

        help_text="Текст для гостей, например: Пн–Вс 10:00–23:00",

    )

    about_restaurant = models.TextField(

        blank=True,

        verbose_name="О ресторане",

        help_text="Кухня, атмосфера, особенности",

    )

    delivery_info = models.TextField(

        blank=True,

        verbose_name="Доставка",

        help_text="Условия, зона, минимальный заказ",

    )

    booking_info = models.TextField(

        blank=True,

        verbose_name="Бронирование",

        help_text="Как забронировать стол, правила",

    )

    welcome_message = models.TextField(

        default="Здравствуйте! Я помощник ресторана. Спросите о меню, столах, брони или времени работы.",

        verbose_name="Приветствие",

    )



    ai_provider = models.CharField(

        max_length=20,

        choices=AIProvider.choices,

        default=AIProvider.OPENAI,

        verbose_name="Провайдер ИИ",

    )

    ai_api_key = models.CharField(max_length=500, blank=True, verbose_name="API-ключ ИИ")

    ai_model = models.CharField(

        max_length=100,

        default="gpt-4o-mini",

        verbose_name="Модель",

    )

    ai_base_url = models.CharField(

        max_length=300,

        blank=True,

        verbose_name="Base URL API",

        help_text="Для OpenRouter или своего сервера",

    )

    agent_instruction = models.TextField(

        blank=True,

        verbose_name="Инструкция для ИИ-агента",

        help_text="Главные правила поведения: тон, что можно/нельзя, сценарии",

    )

    ai_temperature = models.FloatField(

        default=0.4,

        validators=[MinValueValidator(0.0), MaxValueValidator(2.0)],

        verbose_name="Температура",

        help_text="0 — точные ответы, 1+ — более свободные. Рекомендуется 0.3–0.6",

    )

    max_output_tokens = models.PositiveSmallIntegerField(

        default=800,

        verbose_name="Макс. длина ответа (токены)",

    )

    max_history_turns = models.PositiveSmallIntegerField(

        default=8,

        verbose_name="Глубина памяти диалога",

        help_text="Сколько последних пар сообщений помнит ассистент",

    )



    operator_handoff_enabled = models.BooleanField(

        default=True,

        verbose_name="Контроль вмешательства оператора",

        help_text="Передавать диалог человеку по ключевым словам",

    )

    operator_handoff_keywords = models.TextField(

        default="оператор, человек, менеджер, администратор, позовите",

        blank=True,

        verbose_name="Слова для вызова оператора",

        help_text="Через запятую",

    )

    operator_handoff_message = models.TextField(

        default="Сейчас подключим сотрудника ресторана. Ожидайте ответа по телефону или в чате.",

        verbose_name="Сообщение при вызове оператора",

    )

    operator_pause_minutes = models.PositiveSmallIntegerField(

        default=30,

        verbose_name="Пауза ИИ после вызова оператора (мин)",

        help_text="На это время ассистент не отвечает в этом чате",

    )



    reply_format = models.CharField(

        max_length=20,

        choices=ReplyFormat.choices,

        default=ReplyFormat.PLAIN,

        verbose_name="Форматирование текста",

    )

    use_emoji = models.BooleanField(

        default=True,

        verbose_name="Эмодзи в ответах",

    )

    split_long_messages = models.BooleanField(

        default=True,

        verbose_name="Делить длинные ответы",

        help_text="Telegram/WhatsApp: отправка частями до 4000 символов",

    )



    voice_messages_enabled = models.BooleanField(

        default=False,

        verbose_name="Голосовые сообщения",

        help_text="Распознавание голоса в Telegram и WhatsApp",

    )

    voice_provider = models.CharField(

        max_length=20,

        choices=VoiceProvider.choices,

        default=VoiceProvider.OPENAI_WHISPER,

        verbose_name="Сервис распознавания голоса",

    )

    voice_language = models.CharField(

        max_length=10,

        default="ru",

        verbose_name="Язык голоса",

    )



    typing_indicator_enabled = models.BooleanField(

        default=True,

        verbose_name="Индикатор «печатает…» (Telegram)",

    )

    response_delay_ms = models.PositiveIntegerField(

        default=0,

        verbose_name="Задержка ответа (мс)",

        help_text="Имитация времени на ответ, 0 — без задержки",

    )

    business_hours_only = models.BooleanField(

        default=False,

        verbose_name="Отвечать только в часы работы",

    )

    off_hours_message = models.TextField(

        default="Сейчас ресторан закрыт. Мы ответим в рабочее время.",

        blank=True,

        verbose_name="Сообщение вне часов работы",

    )

    fallback_message = models.TextField(

        default="Не удалось обработать запрос. Позвоните в ресторан — мы поможем.",

        blank=True,

        verbose_name="Сообщение при ошибке ИИ",

    )



    # Сохранено для обратной совместимости миграций

    extra_system_prompt = models.TextField(

        blank=True,

        verbose_name="Доп. инструкции (устар.)",

        editable=False,

    )



    telegram_enabled = models.BooleanField(default=False, verbose_name="Telegram")

    telegram_bot_token = models.CharField(max_length=200, blank=True, verbose_name="Telegram Bot Token")



    whatsapp_enabled = models.BooleanField(default=False, verbose_name="WhatsApp")

    whatsapp_phone_number_id = models.CharField(

        max_length=50, blank=True, verbose_name="WhatsApp Phone Number ID"

    )

    whatsapp_access_token = models.CharField(

        max_length=500, blank=True, verbose_name="WhatsApp Access Token"

    )

    whatsapp_verify_token = models.CharField(

        max_length=100,

        blank=True,

        verbose_name="WhatsApp Verify Token",

        help_text="Для подтверждения webhook в Meta",

    )



    updated_at = models.DateTimeField(auto_now=True)



    class Meta:

        verbose_name = "Настройки ассистента"

        verbose_name_plural = "Настройки ассистента"



    def __str__(self):

        return f"ИИ-ассистент ({self.restaurant_name})"



    @property

    def has_ai_key(self):

        return bool(self.ai_api_key.strip())



    def get_agent_instruction(self) -> str:

        return (self.agent_instruction or self.extra_system_prompt or "").strip()





class AssistantChannelState(models.Model):

    """Состояние чата: пауза ИИ после вызова оператора."""



    channel = models.CharField(max_length=20)

    external_user_id = models.CharField(max_length=100)

    ai_paused_until = models.DateTimeField(null=True, blank=True)

    operator_requested_at = models.DateTimeField(null=True, blank=True)

    pending_order_json = models.TextField(

        blank=True,

        verbose_name="Незавершённый заказ",

        help_text="Пошаговая квалификация заказа (JSON)",

    )

    guest_language = models.CharField(

        max_length=5,

        blank=True,

        default="",

        verbose_name="Язык гостя",

        help_text="ru или ky — язык последних сообщений гостя",

    )

    updated_at = models.DateTimeField(auto_now=True)



    class Meta:

        unique_together = [("channel", "external_user_id")]

        verbose_name = "Состояние канала"

        verbose_name_plural = "Состояния каналов"





class AssistantChatLog(models.Model):

    class Channel(models.TextChoices):

        TELEGRAM = "telegram", "Telegram"

        WHATSAPP = "whatsapp", "WhatsApp"

        WEB_TEST = "web_test", "Тест на сайте"



    channel = models.CharField(max_length=20, choices=Channel.choices)

    external_user_id = models.CharField(max_length=100, blank=True)

    user_message = models.TextField()

    assistant_reply = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)



    class Meta:

        ordering = ["-created_at"]

        verbose_name = "Лог диалога"

        verbose_name_plural = "Логи диалогов"


