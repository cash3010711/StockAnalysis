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
