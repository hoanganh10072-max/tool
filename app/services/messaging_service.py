import asyncio
import logging

from app.automation.browser import browser_manager
from app.automation.exceptions import ContactNotFoundError, LoginRequiredError, TemporaryAutomationError, UserActionRequiredError
from app.automation.zalo_client import ZaloClient
from app.config import settings
from app.utils.phone import normalize_phone, validate_phone

logger = logging.getLogger(__name__)
automation_lock = asyncio.Lock()


class ValidationError(ValueError):
    pass


class AutomationBusyError(RuntimeError):
    pass


class MessagingService:
    def __init__(self, client: ZaloClient | None = None) -> None:
        self.client = client or ZaloClient()

    async def open_zalo(self) -> dict:
        return await self.client.open_zalo()

    async def zalo_status(self) -> dict:
        alive = await browser_manager.is_browser_alive()
        if not alive:
            return {"browser": False, "zalo_login": False, "status": "BROWSER_DISCONNECTED", "profile": None}
        status = await self.client.check_login(navigate_if_needed=False)
        return {
            "browser": True,
            "zalo_login": status.get("logged_in", False),
            "status": status["status"],
            "profile": status.get("profile"),
        }

    async def search_contact(self, phone: str) -> dict:
        normalized = self._validate_phone(phone)
        if automation_lock.locked():
            raise AutomationBusyError("Automation is busy. Wait for the current action to finish.")
        async with automation_lock:
            return await self.search_contact_unlocked(normalized)

    async def send_single(self, phone: str, message: str) -> dict:
        normalized = self._validate_phone(phone)
        clean_message = self._validate_message(message)
        if automation_lock.locked():
            raise AutomationBusyError("Automation is busy. Wait for the current action to finish.")
        async with automation_lock:
            return await self.send_single_unlocked(normalized, clean_message)

    async def search_contact_unlocked(self, phone: str) -> dict:
        if settings.dry_run:
            await asyncio.sleep(settings.dry_run_delay)
            return {"success": True, "phone": phone, "found": True, "name": "Dry Run Contact", "status": "FOUND"}
        return await self.client.search_phone(phone)

    async def send_single_unlocked(self, phone: str, message: str, image_paths: list[str] | None = None) -> dict:
        if settings.dry_run:
            await asyncio.sleep(settings.dry_run_delay)
            if phone.endswith("000"):
                raise ContactNotFoundError(f"Dry-run contact not found for {phone}")
            return {"success": True, "phone": phone, "status": "SENT"}
        return await self.client.send_message(phone, message, image_paths=image_paths or [])

    def _validate_phone(self, phone: str) -> str:
        normalized = normalize_phone(phone)
        if not validate_phone(normalized):
            raise ValidationError("Invalid Vietnamese mobile phone number")
        return normalized

    def _validate_message(self, message: str) -> str:
        text = message.strip()
        if not text:
            raise ValidationError("Message cannot be empty")
        if len(text) > 4000:
            raise ValidationError("Message is too long")
        return text


messaging_service = MessagingService()
