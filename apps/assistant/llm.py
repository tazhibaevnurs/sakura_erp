import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings as django_settings

from .actions import ActionContext
from .knowledge import build_system_prompt
from .models import AssistantSettings
from .tools import (
    gemini_tools_payload,
    get_tools_system_addendum,
    openai_tools_payload,
    run_tool,
)

logger = logging.getLogger("apps.assistant")

DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash-lite"
MAX_KNOWLEDGE_CHARS = 14000

# Устаревшие имена → актуальные (gemini-1.5-* сняты с API)
GEMINI_MODEL_ALIASES = {
    "gemini-1.5-flash": "gemini-2.5-flash-lite",
    "gemini-1.5-flash-latest": "gemini-2.5-flash-lite",
    "gemini-1.5-flash-001": "gemini-2.5-flash-lite",
    "gemini-1.5-flash-002": "gemini-2.5-flash-lite",
    "gemini-1.5-flash-8b": "gemini-2.5-flash-lite",
    "gemini-1.5-pro": "gemini-2.5-flash",
    "gemini-1.5-pro-latest": "gemini-2.5-flash",
    "gemini-2.0-flash": "gemini-2.5-flash-lite",
}

GEMINI_FALLBACK_MODELS = (
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.0-flash-lite",
)


class AssistantLLMError(Exception):
    pass


def _resolve_api_key(cfg: AssistantSettings) -> str:
    key = (cfg.ai_api_key or "").strip()
    if key:
        return key
    if cfg.ai_provider == AssistantSettings.AIProvider.GEMINI:
        return getattr(django_settings, "ASSISTANT_GEMINI_API_KEY", "") or ""
    return getattr(django_settings, "ASSISTANT_AI_API_KEY", "") or ""


def _compact_system_prompt(cfg: AssistantSettings, *, language: str = "ru") -> str:
    prompt = build_system_prompt(cfg, language=language) + get_tools_system_addendum(cfg)
    if len(prompt) <= MAX_KNOWLEDGE_CHARS:
        return prompt
    return (
        prompt[:MAX_KNOWLEDGE_CHARS]
        + "\n\n[... база знаний сокращена для лимита API ...]"
    )


def _friendly_http_error(code: int, body: str, cfg: AssistantSettings) -> str:
    model = _default_model(cfg)
    if code == 429:
        if cfg.ai_provider == AssistantSettings.AIProvider.GEMINI:
            return (
                f"Квота Gemini исчерпана (модель {model}). "
                "Подождите 1–2 минуты, смените модель на gemini-2.5-flash-lite "
                "или включите биллинг в Google AI Studio."
            )
        return "Превышен лимит запросов к ИИ API. Подождите и повторите."
    if code in (401, 403):
        if cfg.ai_provider == AssistantSettings.AIProvider.GEMINI:
            return "Неверный Gemini API key. Проверьте ключ в Google AI Studio."
        return "Неверный API-ключ ИИ. Проверьте настройки."
    if code == 404:
        return (
            f"Модель «{model}» недоступна в Gemini API. "
            "Укажите gemini-2.5-flash-lite или gemini-2.5-flash."
        )
    try:
        data = json.loads(body)
        msg = data.get("error", {}).get("message") or data.get("message", "")
        if msg:
            return f"Ошибка ИИ API ({code}): {msg[:200]}"
    except json.JSONDecodeError:
        pass
    return f"Ошибка ИИ API ({code})"


def _default_model(cfg: AssistantSettings) -> str:
    if cfg.ai_model:
        return cfg.ai_model.strip()
    if cfg.ai_provider == AssistantSettings.AIProvider.GEMINI:
        return DEFAULT_GEMINI_MODEL
    return DEFAULT_OPENAI_MODEL


def _resolve_gemini_model(cfg: AssistantSettings) -> str:
    model = _default_model(cfg)
    return GEMINI_MODEL_ALIASES.get(model, model)


