import logging
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from app.config import settings
from app.automation.exceptions import BrowserDisconnectedError

logger = logging.getLogger("automation.browser")


class BrowserManager:
    def __init__(self, profile_dir: Path | None = None) -> None:
        self.profile_dir = profile_dir or settings.browser_profile_dir
        self._playwright: Any = None
        self._context: Any = None
        self._page: Any = None

    async def start_browser(self) -> Any:
        if await self.is_browser_alive():
            return self._page
        from playwright.async_api import async_playwright

        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self._playwright = await async_playwright().start()
        timeout_ms = settings.page_timeout * 1000
        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.profile_dir),
            headless=settings.browser_headless,
            viewport={"width": 1366, "height": 850},
            timeout=timeout_ms,
        )
        await self._grant_runtime_permissions()
        self._context.set_default_timeout(settings.element_timeout * 1000)
        self._context.set_default_navigation_timeout(timeout_ms)
        self._page = self._context.pages[0] if self._context.pages else await self._context.new_page()
        logger.info("Persistent Chromium started at %s", self.profile_dir)
        return self._page

    async def _grant_runtime_permissions(self) -> None:
        if not self._context:
            return
        try:
            parsed = urlparse(settings.zalo_web_url)
            origin = f"{parsed.scheme}://{parsed.netloc}"
            await self._context.grant_permissions(["clipboard-read", "clipboard-write"], origin=origin)
        except Exception as exc:
            logger.debug("Could not grant browser clipboard permissions: %s", exc)

    async def get_page(self) -> Any:
        if not await self.is_browser_alive():
            return await self.start_browser()
        return self._page

    async def is_browser_alive(self) -> bool:
        if not self._page or self._page.is_closed():
            return False
        try:
            await self._page.evaluate("() => true")
            return True
        except Exception:
            return False

    async def restart_browser(self) -> Any:
        await self.close_browser()
        return await self.start_browser()

    async def close_browser(self) -> None:
        if self._context:
            try:
                await self._context.close()
            except Exception as exc:
                logger.debug("Ignoring browser context close error: %s", exc)
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception as exc:
                logger.debug("Ignoring Playwright stop error: %s", exc)
        self._context = None
        self._page = None
        self._playwright = None

    async def require_page(self) -> Any:
        page = await self.get_page()
        if not page or page.is_closed():
            raise BrowserDisconnectedError("Browser is disconnected")
        return page


browser_manager = BrowserManager()
