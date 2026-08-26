from datetime import datetime


def utc_now() -> datetime:
    return datetime.utcnow()


def clamp_text(value: str, max_len: int = 500) -> str:
    text = value.strip()
    return text if len(text) <= max_len else text[:max_len]
