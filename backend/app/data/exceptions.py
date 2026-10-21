"""Custom exceptions for FinMind and data layer."""


class FinMindError(Exception):
    """Base exception for FinMind operations."""
    code: str = "FINMIND_ERROR"

    def __init__(self, message: str, hint: str = ""):
        super().__init__(message)
        self.message = message
        self.hint = hint


class FinMindTokenMissingError(FinMindError):
    """Raised when FINMIND_TOKEN is not configured."""
    code: str = "TOKEN_MISSING"

    def __init__(
        self,
        message: str = "尚未設定 FinMind token",
        hint: str = "請至 https://finmindtrade.com/ 註冊並在 backend/.env 中設定 FINMIND_TOKEN=<your_token>",
    ):
        super().__init__(message, hint)


class FinMindQuotaExceededError(FinMindError):
    """Raised when FinMind API quota / rate limit is exceeded."""
    code: str = "QUOTA_EXCEEDED"

    def __init__(
        self,
        message: str = "API 額度已用盡，請稍後再試",
        hint: str = "FinMind 免費方案每小時請求次數已達上限，請等待額度重置或升級贊助方案",
    ):
        super().__init__(message, hint)


class FinMindApiError(FinMindError):
    """Raised when FinMind API returns an error status or HTTP failure."""
    code: str = "API_ERROR"

    def __init__(self, message: str, status_code: int = 500, hint: str = ""):
        super().__init__(message, hint)
        self.status_code = status_code


class StockNotSupportedError(FinMindError):
    """Raised when querying or analyzing unsupported securities (ETF, warrant, emerging, preferred)."""
    code: str = "STOCK_NOT_SUPPORTED"
    status_code: int = 400

    def __init__(
        self,
        message: str = "目前只支援上市、上櫃普通股",
        hint: str = "目前只支援上市、上櫃普通股",
    ):
        super().__init__(message, hint)
        self.status_code = 400


class InsufficientDataError(FinMindError):
    """Raised when data history is insufficient."""
    code: str = "INSUFFICIENT_HISTORY"

    def __init__(self, message: str = "歷史資料不足", hint: str = ""):
        super().__init__(message, hint)
