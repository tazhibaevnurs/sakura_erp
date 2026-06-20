"""Извлечение даты, времени и кабинки из текста клиента (рус/кырг)."""
from __future__ import annotations

import re
from datetime import datetime

MONTHS_RU = {
    "январ": 1, "феврал": 2, "март": 3, "апрел": 4, "май": 5, "мая": 5,
    "июн": 6, "июл": 7, "август": 8, "сентябр": 9, "октябр": 10, "ноябр": 11, "декабр": 12,
}


def extract_booking_hints(text: str) -> dict:
    text = (text or "").strip()
    if not text:
        return {}

    hints: dict = {}
    lower = text.lower()

    m = re.search(r"(?:кабин(?:к|у|а|ы)?|стол(?:а|ик)?|№|#)\s*(\d{1,2})", lower)
    if not m:
        m = re.search(r"(\d{1,2})\s*(?:кабин|стол|№)", lower)
    if m:
        hints["table_number"] = int(m.group(1))

    tm = re.search(r"(\d{1,2})[:.](\d{2})", text)
    if tm:
        h, mi = int(tm.group(1)), int(tm.group(2))
        if 0 <= h <= 23 and 0 <= mi <= 59:
            hints["time"] = f"{h:02d}:{mi:02d}"
    elif re.search(r"(?:на|в|saat|убак)\s*(\d{1,2})\s*(?:[:.]00|час|saat)?", lower):
        tm2 = re.search(r"(?:на|в)\s*(\d{1,2})(?:[:.]00)?", lower)
        if tm2:
            h = int(tm2.group(1))
            if 0 <= h <= 23:
                hints["time"] = f"{h:02d}:00"

    dm = re.search(r"(\d{1,2})[./](\d{1,2})(?:[./](\d{2,4}))?", text)
    if dm:
        day, month = int(dm.group(1)), int(dm.group(2))
        year = int(dm.group(3)) if dm.group(3) else datetime.now().year
        if year < 100:
            year += 2000
        if 1 <= month <= 12 and 1 <= day <= 31:
            hints["date"] = f"{day:02d}.{month:02d}.{year}"
    else:
        for stem, month in MONTHS_RU.items():
            if stem in lower:
                dm2 = re.search(rf"(\d{{1,2}})\s*{stem}", lower)
                if dm2:
                    day = int(dm2.group(1))
                    year = datetime.now().year
                    hints["date"] = f"{day:02d}.{month:02d}.{year}"
                break

    gm = re.search(r"(\d{1,2})\s*(?:гост|челов|konok|адам|киши)", lower)
    if gm:
        hints["guests"] = int(gm.group(1))

    return hints
