from .base import *  # noqa: F403

# =============================================================================
# PRODUCTION / СЕРВЕР
# PostgreSQL + Redis из .env (см. .env.prod.example).
# Celery worker обязателен: celery -A config worker -l info
# Или контейнер celery в deploy/docker-compose.yml
# =============================================================================

DEBUG = env.bool("DJANGO_DEBUG", default=False)  # noqa: F405

# Асинхронные задачи через Redis (настройки брокера — в base.py)
CELERY_TASK_ALWAYS_EAGER = False
CELERY_TASK_EAGER_PROPAGATES = False

# За nginx / reverse proxy
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = env.bool("DJANGO_USE_X_FORWARDED_HOST", default=True)  # noqa: F405

# HTTPS: включите DJANGO_USE_HTTPS=True после настройки TLS (Let's Encrypt и т.д.)
USE_HTTPS = env.bool("DJANGO_USE_HTTPS", default=False)  # noqa: F405

CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])  # noqa: F405

if USE_HTTPS:
    SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)  # noqa: F405
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = env.int("DJANGO_HSTS_SECONDS", default=31536000)  # noqa: F405
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = env.bool("DJANGO_HSTS_PRELOAD", default=False)  # noqa: F405
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"
else:
    # HTTP-only (первый деплой без сертификата) — иначе формы/login не работают
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False

# Логирование в stdout для Docker
LOGGING["handlers"]["console"]["level"] = env("DJANGO_LOG_LEVEL", default="INFO")  # noqa: F405
LOGGING["loggers"]["django"] = {  # noqa: F405
    "handlers": ["console"],
    "level": env("DJANGO_LOG_LEVEL", default="INFO"),  # noqa: F405
    "propagate": False,
}
LOGGING["loggers"]["apps.ai_assistant"] = {  # noqa: F405
    "handlers": ["console"],
    "level": "INFO",
    "propagate": False,
}

# Sentry (опционально)
SENTRY_DSN = env("SENTRY_DSN", default="")  # noqa: F405
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration(), CeleryIntegration()],
        environment=env("SENTRY_ENVIRONMENT", default="production"),  # noqa: F405
        traces_sample_rate=env.float("SENTRY_TRACES_SAMPLE_RATE", default=0.1),  # noqa: F405
        send_default_pii=False,
    )
