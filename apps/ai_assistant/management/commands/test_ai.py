"""Быстрая проверка связи с LLM (OpenAI / OpenRouter / Gemini)."""
from django.core.management.base import BaseCommand, CommandError

from apps.ai_assistant.services.ai_engine import AIEngine, AIEngineError


class Command(BaseCommand):
    help = "Отправить тестовый запрос к LLM и показать ответ или ошибку."

    def handle(self, *args, **options):
        try:
            engine = AIEngine()
        except AIEngineError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            f"Провайдер: {engine.provider}, модель: {engine.model}"
        )

        try:
            if engine.provider == "openai":
                raw, tokens = engine._call_openai(
                    "Ответь JSON: {\"reply\": \"OK\", \"intent\": \"other\", \"extracted_data\": {}}",
                    [],
                    "ping",
                )
            else:
                raw, tokens = engine._call_gemini(
                    "Ответь JSON: {\"reply\": \"OK\", \"intent\": \"other\", \"extracted_data\": {}}",
                    [],
                    "ping",
                )
        except AIEngineError as exc:
            raise CommandError(f"Ошибка API: {exc}") from exc
        except Exception as exc:
            raise CommandError(f"Ошибка API: {exc}") from exc

        self.stdout.write(self.style.SUCCESS(f"OK — ответ получен ({tokens} токенов):"))
        self.stdout.write(raw[:500])
