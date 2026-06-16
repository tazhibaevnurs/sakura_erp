from django.urls import path

from . import views

app_name = "assistant"

urlpatterns = [
    path("settings/", views.AssistantSettingsView.as_view(), name="settings"),
    path("knowledge/", views.AssistantKnowledgeView.as_view(), name="knowledge"),
    path("dialogs/", views.AssistantDialogListView.as_view(), name="dialogs"),
    path(
        "dialogs/<str:channel>/<str:external_user_id>/",
        views.AssistantDialogDetailView.as_view(),
        name="dialog_detail",
    ),
    path("api/test-chat/", views.AssistantTestChatView.as_view(), name="test_chat"),
    path("webhook/telegram/", views.TelegramWebhookView.as_view(), name="telegram_webhook"),
    path("webhook/whatsapp/", views.WhatsAppWebhookView.as_view(), name="whatsapp_webhook"),
]
