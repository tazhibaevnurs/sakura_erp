from django.urls import path

from .webhooks import views

urlpatterns = [
    path("webhook/telegram/", views.telegram_webhook, name="telegram_webhook"),
    path("webhook/whatsapp/", views.whatsapp_webhook, name="whatsapp_webhook"),
    path("webhook/instagram/", views.instagram_webhook, name="instagram_webhook"),
]
