class ZaloAutomationError(Exception):
    status = "ERROR"


class LoginRequiredError(ZaloAutomationError):
    status = "LOGIN_REQUIRED"


class ContactNotFoundError(ZaloAutomationError):
    status = "NOT_FOUND"


class BrowserDisconnectedError(ZaloAutomationError):
    status = "BROWSER_DISCONNECTED"


class ElementNotFoundError(ZaloAutomationError):
    status = "ELEMENT_NOT_FOUND"


class UserActionRequiredError(ZaloAutomationError):
    status = "USER_ACTION_REQUIRED"


class TemporaryAutomationError(ZaloAutomationError):
    status = "TIMEOUT"
