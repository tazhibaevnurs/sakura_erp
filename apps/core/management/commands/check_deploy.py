"""Проверка готовности к production перед деплоем."""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Проверить обязательные production-настройки (.env, БД, Redis, HTTPS)."

    def handle(self, *args, **options):
        errors: list[str] = []
        warnings: list[str] = []

        secret = settings.SECRET_KEY
        if not secret or secret in {
            "dev-insecure-key-change-me",
            "change-me-long-random-secret",
        }:
            errors.append("DJANGO_SECRET_KEY не задан или использует шаблонное значение.")

        if settings.DEBUG:
            warnings.append("DJANGO_DEBUG=True — на сервере должно быть False.")

        _internal = {"localhost", "127.0.0.1", "web"}
        public_hosts = [h for h in settings.ALLOWED_HOSTS if h not in _internal]
        if not public_hosts:
            errors.append("DJANGO_ALLOWED_HOSTS: укажите домен или IP сервера.")

        use_https = getattr(settings, "USE_HTTPS", False)
        if use_https and not getattr(settings, "CSRF_TRUSTED_ORIGINS", []):
            errors.append(
                "DJANGO_USE_HTTPS=True, но CSRF_TRUSTED_ORIGINS пуст — "
                "добавьте https://ваш-домен"
            )

        db = settings.DATABASES["default"]
        if db.get("PASSWORD") in {"", "chaihana_secret"}:
            warnings.append("DB_PASSWORD: смените пароль PostgreSQL по умолчанию.")

        if not settings.ASSISTANT_PUBLIC_URL:
            warnings.append("ASSISTANT_PUBLIC_URL не задан — Telegram webhook не заработает.")

        ai_cfg = getattr(settings, "AI_ASSISTANT", {})
        if not ai_cfg.get("OPENAI_API_KEY") and not ai_cfg.get("GEMINI_API_KEY"):
            warnings.append("Не задан OPENAI_API_KEY / GEMINI_API_KEY — ИИ-ассистент отключён.")

        for msg in warnings:
            self.stdout.write(self.style.WARNING(f"WARN: {msg}"))

        if errors:
            for msg in errors:
                self.stderr.write(self.style.ERROR(f"ERR: {msg}"))
            raise CommandError(f"Проверка не пройдена: {len(errors)} ошибок.")

        self.stdout.write(self.style.SUCCESS("OK: Production-проверка пройдена."))
