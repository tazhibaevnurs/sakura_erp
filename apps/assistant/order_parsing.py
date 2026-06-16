"""Разбор заказов гостя без LLM."""

from __future__ import annotations



import re

from dataclasses import dataclass, field



from apps.menu.models import MenuItem

from apps.orders.services import find_menu_item



ORDER_INTENT_WORDS = (

    "заказ",

    "закаж",

    "хочу",

    "привез",

    "доставк",

    "навынос",

    "с собой",

    "оформ",

    "заказ кыл",

    "заказ бер",

    "кылайын",

    "берейин",

    "порция",

    "порци",

)



DELIVERY_WORDS = ("доставк", "привез", "курьер", "по адресу", "жеткир")

TAKEAWAY_WORDS = ("навынос", "с собой", "забрать", "самовывоз", "өзүм", "алып кет")

DINE_IN_WORDS = ("кабин", "в зале", "зале", "стол", "ішим")





@dataclass

class ParsedOrderLine:

    name: str

    quantity: int = 1





@dataclass

class OrderRequest:

    order_type: str

    items: list[ParsedOrderLine] = field(default_factory=list)

    customer_name: str = ""

    customer_phone: str = ""

    delivery_address: str = ""

    table_number: int | None = None

    comment: str = ""





def _parse_phone(text: str) -> str:

    match = re.search(r"(\+?\d[\d\s\-()]{8,}\d)", text)

    return match.group(1).strip() if match else ""





def _parse_guest_name(text: str) -> str:

    match = re.search(

        r"(?:,\s*|^|\s)([А-ЯЁа-яA-Za-z][А-ЯЁа-яA-Za-z\s\-]{0,40}?)\s*,\s*\+?\d",

        text,

    )

    if match:

        return match.group(1).strip()

    match = re.search(

        r"(?:имя|зовут|я|атым|менин атым)\s+([А-ЯЁа-яA-Za-z][А-ЯЁа-яA-Za-z\s\-]{1,30})",

        text,

        re.IGNORECASE,

    )

    if match:

        return match.group(1).strip()

    return ""





def _parse_address(text: str) -> str:

    patterns = (

        r"(?:адрес|ул\.?|улиц[аеу]|доставк[аи]\s+(?:на|по))\s*[:\-]?\s*([^,\n]+)",

        r"(?:по адресу)\s+([^,\n]+)",

    )

    for pattern in patterns:

        match = re.search(pattern, text, re.IGNORECASE)

        if match:

            return match.group(1).strip()

    return ""





def _parse_table_number(text: str) -> int | None:

    match = re.search(

        r"(?:стол|кабин[а-я]*)\s*(?:№|#)?\s*(\d{1,3})",

        text.lower(),

    )

    return int(match.group(1)) if match else None





def _detect_order_type(text: str) -> str:

    lowered = text.lower()

    if any(word in lowered for word in DELIVERY_WORDS):

        return "delivery"

    if any(word in lowered for word in TAKEAWAY_WORDS):

        return "takeaway"

    if any(word in lowered for word in DINE_IN_WORDS) or _parse_table_number(text):

        return "dine_in"

    return ""





def _menu_item_names() -> list[str]:

    return list(

        MenuItem.objects.filter(is_available=True)

        .order_by("-name")

        .values_list("name", flat=True)

    )





def _names_match(query: str, item_name: str) -> bool:

    q, n = query.lower(), item_name.lower()

    if q == n or q in n or n in q:

        return True

    stem_len = min(len(q), len(n), max(4, min(len(q), len(n)) - 1))

    return stem_len >= 3 and q[:stem_len] == n[:stem_len]





def _merge_items(items: list[ParsedOrderLine]) -> list[ParsedOrderLine]:

    merged: dict[str, int] = {}

    for item in items:

        merged[item.name] = merged.get(item.name, 0) + item.quantity

    return [ParsedOrderLine(name=k, quantity=v) for k, v in merged.items()]





def _extract_items_from_part(part: str) -> list[ParsedOrderLine]:

    lowered = part.lower().strip()

    found: list[ParsedOrderLine] = []

    used_spans: list[tuple[int, int]] = []



    for name in _menu_item_names():

        name_lower = name.lower()

        patterns = (

            rf"(\d+)\s*(?:х|x|шт\.?)?\s*{re.escape(name_lower)}",

            rf"(\d+)\s*порци\w*\s*{re.escape(name_lower)}",

            rf"{re.escape(name_lower)}\s+(\d+)\s*порци\w*",

            rf"{re.escape(name_lower)}\s*(\d+)",

            re.escape(name_lower),

        )

        for pattern in patterns:

            for match in re.finditer(pattern, lowered):

                start, end = match.span()

                if any(start < u_end and end > u_start for u_start, u_end in used_spans):

                    continue

                qty = 1

                if match.lastindex and match.group(1) and str(match.group(1)).isdigit():

                    qty = int(match.group(1))

                found.append(ParsedOrderLine(name=name, quantity=max(1, qty)))

                used_spans.append((start, end))

                break



    for match in re.finditer(

        r"(\d+)\s*(?:шт\.?|порци\w*|х|x)\s*([а-яёa-z\-]+)",

        lowered,

    ):

        start, end = match.span()

        if any(start < u_end and end > u_start for u_start, u_end in used_spans):

            continue

        qty = int(match.group(1))

        word = match.group(2)

        item = find_menu_item(word)

        if item is None:

            for name in _menu_item_names():

                if _names_match(word, name):

                    item = find_menu_item(name)

                    break

        if item is None:

            continue

        found.append(ParsedOrderLine(name=item.name, quantity=max(1, qty)))

        used_spans.append((start, end))



    for match in re.finditer(r"(\d+)\s+([а-яёa-z\-]+)", lowered):

        start, end = match.span()

        if any(start < u_end and end > u_start for u_start, u_end in used_spans):

            continue

        qty = int(match.group(1))

        word = match.group(2)

        if word in {"порция", "порций", "порции", "шт", "штук"}:

            continue

        item = find_menu_item(word)

        if item is None:

            for name in _menu_item_names():

                if _names_match(word, name):

                    item = find_menu_item(name)

                    break

        if item is None:

            continue

        found.append(ParsedOrderLine(name=item.name, quantity=max(1, qty)))

        used_spans.append((start, end))



    return found





def _extract_items(text: str) -> list[ParsedOrderLine]:

    parts = re.split(r"\s+и\s+|\s*,\s*", text.lower())

    found: list[ParsedOrderLine] = []

    for part in parts:

        found.extend(_extract_items_from_part(part))

    return _merge_items(found)





def _looks_like_order_intent(text: str) -> bool:
    from .menu_items import is_menu_item_availability_question

    if is_menu_item_availability_question(text):
        return False

    lowered = text.lower()
    if any(word in lowered for word in ORDER_INTENT_WORDS):
        return True

    items = _extract_items(text)
    if not items:
        return False

    if any(
        marker in lowered
        for marker in ("барбы", "жокпу", "есть ли", "в меню", "ээлүүбү")
    ):
        return False

    return True





def parse_order_request(text: str) -> OrderRequest | None:

    if not _looks_like_order_intent(text):

        return None

    items = _extract_items(text)

    if not items:

        return None

    return OrderRequest(

        order_type=_detect_order_type(text),

        items=items,

        customer_name=_parse_guest_name(text),

        customer_phone=_parse_phone(text),

        delivery_address=_parse_address(text),

        table_number=_parse_table_number(text),

    )


