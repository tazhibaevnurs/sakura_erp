from .base import *  # noqa: F403

DEBUG = True
ALLOWED_HOSTS = ["*"]

# =============================================================================
# ЛОКАЛЬНАЯ РАЗРАБОТКА
# SQLite + in-memory — Redis, PostgreSQL и Celery worker не нужны.
# ИИ-ассистент: webhook → process_incoming_message.delay() выполняется сразу.
# Запуск: .\run-local.ps1
# =============================================================================

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",  # noqa: F405
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}

# Celery синхронный — Redis не используется, worker не запускаем
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

INSTALLED_APPS += ["debug_toolbar"]  # noqa: F405

MIDDLEWARE = ["debug_toolbar.middleware.DebugToolbarMiddleware"] + MIDDLEWARE  # noqa: F405

INTERNAL_IPS = ["127.0.0.1", "localhost"]

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
