"""Распознавание голосовых сообщений."""
import base64
import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings as django_settings

from .llm import AssistantLLMError, _resolve_api_key
from .models import AssistantSettings

logger = logging.getLogger("apps.assistant")


def _openai_whisper_key(cfg: AssistantSettings) -> str:
    if cfg.ai_provider == AssistantSettings.AIProvider.OPENAI:
        return _resolve_api_key(cfg)
    return getattr(django_settings, "ASSISTANT_AI_API_KEY", "") or ""


def transcribe_openai_whisper(
    audio_bytes: bytes,
    cfg: AssistantSettings,
    *,
    filename: str = "voice.ogg",
    mime_type: str = "audio/ogg",
) -> str:
    api_key = _openai_whisper_key(cfg)
    if not api_key:
        raise AssistantLLMError(
            "Для Whisper нужен OpenAI API key (провайдер OpenAI или ASSISTANT_AI_API_KEY)."
        )

    boundary = "----SakuraVoiceBoundary"
    body = []
    body.append(f"--{boundary}\r\n".encode())
    body.append(
        b'Content-Disposition: form-data; name="model"\r\n\r\nwhisper-1\r\n'
    )
    body.append(f"--{boundary}\r\n".encode())
    body.append(
        f'Content-Disposition: form-data; name="language"\r\n\r\n{cfg.voice_language}\r\n'.encode()
    )
    body.append(f"--{boundary}\r\n".encode())
    body.append(
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode()
    )
    body.append(f"Content-Type: {mime_type}\r\n\r\n".encode())
    body.append(audio_bytes)
    body.append(f"\r\n--{boundary}--\r\n".encode())
    payload = b"".join(body)

    req = urllib.request.Request(
        "https://api.openai.com/v1/audio/transcriptions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    text = (data.get("text") or "").strip()
    if not text:
        raise AssistantLLMError("Не удалось распознать голосовое сообщение.")
    return text


def transcribe_gemini(audio_bytes: bytes, cfg: AssistantSettings, mime_type: str) -> str:
    api_key = _resolve_api_key(cfg)
    if not api_key:
        raise AssistantLLMError("Не настроен Gemini API key для распознавания голоса.")

    model = "gemini-2.5-flash-lite"
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{urllib.parse.quote(model, safe='')}:generateContent"
        f"?key={urllib.parse.quote(api_key, safe='')}"
    )
    payload = json.dumps(
        {
            "contents": [
                {
                    "parts": [
                        {
                            "text": (
                                "Распознай речь в аудио и верни только текст на русском. "
                                "Без пояснений."
                            )
                        },
                        {
                            "inlineData": {
                                "mimeType": mime_type,
                                "data": base64.b64encode(audio_bytes).decode("ascii"),
                            }
                        },
                    ]
                }
            ],
            "generationConfig": {"temperature": 0, "maxOutputTokens": 500},
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        logger.error("Gemini voice parse error: %s", data)
        raise AssistantLLMError("Не удалось распознать голос через Gemini.") from exc
    if not text:
        raise AssistantLLMError("Пустой результат распознавания голоса.")
    return text


def transcribe_audio(
    audio_bytes: bytes,
    cfg: AssistantSettings,
    *,
    filename: str = "voice.ogg",
    mime_type: str = "audio/ogg",
) -> str:
    if not cfg.voice_messages_enabled:
        raise AssistantLLMError("Голосовые сообщения отключены в настройках.")
    if cfg.voice_provider == AssistantSettings.VoiceProvider.GEMINI:
        return transcribe_gemini(audio_bytes, cfg, mime_type)
    return transcribe_openai_whisper(
        audio_bytes, cfg, filename=filename, mime_type=mime_type
    )
