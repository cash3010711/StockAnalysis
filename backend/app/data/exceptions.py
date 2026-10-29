"""Custom exceptions for FinMind and data layer."""


class FinMindError(Exception):
    """Base exception for FinMind operations."""
    code: str = "FINMIND_ERROR"
    status_code: int = 400

    def __init__(self, message: str, hint: str = ""):
        super().__init__(message)
        self.message = message
        self.hint = hint


class FinMindTokenMissingError(FinMindError):
    """Raised when FINMIND_TOKEN is not configured."""
    code: str = "TOKEN_MISSING"
    status_code: int = 400

    def __init__(
        self,
        message: str = "尚未設定 FinMind token",
        hint: str = "請至 https://finmindtrade.com/ 註冊並在 backend/.env 中設定 FINMIND_TOKEN=<your_token>",
    ):
        super().__init__(message, hint)
        self.status_code = 400


class FinMindQuotaExceededError(FinMindError):
    """Raised when FinMind API quota / rate limit is exceeded."""
    code: str = "QUOTA_EXCEEDED"
    status_code: int = 400

    def __init__(
        self,
        message: str = "API 額度已用盡，請稍後再試",
        hint: str = "FinMind 免費方案每小時請求次數已達上限，且本機無快取資料，請稍後再試",
    ):
        super().__init__(message, hint)
        self.status_code = 400


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
    status_code: int = 400

    def __init__(
        self,
        message: str = "歷史資料不足，無法進行分析",
        hint: str = "歷史交易日過少（需至少 35 個交易日），尚無法計算技術指標",
    ):
        super().__init__(message, hint)
        self.status_code = 400


class GeminiApiKeyMissingError(FinMindError):
    """Raised when GEMINI_API_KEY is not configured."""
    code: str = "GEMINI_API_KEY_MISSING"
    status_code: int = 400

    def __init__(
        self,
        message: str = "尚未設定 Gemini API 金鑰",
        hint: str = "請至 https://aistudio.google.com/ 申請金鑰並在 backend/.env 中設定 GEMINI_API_KEY=<your_api_key>",
    ):
        super().__init__(message, hint)
        self.status_code = 400


class AiAdvisorError(FinMindError):
    """Raised when AI advice generation fails."""
    code: str = "AI_ADVISOR_ERROR"
    status_code: int = 500

    def __init__(
        self,
        message: str = "AI 戰略分析生成失敗",
        hint: str = "請稍後重試或確認網路與 API 配額狀態",
    ):
        super().__init__(message, hint)
        self.status_code = 500

