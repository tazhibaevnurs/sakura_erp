"""Форматирование ответов ассистента для разных каналов."""
import re

from .models import AssistantSettings


def _strip_markdown_for_plain(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    return text


def _markdown_to_telegram_html(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    return text


def apply_reply_format(text: str, cfg: AssistantSettings) -> str:
    text = (text or "").strip()
    if not text:
        return text

    if not cfg.use_emoji:
        text = re.sub(
            r"[\U0001F300-\U0001FAFF\U00002700-\U000027BF\U00002600-\U000026FF]+",
            "",
            text,
        ).strip()

    if cfg.reply_format == AssistantSettings.ReplyFormat.MARKDOWN:
        return text
    if cfg.reply_format == AssistantSettings.ReplyFormat.TELEGRAM_HTML:
        return _markdown_to_telegram_html(text)
    return _strip_markdown_for_plain(text)


def split_message(text: str, limit: int = 4000) -> list[str]:
    text = text.strip()
    if len(text) <= limit:
        return [text]
    parts = []
    while text:
        if len(text) <= limit:
            parts.append(text)
            break
        cut = text.rfind("\n", 0, limit)
        if cut < limit // 2:
            cut = limit
        parts.append(text[:cut].strip())
        text = text[cut:].strip()
    return [p for p in parts if p]
