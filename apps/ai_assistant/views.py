from django.contrib import messages
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.generic import DetailView, ListView, TemplateView, View
from apps.core.mixins import RoleRequiredMixin

from .forms import AssistantConfigForm
from .models import AIOrder, AssistantConfig, ClientProfile, Conversation, Message
from .services.helpers import format_client_phone, format_draft_display, get_intent_label
from .services.prompts import BASE_SYSTEM_PROMPT, build_system_prompt
from .services.status import get_assistant_status
from .services.test_chat import get_test_conversation, get_test_messages, reset_test_conversation, send_test_message

class AssistantAccessMixin(RoleRequiredMixin):
    allowed_roles = ["admin", "owner"]


class AssistantDashboardView(AssistantAccessMixin, TemplateView):
    template_name = "ai_assistant/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = timezone.localdate()
        ctx["stats"] = {
            "clients": ClientProfile.objects.count(),
            "active_dialogs": Conversation.objects.filter(
                status__in=["active", "waiting_confirm"]
            ).count(),
            "messages_today": Message.objects.filter(created_at__date=today).count(),
            "orders_today": AIOrder.objects.filter(created_at__date=today).count(),
            "escalated": Conversation.objects.filter(status="escalated").count(),
        }
        ctx["recent_dialogs"] = (
            Conversation.objects.select_related("client")
            .annotate(msg_count=Count("messages"))
            .order_by("-updated_at")[:8]
        )
        ctx["status"] = get_assistant_status()
        return ctx


class ConversationListView(AssistantAccessMixin, ListView):
    template_name = "ai_assistant/dialogs.html"
    context_object_name = "conversations"
    paginate_by = 25

    def get_queryset(self):
        qs = Conversation.objects.select_related("client").annotate(
            msg_count=Count("messages")
        )
        channel = self.request.GET.get("channel", "")
        status = self.request.GET.get("status", "")
        q = self.request.GET.get("q", "").strip()

        if channel:
            qs = qs.filter(channel=channel)
        if status:
            qs = qs.filter(status=status)
        if q:
            qs = qs.filter(
                Q(client__name__icontains=q)
                | Q(client__phone__icontains=q)
                | Q(client__telegram_id__icontains=q)
            )
        return qs.order_by("-updated_at")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["filter_channel"] = self.request.GET.get("channel", "")
        ctx["filter_status"] = self.request.GET.get("status", "")
        ctx["filter_q"] = self.request.GET.get("q", "")
        ctx["channel_choices"] = Conversation.CHANNEL_CHOICES
        ctx["status_choices"] = Conversation.STATUS_CHOICES
        return ctx


class ConversationDetailView(AssistantAccessMixin, DetailView):
    template_name = "ai_assistant/dialog_detail.html"
    context_object_name = "conversation"
    model = Conversation

    def get_queryset(self):
        return Conversation.objects.select_related("client").prefetch_related("messages")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        messages = self.object.messages.order_by("created_at")
        ctx["messages_list"] = messages
        ctx["message_count"] = messages.count()
        ctx["status_choices"] = Conversation.STATUS_CHOICES
        ctx["draft_lines"] = format_draft_display(self.object.draft_data)
        ctx["intent_label"] = get_intent_label(self.object.current_intent)
        ctx["client_phone_display"] = format_client_phone(self.object.client.phone)
        ctx["linked_booking"] = (
            self.object.client.ai_bookings.select_related(
                "erp_reservation__table"
            )
            .filter(created_at__gte=self.object.created_at)
            .order_by("-created_at")
            .first()
        )
        return ctx

class AssistantSettingsView(AssistantAccessMixin, TemplateView):
    template_name = "ai_assistant/settings.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        config = AssistantConfig.load()
        ctx["config"] = config
        ctx["config_form"] = AssistantConfigForm(instance=config)
        ctx["status"] = get_assistant_status()
        ctx["base_prompt_preview"] = BASE_SYSTEM_PROMPT.split("{custom_instructions}")[0].strip()
        ctx["prompt_preview"] = build_system_prompt(
            restaurant_name=config.restaurant_name,
            custom_instructions=config.custom_system_prompt,
            business_context="[меню и часы работы из БД]",
            client_context="[данные клиента]",
            draft_data="{}",
        )
        return ctx

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action")
        config = AssistantConfig.load()

        if action == "save_config":
            form = AssistantConfigForm(request.POST, instance=config)
            if form.is_valid():
                form.save()
                messages.success(request, "Настройки и системный промпт сохранены.")
            else:
                messages.error(request, "Проверьте форму — есть ошибки.")
            return redirect("ai_assistant:settings")

        if action == "register_webhook":
            from django.core.management import call_command
            from io import StringIO

            out = StringIO()
            try:
                call_command("register_telegram_webhook", stdout=out)
                messages.success(request, out.getvalue() or "Webhook зарегистрирован.")
            except Exception as exc:
                messages.error(request, str(exc))
        return redirect("ai_assistant:settings")


class ConversationStatusView(AssistantAccessMixin, View):
    def post(self, request, pk):
        conversation = get_object_or_404(Conversation, pk=pk)
        new_status = request.POST.get("status")
        valid = {choice[0] for choice in Conversation.STATUS_CHOICES}
        if new_status in valid:
            conversation.status = new_status
            conversation.save(update_fields=["status", "updated_at"])
            messages.success(request, f"Статус изменён: {conversation.get_status_display()}")
        return redirect("ai_assistant:dialog_detail", pk=pk)


class TestChatView(AssistantAccessMixin, TemplateView):
    template_name = "ai_assistant/test_chat.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        conversation = get_test_conversation(self.request.user)
        ctx["messages_list"] = get_test_messages(self.request.user)
        ctx["conversation"] = conversation
        ctx["status"] = get_assistant_status()
        return ctx


class TestChatApiView(AssistantAccessMixin, View):
    def post(self, request):
        action = request.POST.get("action", "send")
        if action == "reset":
            reset_test_conversation(request.user)
            return JsonResponse({"ok": True, "messages": []})

        text = request.POST.get("message", "")
        data = send_test_message(request.user, text)
        if not data.get("ok"):
            return JsonResponse(data, status=400)
        data["messages"] = get_test_messages(request.user)
        return JsonResponse(data)