from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(r"ws/orders/list/$", consumers.OrdersListConsumer.as_asgi()),
    re_path(r"ws/orders/(?P<order_id>\d+)/$", consumers.OrderNotifyConsumer.as_asgi()),
]
