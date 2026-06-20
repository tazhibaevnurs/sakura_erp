import json
import logging

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from ..tasks.celery_tasks import process_incoming_message

logger = logging.getLogger("apps.ai_assistant")


@csrf_exempt
@require_http_methods(["POST"])
def telegram_webhook(request):
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    expected = settings.TELEGRAM_WEBHOOK_SECRET
    if expected and secret != expected:
        return JsonResponse({"ok": False, "error": "invalid secret"}, status=403)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

    process_incoming_message.delay("telegram", data)
    return JsonResponse({"ok": True})


@csrf_exempt
@require_http_methods(["GET", "POST"])
def whatsapp_webhook(request):
    if request.method == "GET":
        from ..channels.whatsapp_handler import WhatsAppHandler

        handler = WhatsAppHandler()
        challenge = handler.verify_webhook(request.GET.dict())
        if challenge is not None:
            return HttpResponse(challenge)
        return HttpResponse("Forbidden", status=403)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"ok": False}, status=400)

    process_incoming_message.delay("whatsapp", data)
    return JsonResponse({"ok": True})


@csrf_exempt
@require_http_methods(["GET", "POST"])
def instagram_webhook(request):
    if request.method == "GET":
        from ..channels.instagram_handler import InstagramHandler

        handler = InstagramHandler()
        challenge = handler.verify_webhook(request.GET.dict())
        if challenge is not None:
            return HttpResponse(challenge)
        return HttpResponse("Forbidden", status=403)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"ok": False}, status=400)

    process_incoming_message.delay("instagram", data)
    return JsonResponse({"ok": True})
