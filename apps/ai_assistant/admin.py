from django.contrib import admin

from .models import AssistantConfig, ClientProfile, Conversation, Message


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ("role", "content", "intent_detected", "tokens_used", "created_at")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(AssistantConfig)
class AssistantConfigAdmin(admin.ModelAdmin):
    list_display = ("restaurant_name", "is_enabled", "updated_at")
    fieldsets = (
        (None, {"fields": ("is_enabled", "restaurant_name", "restaurant_phone", "restaurant_address", "working_hours")}),
        ("Для гостей", {"fields": ("about_restaurant", "delivery_info", "booking_info", "promotions")}),
        ("ИИ", {"fields": ("welcome_message", "custom_system_prompt")}),
    )

    def has_add_permission(self, request):
        return not AssistantConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ClientProfile)
class ClientProfileAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "telegram_id", "whatsapp_phone", "instagram_id", "total_orders", "last_interaction")
    search_fields = ("name", "phone", "telegram_id", "whatsapp_phone", "instagram_id")
    readonly_fields = ("telegram_id", "whatsapp_phone", "instagram_id", "total_orders", "last_interaction", "created_at")
    list_filter = ("preferred_channel", "preferred_order_type")


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "client", "channel", "status", "current_intent", "updated_at")
    list_filter = ("channel", "status", "current_intent")
    search_fields = ("client__name", "client__phone", "client__telegram_id")
    readonly_fields = ("created_at", "updated_at")
    inlines = [MessageInline]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "role", "content_preview", "intent_detected", "created_at")
    list_filter = ("role",)
    search_fields = ("content",)
    readonly_fields = ("conversation", "role", "content", "intent_detected", "tokens_used", "created_at")

    def content_preview(self, obj):
        return obj.content[:80]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
