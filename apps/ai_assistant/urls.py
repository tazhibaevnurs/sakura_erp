from django.urls import path

from . import views

app_name = "ai_assistant"

urlpatterns = [
    path("", views.AssistantDashboardView.as_view(), name="dashboard"),
    path("dialogs/", views.ConversationListView.as_view(), name="dialogs"),
    path("dialogs/<int:pk>/", views.ConversationDetailView.as_view(), name="dialog_detail"),
    path("dialogs/<int:pk>/status/", views.ConversationStatusView.as_view(), name="dialog_status"),
    path("settings/", views.AssistantSettingsView.as_view(), name="settings"),
    path("test/", views.TestChatView.as_view(), name="test_chat"),
    path("test/send/", views.TestChatApiView.as_view(), name="test_chat_api"),
]