def _gemini_model_chain(cfg: AssistantSettings) -> list[str]:
    primary = _resolve_gemini_model(cfg)
    chain = [primary]
    for model in GEMINI_FALLBACK_MODELS:
        if model not in chain:
            chain.append(model)
    return chain


def _openai_api_url(cfg: AssistantSettings) -> str:
    if cfg.ai_provider == AssistantSettings.AIProvider.OPENROUTER:
        return cfg.ai_base_url.strip() or "https://openrouter.ai/api/v1/chat/completions"
    if cfg.ai_provider == AssistantSettings.AIProvider.CUSTOM and cfg.ai_base_url.strip():
        base = cfg.ai_base_url.rstrip("/")
        return f"{base}/chat/completions" if not base.endswith("chat/completions") else base
    return "https://api.openai.com/v1/chat/completions"


def _openai_post(api_key: str, cfg: AssistantSettings, payload: dict) -> dict:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    if cfg.ai_provider == AssistantSettings.AIProvider.OPENROUTER:
        headers["HTTP-Referer"] = "https://sakura-erp.local"
        headers["X-Title"] = cfg.restaurant_name

    req = urllib.request.Request(
        _openai_api_url(cfg),
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _llm_temperature(cfg: AssistantSettings) -> float:
    return max(0.0, min(2.0, float(cfg.ai_temperature or 0.4)))


def _llm_max_tokens(cfg: AssistantSettings) -> int:
    return max(100, min(4000, int(cfg.max_output_tokens or 800)))


def _generate_openai_compatible(
    cfg: AssistantSettings,
    api_key: str,
    user_message: str,
    history: list[dict] | None,
    action_ctx: ActionContext | None = None,
) -> str:
    language = getattr(action_ctx, "language", "ru") if action_ctx else "ru"
    messages = [{"role": "system", "content": _compact_system_prompt(cfg, language=language)}]
    for item in history or []:
        messages.append({"role": item["role"], "content": item["content"]})
    messages.append({"role": "user", "content": user_message})

    for _ in range(6):
        payload = {
            "model": _default_model(cfg),
            "messages": messages,
            "temperature": _llm_temperature(cfg),
            "max_tokens": _llm_max_tokens(cfg),
            "tools": openai_tools_payload(cfg),
        }
        data = _openai_post(api_key, cfg, payload)
        message = data["choices"][0]["message"]
        tool_calls = message.get("tool_calls") or []
        if not tool_calls:
            return (message.get("content") or "").strip()

        messages.append(message)
        for call in tool_calls:
            fn = call.get("function", {})
            name = fn.get("name", "")
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            result = run_tool(name, args, action_ctx, cfg)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.get("id", name),
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )

    raise AssistantLLMError("Не удалось завершить ответ ассистента")


def _gemini_contents_from_history(
    history: list[dict] | None, user_message: str
) -> list[dict]:
    contents = []
    for item in history or []:
        role = "model" if item["role"] == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": item["content"]}]})
    contents.append({"role": "user", "parts": [{"text": user_message}]})
    return contents


def _gemini_generate_once(
    api_key: str,
    model: str,
    system_prompt: str,
    contents: list[dict],
    cfg: AssistantSettings,
    *,
    tools: bool,
) -> dict:
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{urllib.parse.quote(model, safe='')}:generateContent"
        f"?key={urllib.parse.quote(api_key, safe='')}"
    )
    body = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": contents,
        "generationConfig": {
            "temperature": _llm_temperature(cfg),
            "maxOutputTokens": _llm_max_tokens(cfg),
        },
    }
    if tools:
        body["tools"] = gemini_tools_payload(cfg)

    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _gemini_extract_text(parts: list[dict]) -> str:
    chunks = []
    for part in parts:
        if text := part.get("text"):
            chunks.append(text.strip())
    return "\n".join(chunks).strip()


