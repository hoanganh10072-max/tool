import logging
from logging.handlers import RotatingFileHandler

from app.config import settings


def configure_logging() -> None:
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")

    app_handler = RotatingFileHandler(settings.logs_dir / "app.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    app_handler.setFormatter(formatter)

    automation_handler = RotatingFileHandler(
        settings.logs_dir / "automation.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    automation_handler.setFormatter(formatter)
    automation_handler.addFilter(lambda record: record.name.startswith("automation"))

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if not any(isinstance(handler, RotatingFileHandler) for handler in root.handlers):
        root.addHandler(app_handler)
        root.addHandler(automation_handler)
