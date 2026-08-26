import math
import re
import unicodedata
from typing import Any


VN_MOBILE_RE = re.compile(r"^0(3|5|7|8|9)\d{8}$")


def normalize_phone(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        if math.isnan(value):
            return ""
        if value.is_integer():
            value = int(value)
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"\.0$", "", text)
    text = re.sub(r"[^\d+]", "", text)
    if text.startswith("+84"):
        text = "0" + text[3:]
    elif text.startswith("84") and len(text) in {11, 12}:
        text = "0" + text[2:]
    elif len(text) == 9 and text[0] in "35789":
        text = "0" + text
    return text


def validate_phone(value: Any) -> bool:
    return bool(VN_MOBILE_RE.match(normalize_phone(value)))
