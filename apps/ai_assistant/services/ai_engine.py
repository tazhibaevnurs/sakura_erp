import json
import logging

from django.conf import settings
from openai import OpenAI

from ..models import AssistantConfig, Conversation
from .context_builder import ContextBuilder
from .prompts import build_system_prompt

logger = logging.getLogger("apps.ai_assistant")

GEMINI_FALLBACK_MODELS = (
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash-lite",
)


class AIEngineError(Exception):
    pass


class AIEngine:
    def __init__(self):
        cfg = getattr(settings, "AI_ASSISTANT", {})
        self.provider = (cfg.get("PROVIDER") or "gemini").lower()
        self.max_tokens = cfg.get("MAX_TOKENS", 500)
        self.temperature = cfg.get("TEMPERATURE", 0.7)
        self.context_builder = ContextBuilder()
        self.config = AssistantConfig.load()

        if self.provider == "openai":
            api_key = cfg.get("OPENAI_API_KEY", "")
            if not api_key:
                raise AIEngineError("OPENAI_API_KEY не настроен.")
            base_url = cfg.get("OPENAI_BASE_URL", "") or None
            if not base_url and api_key.startswith("sk-or-"):
                base_url = "https://openrouter.ai/api/v1"
                logger.info("OpenRouter key detected — using %s", base_url)
            default_headers = {}
            if base_url and "openrouter.ai" in base_url:
                referer = cfg.get("OPENROUTER_HTTP_REFERER") or "https://sakura.local"
                default_headers = {
                    "HTTP-Referer": referer,
                    "X-Title": "Sakura ERP",
                }
            self.client = OpenAI(
                api_key=api_key,
                base_url=base_url,
                default_headers=default_headers or None,
            )
            default_model = (
                "openai/gpt-4o-mini"
                if base_url and "openrouter.ai" in base_url
                else "gpt-4o-mini"
            )
            self.model = cfg.get("MODEL") or default_model
            if base_url and "openrouter.ai" in base_url and self.model.startswith("gemini"):
                logger.warning(
                    "AI_MODEL=%s не подходит для OpenRouter, используем openai/gpt-4o-mini",
                    self.model,
                )
                self.model = "openai/gpt-4o-mini"
        else:
            api_key = cfg.get("GEMINI_API_KEY", "")
            if not api_key:
                raise AIEngineError("GEMINI_API_KEY не настроен.")
            from google import genai

            self.gemini_client = genai.Client(api_key=api_key)
            self.model = cfg.get("MODEL", "gemini-2.5-flash")

    def get_response(self, conversation: Conversation, user_message: str) -> dict:
        if not self.config.is_enabled:
            phone = self.config.restaurant_phone or settings.AI_ASSISTANT.get("FALLBACK_PHONE", "")
            return {
                "reply": f"Ассистент временно недоступен. Позвоните нам: {phone}",
                "intent": "other",
                "extracted_data": {},
                "action_required": None,
                "tokens_used": 0,
            }

        business_context = self.context_builder.build_business_context()
        client_context = self.context_builder.build_client_context(conversation.client)
        history = self.context_builder.get_history_messages(conversation)

        from .language import (
            ensure_conversation_language,
            language_instruction,
            resolve_conversation_language,
        )

        lang = resolve_conversation_language(conversation, user_message)
        lang = ensure_conversation_language(conversation, lang)
        system_prompt = build_system_prompt(
            restaurant_name=self.config.restaurant_name,
            custom_instructions=self.config.custom_system_prompt,
            business_context=business_context,
            client_context=client_context,
            draft_data=json.dumps(conversation.draft_data or {}, ensure_ascii=False),
        )
        system_prompt = f"{system_prompt}\n\n{language_instruction(lang)}"

        try:
            if self.provider == "openai":
                raw, tokens_used = self._call_openai(system_prompt, history, user_message)
            else:
                raw, tokens_used = self._call_gemini(system_prompt, history, user_message)
        except AIEngineError:
            raise
        except Exception as exc:
            logger.exception("AI API error (%s)", self.provider)
            raise AIEngineError(str(exc)) from exc

        try:
            data = self._parse_json(raw)
        except json.JSONDecodeError as exc:
            raise AIEngineError("Некорректный JSON от модели.") from exc

        return {
            "reply": data.get("reply", "Извините, не понял. Можете переформулировать?"),
            "intent": data.get("intent", "other"),
            "extracted_data": data.get("extracted_data") or {},
            "action_required": None,
            "tokens_used": tokens_used,
        }

    @staticmethod
    def _parse_json(raw: str) -> dict:
        text = (raw or "").strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
            if "```" in text:
                text = text.rsplit("```", 1)[0]
        return json.loads(text.strip())

    def _call_openai(self, system_prompt: str, history: list, user_message: str) -> tuple[str, int]:
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content or "{}"
        tokens_used = response.usage.total_tokens if response.usage else 0
        return raw, tokens_used

    def _gemini_models_to_try(self) -> list[str]:
        models = [self.model]
        for model in GEMINI_FALLBACK_MODELS:
            if model not in models:
                models.append(model)
        return models

    @staticmethod
    def _is_retryable_gemini_error(exc: Exception) -> bool:
        message = str(exc).lower()
        return any(
            token in message
            for token in ("429", "503", "resource_exhausted", "unavailable", "quota")
        )

    def _call_gemini(self, system_prompt: str, history: list, user_message: str) -> tuple[str, int]:
        last_exc: Exception | None = None
        for model in self._gemini_models_to_try():
            try:
                return self._call_gemini_model(
                    model, system_prompt, history, user_message
                )
            except Exception as exc:
                if self._is_retryable_gemini_error(exc):
                    logger.warning("Gemini model %s unavailable: %s", model, exc)
                    last_exc = exc
                    continue
                logger.exception("AI API error (gemini, model=%s)", model)
                raise AIEngineError(str(exc)) from exc

        raise AIEngineError(str(last_exc or "Gemini недоступен."))

    def _call_gemini_model(
        self,
        model: str,
        system_prompt: str,
        history: list,
        user_message: str,
    ) -> tuple[str, int]:
        from google.genai import types

        contents = []
        for msg in history:
            role = "model" if msg["role"] == "assistant" else "user"
            contents.append(
                types.Content(role=role, parts=[types.Part(text=msg["content"])])
            )
        contents.append(types.Content(role="user", parts=[types.Part(text=user_message)]))

        response = self.gemini_client.models.generate_content(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=self.temperature,
                max_output_tokens=self.max_tokens,
                response_mime_type="application/json",
            ),
        )
        raw = (response.text or "").strip() or "{}"
        tokens_used = 0
        usage = getattr(response, "usage_metadata", None)
        if usage:
            tokens_used = (usage.prompt_token_count or 0) + (usage.candidates_token_count or 0)
        return raw, tokens_used
