import json
import logging

from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import FormView, TemplateView

from apps.core.mixins import RoleRequiredMixin

from .forms import AssistantSettingsForm, TestChatForm
from .dialogs import (
    _guest_label,
    get_dialog_messages,
    get_dialog_state,
    get_dialog_summaries,
)
from .knowledge import build_knowledge_context
from .models import AssistantChatLog
from .llm import AssistantLLMError
from .services import (
    ask_assistant,
    get_assistant_status,
    get_settings,
    get_telegram_webhook_status,
    get_webhook_urls,
    send_assistant_reply_whatsapp,
    send_whatsapp_message,
    setup_telegram_webhook,
)
from .voice import transcribe_audio

logger = logging.getLogger("apps.assistant")


class AssistantSettingsView(RoleRequiredMixin, FormView):
    template_name = "assistant/settings.html"
    form_class = AssistantSettingsForm
    allowed_roles = ["admin", "owner"]

    def get_object(self):
        return get_settings()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.get_object()
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        cfg = self.get_object()
        ctx["config"] = cfg
        ctx["webhooks"] = get_webhook_urls(self.request)
        ctx["telegram_webhook"] = get_telegram_webhook_status(cfg, self.request)
        ctx["recent_logs"] = AssistantChatLog.objects.all()[:15]
        ctx["test_form"] = TestChatForm()
        ctx["knowledge_preview"] = build_knowledge_context(cfg)[:3000]
        ctx["assistant_status"] = get_assistant_status(cfg)
        return ctx

    def form_valid(self, form):
        from .llm import GEMINI_MODEL_ALIASES

        old_model = self.get_object().ai_model
        form.save()
        new_model = self.get_object().ai_model
        if old_model != new_model and old_model in GEMINI_MODEL_ALIASES:
            messages.info(
                self.request,
                f"Модель {old_model} устарела — заменена на {new_model}.",
            )
        messages.success(self.request, "Настройки ассистента сохранены")

        if (
            form.cleaned_data.get("telegram_enabled")
            and form.cleaned_data.get("telegram_bot_token")
            and "setup_telegram" in self.request.POST
        ):
            ok, msg = setup_telegram_webhook(
                form.cleaned_data["telegram_bot_token"],
                get_webhook_urls(self.request)["telegram"],
            )
            if ok:
                messages.success(self.request, msg)
            else:
                messages.warning(self.request, f"Telegram webhook: {msg}")

        return redirect("assistant:settings")


class AssistantKnowledgeView(RoleRequiredMixin, TemplateView):
    template_name = "assistant/knowledge.html"
    allowed_roles = ["admin", "owner"]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        cfg = get_settings()
        ctx["knowledge"] = build_knowledge_context(cfg)
        return ctx


class AssistantDialogListView(RoleRequiredMixin, TemplateView):
    template_name = "assistant/dialogs.html"
    allowed_roles = ["admin", "owner"]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        channel = self.request.GET.get("channel", "").strip()
        search = self.request.GET.get("q", "").strip()
        try:
            page = max(1, int(self.request.GET.get("page", 1)))
        except ValueError:
            page = 1

        page_obj, summaries = get_dialog_summaries(
            channel=channel,
            search=search,
            page=page,
        )
        ctx["page_obj"] = page_obj
        ctx["summaries"] = summaries
        ctx["channel_filter"] = channel
        ctx["search_query"] = search
        ctx["channel_choices"] = AssistantChatLog.Channel.choices
        return ctx


class AssistantDialogDetailView(RoleRequiredMixin, TemplateView):
    template_name = "assistant/dialog_detail.html"
    allowed_roles = ["admin", "owner"]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        channel = kwargs["channel"]
        external_user_id = kwargs["external_user_id"]

        messages = get_dialog_messages(channel, external_user_id)
        if not messages:
            from django.http import Http404

            raise Http404("Диалог не найден")

        state = get_dialog_state(channel, external_user_id)
        first = messages[0]
        ctx["messages"] = messages
        ctx["channel"] = channel
        ctx["external_user_id"] = external_user_id
        ctx["channel_label"] = first.get_channel_display()
        ctx["guest_label"] = _guest_label(channel, external_user_id)
        ctx["state"] = state
        ctx["message_count"] = len(messages)
        return ctx


class AssistantTestChatView(RoleRequiredMixin, View):
    allowed_roles = ["admin", "owner"]

    def post(self, request):
        form = TestChatForm(request.POST)
        if not form.is_valid():
            return JsonResponse({"error": "Введите сообщение"}, status=400)
        user = request.user
        guest_name = user.get_full_name() or user.get_username()
        reply = ask_assistant(
            form.cleaned_data["message"],
            channel=AssistantChatLog.Channel.WEB_TEST,
            external_user_id=str(user.pk),
            guest_name=guest_name,
            allow_when_disabled=True,
        )
        return JsonResponse({"reply": reply})


@method_decorator(csrf_exempt, name="dispatch")
class TelegramWebhookView(View):
    def post(self, request):
        cfg = get_settings()
        if not cfg.is_enabled or not cfg.telegram_enabled or not cfg.telegram_bot_token:
            return HttpResponse("ok")

        try:
            payload = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            return HttpResponse("ok")

        from .telegram_bot import process_telegram_update

        process_telegram_update(cfg, payload)
        return HttpResponse("ok")


@method_decorator(csrf_exempt, name="dispatch")
class WhatsAppWebhookView(View):
    def get(self, request):
        cfg = get_settings()
        mode = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")
        if (
            mode == "subscribe"
            and token
            and token == cfg.whatsapp_verify_token
        ):
            return HttpResponse(challenge or "")
        return HttpResponse(status=403)

    def post(self, request):
        cfg = get_settings()
        if not cfg.is_enabled or not cfg.whatsapp_enabled:
            return HttpResponse("ok")

        try:
            payload = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            return HttpResponse("ok")

        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                for msg in value.get("messages", []):
                    from_id = msg.get("from", "")
                    text = ""
                    if msg.get("type") == "text":
                        text = msg.get("text", {}).get("body", "").strip()
                    elif cfg.voice_messages_enabled and msg.get("type") == "audio":
                        try:
                            from .services import download_whatsapp_media

                            audio = download_whatsapp_media(cfg, msg["audio"]["id"])
                            text = transcribe_audio(
                                audio,
                                cfg,
                                filename="voice.ogg",
                                mime_type=msg["audio"].get("mime_type") or "audio/ogg",
                            )
                        except AssistantLLMError as exc:
                            from .services import send_whatsapp_message

                            send_whatsapp_message(cfg, from_id, str(exc))
                            continue
                    if not text:
                        continue
                    reply = ask_assistant(
                        text,
                        channel=AssistantChatLog.Channel.WHATSAPP,
                        external_user_id=from_id,
                        guest_phone=from_id,
                    )
                    try:
                        send_assistant_reply_whatsapp(cfg, from_id, reply)
                    except Exception:
                        logger.exception("WhatsApp send failed")
        return HttpResponse("ok")
