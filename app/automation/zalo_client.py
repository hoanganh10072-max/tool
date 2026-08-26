import logging
import base64
import mimetypes
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from app.automation.browser import BrowserManager, browser_manager
from app.automation import selectors
from app.automation.exceptions import (
    BrowserDisconnectedError,
    ContactNotFoundError,
    ElementNotFoundError,
    LoginRequiredError,
    TemporaryAutomationError,
    UserActionRequiredError,
    ZaloAutomationError,
)
from app.config import settings

logger = logging.getLogger("automation.zalo")

ADD_FRIEND_RESULT_TIMEOUT_MS = 4500


class ZaloClient:
    def __init__(self, manager: BrowserManager | None = None) -> None:
        self.manager = manager or browser_manager

    async def open_zalo(self) -> dict:
        await self._goto_zalo_with_recovery()
        return await self.check_login(navigate_if_needed=False)

    async def check_login(self, navigate_if_needed: bool = False) -> dict:
        page = await self.manager.get_page()
        if navigate_if_needed and not self._is_zalo_url(page.url):
            page = await self._goto_zalo_with_recovery()
        for attempt in range(5):
            if await self._looks_logged_in():
                return {"status": "LOGGED_IN", "logged_in": True, "profile": await self._read_profile()}
            if await self._any_visible(selectors.CONVERSATION_PANE + selectors.SEARCH_INPUTS, timeout=1500):
                return {"status": "LOGGED_IN", "logged_in": True, "profile": await self._read_profile()}
            if await self._any_visible(selectors.LOGIN_INDICATORS, timeout=900):
                return {"status": "LOGIN_REQUIRED", "logged_in": False}
            if await self._any_visible(selectors.USER_ACTION_INDICATORS, timeout=700):
                return {"status": "USER_ACTION_REQUIRED", "logged_in": False}
            if attempt < 4:
                await page.wait_for_timeout(1000)
        return {"status": "UNKNOWN", "logged_in": False}

    def _is_zalo_url(self, url: str) -> bool:
        try:
            current_host = urlparse(url).netloc.lower()
            target_host = urlparse(settings.zalo_web_url).netloc.lower()
            return (
                current_host == target_host
                or current_host.endswith(f".{target_host}")
                or current_host == "zalo.me"
                or current_host.endswith(".zalo.me")
            )
        except Exception:
            return False

    async def _goto_zalo_with_recovery(self):
        for attempt in range(2):
            page = await self.manager.get_page()
            try:
                await page.goto(settings.zalo_web_url, wait_until="domcontentloaded")
                return page
            except PlaywrightError as exc:
                if not self._is_browser_closed_error(exc):
                    raise TemporaryAutomationError(f"Không mở được Zalo Web: {exc}") from exc
                logger.warning("Browser closed while opening Zalo, attempt=%s", attempt + 1)
                await self.manager.restart_browser()
        raise BrowserDisconnectedError(
            "Trình duyệt automation đã bị đóng hoặc bị crash khi mở Zalo. Bấm Mở Zalo để thử lại."
        )

    def _is_browser_closed_error(self, exc: Exception) -> bool:
        message = str(exc).lower()
        return "target page, context or browser has been closed" in message or "browser has been closed" in message

    async def search_phone(self, phone: str) -> dict:
        await self._ensure_logged_in()
        await self._open_add_friend_dialog()

        page = await self.manager.get_page()
        phone_input = await self._focus_add_friend_phone_input()
        await self._replace_text(phone_input, phone)
        logger.info("PHONE=%s entered into Zalo add-friend phone field", phone)
        await page.wait_for_timeout(350)
        await self._click_add_friend_search_button()
        await page.wait_for_timeout(600)

        result = await self._wait_for_add_friend_search_outcome(phone)
        logger.info("PHONE=%s search status=%s", phone, result["status"])
        return result

    async def _ensure_logged_in(self) -> dict:
        login = await self.check_login(navigate_if_needed=True)
        status = login.get("status")
        if login.get("logged_in"):
            logger.info("Zalo login check passed")
            return login
        if status == "USER_ACTION_REQUIRED":
            raise UserActionRequiredError("Zalo đang yêu cầu xác minh thủ công trong trình duyệt.")
        if status == "LOGIN_REQUIRED":
            raise LoginRequiredError("Bạn cần đăng nhập Zalo Web trước khi chạy tự động.")
        raise LoginRequiredError("Chưa xác nhận được trạng thái đăng nhập Zalo Web. Bấm Mở Zalo và đăng nhập lại.")

    async def _open_add_friend_dialog(self) -> None:
        page = await self.manager.get_page()
        if await self._any_visible(selectors.ADD_FRIEND_DIALOGS, timeout=600):
            logger.info("Zalo add-friend dialog is already open")
            return

        button = await self._first_locator(selectors.ADD_FRIEND_BUTTONS, timeout=1800)
        if button:
            await button.click()
        elif not await self._click_add_friend_button_by_dom():
            raise ElementNotFoundError("Không tìm thấy nút Thêm bạn trên Zalo Web")

        await page.wait_for_timeout(500)
        if not await self._any_visible(selectors.ADD_FRIEND_DIALOGS, timeout=4500):
            raise ElementNotFoundError("Đã bấm Thêm bạn nhưng chưa thấy hộp Thêm bạn")
        logger.info("Zalo add-friend dialog opened")

    async def _focus_add_friend_phone_input(self):
        await self._open_add_friend_dialog()
        page = await self.manager.get_page()
        phone_input = await self._first_locator(selectors.ADD_FRIEND_PHONE_INPUTS, timeout=2500)
        if phone_input:
            await phone_input.click()
            await page.wait_for_timeout(150)
            return phone_input

        handle = await self._find_add_friend_phone_input_by_dom()
        if not handle:
            raise ElementNotFoundError("Không tìm thấy ô Số điện thoại trong hộp Thêm bạn")
        locator = handle.as_element()
        if not locator:
            raise ElementNotFoundError("Không thể chọn ô Số điện thoại trong hộp Thêm bạn")
        await locator.click()
        await page.wait_for_timeout(150)
        return locator

    async def _find_add_friend_phone_input_by_dom(self):
        page = await self.manager.get_page()
        try:
            return await page.evaluate_handle(
                """() => {
                    const visible = (el) => {
                        if (!el) return false;
                        const rect = el.getBoundingClientRect();
                        const style = window.getComputedStyle(el);
                        return rect.width >= 80 && rect.height >= 20 &&
                            style.visibility !== "hidden" && style.display !== "none" &&
                            style.opacity !== "0";
                    };
                    const clean = (value) => String(value || "").replace(/\\s+/g, " ").trim().toLowerCase();
                    const dialogs = Array.from(document.querySelectorAll("[id^='zl-modal'], [role='dialog'], [class*='modal' i], [class*='dialog' i], [class*='popup' i]"))
                        .filter(visible)
                        .filter((el) => {
                            const text = clean(el.innerText);
                            return text.includes("thêm bạn") || text.includes("số điện thoại");
                        });
                    for (const dialog of dialogs) {
                        const inputs = Array.from(dialog.querySelectorAll("input, [contenteditable='true']"))
                            .filter(visible)
                            .map((el) => {
                                const label = clean([
                                    el.getAttribute("placeholder"),
                                    el.getAttribute("aria-label"),
                                    el.getAttribute("title"),
                                    el.getAttribute("type"),
                                    el.getAttribute("inputmode"),
                                    el.getAttribute("autocomplete"),
                                    el.className,
                                    el.id
                                ].join(" "));
                                const rect = el.getBoundingClientRect();
                                let score = 0;
                                if (label.includes("số điện thoại")) score += 20;
                                if (label.includes("phone") || label.includes("tel")) score += 14;
                                if (rect.width >= 160) score += 3;
                                if (rect.top < 420) score += 2;
                                return { el, score };
                            })
                            .filter((item) => item.score >= 8)
                            .sort((a, b) => b.score - a.score);
                        if (inputs.length) return inputs[0].el;
                    }
                    return null;
                }"""
            )
        except Exception:
            logger.debug("Could not find Zalo add-friend phone input by DOM", exc_info=True)
            return None

    async def _click_add_friend_search_button(self) -> None:
        page = await self.manager.get_page()
        for _ in range(5):
            if await self._click_add_friend_search_button_by_dom():
                logger.info("Zalo add-friend footer search button clicked by DOM")
                return
            button = await self._first_enabled_locator(selectors.ADD_FRIEND_SEARCH_BUTTONS, timeout=700)
            if button:
                await button.click()
                logger.info("Zalo add-friend search button clicked")
                return
            await page.wait_for_timeout(400)
        raise ElementNotFoundError("Không tìm thấy hoặc chưa bấm được nút Tìm kiếm trong hộp Thêm bạn")

    async def _click_add_friend_search_button_by_dom(self) -> bool:
        page = await self.manager.get_page()
        try:
            return bool(
                await page.evaluate(
                    """() => {
                        const visible = (el) => {
                            if (!el) return false;
                            const rect = el.getBoundingClientRect();
                            const style = window.getComputedStyle(el);
                            return rect.width >= 40 && rect.height >= 24 &&
                                style.visibility !== "hidden" && style.display !== "none" &&
                                style.opacity !== "0";
                        };
                        const disabled = (el) =>
                            el.disabled ||
                            el.getAttribute("aria-disabled") === "true" ||
                            el.className?.toString().toLowerCase().includes("disabled");
                        const clean = (value) => String(value || "").replace(/\\s+/g, " ").trim().toLowerCase();
                        const dialogs = Array.from(document.querySelectorAll("[id^='zl-modal'], [role='dialog'], [class*='modal' i], [class*='dialog' i], [class*='popup' i]"))
                            .filter(visible)
                            .filter((el) => {
                                const text = clean(el.innerText);
                                return text.includes("thêm bạn") || text.includes("số điện thoại");
                            });
                        for (const dialog of dialogs) {
                            const dialogRect = dialog.getBoundingClientRect();
                            const translatedSearchLabels = Array.from(dialog.querySelectorAll(
                                "div.truncate[data-translate-inner='STR_SEARCH'], [data-translate-inner='STR_SEARCH']"
                            ))
                                .filter((el) => {
                                    const text = clean(el.innerText || el.textContent);
                                    const rect = el.getBoundingClientRect();
                                    return visible(el) &&
                                        (text === "tìm kiếm" || text === "search") &&
                                        rect.top > dialogRect.top + dialogRect.height * 0.68 &&
                                        rect.right > dialogRect.right - 180;
                                })
                                .map((el) => {
                                    const clickable = el.closest("button, [role='button'], [tabindex], [data-id], .btn, .z--btn") || el.parentElement || el;
                                    const rect = clickable.getBoundingClientRect();
                                    let score = 50;
                                    if (rect.right > dialogRect.right - 150) score += 16;
                                    if (rect.bottom > dialogRect.bottom - 90) score += 12;
                                    if (rect.width >= 80) score += 5;
                                    return { el: clickable, score };
                                })
                                .filter((item) => visible(item.el) && !disabled(item.el))
                                .sort((a, b) => b.score - a.score);
                            if (translatedSearchLabels.length) {
                                translatedSearchLabels[0].el.click();
                                return true;
                            }

                            const buttons = Array.from(dialog.querySelectorAll("button, [role='button']"))
                                .filter((el) => {
                                    const tag = el.tagName.toLowerCase();
                                    return tag !== "input" && tag !== "textarea" && visible(el) && !disabled(el);
                                })
                                .map((el) => {
                                    const rect = el.getBoundingClientRect();
                                    const label = clean([
                                        el.innerText,
                                        el.getAttribute("aria-label"),
                                        el.getAttribute("title"),
                                        el.getAttribute("data-id")
                                    ].join(" "));
                                    let score = 0;
                                    if (label === "tìm kiếm" || label === "search") score += 40;
                                    else if (label.includes("tìm kiếm") || label.includes("search")) score += 20;
                                    if (label.includes("btn_search") || label.includes("searchbutton")) score += 12;
                                    if (clean(el.closest("[id^='zl-modal'], [role='dialog'], [class*='modal' i], [class*='dialog' i], [class*='popup' i]")?.innerText).includes("thêm bạn")) score += 8;
                                    if (rect.top > dialogRect.top + dialogRect.height * 0.72) score += 16;
                                    if (rect.right > dialogRect.right - 150) score += 12;
                                    if (rect.bottom > dialogRect.bottom - 80) score += 10;
                                    if (rect.width >= 80) score += 3;
                                    return { el, score };
                                })
                                .filter((item) => item.score >= 40)
                                .sort((a, b) => b.score - a.score);
                            if (buttons.length) {
                                buttons[0].el.click();
                                return true;
                            }
                        }
                        return false;
                    }"""
                )
            )
        except Exception:
            logger.debug("Could not click Zalo add-friend search button by DOM", exc_info=True)
            return False

    async def _click_add_friend_button_by_dom(self) -> bool:
        page = await self.manager.get_page()
        try:
            return bool(
                await page.evaluate(
                    """() => {
                        const visible = (el) => {
                            if (!el) return false;
                            const rect = el.getBoundingClientRect();
                            const style = window.getComputedStyle(el);
                            return rect.width >= 18 && rect.height >= 18 &&
                                style.visibility !== "hidden" && style.display !== "none" &&
                                style.opacity !== "0";
                        };
                        const clean = (value) => String(value || "").replace(/\\s+/g, " ").trim().toLowerCase();
                        const candidates = Array.from(document.querySelectorAll(
                            "button, [role='button'], [aria-label], [title], [data-id], [data-tooltip], [data-title]"
                        ))
                            .filter(visible)
                            .map((el) => {
                                const rect = el.getBoundingClientRect();
                                const label = clean([
                                    el.innerText,
                                    el.getAttribute("aria-label"),
                                    el.getAttribute("title"),
                                    el.getAttribute("data-tooltip"),
                                    el.getAttribute("data-title"),
                                    el.getAttribute("data-id"),
                                    el.className
                                ].join(" "));
                                let score = 0;
                                if (/thêm bạn|them ban|add friend/.test(label)) score += 20;
                                if (/addfriend|add_friend|friend_add|friend-add|add-user|adduser|user-add|person-add|contact-add/.test(label)) score += 16;
                                if (/friend|contact|user|person/.test(label) && /add|plus/.test(label)) score += 10;
                                if (rect.top < 220 && rect.left < 380) score += 4;
                                if (rect.width >= 24 && rect.width <= 64 && rect.height >= 24 && rect.height <= 64) score += 3;
                                return { el, score };
                            })
                            .filter((item) => item.score >= 10)
                            .sort((a, b) => b.score - a.score);
                        if (!candidates.length) return false;
                        candidates[0].el.click();
                        return true;
                    }"""
                )
            )
        except Exception:
            logger.debug("Could not click Zalo add-friend button by DOM", exc_info=True)
            return False

    async def open_contact(self, phone: str) -> dict:
        result = await self.search_phone(phone)
        if result["status"] == "NOT_FOUND":
            raise ContactNotFoundError(f"Không tìm thấy kết quả Zalo cho số {phone}")
        if result["status"] != "FOUND":
            raise ContactNotFoundError(f"Không mở được hồ sơ Zalo cho số {phone}")
        return result

    async def send_message(self, phone: str, message: str, image_paths: list[str] | None = None) -> dict:
        clean_message = message.strip()
        clean_image_paths = [str(path) for path in image_paths or [] if path]
        if not clean_message and not clean_image_paths:
            raise ElementNotFoundError("Chưa có nội dung tin nhắn hoặc hình ảnh để gửi")

        result = await self.open_contact(phone)
        await self._open_message_from_profile_if_needed()

        if clean_image_paths:
            await self._send_image_files(clean_image_paths)

        if clean_message:
            message_input = await self._focus_message_input()
            await self._replace_text(message_input, clean_message)
            logger.info("PHONE=%s bulk message entered into Zalo chat input", phone)
            await self._click_send_button_or_press_enter()
            await (await self.manager.get_page()).wait_for_timeout(650)

        await self._prepare_add_friend_for_next_recipient()
        logger.info("PHONE=%s message sent", phone)
        return {"success": True, "phone": phone, "name": result.get("name"), "status": "SENT"}

    async def _click_send_button_or_press_enter(self) -> None:
        send_button = await self._first_locator(selectors.SEND_BUTTONS, timeout=1200)
        if send_button:
            await send_button.click()
        else:
            await self.manager._page.keyboard.press("Enter")

    async def _send_image_files(self, image_paths: list[str]) -> None:
        page = await self.manager.get_page()
        resolved_paths = [str(Path(path).resolve()) for path in image_paths if Path(path).is_file()]
        if not resolved_paths:
            raise ElementNotFoundError("Không tìm thấy file hình ảnh đã chọn")
        try:
            await self._set_image_input_files(resolved_paths)
            logger.info("Queued %s image(s) in Zalo chat input via file input", len(resolved_paths))
            await page.wait_for_timeout(1200)
            await self._click_send_button_or_press_enter()
            await page.wait_for_timeout(800)
            return
        except ElementNotFoundError:
            logger.info("Zalo image file input not found, falling back to clipboard paste")

        await self._paste_and_send_image_files(resolved_paths)

    async def _paste_and_send_image_files(self, image_paths: list[str]) -> None:
        page = await self.manager.get_page()
        for image_path in image_paths:
            await self._focus_message_input()
            await self._write_image_to_browser_clipboard(image_path)
            await page.keyboard.press("Control+V")
            logger.info("Pasted image into Zalo chat input: %s", image_path)
            await page.wait_for_timeout(1800)
            await self._click_send_button_or_press_enter()
            await page.wait_for_timeout(1000)

    async def _write_image_to_browser_clipboard(self, image_path: str) -> None:
        path = Path(image_path)
        mime_type = mimetypes.guess_type(path.name)[0] or "image/png"
        content = base64.b64encode(path.read_bytes()).decode("ascii")
        page = await self.manager.get_page()
        await page.evaluate(
            """async ({ content, mimeType }) => {
                if (!navigator.clipboard || !window.ClipboardItem) {
                    throw new Error("Browser clipboard API is not available");
                }
                const binary = atob(content);
                const bytes = new Uint8Array(binary.length);
                for (let index = 0; index < binary.length; index += 1) {
                    bytes[index] = binary.charCodeAt(index);
                }
                const sourceBlob = new Blob([bytes], { type: mimeType });
                let clipboardBlob = sourceBlob;
                if (mimeType !== "image/png") {
                    clipboardBlob = await new Promise((resolve, reject) => {
                        const image = new Image();
                        image.onload = () => {
                            const canvas = document.createElement("canvas");
                            canvas.width = image.naturalWidth || image.width;
                            canvas.height = image.naturalHeight || image.height;
                            const context = canvas.getContext("2d");
                            context.drawImage(image, 0, 0);
                            canvas.toBlob((blob) => blob ? resolve(blob) : reject(new Error("Cannot convert image")), "image/png");
                        };
                        image.onerror = () => reject(new Error("Cannot load image for clipboard"));
                        image.src = URL.createObjectURL(sourceBlob);
                    });
                }
                await navigator.clipboard.write([
                    new ClipboardItem({ [clipboardBlob.type || "image/png"]: clipboardBlob })
                ]);
            }""",
            {"content": content, "mimeType": mime_type},
        )

    async def _set_image_input_files(self, image_paths: list[str]) -> None:
        page = await self.manager.get_page()
        if await self._try_set_image_input_files(image_paths):
            return
        button = await self._first_locator(selectors.IMAGE_UPLOAD_BUTTONS, timeout=1200)
        if button:
            await button.click()
            await page.wait_for_timeout(500)
            if await self._try_set_image_input_files(image_paths):
                return
        if await self._click_image_upload_button_by_dom():
            await page.wait_for_timeout(500)
            if await self._try_set_image_input_files(image_paths):
                return
        raise ElementNotFoundError("Không tìm thấy nút hoặc ô tải hình ảnh trong Zalo Web")

    async def _try_set_image_input_files(self, image_paths: list[str]) -> bool:
        page = await self.manager.get_page()
        for selector in selectors.IMAGE_FILE_INPUTS:
            inputs = page.locator(selector)
            try:
                count = await inputs.count()
            except Exception:
                continue
            for index in range(count - 1, -1, -1):
                try:
                    await inputs.nth(index).set_input_files(image_paths)
                    return True
                except Exception:
                    logger.debug("Could not set Zalo image file input %s[%s]", selector, index, exc_info=True)
        return False

    async def _click_image_upload_button_by_dom(self) -> bool:
        page = await self.manager.get_page()
        try:
            return bool(
                await page.evaluate(
                    """() => {
                        const visible = (el) => {
                            if (!el) return false;
                            const rect = el.getBoundingClientRect();
                            const style = window.getComputedStyle(el);
                            return rect.width >= 20 && rect.height >= 20 &&
                                style.visibility !== "hidden" && style.display !== "none" &&
                                style.opacity !== "0";
                        };
                        const clean = (value) => String(value || "").replace(/\\s+/g, " ").trim().toLowerCase();
                        const buttons = Array.from(document.querySelectorAll("button, [role='button'], [tabindex], [data-id], [aria-label], [title]"))
                            .filter(visible)
                            .map((el) => {
                                const label = clean([
                                    el.innerText,
                                    el.getAttribute("aria-label"),
                                    el.getAttribute("title"),
                                    el.getAttribute("data-title"),
                                    el.getAttribute("data-tooltip"),
                                    el.getAttribute("data-id"),
                                    el.className
                                ].join(" "));
                                const rect = el.getBoundingClientRect();
                                let score = 0;
                                if (/ảnh|hình|photo|image|picture|media/.test(label)) score += 20;
                                if (/sticker|emoji|gif/.test(label)) score -= 10;
                                if (rect.top > window.innerHeight * 0.55) score += 6;
                                if (rect.left < window.innerWidth * 0.55) score += 2;
                                return { el, score };
                            })
                            .filter((item) => item.score >= 18)
                            .sort((a, b) => b.score - a.score);
                        if (!buttons.length) return false;
                        buttons[0].el.click();
                        return true;
                    }"""
                )
            )
        except Exception:
            logger.debug("Could not click Zalo image upload button by DOM", exc_info=True)
            return False

    async def _prepare_add_friend_for_next_recipient(self) -> None:
        page = await self.manager.get_page()
        await page.wait_for_timeout(900)
        try:
            await self._open_add_friend_dialog()
            logger.info("Zalo add-friend dialog prepared for next recipient")
        except Exception:
            logger.warning("Message was sent, but could not reopen add-friend dialog for next recipient", exc_info=True)

    async def _wait_for_add_friend_search_outcome(self, phone: str) -> dict:
        page = await self.manager.get_page()
        deadline_ms = min(settings.element_timeout * 1000, ADD_FRIEND_RESULT_TIMEOUT_MS)
        elapsed = 0
        try:
            while elapsed < deadline_ms:
                if await self._any_visible(selectors.ADD_FRIEND_NOT_FOUND_INDICATORS, timeout=350):
                    logger.info("PHONE=%s Zalo account not found", phone)
                    return {"success": True, "phone": phone, "found": False, "name": None, "status": "NOT_FOUND"}

                button = await self._first_enabled_locator(selectors.ADD_FRIEND_ACCOUNT_MESSAGE_BUTTONS, timeout=450)
                if button:
                    name = await self._read_contact_name()
                    await self._click_locator_or_clickable_parent(button)
                    await page.wait_for_timeout(800)
                    logger.info("PHONE=%s Zalo account profile found, message button clicked", phone)
                    return {"success": True, "phone": phone, "found": True, "name": name, "status": "FOUND"}

                if await self._click_account_profile_message_button_by_dom():
                    await page.wait_for_timeout(800)
                    name = await self._read_contact_name()
                    logger.info("PHONE=%s Zalo account profile found, message button clicked by DOM", phone)
                    return {"success": True, "phone": phone, "found": True, "name": name, "status": "FOUND"}

                button = await self._first_enabled_locator(selectors.ADD_FRIEND_MESSAGE_BUTTONS, timeout=450)
                if button:
                    name = await self._read_contact_name()
                    await self._click_locator_or_clickable_parent(button)
                    await page.wait_for_timeout(800)
                    logger.info("PHONE=%s Zalo account found, message button clicked", phone)
                    return {"success": True, "phone": phone, "found": True, "name": name, "status": "FOUND"}

                if await self._click_add_friend_message_button_by_dom():
                    await page.wait_for_timeout(800)
                    name = await self._read_contact_name()
                    logger.info("PHONE=%s Zalo account found, message button clicked by DOM", phone)
                    return {"success": True, "phone": phone, "found": True, "name": name, "status": "FOUND"}

                elapsed += 800
                await page.wait_for_timeout(450)
        except PlaywrightTimeoutError as exc:
            raise TemporaryAutomationError(f"Timed out waiting for Zalo account result {phone}") from exc
        logger.info("PHONE=%s no Zalo search result after pressing search", phone)
        return {"success": True, "phone": phone, "found": False, "name": None, "status": "NOT_FOUND"}

    async def _click_locator_or_clickable_parent(self, locator) -> None:
        try:
            clicked = await locator.evaluate(
                """(el) => {
                    const target = el.closest(".z--btn--v2, button, [role='button'], [tabindex], [data-id]") || el;
                    target.click();
                    return target !== el;
                }"""
            )
            if clicked:
                return
        except Exception:
            logger.debug("Could not click parent of locator, falling back to direct click", exc_info=True)
        await locator.click()

    async def _click_account_profile_message_button_by_dom(self) -> bool:
        page = await self.manager.get_page()
        try:
            return bool(
                await page.evaluate(
                    """() => {
                        const visible = (el) => {
                            if (!el) return false;
                            const rect = el.getBoundingClientRect();
                            const style = window.getComputedStyle(el);
                            return rect.width >= 50 && rect.height >= 24 &&
                                style.visibility !== "hidden" && style.display !== "none" &&
                                style.opacity !== "0";
                        };
                        const disabled = (el) =>
                            el.disabled ||
                            el.getAttribute("aria-disabled") === "true" ||
                            el.className?.toString().toLowerCase().includes("disabled");
                        const clean = (value) => String(value || "").replace(/\\s+/g, " ").trim().toLowerCase();
                        const dialogs = Array.from(document.querySelectorAll("[id^='zl-modal'], [role='dialog'], [class*='modal' i], [class*='dialog' i], [class*='popup' i]"))
                            .filter(visible)
                            .filter((el) => {
                                const text = clean(el.innerText);
                                return text.includes("thông tin tài khoản") || text.includes("account");
                            });
                        for (const dialog of dialogs) {
                            const translatedChatLabels = Array.from(dialog.querySelectorAll(
                                "div.truncate[data-translate-inner='STR_CHAT'], [data-translate-inner='STR_CHAT']"
                            ))
                                .filter((el) => {
                                    const text = clean(el.innerText || el.textContent);
                                    return visible(el) && (text === "nhắn tin" || text === "message");
                                })
                                .map((el) => {
                                    const clickable = el.closest(".z--btn--v2, button, [role='button'], [tabindex], [data-id]") || el.parentElement || el;
                                    const rect = clickable.getBoundingClientRect();
                                    let score = 50;
                                    if (clickable.className?.toString().includes("btn-secondary")) score += 10;
                                    if (clickable.className?.toString().includes("--full-width")) score += 8;
                                    if (rect.width >= 100) score += 5;
                                    return { el: clickable, score };
                                })
                                .filter((item) => visible(item.el) && !disabled(item.el))
                                .sort((a, b) => b.score - a.score);
                            if (translatedChatLabels.length) {
                                translatedChatLabels[0].el.click();
                                return true;
                            }

                            const buttons = Array.from(dialog.querySelectorAll("button, [role='button']"))
                                .filter((el) => {
                                    const tag = el.tagName.toLowerCase();
                                    return tag !== "input" && tag !== "textarea" && visible(el) && !disabled(el);
                                })
                                .map((el) => {
                                    const label = clean([
                                        el.innerText,
                                        el.getAttribute("aria-label"),
                                        el.getAttribute("title"),
                                        el.getAttribute("data-id")
                                    ].join(" "));
                                    const rect = el.getBoundingClientRect();
                                    let score = 0;
                                    if (label === "nhắn tin" || label === "message") score += 40;
                                    else if (label.includes("nhắn tin") || label.includes("message")) score += 24;
                                    if (rect.top < dialog.getBoundingClientRect().top + dialog.getBoundingClientRect().height * 0.55) score += 6;
                                    if (rect.width >= 100) score += 3;
                                    return { el, score };
                                })
                                .filter((item) => item.score >= 35)
                                .sort((a, b) => b.score - a.score);
                            if (buttons.length) {
                                buttons[0].el.click();
                                return true;
                            }
                        }
                        return false;
                    }"""
                )
            )
        except Exception:
            logger.debug("Could not click Zalo account profile message button by DOM", exc_info=True)
            return False

    async def _click_add_friend_message_button_by_dom(self) -> bool:
        page = await self.manager.get_page()
        try:
            return bool(
                await page.evaluate(
                    """() => {
                        const visible = (el) => {
                            if (!el) return false;
                            const rect = el.getBoundingClientRect();
                            const style = window.getComputedStyle(el);
                            return rect.width >= 50 && rect.height >= 24 &&
                                style.visibility !== "hidden" && style.display !== "none" &&
                                style.opacity !== "0";
                        };
                        const disabled = (el) =>
                            el.disabled ||
                            el.getAttribute("aria-disabled") === "true" ||
                            el.className?.toString().toLowerCase().includes("disabled");
                        const clean = (value) => String(value || "").replace(/\\s+/g, " ").trim().toLowerCase();
                        const dialogs = Array.from(document.querySelectorAll("[id^='zl-modal'], [role='dialog'], [class*='modal' i], [class*='dialog' i], [class*='popup' i]"))
                            .filter(visible)
                            .filter((el) => {
                                const text = clean(el.innerText);
                                return text.includes("nhắn tin") || text.includes("thêm bạn") || text.includes("số điện thoại");
                            });
                        for (const dialog of dialogs) {
                            const buttons = Array.from(dialog.querySelectorAll("button, [role='button']"))
                                .filter((el) => {
                                    const tag = el.tagName.toLowerCase();
                                    return tag !== "input" && tag !== "textarea" && visible(el) && !disabled(el);
                                })
                                .map((el) => {
                                    const label = clean([
                                        el.innerText,
                                        el.getAttribute("aria-label"),
                                        el.getAttribute("title"),
                                        el.getAttribute("data-id")
                                    ].join(" "));
                                    let score = 0;
                                    if (label.includes("nhắn tin") || label.includes("message")) score += 20;
                                    if (label.includes("btn_message") || label.includes("chat")) score += 10;
                                    if (clean(el.closest("[id^='zl-modal'], [role='dialog'], [class*='modal' i], [class*='dialog' i], [class*='popup' i]")?.innerText).includes("nhắn tin")) score += 8;
                                    return { el, score };
                                })
                                .filter((item) => item.score >= 20)
                                .sort((a, b) => b.score - a.score);
                            if (buttons.length) {
                                buttons[0].el.click();
                                return true;
                            }
                        }
                        return false;
                    }"""
                )
            )
        except Exception:
            logger.debug("Could not click Zalo message button by DOM", exc_info=True)
            return False

    async def _wait_for_search_outcome(self, phone: str) -> dict:
        page = await self.manager.get_page()
        deadline_ms = settings.element_timeout * 1000
        try:
            elapsed = 0
            while elapsed < deadline_ms:
                if await self._any_visible(selectors.NOT_FOUND_INDICATORS, timeout=350):
                    return {"success": True, "phone": phone, "found": False, "name": None, "status": "NOT_FOUND"}
                item = await self._phone_result_locator(phone, timeout=450)
                if item:
                    await item.click()
                    await page.wait_for_timeout(700)
                    name = await self._read_contact_name()
                    return {"success": True, "phone": phone, "found": True, "name": name, "status": "FOUND"}
                elapsed += 800
        except PlaywrightTimeoutError as exc:
            raise TemporaryAutomationError(f"Timed out searching phone {phone}") from exc
        raise ContactNotFoundError(f"Contact not found for phone {phone}")

    async def _focus_main_search_input(self):
        page = await self.manager.get_page()
        search_input = await self._first_locator(selectors.SEARCH_INPUTS, timeout=1500)
        if not search_input:
            button = await self._first_locator(selectors.SEARCH_BUTTONS, timeout=1200)
            if button:
                await button.click()
                await page.wait_for_timeout(250)
                search_input = await self._first_locator(selectors.SEARCH_INPUTS, timeout=2500)
        if not search_input:
            raise ElementNotFoundError("Không tìm thấy ô tìm kiếm chính của Zalo")
        await search_input.click()
        await page.wait_for_timeout(150)
        return search_input

    async def _replace_text(self, locator, text: str) -> None:
        page = await self.manager.get_page()
        await locator.click()
        try:
            await locator.fill(text)
        except Exception:
            await page.keyboard.press("Control+A")
            await page.keyboard.press("Backspace")
            await page.keyboard.type(text, delay=20)

    async def _phone_result_locator(self, phone: str, timeout: int = 500):
        for template in selectors.CONTACT_RESULT_ROWS:
            locator = await self._visible_locator(template.format(phone=phone), timeout=timeout)
            if locator:
                return locator
        for text in selectors.PHONE_SEARCH_RESULT_TEXT:
            for template in selectors.PHONE_RESULT_ROWS:
                locator = await self._visible_locator(template.format(text=text), timeout=timeout)
                if locator:
                    return locator
        phone_text = await self._visible_locator(f"text={phone}", timeout=timeout)
        if phone_text:
            return phone_text
        return None

    async def _open_message_from_profile_if_needed(self) -> None:
        page = await self.manager.get_page()
        if await self._first_locator(selectors.MESSAGE_INPUTS, timeout=1200):
            return
        button = await self._first_locator(selectors.PROFILE_MESSAGE_BUTTONS, timeout=settings.element_timeout * 1000)
        if not button:
            raise ElementNotFoundError("Không tìm thấy nút Nhắn tin trên hồ sơ Zalo")
        await button.click()
        await page.wait_for_timeout(700)
        if not await self._first_locator(selectors.MESSAGE_INPUTS, timeout=settings.element_timeout * 1000):
            raise ElementNotFoundError("Đã bấm Nhắn tin nhưng chưa thấy khung nhập tin nhắn")

    async def _focus_message_input(self):
        page = await self.manager.get_page()
        message_input = await self._first_locator(selectors.MESSAGE_INPUTS, timeout=settings.element_timeout * 1000)
        if message_input:
            await message_input.click()
            await page.wait_for_timeout(150)
            return message_input

        handle = await self._find_message_input_by_dom()
        if not handle:
            raise ElementNotFoundError("Không tìm thấy ô nhập tin nhắn Zalo")
        locator = handle.as_element()
        if not locator:
            raise ElementNotFoundError("Không thể chọn ô nhập tin nhắn Zalo")
        await locator.click()
        await page.wait_for_timeout(150)
        return locator

    async def _find_message_input_by_dom(self):
        page = await self.manager.get_page()
        try:
            return await page.evaluate_handle(
                """() => {
                    const visible = (el) => {
                        if (!el) return false;
                        const rect = el.getBoundingClientRect();
                        const style = window.getComputedStyle(el);
                        return rect.width >= 160 && rect.height >= 20 &&
                            style.visibility !== "hidden" && style.display !== "none" &&
                            style.opacity !== "0";
                    };
                    const clean = (value) => String(value || "").replace(/\\s+/g, " ").trim().toLowerCase();
                    const inputs = Array.from(document.querySelectorAll("[contenteditable='true'], textarea, input"))
                        .filter(visible)
                        .map((el) => {
                            const rect = el.getBoundingClientRect();
                            const label = clean([
                                el.getAttribute("placeholder"),
                                el.getAttribute("aria-placeholder"),
                                el.getAttribute("aria-label"),
                                el.getAttribute("title"),
                                el.getAttribute("data-id"),
                                el.id,
                                el.className
                            ].join(" "));
                            let score = 0;
                            if (label.includes("nhập @")) score += 22;
                            if (label.includes("tin nhắn")) score += 18;
                            if (label.includes("message")) score += 12;
                            if (label.includes("richinput") || label.includes("input_line")) score += 10;
                            if (el.getAttribute("contenteditable") === "true") score += 5;
                            if (rect.top > window.innerHeight * 0.55) score += 8;
                            if (rect.width > 300) score += 4;
                            if (clean(el.closest("[role='dialog'], [class*='modal' i], [class*='popup' i]")?.innerText).includes("thêm bạn")) score -= 30;
                            if (label.includes("tìm kiếm") || label.includes("search") || label.includes("số điện thoại")) score -= 20;
                            return { el, score };
                        })
                        .filter((item) => item.score >= 12)
                        .sort((a, b) => b.score - a.score);
                    return inputs.length ? inputs[0].el : null;
                }"""
            )
        except Exception:
            logger.debug("Could not find Zalo message input by DOM", exc_info=True)
            return None

    async def _read_contact_name(self) -> str | None:
        for selector in selectors.CONTACT_NAME_CANDIDATES:
            try:
                locator = self.manager._page.locator(selector).first
                if await locator.is_visible(timeout=800):
                    text = (await locator.inner_text()).strip()
                    if text:
                        return text
            except Exception:
                continue
        return None

    async def _looks_logged_in(self) -> bool:
        page = await self.manager.get_page()
        try:
            return bool(
                await page.evaluate(
                    """() => {
                        const visible = (el) => {
                            if (!el) return false;
                            const rect = el.getBoundingClientRect();
                            const style = window.getComputedStyle(el);
                            return rect.width > 0 && rect.height > 0 &&
                                style.visibility !== "hidden" && style.display !== "none" &&
                                style.opacity !== "0";
                        };
                        const text = (document.body?.innerText || "").replace(/\\s+/g, " ").toLowerCase();
                        const title = (document.title || "").toLowerCase();
                        const host = location.hostname.toLowerCase();
                        const isChatZalo = host === "chat.zalo.me";
                        const hasQrText = [
                            "quét mã qr",
                            "scan qr"
                        ].some((item) => text.includes(item));
                        const loginText = [
                            "đăng nhập",
                            "login"
                        ].some((item) => text.includes(item));
                        const titleLooksLoggedIn = /^zalo\\s+-\\s+.+/.test(title) && !title.includes("đăng nhập");
                        const hasMessageInput = Array.from(document.querySelectorAll(
                            "#input_line_0, [id^='input_line_'], [contenteditable='true'][role='textbox'], [contenteditable='true'][aria-label*='tin nhắn' i]"
                        )).some(visible);
                        const hasSearch = Array.from(document.querySelectorAll(
                            "input[placeholder*='Tìm' i], input[placeholder*='Search' i], [role='searchbox']"
                        )).some(visible);
                        const hasAppData = Array.from(document.querySelectorAll("[data-id], [id], [class]")).some((el) => {
                            if (!visible(el)) return false;
                            const value = `${el.getAttribute("data-id") || ""} ${el.id || ""} ${el.className || ""}`.toLowerCase();
                            return /tab|chat|conversation|contact|message|sidebar|leftbar|friend/.test(value);
                        });
                        const navHits = [
                            "tin nhắn",
                            "danh bạ",
                            "cloud của tôi",
                            "truyền file",
                            "tạo nhóm"
                        ].filter((item) => text.includes(item)).length;
                        if (isChatZalo && titleLooksLoggedIn && !hasQrText) return true;
                        return !hasQrText && (!loginText || hasMessageInput || hasSearch || hasAppData) &&
                            (hasMessageInput || hasSearch || hasAppData || navHits >= 2);
                    }"""
                )
            )
        except Exception:
            logger.debug("Could not inspect Zalo login state", exc_info=True)
            return False

    async def _read_profile(self) -> dict | None:
        profile = await self._read_own_profile()
        title_profile = await self._read_profile_from_title()
        if profile:
            if not profile.get("name") and title_profile:
                profile["name"] = title_profile.get("name")
            return profile
        return title_profile

    async def _read_profile_from_title(self) -> dict | None:
        page = await self.manager.get_page()
        title = (await page.title()).strip()
        prefix = "Zalo - "
        if not title.startswith(prefix):
            return None
        name = title[len(prefix) :].strip()
        if not name:
            return None
        return {"name": name, "avatar_url": None}

    async def _read_own_profile(self) -> dict | None:
        page = await self.manager.get_page()
        try:
            profile = await page.evaluate(
                """async () => {
                    const visible = (el) => {
                        const rect = el.getBoundingClientRect();
                        const style = window.getComputedStyle(el);
                        return rect.width >= 24 && rect.height >= 24 &&
                            style.visibility !== "hidden" && style.display !== "none" &&
                            style.opacity !== "0";
                    };
                    const clean = (value) => (value || "").replace(/\\s+/g, " ").trim();
                    const urlFromBackground = (value) => {
                        const match = String(value || "").match(/url\\([\"']?([^\"')]+)[\"']?\\)/);
                        return match ? match[1] : null;
                    };
                    const normalizeUrl = async (value) => {
                        if (!value || value.startsWith("blob:")) return null;
                        try { return new URL(value, window.location.href).href; } catch { return null; }
                    };
                    const blobToDataUrl = async (value) => {
                        if (!value || !value.startsWith("blob:")) return null;
                        try {
                            const response = await fetch(value);
                            const blob = await response.blob();
                            return await new Promise((resolve) => {
                                const reader = new FileReader();
                                reader.onloadend = () => resolve(reader.result);
                                reader.onerror = () => resolve(null);
                                reader.readAsDataURL(blob);
                            });
                        } catch {
                            return null;
                        }
                    };
                    const candidates = Array.from(document.querySelectorAll(
                        "img, [class*='avatar' i], [class*='profile' i], [aria-label*='avatar' i], [aria-label*='đại diện' i], [style*='background-image']"
                    ))
                        .filter(visible)
                        .map((el) => {
                            const rect = el.getBoundingClientRect();
                            const holder = el.closest("[role='button'], button, [class*='avatar' i], [class*='profile' i]") || el.parentElement;
                            const text = clean(
                                el.getAttribute("alt") ||
                                el.getAttribute("title") ||
                                el.getAttribute("aria-label") ||
                                holder?.getAttribute("aria-label") ||
                                holder?.getAttribute("title") ||
                                holder?.innerText
                            );
                            const classText = `${el.className || ""} ${holder?.className || ""}`.toLowerCase();
                            const style = window.getComputedStyle(el);
                            const rawSrc = el.currentSrc || el.src || el.getAttribute("src") || urlFromBackground(style.backgroundImage);
                            let score = 0;
                            if (classText.includes("avatar")) score += 8;
                            if (classText.includes("profile")) score += 5;
                            if (String(rawSrc || "").toLowerCase().includes("avatar")) score += 8;
                            if (rect.top < 220) score += 5;
                            if (rect.left < 260) score += 4;
                            if (rect.width >= 32 && rect.width <= 120 && rect.height >= 32 && rect.height <= 120) score += 5;
                            if (holder?.getAttribute("role") === "button" || holder?.tagName === "BUTTON") score += 2;
                            if (text && !/zalo|facebook|tiktok|shopee|video ai/i.test(text)) score += 2;
                            return { rawSrc, name: text || null, score };
                        })
                        .filter((item) => item.rawSrc)
                        .sort((a, b) => b.score - a.score);
                    if (!candidates.length) return null;
                    const best = candidates[0];
                    const src = await blobToDataUrl(best.rawSrc) || await normalizeUrl(best.rawSrc);
                    if (!src) return null;
                    return { name: best.name, avatar_url: src };
                }"""
            )
            if not profile:
                return None
            return {"name": profile.get("name"), "avatar_url": profile.get("avatar_url")}
        except Exception:
            logger.debug("Could not read Zalo profile", exc_info=True)
            return None

    async def _any_visible(self, selector_list: list[str], timeout: int = 1000) -> bool:
        page = await self.manager.get_page()
        for selector in selector_list:
            try:
                if await page.locator(selector).first.is_visible(timeout=timeout):
                    return True
            except Exception:
                continue
        return False

    async def _first_locator(self, selector_list: list[str], timeout: int | None = None):
        page = await self.manager.get_page()
        timeout = timeout if timeout is not None else settings.element_timeout * 1000
        for selector in selector_list:
            locator = await self._visible_locator(selector, timeout=timeout)
            if locator:
                return locator
        return None

    async def _first_enabled_locator(self, selector_list: list[str], timeout: int | None = None):
        page = await self.manager.get_page()
        timeout = timeout if timeout is not None else settings.element_timeout * 1000
        for selector in selector_list:
            locator = await self._visible_locator(selector, timeout=timeout)
            if not locator:
                continue
            try:
                if await locator.is_enabled(timeout=300):
                    return locator
            except Exception:
                continue
        return None

    async def _visible_locator(self, selector: str, timeout: int = 1000):
        page = await self.manager.get_page()
        try:
            locator = page.locator(selector).first
            if await locator.is_visible(timeout=timeout):
                return locator
        except Exception:
            return None
        return None


def automation_status_from_error(exc: Exception) -> str:
    return getattr(exc, "status", "ERROR") if isinstance(exc, ZaloAutomationError) else "ERROR"
