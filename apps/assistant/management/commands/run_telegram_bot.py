from django.core.management.base import BaseCommand, CommandError

from apps.assistant.services import get_settings
from apps.assistant.telegram_bot import run_telegram_polling


class Command(BaseCommand):
    help = "Локальный Telegram-бот через long polling (без ngrok и webhook)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--timeout",
            type=int,
            default=30,
            help="Таймаут long polling в секундах (по умолчанию 30)",
        )

    def handle(self, *args, **options):
        cfg = get_settings()
        if not cfg.telegram_bot_token:
            raise CommandError("Укажите токен бота в настройках ассистента.")
        if not cfg.telegram_enabled:
            raise CommandError("Включите Telegram в настройках ассистента.")
        if not cfg.is_enabled:
            raise CommandError("Включите ассистента (is_enabled) в настройках.")

        self.stdout.write(
            self.style.NOTICE(
                "Режим polling для localhost. На сервере используйте webhook + ASSISTANT_PUBLIC_URL."
            )
        )

        def log(msg: str) -> None:
            self.stdout.write(msg)

        try:
            run_telegram_polling(cfg, poll_timeout=options["timeout"], on_log=log)
        except KeyboardInterrupt:
            self.stdout.write(self.style.SUCCESS("Telegram polling остановлен."))
        except RuntimeError as exc:
            raise CommandError(str(exc)) from exc
