"""Configuration settings loaded from environment and .env."""
import os
from pathlib import Path
from dotenv import load_dotenv

# Resolve backend directory and .env file
BACKEND_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BACKEND_DIR / ".env"

# Load .env if present
if ENV_FILE.exists():
    load_dotenv(dotenv_path=ENV_FILE)
else:
    load_dotenv()


def get_finmind_token() -> str:
    """Return FINMIND_TOKEN from environment."""
    return os.getenv("FINMIND_TOKEN", "")


def is_empty_token_allowed() -> bool:
    """Return whether empty FinMind token is allowed (uses public quota)."""
    return os.getenv("FINMIND_ALLOW_NO_TOKEN", "false").lower() in ("true", "1", "yes")


def get_gemini_api_key() -> str:
    """Return GEMINI_API_KEY from environment."""
    return os.getenv("GEMINI_API_KEY", "").strip()


def has_gemini_api_key() -> bool:
    """Return whether GEMINI_API_KEY is configured and non-empty."""
    return bool(get_gemini_api_key())


