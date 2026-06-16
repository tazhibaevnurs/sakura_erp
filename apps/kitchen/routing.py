from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(r"ws/kitchen/(?P<section_slug>[\w-]+)/$", consumers.KitchenConsumer.as_asgi()),
]
