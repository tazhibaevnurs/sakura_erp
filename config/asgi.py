import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

django_asgi_app = get_asgi_application()

from apps.kitchen.routing import websocket_urlpatterns as kitchen_ws  # noqa: E402
from apps.orders.routing import websocket_urlpatterns as orders_ws  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AuthMiddlewareStack(URLRouter(kitchen_ws + orders_ws)),
    }
)
