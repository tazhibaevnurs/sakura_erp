from django.contrib import admin

from .models import AssistantChannelState, AssistantChatLog, AssistantSettings


@admin.register(AssistantSettings)
class AssistantSettingsAdmin(admin.ModelAdmin):
    list_display = ("restaurant_name", "is_enabled", "telegram_enabled", "whatsapp_enabled", "updated_at")


@admin.register(AssistantChannelState)
class AssistantChannelStateAdmin(admin.ModelAdmin):
    list_display = ("channel", "external_user_id", "ai_paused_until", "operator_requested_at")
    list_filter = ("channel",)


@admin.register(AssistantChatLog)
class AssistantChatLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "channel", "external_user_id", "user_message")
    list_filter = ("channel",)
    readonly_fields = ("created_at",)