def _call_gemini_with_tools(
    api_key: str,
    model: str,
    system_prompt: str,
    user_message: str,
    history: list[dict] | None,
    action_ctx: ActionContext | None,
    cfg: AssistantSettings,
) -> str:
    contents = _gemini_contents_from_history(history, user_message)

    for _ in range(6):
        data = _gemini_generate_once(
            api_key, model, system_prompt, contents, cfg, tools=True
        )
        try:
            parts = data["candidates"][0]["content"]["parts"]
        except (KeyError, IndexError, TypeError) as exc:
            logger.error("Gemini bad response (%s): %s", model, data)
            raise AssistantLLMError("Некорректный ответ Gemini") from exc

        function_calls = [p for p in parts if "functionCall" in p]
        if not function_calls:
            text = _gemini_extract_text(parts)
            if text:
                return text
            if action_ctx:
                from .order_flow import load_pending_order, try_order_flow_reply

                if load_pending_order(action_ctx):
                    recovered = try_order_flow_reply(user_message, history, action_ctx)
                    if recovered:
                        return recovered
            raise AssistantLLMError("Пустой ответ Gemini")

        contents.append({"role": "model", "parts": parts})
        response_parts = []
        for part in function_calls:
            call = part["functionCall"]
            name = call.get("name", "")
            args = call.get("args") or {}
            result = run_tool(name, args, action_ctx, cfg)
            response_parts.append(
                {
                    "functionResponse": {
                        "name": name,
                        "response": result,
                    }
                }
            )
        contents.append({"role": "user", "parts": response_parts})

    raise AssistantLLMError("Не удалось завершить бронирование")


def _generate_gemini(
    cfg: AssistantSettings,
    api_key: str,
    user_message: str,
    history: list[dict] | None,
    action_ctx: ActionContext | None = None,
) -> str:
    language = getattr(action_ctx, "language", "ru") if action_ctx else "ru"
    system_prompt = _compact_system_prompt(cfg, language=language)
    last_http_error = None

    for model in _gemini_model_chain(cfg):
        try:
            return _call_gemini_with_tools(
                api_key,
                model,
                system_prompt,
                user_message,
                history,
                action_ctx,
                cfg,
            )
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            last_http_error = exc
            if exc.code in (404, 429):
                logger.warning("Gemini model %s failed (%s), trying next", model, exc.code)
                continue
            logger.error("LLM HTTP %s: %s", exc.code, body[:500])
            raise AssistantLLMError(_friendly_http_error(exc.code, body, cfg)) from exc

    if last_http_error:
        body = ""
        raise AssistantLLMError(
            _friendly_http_error(last_http_error.code, body, cfg)
        ) from last_http_error
    raise AssistantLLMError("Не удалось вызвать Gemini API")


def generate_reply(
    cfg: AssistantSettings,
    user_message: str,
    history: list[dict] | None = None,
    action_ctx: ActionContext | None = None,
) -> str:
    api_key = _resolve_api_key(cfg)
    if not api_key:
        if cfg.ai_provider == AssistantSettings.AIProvider.GEMINI:
            raise AssistantLLMError(
                "Не настроен Gemini API key. Укажите ключ на странице настроек ассистента "
                "или в ASSISTANT_GEMINI_API_KEY."
            )
        raise AssistantLLMError(
            "Не настроен API-ключ ИИ. Укажите ключ на странице настроек ассистента."
        )

    try:
        if cfg.ai_provider == AssistantSettings.AIProvider.GEMINI:
            return _generate_gemini(
                cfg, api_key, user_message, history, action_ctx
            )
        return _generate_openai_compatible(
            cfg, api_key, user_message, history, action_ctx
        )
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        logger.error("LLM HTTP %s: %s", exc.code, body[:500])
        raise AssistantLLMError(_friendly_http_error(exc.code, body, cfg)) from exc
    except urllib.error.URLError as exc:
        raise AssistantLLMError("Не удалось связаться с ИИ API") from exc
    except (KeyError, IndexError, TypeError) as exc:
        logger.error("LLM parse error")
        raise AssistantLLMError("Некорректный ответ ИИ") from exc
