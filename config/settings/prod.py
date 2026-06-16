from .base import *  # noqa: F403

DEBUG = env.bool("DJANGO_DEBUG", default=False)  # noqa: F405

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
